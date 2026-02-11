"""
X11 global key grab and XTEST key simulation.

Uses a background thread with blocking next_event() to receive X events,
then dispatches to the Qt main thread via signals.
"""

import logging
import threading

from PyQt5.QtCore import QObject, pyqtSignal
from Xlib import X, XK, display, error
from Xlib.ext import xtest

log = logging.getLogger(__name__)

# Lock masks to iterate for NumLock/CapsLock-insensitive grabs
_LOCK_MASK = X.LockMask      # CapsLock
_NUM_LOCK_MASK = X.Mod2Mask   # NumLock (typical)
_IGNORE_MASKS = [
    0,
    _LOCK_MASK,
    _NUM_LOCK_MASK,
    _LOCK_MASK | _NUM_LOCK_MASK,
]


class X11KeyHook(QObject):
    """Grabs keys globally via X11 and simulates replacements with XTEST."""

    key_intercepted = pyqtSignal(int, int)  # keysym, modifiers
    hook_error = pyqtSignal(str)
    # Internal signal: event thread → main thread
    _key_event = pyqtSignal(int, int)  # keycode, clean_mods

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display = None       # main thread: grabs + simulate
        self._evt_display = None   # event thread: blocking next_event()
        self._root = None
        self._grabbed = {}  # (keycode, clean_mods) → callback(keysym, mods)
        self._running = False
        self._thread = None
        self._key_event.connect(self._on_key_event)

    def start(self):
        """Open X display and start listening for grabbed key events."""
        if self._running:
            return
        try:
            self._display = display.Display()
            self._root = self._display.screen().root
            if not self._display.has_extension("XTEST"):
                self.hook_error.emit("XTEST extension not available")
                return
            # Second connection for blocking event reads
            self._evt_display = display.Display()
            self._evt_root = self._evt_display.screen().root
            self._evt_root.change_attributes(event_mask=X.KeyPressMask)
        except Exception as e:
            self.hook_error.emit(f"Cannot open X display: {e}")
            return

        self._running = True
        self._thread = threading.Thread(target=self._event_loop, daemon=True)
        self._thread.start()
        log.info("X11KeyHook started on display %s", self._display.get_display_name())

    def stop(self):
        """Stop listening and ungrab all keys."""
        if not self._running:
            return
        self._running = False
        # Ungrab everything (on main display)
        for keycode, clean_mods in list(self._grabbed.keys()):
            self._ungrab_raw(keycode, clean_mods)
        self._grabbed.clear()
        if self._display:
            self._display.close()
            self._display = None
        if self._evt_display:
            self._evt_display.close()
            self._evt_display = None
        self._thread = None
        log.info("X11KeyHook stopped")

    def cleanup(self):
        """Alias for stop(), suitable for app.aboutToQuit."""
        self.stop()

    def grab_key(self, keysym, modifiers, callback):
        """
        Grab a key globally. Returns True on success, False on conflict.

        callback: callable(keysym, modifiers) invoked when the key is pressed.
        """
        if not self._display:
            self.hook_error.emit("Hook not started")
            return False

        keycode = self._display.keysym_to_keycode(keysym)
        if keycode == 0:
            self.hook_error.emit(f"No keycode for keysym 0x{keysym:04x}")
            return False

        clean_mods = modifiers & ~(_LOCK_MASK | _NUM_LOCK_MASK)
        key = (keycode, clean_mods)
        if key in self._grabbed:
            return False

        old_handler = error.CatchError(error.BadAccess)

        # Grab only on the event display (the one that reads events)
        for extra in _IGNORE_MASKS:
            self._evt_root.grab_key(
                keycode,
                clean_mods | extra,
                False,  # owner_events=False: all events to grab window
                X.GrabModeAsync,
                X.GrabModeAsync,
                onerror=old_handler,
            )
        self._evt_display.sync()

        if old_handler.get_error():
            for extra in _IGNORE_MASKS:
                self._evt_root.ungrab_key(keycode, clean_mods | extra)
            self._evt_display.sync()
            self.hook_error.emit(
                "Key already grabbed by another application"
            )
            return False

        self._grabbed[key] = callback
        log.info("Grabbed keycode=%d mods=0x%x", keycode, clean_mods)
        return True

    def ungrab_key(self, keysym, modifiers):
        """Ungrab a previously grabbed key."""
        if not self._display:
            return

        keycode = self._display.keysym_to_keycode(keysym)
        clean_mods = modifiers & ~(_LOCK_MASK | _NUM_LOCK_MASK)
        key = (keycode, clean_mods)

        if key not in self._grabbed:
            return

        self._ungrab_raw(keycode, clean_mods)
        del self._grabbed[key]
        log.info("Ungrabbed keycode=%d mods=0x%x", keycode, clean_mods)

    def _ungrab_raw(self, keycode, clean_mods):
        """Send ungrab requests for all lock-mask variants."""
        if self._evt_display is None:
            return
        for extra in _IGNORE_MASKS:
            self._evt_root.ungrab_key(keycode, clean_mods | extra)
        self._evt_display.sync()

    def simulate_key(self, keysym, modifiers):
        """Simulate a key press+release using XTEST, including modifier keys.

        Scans the keyboard mapping to find which keycode + shift state
        produces the requested keysym, so characters like '@' (Shift+2)
        are handled automatically.
        """
        if not self._display:
            return

        keycode, extra_mods = self._resolve_keysym(keysym)
        log.debug("simulate_key: keysym=0x%x -> keycode=%s extra_mods=0x%x",
                  keysym, keycode, extra_mods)
        if keycode is None or keycode == 0:
            return

        combined_mods = modifiers | extra_mods
        mod_keycodes = self._modifier_keycodes(combined_mods)

        # Press modifiers
        for mc in mod_keycodes:
            xtest.fake_input(self._display, X.KeyPress, mc)

        # Press and release the main key
        xtest.fake_input(self._display, X.KeyPress, keycode)
        xtest.fake_input(self._display, X.KeyRelease, keycode)

        # Release modifiers (reverse order)
        for mc in reversed(mod_keycodes):
            xtest.fake_input(self._display, X.KeyRelease, mc)

        self._display.sync()

    def _resolve_keysym(self, keysym):
        """Find the keycode and modifier mask needed to produce a keysym.

        Scans the keyboard mapping table. Index 0 = no modifier,
        index 1 = Shift. Returns (keycode, modifier_mask) or (None, 0).
        """
        min_kc = self._display.display.info.min_keycode
        max_kc = self._display.display.info.max_keycode
        count = max_kc - min_kc + 1

        mapping = self._display.get_keyboard_mapping(min_kc, count)

        for i, keysyms in enumerate(mapping):
            for index, ks in enumerate(keysyms):
                if ks == keysym:
                    mods = 0
                    if index == 1:
                        mods = X.ShiftMask
                    if index <= 1:
                        return min_kc + i, mods

        # Fallback
        kc = self._display.keysym_to_keycode(keysym)
        if kc != 0:
            return kc, 0
        return None, 0

    def _modifier_keycodes(self, modifiers):
        """Return list of keycodes for modifier bits that need press/release."""
        keycodes = []
        mod_keysyms = []
        if modifiers & (1 << 0):  # ShiftMask
            mod_keysyms.append(XK.XK_Shift_L)
        if modifiers & (1 << 2):  # ControlMask
            mod_keysyms.append(XK.XK_Control_L)
        if modifiers & (1 << 3):  # Mod1Mask (Alt)
            mod_keysyms.append(XK.XK_Alt_L)
        if modifiers & (1 << 6):  # Mod4Mask (Super)
            mod_keysyms.append(XK.XK_Super_L)
        for ks in mod_keysyms:
            kc = self._display.keysym_to_keycode(ks)
            if kc:
                keycodes.append(kc)
        return keycodes

    def _event_loop(self):
        """Background thread: blocking read of X events, dispatch via signal."""
        log.debug("Event thread started")
        while self._running:
            try:
                evt = self._evt_display.next_event()
            except Exception:
                if self._running:
                    log.exception("Error reading X event")
                break
            if evt.type == X.KeyPress:
                keycode = evt.detail
                clean_mods = evt.state & ~(_LOCK_MASK | _NUM_LOCK_MASK)
                # Emit signal to main thread
                self._key_event.emit(keycode, clean_mods)
        log.debug("Event thread exited")

    def _on_key_event(self, keycode, clean_mods):
        """Main thread handler: look up callback and invoke it."""
        key = (keycode, clean_mods)
        callback = self._grabbed.get(key)
        if callback:
            keysym = self._display.keycode_to_keysym(keycode, 0)
            log.debug("Invoking callback for keycode=%d keysym=0x%x", keycode, keysym)
            try:
                callback(keysym, clean_mods)
            except Exception:
                log.exception("Error in key callback")

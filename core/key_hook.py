"""
Key interception via evdev + key simulation via XTEST.

Architecture:
- A background thread reads raw key events from /dev/input/event* via evdev.
- Grabbed (mapped) keys are suppressed at the evdev level — they never reach
  the X server or compositor.
- Non-grabbed keys are forwarded transparently via a uinput virtual keyboard.
- Replacement keys are simulated via XTEST on an X11 Display connection
  (owned exclusively by the event thread).
- Event thread → Qt main thread communication via pyqtSignal.
- Main thread → event thread communication via queue.Queue.

This approach works on all Linux desktops (X11, Xwayland compositors like
Mutter/Muffin/KWin) because evdev operates below the compositor layer.
"""

import logging
import queue
import threading

import evdev
from evdev import InputDevice, UInput, categorize, ecodes

from PyQt5.QtCore import QObject, pyqtSignal
from Xlib import X, XK, display
from Xlib.ext import xtest

log = logging.getLogger(__name__)


def _find_keyboards():
    """Return list of evdev paths for real keyboard devices."""
    keyboards = []
    for path in evdev.list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities().get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in caps:
                keyboards.append(path)
        except (OSError, PermissionError):
            pass
    return keyboards


# Mapping from evdev key codes to X11 keysyms for common keys.
# Evdev KEY_* → X11 keysym.  We build this from Xlib at runtime
# using the X display's keyboard mapping, but we need a static
# table for keys that don't have a 1:1 keycode correspondence.
_EVDEV_TO_KEYSYM = {}

def _build_evdev_keysym_table(dpy):
    """Build evdev-keycode → X11-keysym mapping using the X display."""
    # X11 keycodes = evdev keycodes + 8
    min_kc = dpy.display.info.min_keycode
    max_kc = dpy.display.info.max_keycode
    mapping = dpy.get_keyboard_mapping(min_kc, max_kc - min_kc + 1)
    table = {}
    for i, keysyms in enumerate(mapping):
        x_keycode = min_kc + i
        evdev_keycode = x_keycode - 8
        if keysyms and keysyms[0] != 0:
            table[evdev_keycode] = keysyms[0]  # unshifted keysym
    return table


class X11KeyHook(QObject):
    """Intercepts keys via evdev, simulates replacements via XTEST."""

    key_intercepted = pyqtSignal(int, int)
    hook_error = pyqtSignal(str)
    _key_event = pyqtSignal(int, int)  # evdev_keycode, 0 (mods not used yet)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grabbed = {}        # evdev_keycode → callback
        self._grabbed_with_mods = {}  # (evdev_keycode, x11_mods) → callback
        self._keysym_to_evdev = {}  # x11_keysym → evdev_keycode
        self._evdev_to_keysym = {}
        self._running = False
        self._thread = None
        self._cmd_q = queue.Queue()
        self._result_q = queue.Queue()
        self._key_event.connect(self._on_key_event)

    def start(self):
        if self._running:
            return

        keyboards = _find_keyboards()
        if not keyboards:
            self.hook_error.emit("No keyboard devices found in /dev/input/")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._event_loop, args=(keyboards,), daemon=True
        )
        self._thread.start()

        # Wait for init
        try:
            ok = self._result_q.get(timeout=5)
        except queue.Empty:
            ok = False
        if not ok:
            self._running = False
            self.hook_error.emit("Event thread failed to start")

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._grabbed.clear()
        self._grabbed_with_mods.clear()
        log.info("X11KeyHook stopped")

    def cleanup(self):
        self.stop()

    def grab_key(self, keysym, modifiers, callback):
        """Grab a key. Returns True on success."""
        if not self._running:
            self.hook_error.emit("Hook not started")
            return False

        ev_kc = self._keysym_to_evdev.get(keysym)
        if ev_kc is None:
            self.hook_error.emit(f"No evdev keycode for keysym 0x{keysym:04x}")
            return False

        if ev_kc in self._grabbed:
            return False

        self._grabbed[ev_kc] = callback
        log.info("Grabbed evdev keycode=%d (keysym=0x%x)", ev_kc, keysym)
        return True

    def ungrab_key(self, keysym, modifiers):
        """Ungrab a previously grabbed key."""
        ev_kc = self._keysym_to_evdev.get(keysym)
        if ev_kc is None:
            return
        self._grabbed.pop(ev_kc, None)
        log.info("Ungrabbed evdev keycode=%d", ev_kc)

    def simulate_key(self, keysym, modifiers):
        """Queue a key simulation (fire-and-forget)."""
        if not self._running:
            return
        self._cmd_q.put(('simulate', keysym, modifiers))

    # ── event thread ─────────────────────────────────────────────

    def _event_loop(self, keyboard_paths):
        """Runs in dedicated thread. Owns evdev devices + X display."""
        # Open X display for XTEST simulation
        try:
            dpy = display.Display()
            if not dpy.has_extension("XTEST"):
                self._result_q.put(False)
                return
        except Exception:
            log.exception("Cannot open X display")
            self._result_q.put(False)
            return

        # Build keysym ↔ evdev keycode tables
        self._evdev_to_keysym = _build_evdev_keysym_table(dpy)
        self._keysym_to_evdev = {v: k for k, v in self._evdev_to_keysym.items()}

        # Open keyboard devices and grab them
        devices = []
        for path in keyboard_paths:
            try:
                dev = InputDevice(path)
                dev.grab()  # exclusive access
                devices.append(dev)
                log.info("Grabbed device: %s (%s)", dev.name, path)
            except (OSError, PermissionError) as e:
                log.warning("Cannot grab %s: %s", path, e)

        if not devices:
            self._result_q.put(False)
            dpy.close()
            return

        # Create virtual keyboard for forwarding non-mapped keys
        try:
            # Copy capabilities from first real keyboard
            caps = devices[0].capabilities(absinfo=False)
            # Remove EV_SYN (0) — UInput adds it automatically
            caps.pop(ecodes.EV_SYN, None)
            uinput = UInput(caps, name="ReKey Virtual Keyboard")
        except Exception:
            log.exception("Cannot create UInput device")
            for dev in devices:
                try:
                    dev.ungrab()
                except Exception:
                    pass
            self._result_q.put(False)
            dpy.close()
            return

        log.info("X11KeyHook started (evdev + XTEST)")
        self._result_q.put(True)

        # Event loop
        selector_map = {dev.fd: dev for dev in devices}
        import select

        while self._running:
            # Process simulation commands
            self._drain_commands(dpy)

            # Wait for events with a short timeout
            try:
                readable, _, _ = select.select(
                    list(selector_map.keys()), [], [], 0.02
                )
            except (ValueError, OSError):
                break

            for fd in readable:
                dev = selector_map.get(fd)
                if dev is None:
                    continue
                try:
                    for event in dev.read():
                        self._handle_evdev_event(event, uinput, dpy)
                except (OSError, IOError):
                    log.warning("Lost device: %s", dev.name)
                    selector_map.pop(fd, None)

        # Cleanup
        try:
            uinput.close()
        except Exception:
            pass
        for dev in devices:
            try:
                dev.ungrab()
                dev.close()
            except Exception:
                pass
        try:
            dpy.close()
        except Exception:
            pass
        log.debug("Event thread exited")

    def _handle_evdev_event(self, event, uinput, dpy):
        """Process a single evdev event."""
        if event.type != ecodes.EV_KEY:
            # Forward non-key events (SYN, etc.) transparently
            uinput.write_event(event)
            uinput.syn()
            return

        key_event = categorize(event)
        ev_keycode = event.code

        # Is this key grabbed?
        if ev_keycode in self._grabbed:
            # Only fire on key-down (not repeat or release)
            if key_event.keystate == key_event.key_down:
                self._key_event.emit(ev_keycode, 0)
            # Suppress: don't forward to uinput
            return

        # Not grabbed — forward transparently
        uinput.write_event(event)
        uinput.syn()

    def _drain_commands(self, dpy):
        """Process pending simulation commands."""
        while not self._cmd_q.empty():
            try:
                cmd = self._cmd_q.get_nowait()
            except queue.Empty:
                break
            if cmd[0] == 'simulate':
                self._do_simulate(dpy, cmd[1], cmd[2])

    def _do_simulate(self, dpy, keysym, modifiers):
        """Simulate a key press+release via XTEST."""
        keycode, extra_mods = self._resolve_keysym(dpy, keysym)
        if keycode is None or keycode == 0:
            return

        combined = modifiers | extra_mods
        mod_kcs = self._modifier_keycodes(dpy, combined)

        for mc in mod_kcs:
            xtest.fake_input(dpy, X.KeyPress, mc)
        xtest.fake_input(dpy, X.KeyPress, keycode)
        xtest.fake_input(dpy, X.KeyRelease, keycode)
        for mc in reversed(mod_kcs):
            xtest.fake_input(dpy, X.KeyRelease, mc)
        dpy.sync()

    @staticmethod
    def _resolve_keysym(dpy, keysym):
        """Find X11 keycode + modifier for a keysym."""
        min_kc = dpy.display.info.min_keycode
        max_kc = dpy.display.info.max_keycode
        mapping = dpy.get_keyboard_mapping(min_kc, max_kc - min_kc + 1)
        for i, keysyms in enumerate(mapping):
            for idx, ks in enumerate(keysyms):
                if ks == keysym and idx <= 1:
                    return min_kc + i, X.ShiftMask if idx == 1 else 0
        kc = dpy.keysym_to_keycode(keysym)
        return (kc, 0) if kc != 0 else (None, 0)

    @staticmethod
    def _modifier_keycodes(dpy, modifiers):
        kcs = []
        for bit, ksym in [(0, XK.XK_Shift_L), (2, XK.XK_Control_L),
                           (3, XK.XK_Alt_L), (6, XK.XK_Super_L)]:
            if modifiers & (1 << bit):
                kc = dpy.keysym_to_keycode(ksym)
                if kc:
                    kcs.append(kc)
        return kcs

    # ── main-thread signal handler ───────────────────────────────

    def _on_key_event(self, ev_keycode, mods):
        """Main thread: look up callback and invoke it."""
        callback = self._grabbed.get(ev_keycode)
        if callback:
            keysym = self._evdev_to_keysym.get(ev_keycode, 0)
            log.debug("Key callback: evdev=%d keysym=0x%x", ev_keycode, keysym)
            try:
                callback(ev_keycode, mods)
            except Exception:
                log.exception("Error in key callback")

"""
Bidirectional mapping between Qt key codes, X11 keysyms, and human-readable names.
"""

from PyQt5.QtCore import Qt
from Xlib import XK


# Mapping: (Qt key code, X11 keysym, display name)
_SPECIAL_KEYS = [
    # Function keys
    (Qt.Key_F1, XK.XK_F1, "F1"),
    (Qt.Key_F2, XK.XK_F2, "F2"),
    (Qt.Key_F3, XK.XK_F3, "F3"),
    (Qt.Key_F4, XK.XK_F4, "F4"),
    (Qt.Key_F5, XK.XK_F5, "F5"),
    (Qt.Key_F6, XK.XK_F6, "F6"),
    (Qt.Key_F7, XK.XK_F7, "F7"),
    (Qt.Key_F8, XK.XK_F8, "F8"),
    (Qt.Key_F9, XK.XK_F9, "F9"),
    (Qt.Key_F10, XK.XK_F10, "F10"),
    (Qt.Key_F11, XK.XK_F11, "F11"),
    (Qt.Key_F12, XK.XK_F12, "F12"),
    (Qt.Key_F13, XK.XK_F13, "F13"),
    (Qt.Key_F14, XK.XK_F14, "F14"),
    (Qt.Key_F15, XK.XK_F15, "F15"),
    (Qt.Key_F16, XK.XK_F16, "F16"),
    (Qt.Key_F17, XK.XK_F17, "F17"),
    (Qt.Key_F18, XK.XK_F18, "F18"),
    (Qt.Key_F19, XK.XK_F19, "F19"),
    (Qt.Key_F20, XK.XK_F20, "F20"),
    (Qt.Key_F21, XK.XK_F21, "F21"),
    (Qt.Key_F22, XK.XK_F22, "F22"),
    (Qt.Key_F23, XK.XK_F23, "F23"),
    (Qt.Key_F24, XK.XK_F24, "F24"),

    # Modifiers
    (Qt.Key_Shift, XK.XK_Shift_L, "Shift"),
    (Qt.Key_Control, XK.XK_Control_L, "Ctrl"),
    (Qt.Key_Alt, XK.XK_Alt_L, "Alt"),
    (Qt.Key_Meta, XK.XK_Super_L, "Super"),
    (Qt.Key_CapsLock, XK.XK_Caps_Lock, "CapsLock"),
    (Qt.Key_NumLock, XK.XK_Num_Lock, "NumLock"),
    (Qt.Key_ScrollLock, XK.XK_Scroll_Lock, "ScrollLock"),

    # Navigation
    (Qt.Key_Escape, XK.XK_Escape, "Escape"),
    (Qt.Key_Tab, XK.XK_Tab, "Tab"),
    (Qt.Key_Backtab, 0xFE20, "Backtab"),  # XK_ISO_Left_Tab
    (Qt.Key_Backspace, XK.XK_BackSpace, "Backspace"),
    (Qt.Key_Return, XK.XK_Return, "Return"),
    (Qt.Key_Enter, XK.XK_KP_Enter, "Enter"),
    (Qt.Key_Insert, XK.XK_Insert, "Insert"),
    (Qt.Key_Delete, XK.XK_Delete, "Delete"),
    (Qt.Key_Pause, XK.XK_Pause, "Pause"),
    (Qt.Key_Print, XK.XK_Print, "Print"),
    (Qt.Key_Home, XK.XK_Home, "Home"),
    (Qt.Key_End, XK.XK_End, "End"),
    (Qt.Key_Left, XK.XK_Left, "Left"),
    (Qt.Key_Up, XK.XK_Up, "Up"),
    (Qt.Key_Right, XK.XK_Right, "Right"),
    (Qt.Key_Down, XK.XK_Down, "Down"),
    (Qt.Key_PageUp, XK.XK_Page_Up, "PageUp"),
    (Qt.Key_PageDown, XK.XK_Page_Down, "PageDown"),
    (Qt.Key_Space, XK.XK_space, "Space"),
    (Qt.Key_Menu, XK.XK_Menu, "Menu"),

    # Punctuation / symbols
    (Qt.Key_Minus, XK.XK_minus, "-"),
    (Qt.Key_Equal, XK.XK_equal, "="),
    (Qt.Key_BracketLeft, XK.XK_bracketleft, "["),
    (Qt.Key_BracketRight, XK.XK_bracketright, "]"),
    (Qt.Key_Backslash, XK.XK_backslash, "\\"),
    (Qt.Key_Semicolon, XK.XK_semicolon, ";"),
    (Qt.Key_Apostrophe, XK.XK_apostrophe, "'"),
    (Qt.Key_QuoteLeft, XK.XK_grave, "`"),
    (Qt.Key_Comma, XK.XK_comma, ","),
    (Qt.Key_Period, XK.XK_period, "."),
    (Qt.Key_Slash, XK.XK_slash, "/"),
]

# Modifier flag constants (X11 modifier masks)
MOD_SHIFT = 1 << 0   # ShiftMask
MOD_CTRL = 1 << 2    # ControlMask
MOD_ALT = 1 << 3     # Mod1Mask
MOD_SUPER = 1 << 6   # Mod4Mask

_MODIFIER_NAMES = [
    (MOD_CTRL, "Ctrl"),
    (MOD_ALT, "Alt"),
    (MOD_SHIFT, "Shift"),
    (MOD_SUPER, "Super"),
]

# Qt modifier flags → our modifier bits
_QT_MODIFIER_MAP = {
    Qt.ShiftModifier: MOD_SHIFT,
    Qt.ControlModifier: MOD_CTRL,
    Qt.AltModifier: MOD_ALT,
    Qt.MetaModifier: MOD_SUPER,
}


class KeyNameResolver:
    """Resolves between Qt key codes, X11 keysyms, and human-readable names."""

    def __init__(self):
        self._qt_to_keysym = {}
        self._keysym_to_name = {}
        self._name_to_keysym = {}
        self._keysym_to_qt = {}

        for qt_key, keysym, name in _SPECIAL_KEYS:
            self._qt_to_keysym[qt_key] = keysym
            self._keysym_to_name[keysym] = name
            self._name_to_keysym[name.lower()] = keysym
            self._keysym_to_qt[keysym] = qt_key

        # Latin letters: Qt.Key_A (0x41) maps to XK_a (0x61)
        for i in range(26):
            qt_key = Qt.Key_A + i
            keysym = XK.XK_a + i
            name = chr(ord('A') + i)
            self._qt_to_keysym[qt_key] = keysym
            self._keysym_to_name[keysym] = name
            self._name_to_keysym[name.lower()] = keysym
            self._keysym_to_qt[keysym] = qt_key

        # Digits: Qt.Key_0 (0x30) maps to XK_0 (0x30)
        for i in range(10):
            qt_key = Qt.Key_0 + i
            keysym = XK.XK_0 + i
            name = str(i)
            self._qt_to_keysym[qt_key] = keysym
            self._keysym_to_name[keysym] = name
            self._name_to_keysym[name] = keysym
            self._keysym_to_qt[keysym] = qt_key

    def qt_key_to_keysym(self, qt_key):
        """Convert a Qt key code to an X11 keysym. Returns None if unknown."""
        return self._qt_to_keysym.get(qt_key)

    def keysym_to_name(self, keysym):
        """Convert an X11 keysym to a human-readable name."""
        name = self._keysym_to_name.get(keysym)
        if name:
            return name
        # Fallback: use Xlib's keysym_to_string
        s = XK.keysym_to_string(keysym)
        if s:
            return s
        return f"0x{keysym:04x}"

    def name_to_keysym(self, name):
        """Convert a human-readable name to an X11 keysym. Returns None if unknown."""
        result = self._name_to_keysym.get(name.lower())
        if result:
            return result
        # Fallback: try Xlib's string_to_keysym
        sym = XK.string_to_keysym(name)
        return sym if sym != 0 else None

    def qt_modifiers_to_x11(self, qt_modifiers):
        """Convert Qt modifier flags to X11 modifier mask."""
        mask = 0
        for qt_mod, x11_mod in _QT_MODIFIER_MAP.items():
            if qt_modifiers & qt_mod:
                mask |= x11_mod
        return mask

    def describe_combo(self, keysym, modifiers):
        """Return a human-readable string like 'Ctrl+Shift+A'."""
        parts = []
        for mod_mask, mod_name in _MODIFIER_NAMES:
            if modifiers & mod_mask:
                parts.append(mod_name)
        parts.append(self.keysym_to_name(keysym))
        return "+".join(parts)

    def char_to_keysym(self, char):
        """Convert a single character to its X11 keysym. Returns None on failure."""
        if len(char) != 1:
            return None
        # For Latin-1 range (0x20-0xFF), keysym == Unicode code point
        code = ord(char)
        if 0x20 <= code <= 0x7E:
            return code
        if 0xA0 <= code <= 0xFF:
            return code
        # For Unicode above Latin-1, keysym = 0x01000000 + code point
        if code > 0xFF:
            return 0x01000000 + code
        return None

    def parse_key_combo(self, combo_str):
        """Parse 'Ctrl+Shift+A' into (keysym, modifiers). Returns (None, 0) on failure."""
        parts = combo_str.strip().split("+")
        modifiers = 0
        key_part = None

        mod_lookup = {name.lower(): mask for mask, name in _MODIFIER_NAMES}

        for part in parts:
            lower = part.strip().lower()
            if lower in mod_lookup:
                modifiers |= mod_lookup[lower]
            else:
                key_part = part.strip()

        if key_part is None:
            return None, 0

        keysym = self.name_to_keysym(key_part)
        return keysym, modifiers

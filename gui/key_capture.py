"""
Key capture dialog and button widget.

The dialog intercepts key events to let the user select a key or key combination.
Uses event.nativeVirtualKey() to get the X11 keysym directly from Qt.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
)

from core.key_names import KeyNameResolver, _QT_MODIFIER_MAP


class KeyCaptureDialog(QDialog):
    """Modal dialog that captures a single key or key+modifier combination."""

    key_captured = pyqtSignal(int, int)  # keysym, modifiers

    # Keys that are modifiers themselves (we accept them on release)
    _MODIFIER_KEYS = {
        Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta,
        Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock,
    }

    def __init__(self, key_names: KeyNameResolver, parent=None):
        super().__init__(parent)
        self._key_names = key_names
        self._captured_keysym = None
        self._captured_mods = 0
        self._waiting_for_modifier_release = False
        self._modifier_qt_key = None

        self.setWindowTitle("Capture Key")
        self.setFixedSize(320, 120)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        self._label = QLabel("Press any key or combination...")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._label)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def keyPressEvent(self, event):
        qt_key = event.key()

        if qt_key == Qt.Key_Escape and not event.modifiers():
            self.reject()
            return

        # If it's a modifier-only press, wait for release
        if qt_key in self._MODIFIER_KEYS:
            self._waiting_for_modifier_release = True
            self._modifier_qt_key = qt_key
            self._label.setText(f"Release to capture modifier key...")
            return

        self._waiting_for_modifier_release = False

        # Regular key (possibly with modifiers)
        keysym = self._resolve_keysym(event)
        if keysym is None:
            return

        mods = self._key_names.qt_modifiers_to_x11(event.modifiers())
        self._accept_key(keysym, mods)

    def keyReleaseEvent(self, event):
        if not self._waiting_for_modifier_release:
            return

        qt_key = event.key()
        if qt_key != self._modifier_qt_key:
            return

        self._waiting_for_modifier_release = False

        keysym = self._key_names.qt_key_to_keysym(qt_key)
        if keysym is None:
            return

        # Modifier-only capture: keysym is the modifier, modifiers mask is 0
        self._accept_key(keysym, 0)

    def _resolve_keysym(self, event):
        """Get X11 keysym from a Qt key event."""
        # First try nativeVirtualKey (gives raw X11 keysym)
        native = event.nativeVirtualKey()
        if native and native != 0:
            return native
        # Fall back to Qt key code mapping
        return self._key_names.qt_key_to_keysym(event.key())

    def _accept_key(self, keysym, mods):
        self._captured_keysym = keysym
        self._captured_mods = mods
        self.key_captured.emit(keysym, mods)
        self.accept()

    @property
    def captured_keysym(self):
        return self._captured_keysym

    @property
    def captured_modifiers(self):
        return self._captured_mods


class KeyCaptureButton(QPushButton):
    """Button that shows the currently captured key and opens a capture dialog on click."""

    key_captured = pyqtSignal(int, int)  # keysym, modifiers

    def __init__(self, key_names: KeyNameResolver, label="Click to set...", parent=None):
        super().__init__(label, parent)
        self._key_names = key_names
        self._keysym = None
        self._modifiers = 0
        self._default_label = label
        self.clicked.connect(self._open_dialog)
        self.setMinimumWidth(140)

    def _open_dialog(self):
        dlg = KeyCaptureDialog(self._key_names, self)
        if dlg.exec_() == QDialog.Accepted:
            self._keysym = dlg.captured_keysym
            self._modifiers = dlg.captured_modifiers
            self.setText(self._key_names.describe_combo(self._keysym, self._modifiers))
            self.key_captured.emit(self._keysym, self._modifiers)

    @property
    def keysym(self):
        return self._keysym

    @property
    def modifiers(self):
        return self._modifiers

    def reset(self):
        """Clear the captured key."""
        self._keysym = None
        self._modifiers = 0
        self.setText(self._default_label)

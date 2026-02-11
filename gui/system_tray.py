"""
System tray icon with context menu.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle


class SystemTrayManager:
    """Manages the system tray icon and its context menu."""

    def __init__(self, main_window, remapper):
        self._window = main_window
        self._remapper = remapper

        # Use a built-in icon (keyboard-like) as fallback
        icon = QApplication.instance().style().standardIcon(QStyle.SP_ComputerIcon)
        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip("ReKey - Keyboard Remapper")

        # Context menu
        menu = QMenu()
        self._show_action = menu.addAction("Show/Hide")
        self._show_action.triggered.connect(self._toggle_window)
        menu.addSeparator()
        self._enable_all = menu.addAction("Enable All")
        self._enable_all.triggered.connect(self._remapper.enable_all)
        self._disable_all = menu.addAction("Disable All")
        self._disable_all.triggered.connect(self._remapper.disable_all)
        menu.addSeparator()
        self._quit_action = menu.addAction("Quit")
        self._quit_action.triggered.connect(QApplication.instance().quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

        # Update tooltip on mapping changes
        self._remapper.mapping_added.connect(lambda _: self._update_tooltip())
        self._remapper.mapping_removed.connect(lambda _: self._update_tooltip())
        self._remapper.mapping_toggled.connect(lambda *_: self._update_tooltip())

        self._tray.show()

    def _toggle_window(self):
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # single click
            self._toggle_window()

    def _update_tooltip(self):
        count = self._remapper.active_count()
        self._tray.setToolTip(f"ReKey - {count} active mapping{'s' if count != 1 else ''}")

#!/usr/bin/env python3
"""
ReKey - Keyboard Re-purposing Application
Entry point: wires all components together.
"""

import logging
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

from core.key_names import KeyNameResolver
from core.key_hook import X11KeyHook
from core.storage import Storage
from core.remapper import KeyRemapper
from gui.main_window import MainWindow
from gui.system_tray import SystemTrayManager


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    log = logging.getLogger("rekey")

    app = QApplication(sys.argv)
    app.setApplicationName("ReKey")
    app.setOrganizationName("ReKey")
    app.setQuitOnLastWindowClosed(False)

    # Build dependency graph
    storage = Storage()
    key_names = KeyNameResolver()
    hook = X11KeyHook()
    remapper = KeyRemapper(hook, storage, key_names)

    # Start X11 hook
    hook.start()
    hook.hook_error.connect(lambda msg: log.error("Hook error: %s", msg))

    # Create GUI
    window = MainWindow(remapper, key_names, storage)
    tray = SystemTrayManager(window, remapper)

    # Load saved mappings
    remapper.load_from_storage()

    # Show window (or start minimized)
    if not storage.get_setting("start_minimized", False):
        window.show()

    # Clean shutdown
    app.aboutToQuit.connect(hook.cleanup)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

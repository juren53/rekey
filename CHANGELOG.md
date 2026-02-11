# Changelog

## [v0.0.1] - 2026-02-11

### Added
- Initial project structure with core and gui packages
- Key name resolver with bidirectional Qt/X11 keysym/display name mapping
- X11 global key grab via XGrabKey with NumLock/CapsLock-insensitive variants
- XTEST key simulation with automatic keyboard mapping lookup (e.g. @ resolves to Shift+2)
- JSON persistence with atomic writes to ~/.config/rekey/mappings.json
- Key remapper with conflict detection and auto-save
- Key capture dialog supporting modifier-only keys and key combinations
- Character input field for target keys (type @, #, $ etc. directly)
- Main window with mapping table, enable/disable checkboxes, and delete buttons
- System tray icon with Show/Hide, Enable All, Disable All, Quit menu
- Settings: start minimized, enable mappings on startup

### Known Issues
- Event loop thread safety needs improvement (python-xlib Display not thread-safe)

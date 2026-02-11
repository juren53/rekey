# ReKey Implementation Plan

## Context

ReKey is a keyboard re-purposing application for Linux/X11. The original plan proposed `pyqtkeybind`, which can only register hotkeys — it cannot intercept and suppress key events. We use **python-xlib** instead, which supports `XGrabKey` (intercept + suppress) and `XTEST` (simulate replacement keys). Both `PyQt5` and `python-xlib` are already installed. No sudo/root is needed.

Target: Linux, X11, Python 3.11, PyQt5 5.15, python-xlib 0.33. User is in the `input` group.

## File Structure

```
rekey/
├── main.py                  # Entry point, wires everything together
├── core/
│   ├── __init__.py
│   ├── key_names.py         # Qt ↔ X11 keysym ↔ human name resolution
│   ├── key_hook.py          # X11 global key grab + XTEST simulation
│   ├── remapper.py          # Mapping lifecycle, conflict detection
│   └── storage.py           # JSON persistence (~/.config/rekey/)
├── gui/
│   ├── __init__.py
│   ├── key_capture.py       # "Press any key..." dialog + button widget
│   ├── main_window.py       # Main window with mapping table + settings
│   └── system_tray.py       # System tray icon + context menu
└── requirements.txt
```

## Implementation Order (risk-first)

### Step 1: `requirements.txt`
```
PyQt5>=5.15.0
python-xlib>=0.33
```

### Step 2: `core/key_names.py` — KeyNameResolver
Bidirectional mapping between Qt key codes, X11 keysyms, and display names.
- Explicit mapping table for ~60 special keys (F1-F24, modifiers, navigation, etc.)
- Latin letters: Qt.Key_A (0x41) → XK_a (0x61), digits/space map directly
- Methods: `qt_key_to_keysym()`, `keysym_to_name()`, `name_to_keysym()`, `parse_key_combo(str) → (keysym, modifiers)`, `describe_combo(keysym, modifiers) → str`

### Step 3: `core/key_hook.py` — X11KeyHook(QObject)
The most critical component. Uses QSocketNotifier on the Xlib display fd to process X events in the Qt main thread (no threading needed).

Key design decisions:
- **NumLock/CapsLock handling**: Each logical grab creates 4 X11 grabs (combinations of LockMask and Mod2Mask)
- **QSocketNotifier**: Watches `display.fileno()` for readability, drains all pending events in callback
- **XTEST simulation**: `fake_input()` for press/release of target key + modifier keys

Signals: `key_intercepted(int, int)`, `hook_error(str)`
Methods: `grab_key()`, `ungrab_key()`, `simulate_key()`, `start()`, `stop()`, `cleanup()`

### Step 4: `core/storage.py` — Storage
- Config dir: `~/.config/rekey/mappings.json`
- Atomic writes (write to .tmp, then `os.replace()`)
- Format: `{"version": 1, "mappings": [...], "settings": {...}}`
- Methods: `load_mappings()`, `save_mappings()`, `get_setting()`, `set_setting()`

### Step 5: `core/remapper.py` — KeyRemapper(QObject)
- `KeyMapping` dataclass: id, source_keysym, source_modifiers, target_keysym, target_modifiers, enabled, description
- Orchestrates hook grabs ↔ storage persistence
- Conflict detection: rejects duplicate source key+modifier combos
- Signals: `mapping_added`, `mapping_removed`, `mapping_toggled`, `error_occurred`
- Auto-saves on every change

### Step 6: `gui/key_capture.py` — KeyCaptureDialog + KeyCaptureButton
- Modal dialog: "Press any key or combination..."
- Handles modifier-only keys (CapsLock, Shift alone) via keyRelease tracking
- Uses `event.nativeVirtualKey()` to get X11 keysym directly from Qt
- `KeyCaptureButton(QPushButton)`: shows captured key name, opens dialog on click, emits `key_captured(int, int)`

### Step 7: `gui/main_window.py` — MainWindow(QMainWindow)
- **Top**: Two KeyCaptureButtons ("From" + "To") + description field + "Add Mapping" button
- **Middle**: QTableWidget — Source Key | Target Key | Description | Enabled (checkbox) | Delete (button)
- **Bottom**: Settings checkboxes (start minimized, enable on startup)
- **Status bar**: "N active mappings" or error info
- closeEvent hides to tray instead of quitting

### Step 8: `gui/system_tray.py` — SystemTrayManager
- QSystemTrayIcon with context menu: Show/Hide, Enable All, Disable All, Quit
- Single-click toggles window visibility
- Tooltip shows active mapping count

### Step 9: `main.py` — Entry point
- Creates all objects in dependency order: Storage → KeyNameResolver → X11KeyHook → KeyRemapper → MainWindow → SystemTrayManager
- `app.setQuitOnLastWindowClosed(False)` for tray operation
- `app.aboutToQuit.connect(hook.cleanup)` for clean shutdown
- Loads saved mappings, respects `start_minimized` setting

## Key Technical Details

| Concern | Solution |
|---|---|
| Key suppression | `XGrabKey` on root window — grabbed keys don't reach other apps |
| Key simulation | XTEST `fake_input()` for KeyPress/KeyRelease |
| NumLock/CapsLock | Grab 4 variants per key (±LockMask ±Mod2Mask) |
| Threading | None — QSocketNotifier on Xlib fd, all in main thread |
| Grab conflicts | Catch `BadAccess` → report "key already grabbed by another app" |
| Persistence | Atomic JSON writes to `~/.config/rekey/` |
| Key name translation | Explicit mapping table in key_names.py |

## Verification

1. Run `python3 main.py` — window should appear with empty mapping table
2. Click "From" capture button → press F1 → should show "F1"
3. Click "To" capture button → press F2 → should show "F2"
4. Click "Add Mapping" → row appears in table
5. Open a text editor, press F1 → should produce F2 instead
6. Toggle the mapping's checkbox off → F1 should work normally again
7. Close the window → app stays in system tray
8. Right-click tray icon → "Show" brings window back
9. Kill and restart app → mapping should be restored from disk

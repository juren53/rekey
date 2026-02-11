# ReKey - Keyboard Re-purposing Application Implementation Plan

## Overview
ReKey is a PyQt5 application that allows users to re-purpose keyboard keys, providing global key remapping functionality that persists across sessions and runs minimized in the system tray.

## Technical Architecture

### Core Libraries
- **PyQt5/PySide2** for GUI framework
- **keyboard** for global keyboard interception and key simulation
- **JSON** for persistent storage of key mappings

### Application Structure

#### 1. Main Components

##### KeyReMapperApp (QMainWindow)
- Key mapping configuration interface
- Table widget for displaying/managing mappings
- Key selection dropdown and action assignment

##### SystemTrayManager (QSystemTrayIcon)
- Minimize to system tray
- Context menu (Show, Exit, Enable/Disable)
- Status notifications

##### GlobalKeyHook
- Uses keyboard library for global key interception and suppression
- Maps intercepted keys to new actions using keyboard.press/release/write
- Thread-safe communication between keyboard callbacks and PyQt GUI

#### 2. Key Mapping Storage Format
```json
{
  "mappings": [
    {
      "original_key": "F1",
      "new_action": "ctrl+alt+t",
      "enabled": true,
      "description": "Open terminal"
    }
  ],
  "settings": {
    "start_minimized": false,
    "enable_on_startup": true
  }
}
```

#### 3. User Interface Layout

##### Top Section - Add New Mapping
- Dropdown: "Select key to re-purpose" (F1-F12, Caps Lock, etc.)
- Input: "New action/key sequence"
- Button: "Add Mapping"

##### Middle Section - Mappings Table
- Columns: Original Key, New Action, Status, Actions
- Edit/Delete/Enable-Disable buttons per row

##### Bottom Section - Settings
- Start minimized checkbox
- Enable on startup checkbox

#### 4. Implementation Phases

**Phase 1: Core GUI**
1. Create main window with basic layout
2. Implement key selection dropdown
3. Add table widget for mappings
4. Basic add/edit/delete functionality

**Phase 2: Global Key Hook**
1. Integrate keyboard library for global key interception and suppression
2. Implement key remapping logic using keyboard simulation methods
3. Thread-safe communication between keyboard callbacks and PyQt GUI using signals/slots

**Phase 3: System Tray Integration**
1. Add QSystemTrayIcon functionality
2. Implement minimize-to-tray behavior
3. Add context menu and notifications

**Phase 4: Storage & Settings**
1. Implement JSON file I/O
2. Add application settings
3. Auto-save and restore mappings

#### 5. Key Action Types to Support
- **Key sequences**: "ctrl+alt+t", "win+r" (using keyboard.press_and_release)
- **Application launches**: "notepad.exe", "/usr/bin/firefox" (using subprocess)
- **Text insertion**: Type custom text (using keyboard.write)
- **Macro sequences**: Multiple actions in sequence
- **Key suppression**: Prevent original key from being processed

#### 6. File Structure
```
rekey/
├── main.py              # Application entry point
├── gui/
│   ├── __init__.py
│   ├── main_window.py    # Main GUI window
│   ├── key_mapper.py     # Key mapping logic
│   └── system_tray.py    # System tray integration
├── core/
│   ├── __init__.py
│   ├── key_hook.py       # Global keyboard hook
│   └── storage.py        # JSON storage management
├── resources/
│   └── icon.ico          # Application icon
├── requirements.txt
└── README.md
```

#### 7. Dependencies
```
PyQt5>=5.15.0
keyboard>=0.13.5
```

#### 8. Key Features
- Global key interception and remapping
- System tray operation
- Persistent storage of mappings
- Table-based management interface
- Support for complex key sequences
- Cross-platform compatibility (Windows/Linux)
- Enable/disable individual mappings

#### 9. Technical Considerations
- Thread safety: keyboard callbacks run in separate thread, must use PyQt signals for GUI updates
- Key suppression: keyboard.hook() with suppress=True parameter
- Linux permissions: requires sudo/root to read /dev/input/input* devices
- Windows compatibility: Full key suppression support available
- Proper cleanup: keyboard.unhook_all() on application exit
- Error handling: Invalid key sequences, permission denied scenarios

#### 10. Future Enhancements
- Import/export mapping profiles
- GUI-based key capture instead of dropdown
- Plugin system for custom action types
- Statistics and usage tracking
- Network synchronization of mappings

## Development Notes
This modular design provides a solid foundation for the keyboard re-purposing application while maintaining flexibility for future enhancements. The chosen libraries integrate well together and provide the necessary functionality for cross-platform deployment.
# ReKey - Keyboard Re-purposing Application

A PyQt5 application that allows users to re-purpose keyboard keys globally. The application runs minimized in the system tray and provides persistent key remapping functionality.

## Features

- Global key interception and remapping
- System tray operation with context menu
- Persistent storage of mappings in JSON format
- Table-based management interface
- Support for complex key sequences, text insertion, and application launches
- Cross-platform compatibility (Windows/Linux)
- Enable/disable individual mappings

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

**Note**: On Linux, the application requires root/sudo privileges to access keyboard devices:
```bash
sudo python main.py
```

## Usage

1. Select a key to re-purpose from the dropdown
2. Enter the new action (key sequence, text, or application)
3. Click "Add Mapping"
4. Minimize to system tray - mappings remain active
5. Right-click tray icon to show/quit application

## Key Action Types

- **Key sequences**: `ctrl+alt+t`, `win+r`
- **Application launches**: `notepad.exe`, `/usr/bin/firefox`
- **Text insertion**: Any custom text
- **Macro sequences**: Multiple actions separated by commas

## File Structure

```
rekey/
├── main.py              # Application entry point
├── gui/                 # GUI components
├── core/                # Core functionality
├── resources/           # Resources (icons, etc.)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## License

MIT License
"""
Main window with mapping table, add controls, and settings.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QLabel, QCheckBox,
    QStatusBar, QMessageBox, QAbstractItemView,
)

from core.key_names import KeyNameResolver
from core.remapper import KeyRemapper, KeyMapping
from gui.key_capture import KeyCaptureButton


class MainWindow(QMainWindow):
    def __init__(self, remapper: KeyRemapper, key_names: KeyNameResolver,
                 storage, parent=None):
        super().__init__(parent)
        self._remapper = remapper
        self._key_names = key_names
        self._storage = storage

        self.setWindowTitle("ReKey - Keyboard Remapper")
        self.setMinimumSize(600, 400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top: Add mapping controls ---
        add_layout = QHBoxLayout()

        add_layout.addWidget(QLabel("From:"))
        self._from_btn = KeyCaptureButton(key_names, "Source key...")
        add_layout.addWidget(self._from_btn)

        add_layout.addWidget(QLabel("To:"))
        self._to_btn = KeyCaptureButton(key_names, "Target key...")
        add_layout.addWidget(self._to_btn)

        add_layout.addWidget(QLabel("or char:"))
        self._char_edit = QLineEdit()
        self._char_edit.setMaxLength(1)
        self._char_edit.setFixedWidth(40)
        self._char_edit.setToolTip("Type a single character (e.g. @, #, $)")
        self._char_edit.textChanged.connect(self._on_char_changed)
        self._to_btn.key_captured.connect(lambda *_: self._char_edit.clear())
        add_layout.addWidget(self._char_edit)

        add_layout.addWidget(QLabel("Desc:"))
        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText("Optional description")
        self._desc_edit.setMaximumWidth(160)
        add_layout.addWidget(self._desc_edit)

        self._add_btn = QPushButton("Add Mapping")
        self._add_btn.clicked.connect(self._on_add_mapping)
        add_layout.addWidget(self._add_btn)

        layout.addLayout(add_layout)

        # --- Middle: Mapping table ---
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            "Source Key", "Target Key", "Description", "Enabled", "Actions",
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        # --- Bottom: Settings ---
        settings_layout = QHBoxLayout()
        self._start_minimized_cb = QCheckBox("Start minimized to tray")
        self._start_minimized_cb.setChecked(
            self._storage.get_setting("start_minimized", False)
        )
        self._start_minimized_cb.toggled.connect(
            lambda v: self._storage.set_setting("start_minimized", v)
        )
        settings_layout.addWidget(self._start_minimized_cb)

        self._enable_on_startup_cb = QCheckBox("Enable mappings on startup")
        self._enable_on_startup_cb.setChecked(
            self._storage.get_setting("enable_on_startup", True)
        )
        self._enable_on_startup_cb.toggled.connect(
            lambda v: self._storage.set_setting("enable_on_startup", v)
        )
        settings_layout.addWidget(self._enable_on_startup_cb)
        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # --- Status bar ---
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # Connect remapper signals
        self._remapper.mapping_added.connect(self._on_mapping_added)
        self._remapper.mapping_removed.connect(self._on_mapping_removed)
        self._remapper.mapping_toggled.connect(self._on_mapping_toggled)
        self._remapper.error_occurred.connect(self._on_error)

        self._update_status()

    def _on_char_changed(self, text):
        """When user types a character, clear the capture button (they're alternatives)."""
        if text:
            self._to_btn.reset()

    def _on_add_mapping(self):
        if self._from_btn.keysym is None:
            QMessageBox.warning(self, "ReKey", "Please capture a source key first.")
            return

        # Target: prefer character input if set, otherwise use capture button
        char_text = self._char_edit.text()
        if char_text:
            target_keysym = self._key_names.char_to_keysym(char_text)
            if target_keysym is None:
                QMessageBox.warning(self, "ReKey", f"Cannot map character: {char_text}")
                return
            target_mods = 0  # simulate_key resolves shift automatically
        elif self._to_btn.keysym is not None:
            target_keysym = self._to_btn.keysym
            target_mods = self._to_btn.modifiers
        else:
            QMessageBox.warning(self, "ReKey",
                                "Please capture a target key or type a character.")
            return

        mapping = self._remapper.add_mapping(
            self._from_btn.keysym,
            self._from_btn.modifiers,
            target_keysym,
            target_mods,
            self._desc_edit.text().strip(),
        )

        if mapping:
            self._from_btn.reset()
            self._to_btn.reset()
            self._char_edit.clear()
            self._desc_edit.clear()

    def _on_mapping_added(self, mapping: KeyMapping):
        row = self._table.rowCount()
        self._table.insertRow(row)

        src = self._key_names.describe_combo(mapping.source_keysym, mapping.source_modifiers)
        tgt = self._key_names.describe_combo(mapping.target_keysym, mapping.target_modifiers)

        src_item = QTableWidgetItem(src)
        src_item.setData(Qt.UserRole, mapping.id)
        self._table.setItem(row, 0, src_item)
        self._table.setItem(row, 1, QTableWidgetItem(tgt))
        self._table.setItem(row, 2, QTableWidgetItem(mapping.description))

        # Enabled checkbox
        cb = QCheckBox()
        cb.setChecked(mapping.enabled)
        cb.toggled.connect(lambda checked, mid=mapping.id: self._remapper.toggle_mapping(mid, checked))
        cb_widget = QWidget()
        cb_layout = QHBoxLayout(cb_widget)
        cb_layout.addWidget(cb)
        cb_layout.setAlignment(Qt.AlignCenter)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, 3, cb_widget)

        # Delete button
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(lambda _, mid=mapping.id: self._remapper.remove_mapping(mid))
        self._table.setCellWidget(row, 4, del_btn)

        self._update_status()

    def _on_mapping_removed(self, mapping_id: str):
        row = self._find_row(mapping_id)
        if row >= 0:
            self._table.removeRow(row)
        self._update_status()

    def _on_mapping_toggled(self, mapping_id: str, enabled: bool):
        row = self._find_row(mapping_id)
        if row >= 0:
            widget = self._table.cellWidget(row, 3)
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(enabled)
                    cb.blockSignals(False)
        self._update_status()

    def _on_error(self, msg: str):
        self._status.showMessage(f"Error: {msg}", 5000)

    def _find_row(self, mapping_id: str):
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(Qt.UserRole) == mapping_id:
                return row
        return -1

    def _update_status(self):
        count = self._remapper.active_count()
        self._status.showMessage(f"{count} active mapping{'s' if count != 1 else ''}")

    def closeEvent(self, event):
        """Hide to tray instead of quitting."""
        event.ignore()
        self.hide()

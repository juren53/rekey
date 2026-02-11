"""
Key remapping lifecycle: manages mappings, grabs, conflict detection, persistence.
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict

from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)


@dataclass
class KeyMapping:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_keysym: int = 0
    source_modifiers: int = 0
    target_keysym: int = 0
    target_modifiers: int = 0
    enabled: bool = True
    description: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class KeyRemapper(QObject):
    """Orchestrates key grabs, XTEST simulation, storage, and conflict detection."""

    mapping_added = pyqtSignal(object)      # KeyMapping
    mapping_removed = pyqtSignal(str)        # mapping id
    mapping_toggled = pyqtSignal(str, bool)  # mapping id, enabled
    error_occurred = pyqtSignal(str)

    def __init__(self, hook, storage, key_names, parent=None):
        super().__init__(parent)
        self._hook = hook
        self._storage = storage
        self._key_names = key_names
        self._mappings = {}  # id → KeyMapping

    @property
    def mappings(self):
        return list(self._mappings.values())

    def load_from_storage(self):
        """Restore mappings from disk and grab enabled ones."""
        saved = self._storage.load_mappings()
        for d in saved:
            mapping = KeyMapping.from_dict(d)
            self._mappings[mapping.id] = mapping
            if mapping.enabled:
                self._grab(mapping)
            self.mapping_added.emit(mapping)

    def add_mapping(self, source_keysym, source_modifiers,
                    target_keysym, target_modifiers, description=""):
        """Add a new mapping. Returns the KeyMapping or None on conflict."""
        # Conflict detection: same source key+mods already mapped?
        for m in self._mappings.values():
            if (m.source_keysym == source_keysym
                    and m.source_modifiers == source_modifiers):
                self.error_occurred.emit(
                    f"Source key already mapped: "
                    f"{self._key_names.describe_combo(source_keysym, source_modifiers)}"
                )
                return None

        mapping = KeyMapping(
            source_keysym=source_keysym,
            source_modifiers=source_modifiers,
            target_keysym=target_keysym,
            target_modifiers=target_modifiers,
            description=description,
        )

        if not self._grab(mapping):
            return None

        self._mappings[mapping.id] = mapping
        self._persist()
        self.mapping_added.emit(mapping)
        return mapping

    def remove_mapping(self, mapping_id):
        """Remove a mapping by id."""
        mapping = self._mappings.pop(mapping_id, None)
        if mapping is None:
            return
        if mapping.enabled:
            self._ungrab(mapping)
        self._persist()
        self.mapping_removed.emit(mapping_id)

    def toggle_mapping(self, mapping_id, enabled):
        """Enable or disable a mapping."""
        mapping = self._mappings.get(mapping_id)
        if mapping is None:
            return

        if mapping.enabled == enabled:
            return

        if enabled:
            if not self._grab(mapping):
                return
        else:
            self._ungrab(mapping)

        mapping.enabled = enabled
        self._persist()
        self.mapping_toggled.emit(mapping_id, enabled)

    def active_count(self):
        """Return number of currently enabled mappings."""
        return sum(1 for m in self._mappings.values() if m.enabled)

    def enable_all(self):
        for m in self._mappings.values():
            if not m.enabled:
                self.toggle_mapping(m.id, True)

    def disable_all(self):
        for m in self._mappings.values():
            if m.enabled:
                self.toggle_mapping(m.id, False)

    def _grab(self, mapping):
        """Grab the source key and register a callback that simulates the target."""
        def on_key(keysym, mods):
            self._hook.simulate_key(mapping.target_keysym, mapping.target_modifiers)

        ok = self._hook.grab_key(
            mapping.source_keysym, mapping.source_modifiers, on_key
        )
        if not ok:
            self.error_occurred.emit(
                f"Failed to grab "
                f"{self._key_names.describe_combo(mapping.source_keysym, mapping.source_modifiers)}"
            )
        return ok

    def _ungrab(self, mapping):
        self._hook.ungrab_key(mapping.source_keysym, mapping.source_modifiers)

    def _persist(self):
        data = [m.to_dict() for m in self._mappings.values()]
        self._storage.save_mappings(data)

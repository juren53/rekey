"""
JSON persistence for key mappings and settings.
Config directory: ~/.config/rekey/
"""

import json
import logging
import os
import tempfile

log = logging.getLogger(__name__)

_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "rekey")
_MAPPINGS_FILE = os.path.join(_CONFIG_DIR, "mappings.json")

_DEFAULT_DATA = {
    "version": 1,
    "mappings": [],
    "settings": {
        "start_minimized": False,
        "enable_on_startup": True,
    },
}


class Storage:
    """Atomic JSON read/write for ReKey configuration."""

    def __init__(self, config_dir=None):
        self._config_dir = config_dir or _CONFIG_DIR
        self._mappings_file = os.path.join(self._config_dir, "mappings.json")
        self._data = None

    def _ensure_dir(self):
        os.makedirs(self._config_dir, exist_ok=True)

    def _load(self):
        """Load from disk, or create default data."""
        if self._data is not None:
            return
        if os.path.exists(self._mappings_file):
            try:
                with open(self._mappings_file, "r") as f:
                    self._data = json.load(f)
                log.info("Loaded config from %s", self._mappings_file)
                return
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Failed to load config: %s", e)
        self._data = json.loads(json.dumps(_DEFAULT_DATA))  # deep copy

    def _save(self):
        """Atomic write: write to tmp file then os.replace()."""
        self._ensure_dir()
        fd, tmp_path = tempfile.mkstemp(
            dir=self._config_dir, suffix=".tmp", prefix="mappings_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp_path, self._mappings_file)
            log.info("Saved config to %s", self._mappings_file)
        except OSError:
            log.exception("Failed to save config")
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def load_mappings(self):
        """Return the list of mapping dicts."""
        self._load()
        return list(self._data.get("mappings", []))

    def save_mappings(self, mappings):
        """Persist the list of mapping dicts."""
        self._load()
        self._data["mappings"] = mappings
        self._save()

    def get_setting(self, key, default=None):
        """Get a setting value."""
        self._load()
        return self._data.get("settings", {}).get(key, default)

    def set_setting(self, key, value):
        """Set a setting value and persist."""
        self._load()
        if "settings" not in self._data:
            self._data["settings"] = {}
        self._data["settings"][key] = value
        self._save()

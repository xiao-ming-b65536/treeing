"""
treeing/gui/settings.py

Defines GUI user-preference persistence.
Saves/loads the last generate directory, font size, import encoding and other
settings to ~/.treeing/settings.json.
"""

import json
from pathlib import Path

_SETTINGS_PATH = Path.home() / '.treeing' / 'settings.json'
_DEFAULT_FONT_SIZE = 10
_DEFAULT_IMPORT_ENCODING = 'utf-8'
_DEFAULT_IMPORT_ENCODINGS = (
    'utf-8', 'utf-16', 'cp1252', 'iso-8859-1', 'mac-roman',
)


def load_settings() -> dict:
    """Load user settings; return an empty dict on failure."""
    try:
        if _SETTINGS_PATH.is_file():
            return json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


def save_settings(data: dict) -> None:
    """Save user settings, creating the parent directory as needed."""
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    except OSError:
        pass


def get_font_size(settings: dict | None = None) -> int:
    """Return a valid font size in the range 8-24; fall back to the default for invalid values."""
    raw = (settings or load_settings()).get('font_size', _DEFAULT_FONT_SIZE)
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_FONT_SIZE
    return max(8, min(size, 24))


def get_last_generate_dir(settings: dict | None = None) -> str | None:
    """Return the directory used for the last generation, or None when it no longer exists."""
    path = (settings or load_settings()).get('last_generate_dir')
    if path and Path(path).is_dir():
        return path
    return None


def get_import_encodings(settings: dict | None = None) -> list[str]:
    """Dropdown preset list; settings.json's import_encodings may add or remove entries; empty falls back to the built-in default."""
    raw = (settings or load_settings()).get('import_encodings')
    if isinstance(raw, list) and raw:
        seen: list[str] = []
        for item in raw:
            if isinstance(item, str):
                enc = item.strip()
                if enc and enc not in seen:
                    seen.append(enc)
        if seen:
            return seen
    return list(_DEFAULT_IMPORT_ENCODINGS)


def get_import_encoding(settings: dict | None = None) -> str:
    """Return the last chosen import encoding; default utf-8."""
    raw = (settings or load_settings()).get('import_encoding', _DEFAULT_IMPORT_ENCODING)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return _DEFAULT_IMPORT_ENCODING

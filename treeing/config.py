"""treeing/config.py

Defines string-resource loading and configuration management.
Loads, formats and falls back for strings.json / strings.bootstrap.json,
providing a unified multi-language text interface for the CLI and GUI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_CONFIG = None
_BOOTSTRAP: dict | None = None
_BOOTSTRAP_FAILED_PATH: Path | None = None

_BOOTSTRAP_FILENAME = "strings.bootstrap.json"


class ConfigError(Exception):
    """
    Raised when strings.json cannot be loaded or is malformed.

    MING keeps error messages in strings.json too, but if strings.json itself is
    broken, the code falls back to the minimal text in strings.bootstrap.json so
    the user still sees a sensible error message.
    """


def _resource_dir() -> Path:
    """
    Locate the directory that holds strings.json.

    In development this is the source directory; under a PyInstaller bundle it
    is the _MEIPASS temporary directory.
    """
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass is not None:
            return Path(meipass) / "treeing"
    return Path(__file__).parent


def _format_string(text: str, **kwargs) -> str:
    """
    Interpolate text via str.format, returning the original on failure.

    MING wraps this in try/except because user-supplied placeholders may not
    match the text; showing the raw string is easier to debug than raising.
    """
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError, IndexError):
        return text


def _bootstrap_unavailable_fallback(key: str, path: Path, **kwargs) -> str:
    """
    Last-resort fallback when the bootstrap JSON is unreadable.

    Returns only technical information such as the key name and path (no
    user-visible text is hard-coded), so the user never sees garbled output
    when both strings.json and the bootstrap file are corrupt.
    """
    parts = [key, f"path={path}"]
    for name, value in kwargs.items():
        if name != 'path':
            parts.append(f"{name}={value}")
    return " ".join(parts)


def _load_bootstrap() -> dict:
    """
    Load the bootstrap text (the minimal configurable set used when the main strings.json is unavailable).

    The result is cached in _BOOTSTRAP; on failure _BOOTSTRAP_FAILED_PATH records the path.
    """
    global _BOOTSTRAP, _BOOTSTRAP_FAILED_PATH
    if _BOOTSTRAP is not None:
        return _BOOTSTRAP

    bootstrap_path = _resource_dir() / _BOOTSTRAP_FILENAME
    try:
        with open(bootstrap_path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            _BOOTSTRAP = {}
            _BOOTSTRAP_FAILED_PATH = bootstrap_path
        else:
            _BOOTSTRAP = data
            _BOOTSTRAP_FAILED_PATH = None
    except (OSError, json.JSONDecodeError):
        _BOOTSTRAP = {}
        _BOOTSTRAP_FAILED_PATH = bootstrap_path
    return _BOOTSTRAP


def bootstrap_string(key: str, **kwargs) -> str:
    """
    Fetch text from strings.bootstrap.json.

    When the bootstrap file is unavailable, falls back to the key name plus
    path= and other technical fields, so the program never crashes.
    """
    data = _load_bootstrap()
    failed_path = _BOOTSTRAP_FAILED_PATH

    if failed_path is not None:
        text = data.get(key)
        if text is None:
            if key == 'config_err_bootstrap_missing':
                report_path = kwargs.get('path', failed_path)
                extra = {k: v for k, v in kwargs.items() if k != 'path'}
                return _bootstrap_unavailable_fallback(key, report_path, **extra)
            return bootstrap_string('config_err_bootstrap_missing', path=failed_path)
    else:
        text = data.get(key, key)

    return _format_string(text, **kwargs)


def load_config():
    """
    Load and cache strings.json.

    Raises ConfigError when the file is missing, the JSON is malformed, the
    root is not an object, or reading fails; the error message is taken from
    bootstrap_string where possible.
    """
    global _CONFIG
    if _CONFIG is None:
        json_path = _resource_dir() / "strings.json"
        try:
            with open(json_path, encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise ConfigError(
                bootstrap_string("config_err_missing", path=json_path),
            ) from e
        except json.JSONDecodeError as e:
            raise ConfigError(
                bootstrap_string("config_err_invalid_json", path=json_path, error=e),
            ) from e
        except OSError as e:
            raise ConfigError(
                bootstrap_string("config_err_read", path=json_path, error=e),
            ) from e
        if not isinstance(data, dict):
            raise ConfigError(
                bootstrap_string("config_err_not_object", path=json_path),
            )
        _CONFIG = data
    return _CONFIG


def get_string(key, **kwargs):
    """
    Fetch and interpolate text from strings.json.

    If the key is missing, the key name itself is returned, so a missing entry
    is immediately obvious during development and testing.
    """
    cfg = load_config()
    text = cfg.get(key, key)
    return _format_string(text, **kwargs)


# Invocation placeholders: help / about text refers to these uniformly, so we
# do not hard-code only the `python -m` form.
CLI_PYTHON = "python -m treeing.main"
CLI_EXE_UNIX = "treeing-cli"
CLI_EXE_WIN = "treeing-cli.exe"
GUI_PYTHON = "python -m treeing.main"
GUI_EXE_UNIX = "treeing-gui"
GUI_EXE_WIN = "treeing-gui.exe"


def invocation_vars() -> dict[str, str]:
    """
    Return the invocation placeholders used in help / about text.

    Covers both source (`python -m`) and PyInstaller artefacts
    (treeing-cli / treeing-gui); the Windows executable carries the .exe suffix.
    """
    return {
        "cli_python": CLI_PYTHON,
        "cli_exe_unix": CLI_EXE_UNIX,
        "cli_exe_win": CLI_EXE_WIN,
        "gui_python": GUI_PYTHON,
        "gui_exe_unix": GUI_EXE_UNIX,
        "gui_exe_win": GUI_EXE_WIN,
    }


def get_ui_string(key: str, **kwargs) -> str:
    """
    Fetch user-visible text that includes invocation placeholders.

    Used by help, about and GUI error prompts that need to show both the
    Python and the executable forms.
    """
    return get_string(key, **invocation_vars(), **kwargs)

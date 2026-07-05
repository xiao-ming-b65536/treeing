"""treeing/path_checks.py

Defines output-path validation logic.
Provides `verify_output_is_directory` and `verify_output_writable`,
shared by the CLI and GUI, to ensure the target directory is legal and writable.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .config import get_string


def verify_output_is_directory(output: str | Path) -> str | None:
    """
    Check whether the output path is legal.

    Returns an error message if the path exists and is a file; otherwise None.
    """
    target = Path(output).expanduser()
    if target.exists() and target.is_file():
        return get_string('cli_output_is_file', path=target)
    return None


def _nearest_existing(path: Path) -> Path | None:
    """Walk upward from path to the nearest existing parent directory; return None if none exists."""
    probe = path
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            return None
        probe = parent
    return probe


def _probe_writable_dir(dir_path: Path, report_path: Path) -> str | None:
    """
    Actually probe whether a directory is writable.

    Checks os.access first, then tries to create a temporary directory as a
    second safeguard. MING added the temporary-directory test because some
    mount/network paths report writable via access but fail on real writes.
    """
    try:
        resolved = dir_path.resolve()
    except OSError:
        return get_string('cli_output_not_writable', path=report_path)

    if not resolved.is_dir():
        return get_string('cli_output_not_writable', path=report_path)

    if not os.access(resolved, os.W_OK):
        return get_string('cli_output_not_writable', path=resolved)
    if os.name != 'nt' and not os.access(resolved, os.X_OK):
        return get_string('cli_output_not_writable', path=resolved)

    try:
        test_dir = tempfile.mkdtemp(prefix='.treeing-write-test-', dir=str(resolved))
        os.rmdir(test_dir)
    except OSError:
        return get_string('cli_output_not_writable', path=report_path)
    return None


def verify_output_writable(output: str | Path) -> str | None:
    """
    Check whether the output path is ultimately writable.

    If the target directory does not exist, walk up to the nearest existing
    parent before probing.
    """
    err = verify_output_is_directory(output)
    if err:
        return err

    target = Path(output).expanduser()
    if target.exists():
        return _probe_writable_dir(target, target)

    existing = _nearest_existing(target)
    if existing is None:
        return get_string('cli_output_not_writable', path=output)
    return _probe_writable_dir(existing, target)

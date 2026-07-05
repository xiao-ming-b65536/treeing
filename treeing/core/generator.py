"""
treeing/core/generator.py

Defines the logic for generating disk directories/files from the node tree.
Handles path registration, conflict detection, Windows reserved names and
over-long paths, strict-mode rollback, and nested-path expansion.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from ..config import get_string
from .constants import TRANSPARENT_NODE_NAMES

# Windows reserved device names that cannot be used as filenames.
# MING lists COM1~COM9 and LPT1~LPT9 here because they have special meaning on Windows.
_WIN_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *{f'COM{i}' for i in range(1, 10)},
    *{f'LPT{i}' for i in range(1, 10)},
}

# Tree decoration characters (various box-drawing lines) replaced in filenames.
_TREE_DECOR_CHARS = re.compile(r'[\u2500-\u257F\u251C\u2514\u2502]')

# Windows path length limit.
_WIN_MAX_PATH = 260
_WIN_PATH_WARN_THRESHOLD = _WIN_MAX_PATH - 12

_CreatedEntry = tuple[str, Path]
_PathKind = str
_PathRegistry = dict[str, _PathKind]


def _kind_label(kind: _PathKind) -> str:
    """
    Turn 'dir'/'file' into a user-friendly label (directory/file).

    Used by conflict error messages; falls back to file for unknown kinds.
    """
    if kind == 'dir':
        return get_string('core_kind_dir')
    return get_string('core_kind_file')


class PathConflictError(Exception):
    """
    Raised on a path conflict.

    MING designed two modes:
    - Normal mode: warn on conflict and continue (may overwrite or skip).
    - Strict mode (--fail-on-conflict): raise immediately and roll back what
      was already created.

    The exception carries a `rolled` field telling the caller how many
    files/directories were rolled back.
    """

    def __init__(self, name: str, rolled: int = 0):
        self.name = name
        self.rolled = rolled
        if rolled > 0:
            msg = get_string("core_err_path_conflict_rolled", name=name, rolled=rolled)
        else:
            msg = get_string("core_err_path_conflict", name=name)
        super().__init__(msg)


DuplicateNameError = PathConflictError


@dataclass
class _CreateContext:
    """
    Generation context: records the output root, the registered paths and the list of created files.

    The created list supports rollback: on a mid-run error, already-created
    entries can be deleted in reverse order. MING made this a dataclass so the
    recursive create_from_tree calls share one registry and one created list
    instead of rebuilding state at every level.
    """
    output_root: Path
    path_registry: _PathRegistry = field(default_factory=dict)
    created: list[_CreatedEntry] | None = None

    @classmethod
    def begin(cls, output_root: Path, *, track_rollback: bool) -> _CreateContext:
        """
        Create a generation context.

        When track_rollback is True, initialise the created list; subsequent
        calls record every newly created directory and file for rollback on
        error.
        """
        return cls(
            output_root=output_root,
            created=[] if track_rollback else None,
        )


def sanitize_filename(name: str, flatten_slashes: bool = True) -> str:
    """
    Replace illegal characters in a filename with underscores, preserving intent where possible.

    Some Windows reserved names (CON, PRN, COM1, ...) cannot be used as
    filenames directly; this function prefixes them with an underscore. Tree
    symbols and control characters are cleaned up too.

    MING added this to catch users who write emoji or CJK punctuation as
    filenames in hand-written trees.

    With flatten_slashes=False, a path like foo/bar is split into segments,
    each sanitised, then rejoined (used with --allow-nested-names).
    """
    name = unicodedata.normalize('NFC', name)
    if not flatten_slashes:
        name = name.replace('\\', '/')
        parts = name.split('/')
        cleaned = [sanitize_filename(part, flatten_slashes=True) for part in parts if part]
        return '/'.join(cleaned) if cleaned else '_'
    illegal_chars = r'[\\/:*?"<>|\t]'
    safe = re.sub(illegal_chars, '_', name)
    safe = _TREE_DECOR_CHARS.sub('_', safe)
    safe = re.sub(r'[\x00-\x1f]', '_', safe)
    safe = safe.strip()
    if sys.platform.startswith('win'):
        safe = safe.rstrip('. ')
    if not safe:
        safe = '_'
    stem = safe.split('.')[0].upper()
    if stem in _WIN_RESERVED:
        safe = f'_{safe}'
    return safe


def parse_nested_name(name: str) -> list[str] | None:
    """
    Parse a nested name (e.g. foo/bar/baz) and return its path segments.

    Returns None if the name is an absolute path (starts with / or a Windows
    drive letter) or contains .., meaning it is unsafe to expand.
    """
    normalized = name.replace('\\', '/')
    if normalized.startswith('/'):
        return None
    if len(normalized) >= 2 and normalized[1] == ':':
        return None
    parts = [p for p in normalized.split('/') if p and p != '.']
    if not parts or '..' in parts:
        return None
    return parts


def _path_str(path: Path) -> str:
    """
    Convert a Path to a string, preferring resolve() and falling back to absolute().

    MING wraps this in try/except because over-long or unusual Windows paths
    may raise OSError on resolve(); absolute() at least lets processing
    continue.
    """
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def _rel_path_key(full_path: Path, output_root: Path) -> str:
    """
    Compute a path's path relative to the output root, used as the registry key.

    If the path is not under the output root (which should not happen), fall
    back to the full path so no registry entry is lost.
    """
    try:
        return full_path.relative_to(output_root).as_posix()
    except ValueError:
        return full_path.as_posix()


def _register_path(
    rel_key: str,
    kind: _PathKind,
    registry: _PathRegistry,
    emit: Callable[[str], None],
    fail_on_conflict: bool,
    *,
    dry_run: bool = False,
) -> bool:
    """
    Register a path in the registry and check for conflicts.

    Conflicts include:
    - Same name but different type (file vs directory).
    - Creating a child path under a file.
    - Creating a same-named file under a directory.

    On conflict with fail_on_conflict set, raise PathConflictError; otherwise
    warn and return False to indicate the node should be skipped.
    """
    if not rel_key:
        return True

    def abort() -> None:
        """Raise PathConflictError in strict mode; do not raise in dry-run."""
        if fail_on_conflict and not dry_run:
            raise PathConflictError(rel_key)

    if rel_key in registry:
        existing = registry[rel_key]
        if existing == kind:
            emit(get_string("core_warn_duplicate_path", name=rel_key))
            abort()
            return not fail_on_conflict
        emit(get_string(
            "core_warn_path_type_conflict",
            path=rel_key,
            existing_kind=_kind_label(existing),
            new_kind=_kind_label(kind),
        ))
        abort()
        return False

    prefix = rel_key + '/'
    for other, other_kind in registry.items():
        if other_kind == 'file' and rel_key.startswith(other + '/'):
            emit(get_string("core_warn_path_under_file", path=rel_key, file=other))
            abort()
            return False
        if kind == 'file' and other.startswith(prefix):
            emit(get_string("core_warn_path_under_file", path=other, file=rel_key))
            abort()
            return False

    registry[rel_key] = kind
    return True


def _existing_disk_kind(path: Path) -> _PathKind | None:
    """
    Check what kind of entry already exists on disk at a path.

    Returns 'file', 'dir' or None (does not exist or access failed).
    """
    prepared = _prepare_windows_path(path)
    try:
        if prepared.is_dir():
            return 'dir'
        if prepared.is_file():
            return 'file'
    except OSError:
        pass
    return None


def _check_disk_conflict(
    path: Path,
    expected_kind: _PathKind,
    rel_key: str,
    emit: Callable[[str], None],
    fail_on_conflict: bool,
    *,
    dry_run: bool = False,
) -> bool:
    """
    Check whether the existing on-disk type conflicts with the type we want to create.

    If a different-typed entry already exists on disk (e.g. a file where we
    want a directory), warn. With fail_on_conflict set, raise.
    """
    existing = _existing_disk_kind(path)
    if existing is None or existing == expected_kind:
        return True
    emit(get_string(
        "core_warn_disk_type_conflict",
        path=rel_key,
        existing_kind=_kind_label(existing),
        new_kind=_kind_label(expected_kind),
    ))
    if fail_on_conflict and not dry_run:
        raise PathConflictError(rel_key)
    return False


def _warn_if_path_long(path: Path, emit: Callable[[str], None]) -> None:
    """
    On Windows, warn when a path approaches the 260-character limit.

    The threshold is 260 - 12 = 248, a buffer MING reserved: some tools append
    extensions or escape characters later, so an early warning is friendlier
    than an error at the actual limit.
    """
    if not sys.platform.startswith('win'):
        return
    text = _path_str(path)
    if len(text) >= _WIN_PATH_WARN_THRESHOLD:
        emit(get_string("core_warn_path_too_long", path=text, length=len(text)))


def _prepare_windows_path(path: Path) -> Path:
    """
    Handle over-long Windows paths.

    If the path length is >= 260 and it has no \\\\?\\ prefix, add one.
    UNC paths use the \\\\?\\UNC\\ form.
    """
    if not sys.platform.startswith('win'):
        return path
    text = _path_str(path)
    if len(text) < _WIN_MAX_PATH or text.startswith('\\\\?\\'):
        return path
    if text.startswith('\\\\'):
        return Path('\\\\?\\UNC\\' + text[2:])
    return Path('\\\\?\\' + os.path.abspath(text))


def _track_new_dirs(path: Path, created: list[_CreatedEntry] | None) -> None:
    """
    Record the parent directories that did not exist before creating a directory, for rollback.

    Walks upward from the target until it hits an existing directory or the
    root, then appends the new chain to `created` from shallow to deep.
    """
    if created is None:
        return
    prepared = _prepare_windows_path(path)
    new_dirs: list[Path] = []
    p = prepared
    while not p.exists() and p != p.parent:
        new_dirs.append(p)
        p = p.parent
    for p in reversed(new_dirs):
        created.append(('dir', p))


def _mkdir(path: Path, dry_run: bool, created: list[_CreatedEntry] | None = None) -> Path:
    """
    Create a directory (supports dry-run and rollback tracking).

    In dry-run mode, returns the prepared path without touching disk. In real
    mode, records the newly created parents first so rollback can delete them
    in reverse order.
    """
    prepared = _prepare_windows_path(path)
    if not dry_run:
        if not prepared.exists():
            _track_new_dirs(prepared, created)
        prepared.mkdir(parents=True, exist_ok=True)
    return prepared


def _touch(path: Path, dry_run: bool, created: list[_CreatedEntry] | None = None) -> Path:
    """
    Create an empty file (supports dry-run and rollback tracking).

    In real mode, ensures the parent directory exists, then records the file
    in the created list. Note: an already-existing file is not appended, so
    rollback does not delete pre-existing files.
    """
    prepared = _prepare_windows_path(path)
    if not dry_run:
        _mkdir(prepared.parent, dry_run, created)
        existed = prepared.exists()
        prepared.touch(exist_ok=True)
        if created is not None and not existed:
            created.append(('file', prepared))
    return prepared


def _rollback_created(created: list[_CreatedEntry]) -> int:
    """
    Roll back created files and directories.

    Deletes in reverse order and returns the number actually removed. Failed
    deletions are ignored (the rollback may already be partial).
    """
    rolled = 0
    for kind, path in reversed(created):
        try:
            prepared = _prepare_windows_path(path)
            if kind == 'file' and prepared.is_file():
                prepared.unlink(missing_ok=True)
                rolled += 1
            elif kind == 'dir' and prepared.is_dir():
                prepared.rmdir()
                rolled += 1
        except OSError:
            pass
    return rolled


def create_from_tree(
    tree: list[dict],
    root_path: Path,
    dry_run: bool = False,
    warnings: list[str] | None = None,
    allow_nested_names: bool = False,
    fail_on_conflict: bool = False,
    fail_on_duplicate: bool | None = None,
    rollback_on_error: bool = False,
    _ctx: _CreateContext | None = None,
) -> None:
    """
    Create directories and files on disk from the parsed tree.

    This is the core function of the generator module. It is fairly complex
    and does the following:

    1. In strict or rollback mode, set up a context with a created list so a
       later error can roll things back.
    2. Walk each node, skipping virtual nodes (they are not created).
    3. Parse nested path names (when allow_nested_names is on).
    4. Sanitise illegal characters out of filenames.
    5. Register the path and check for conflicts.
    6. Check the disk for a same-named entry of a different type.
    7. Create the directory or file.
    8. Recurse into children.

    MING deliberately put the rollback logic at the outermost layer so that no
    matter which step fails, the scene can be cleaned up and no half-finished
    tree is left behind.
    """
    strict = fail_on_conflict or bool(fail_on_duplicate)

    if _ctx is None:
        track_rollback = not dry_run and (strict or rollback_on_error)
        if track_rollback:
            ctx = _CreateContext.begin(root_path, track_rollback=True)
            try:
                create_from_tree(
                    tree, root_path, dry_run, warnings, allow_nested_names,
                    fail_on_conflict=strict, rollback_on_error=False, _ctx=ctx,
                )
            except PathConflictError as e:
                rolled = _rollback_created(ctx.created or [])
                raise PathConflictError(e.name, rolled=rolled) from e
            except Exception:
                _rollback_created(ctx.created or [])
                raise
            return
        _ctx = _CreateContext.begin(root_path, track_rollback=False)

    output_root = _ctx.output_root
    path_registry = _ctx.path_registry
    created = _ctx.created

    def _emit(message: str) -> None:
        """Append a message to the warnings list, or print to stdout when there is no warnings list."""
        if warnings is not None:
            warnings.append(message)
        else:
            print(message)

    def _register_dir_path(full_path: Path) -> bool:
        """Register a directory path in the registry; return whether creation may continue."""
        rel_key = _rel_path_key(full_path, output_root)
        return _register_path(
            rel_key, 'dir', path_registry, _emit, strict, dry_run=dry_run,
        )

    def _ensure_disk_compatible(full_path: Path, kind: _PathKind) -> bool:
        """Check whether the on-disk type is compatible with the type to create; return False if not."""
        rel_key = _rel_path_key(full_path, output_root)
        return _check_disk_conflict(
            full_path, kind, rel_key, _emit, strict, dry_run=dry_run,
        )

    def _resolve_target(node: dict) -> tuple[Path, str, bool, bool]:
        """
        Decide the parent directory and final name for a node.

        When allow_nested_names is on and the name contains a slash, split the
        path, create each intermediate parent, and return the deepest parent
        plus the final segment.

        Returns skip_node=True when the name is illegal (absolute path or
        contains ..).
        """
        raw_name = node['name']
        if allow_nested_names and ('/' in raw_name or '\\' in raw_name):
            nested_parts = parse_nested_name(raw_name)
            if nested_parts is None:
                _emit(get_string("core_warn_nested_rejected", name=raw_name))
            else:
                parent = root_path
                for part in nested_parts[:-1]:
                    segment = sanitize_filename(part)
                    parent = parent / segment
                    _warn_if_path_long(parent, _emit)
                    if not _register_dir_path(parent):
                        return parent, '', False, True
                    if not _ensure_disk_compatible(parent, 'dir'):
                        return parent, '', False, True
                    _mkdir(parent, dry_run, created)
                final = sanitize_filename(nested_parts[-1])
                return parent, final, True, False

        final = sanitize_filename(raw_name)
        return root_path, final, False, False

    def _recurse(children: list[dict], new_root: Path) -> None:
        """Recurse into children, passing new_root as the new output root to create_from_tree."""
        create_from_tree(
            children, new_root, dry_run, warnings, allow_nested_names,
            fail_on_conflict=strict, _ctx=_ctx,
        )

    for node in tree:
        if node['name'] in TRANSPARENT_NODE_NAMES:
            _recurse(node.get('children', []), root_path)
            continue

        parent_path, final_name, used_nested, skip_node = _resolve_target(node)
        if skip_node:
            _emit(get_string("core_warn_skip_subtree", name=node['name']))
            continue

        full_path = parent_path / final_name
        rel_key = _rel_path_key(full_path, output_root)
        node_kind: _PathKind = 'dir' if node.get('is_dir', False) else 'file'
        if not _register_path(
            rel_key, node_kind, path_registry, _emit, strict, dry_run=dry_run,
        ):
            if node.get('children'):
                _emit(get_string("core_warn_skip_subtree", name=node['name']))
            continue

        if not used_nested and final_name != node['name']:
            _emit(get_string("core_warn_name_clean", old=node['name'], new=final_name))

        _warn_if_path_long(full_path, _emit)

        if node.get('is_dir', False):
            if not _ensure_disk_compatible(full_path, 'dir'):
                if node.get('children'):
                    _emit(get_string("core_warn_skip_subtree", name=node['name']))
                continue
            _mkdir(full_path, dry_run, created)
            _recurse(node.get('children', []), full_path)
        else:
            if not _ensure_disk_compatible(full_path, 'file'):
                if node.get('children'):
                    _emit(get_string("core_warn_skip_subtree", name=node['name']))
                continue
            _touch(full_path, dry_run, created)
            if node.get('children'):
                _recurse(node.get('children', []), full_path)


def iter_nodes(tree: list[dict]) -> Iterator[dict]:
    """
    Iterate every node in the tree, skipping virtual nodes (<auto>, <virtual>, .).

    Used to count "nodes actually to be created", or for any traversal that
    needs to ignore virtual nodes.
    """
    for node in tree:
        if node['name'] not in TRANSPARENT_NODE_NAMES:
            yield node
        yield from iter_nodes(node.get('children', []))

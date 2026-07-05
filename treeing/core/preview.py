"""
treeing/core/preview.py

Defines preview-label formatting and ASCII tree rendering.
Provides `format_preview_label` and `render_text_tree`, shared by the GUI
Treeview and the CLI `--format tree` output, so both displays stay in sync.
"""

from __future__ import annotations

from ..config import get_string
from .constants import DOT_ROOT, VIRTUAL_AUTO, VIRTUAL_NODE_NAMES
from .generator import parse_nested_name, sanitize_filename


def _disk_label(name: str, is_dir: bool, *, allow_nested: bool) -> str:
    """
    Turn an on-disk name into the form shown in the preview.

    When `--allow-nested-names` is on, a nested path like `foo/bar` is split,
    each segment sanitised, then rejoined; otherwise the whole thing is
    treated as one name.

    If the name was changed (e.g. illegal characters replaced), the original
    is appended in parentheses so the user can see "I changed this".
    """
    raw = name.rstrip('/')
    trailing_slash = name.endswith('/') or is_dir
    if allow_nested and ('/' in raw or '\\' in raw):
        parts = parse_nested_name(raw)
        if parts:
            label = '/'.join(sanitize_filename(part) for part in parts)
        else:
            label = sanitize_filename(raw)
    else:
        label = sanitize_filename(raw)
    if trailing_slash:
        label += '/'
    if label != name and not (name.endswith('/') and label == name.rstrip('/') + '/'):
        return f"{label} ({name})"
    return label


def format_preview_label(node: dict, *, allow_nested: bool) -> str:
    """
    Return the text a node should show in the preview.

    Virtual nodes (<auto>, <virtual>) and the dot root (.) get special
    treatment: they are prefixed to tell the user these were inserted by the
    program, not written by them.

    Ordinary nodes go through _disk_label: sanitised and/or expanded as needed.
    """
    name = node['name']
    is_virtual = name in VIRTUAL_NODE_NAMES
    is_dot_root = name == DOT_ROOT
    is_dir = node.get('is_dir', False)

    if is_virtual:
        if name == VIRTUAL_AUTO:
            display_name = get_string('preview_virtual_auto_display')
        else:
            display_name = get_string('preview_virtual_root_display')
    elif is_dot_root:
        display_name = get_string('preview_dot_root_display')
    else:
        display_name = _disk_label(name, is_dir, allow_nested=allow_nested)

    if is_virtual or is_dot_root:
        display_name = get_string('preview_virtual_prefix') + display_name
    return display_name


def render_text_tree(tree: list[dict], *, allow_nested: bool) -> list[str]:
    """
    Render the parsed tree into ASCII text lines for the CLI `--format tree` output.

    Root nodes carry no branch prefix; children use ├── / └── and │   as the
    level connector. This matches the `tree` command output, which users are
    used to.

    MING deliberately shares format_preview_label with the GUI Treeview logic,
    so a change in one place updates both and they never drift apart.
    """
    lines: list[str] = []

    def walk_children(nodes: list[dict], prefix: str) -> None:
        for i, node in enumerate(nodes):
            is_last = i == len(nodes) - 1
            branch = '└── ' if is_last else '├── '
            contin = '    ' if is_last else '│   '
            lines.append(prefix + branch + format_preview_label(node, allow_nested=allow_nested))
            walk_children(node.get('children', []), prefix + contin)

    for node in tree:
        lines.append(format_preview_label(node, allow_nested=allow_nested))
        walk_children(node.get('children', []), '')
    return lines

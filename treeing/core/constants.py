"""
treeing/core/constants.py

Defines the special node-name constants used during parsing and generation.
These names mark virtual nodes (<auto>, <virtual>) and the dot root (.),
and need special handling in parsing, preview and generation to avoid
creating or displaying them by mistake.
"""

DOT_ROOT = '.'
VIRTUAL_AUTO = '<auto>'
VIRTUAL_ROOT = '<virtual>'

# Names rendered with the "virtual node" style in the preview and GUI.
VIRTUAL_NODE_NAMES = frozenset({VIRTUAL_AUTO, VIRTUAL_ROOT})

# Names skipped (not actually created) during generation.
# MING includes DOT_ROOT here as well, because '.' only means "the current
# directory" and is not a real folder to create.
TRANSPARENT_NODE_NAMES = frozenset({VIRTUAL_AUTO, VIRTUAL_ROOT, DOT_ROOT})

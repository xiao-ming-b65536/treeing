"""
treeing/core

Core parsing and generation engine.
Provides ASCII/Unicode tree-text parsing (parser), filesystem generation (generator), preview rendering (preview) and constants (constants), shared by the CLI and GUI.
"""

from .constants import DOT_ROOT  # noqa: F401
from .generator import (  # noqa: F401
    DuplicateNameError,
    PathConflictError,
    create_from_tree,
    iter_nodes,
)
from .parser import build_tree  # noqa: F401

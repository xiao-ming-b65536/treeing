"""treeing/gui/preview.py

Re-exports the node display-name formatter used by the GUI preview pane.
Directly reuses core.preview.format_preview_label.
"""

from ..core.preview import format_preview_label

__all__ = ['format_preview_label']

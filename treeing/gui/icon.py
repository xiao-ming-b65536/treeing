"""
treeing/gui/icon.py

Defines the window-icon logic.
Supports Windows (.ico), macOS (.icns) and a PNG fallback.
"""

import sys
import tkinter as tk

from ..config import _resource_dir


def set_window_icon(root: tk.Misc) -> None:
    """
    Set the window and (macOS) Dock icon.

    Tk cannot use an emoji string directly; a resource file must be loaded.
    """
    assets = _resource_dir() / "assets"

    if sys.platform == "darwin":
        icns = assets / "icon.icns"
        if icns.is_file():
            try:
                root.iconbitmap(str(icns))
                return
            except tk.TclError:
                pass

    if sys.platform.startswith("win"):
        ico = assets / "icon.ico"
        if ico.is_file():
            try:
                root.iconbitmap(str(ico))
                return
            except tk.TclError:
                pass

    png = assets / "icon.png"
    if not png.is_file():
        return
    try:
        img = tk.PhotoImage(master=root, file=str(png))
    except (tk.TclError, RuntimeError):
        return
    root.iconphoto(True, img)
    root._treeing_icon = img  # keep a reference so it is not garbage-collected


def apply_window_icon(widget: tk.Misc, *, icon_source: tk.Misc | None = None) -> None:
    """
    Give a Toplevel sub-window a title-bar icon matching the main window.

    Reuses the PhotoImage already loaded on icon_source or a parent window to
    avoid reloading; falls back to loading from the resource directory.
    """
    if icon_source is not None and getattr(icon_source, '_treeing_icon', None) is not None:
        widget.iconphoto(True, icon_source._treeing_icon)
        return

    candidate = icon_source or widget
    while candidate is not None:
        if getattr(candidate, '_treeing_icon', None) is not None:
            widget.iconphoto(True, candidate._treeing_icon)
            return
        candidate = getattr(candidate, 'master', None)

    set_window_icon(widget)

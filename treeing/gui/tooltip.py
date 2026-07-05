"""
treeing/gui/tooltip.py

Defines the hover-tooltip component.
Supports showing explanatory text on Labels, buttons and grouped checkboxes.
"""

import tkinter as tk
from typing import Literal

from ..config import get_string

_DEFAULT_WRAP = 420
_WINDOW_MARGIN = 8
_DEFAULT_H_OFFSET = 16
_RIGHT_HALF_INSET = 8
_TOOLTIP_OFFSET = 4
_TooltipPosition = Literal['below', 'above']


class ToolTip:
    """
    A tooltip component that shows explanatory text on hover.
    Supports custom position (below/above), wrap width and a root window.

    MING changed the Toplevel to "lazy-create + reuse": each ToolTip instance
    holds at most one Toplevel, deiconified on hover and withdrawn on leave,
    instead of creating and destroying one each time. This works around
    macOS-arm, where repeatedly creating/destroying override-redirect windows
    leaves white rectangles (ghost frames) because WindowServer cannot clear
    them in time.
    """

    def __init__(
        self,
        widget,
        text: str,
        *,
        root: tk.Misc | None = None,
        wraplength: int = _DEFAULT_WRAP,
        position: _TooltipPosition = 'below',
    ) -> None:
        """
        Initialise the tooltip and bind the widget's Enter/Leave events.

        `root` is used to compute the tooltip position; when omitted, the
        top-level window holding the widget is used. No window is created
        here; the real creation happens on first _show.
        """
        self.widget = widget
        self.text = text
        self.root = root
        self.wraplength = wraplength
        self.position = position
        self.tip_window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        widget.bind('<Enter>', self._show, add='+')
        widget.bind('<Leave>', self._hide, add='+')

    def _ensure_window(self, root: tk.Misc) -> tk.Toplevel:
        """
        Lazily create and reuse a single Toplevel window.

        On first call, creates the Toplevel, sets it topmost, and packs a
        Label inside; later calls return the existing window. The window
        persists; _hide only withdraws it (no destroy), avoiding the ghost
        frames caused by repeated create/destroy on macOS-arm.
        """
        if self.tip_window is not None:
            return self.tip_window

        tw = tk.Toplevel(root)
        tw.withdraw()
        tw.wm_overrideredirect(True)
        # Topmost keeps the tooltip above the main window; some platforms /
        # window managers do not support this attribute, so failures are
        # silently ignored and do not affect display.
        try:
            tw.wm_attributes('-topmost', True)
        except tk.TclError:
            pass
        self._label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background='#ffffe0',
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=self.wraplength,
        )
        self._label.pack()
        self.tip_window = tw
        return tw

    def _place_tooltip(self, root: tk.Misc, tw: tk.Toplevel) -> None:
        """
        Compute the tooltip's screen coordinates and move the window.

        Horizontal: if the widget is to the right of the centre line, right-align
        with a left inset; otherwise left-align; then clamp within the root
        window's left/right edges.
        Vertical: above or below per `position`; if the target side does not fit
        (above the top or below the bottom of the screen), flip to the other
        side so the tooltip never leaves the visible area.

        Height prefers winfo_reqheight because, while the window is withdrawn,
        winfo_height may return 1 on macOS-arm Tk (not actually mapped), which
        would make an "above" tooltip stick to the widget top and overflow
        downward over the button.
        """
        root.update_idletasks()
        tw.update_idletasks()

        root_x = root.winfo_rootx()
        root_w = root.winfo_width()
        root_right = root_x + root_w

        wx = self.widget.winfo_rootx()
        wy = self.widget.winfo_rooty()
        ww = max(self.widget.winfo_width(), 1)
        wh = max(self.widget.winfo_height(), 1)

        tip_w = max(_to_int(tw.winfo_reqwidth(), 0), _to_int(tw.winfo_width(), 0), 1)
        tip_h = max(_to_int(tw.winfo_reqheight(), 0), _to_int(tw.winfo_height(), 0), 1)

        window_cx = root_x + root_w // 2
        widget_cx = wx + ww // 2

        if widget_cx >= window_cx:
            x = wx + ww - tip_w - _RIGHT_HALF_INSET
        else:
            x = wx + _DEFAULT_H_OFFSET

        x = max(root_x + _WINDOW_MARGIN, min(x, root_right - tip_w - _WINDOW_MARGIN))

        y_above = wy - tip_h - _TOOLTIP_OFFSET
        y_below = wy + wh + _TOOLTIP_OFFSET

        if self.position == 'above':
            y = y_above
            if y < _WINDOW_MARGIN:
                y = y_below
        else:
            y = y_below
            screen_h = _safe_screen_height(root)
            if screen_h and y + tip_h > screen_h - _WINDOW_MARGIN:
                y = y_above

        tw.wm_geometry(f'+{x}+{y}')

    def _show(self, _event=None) -> None:
        """
        Show the tooltip when the mouse enters the widget.

        Reuses the existing window; refreshes the Label if the text changed
        (may happen when one instance is bound to multiple widgets). Positions
        before deiconify, so it does not appear at the default position and
        then jump (which causes flicker / ghost frames).
        """
        if not self.text:
            return
        root = self.root or self.widget.winfo_toplevel()
        tw = self._ensure_window(root)
        if self._label is not None:
            self._label.configure(text=self.text)
        self._place_tooltip(root, tw)
        try:
            tw.deiconify()
        except tk.TclError:
            # Silently skip this show when the parent window has been destroyed.
            self.tip_window = None
            self._label = None

    def _hide(self, _event=None) -> None:
        """
        Hide the tooltip when the mouse leaves the widget.

        Withdraw only, never destroy: the window stays for the next hover,
        which from the source eliminates the ghost frames caused by repeatedly
        destroying override-redirect windows on macOS-arm.
        """
        if self.tip_window is not None:
            try:
                self.tip_window.withdraw()
            except tk.TclError:
                self.tip_window = None
                self._label = None


def _to_int(value, fallback: int) -> int:
    """
    Safely convert a Tk geometry value to int, returning fallback on failure.

    Under mocks or abnormal Tk states, winfo_* may return a non-int (MagicMock,
    empty string, etc.); int() would raise TypeError. This wrapper guards the
    coordinate calculations so they never abort.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_screen_height(root: tk.Misc) -> int | None:
    """
    Return the screen height of the root window's screen, or None on failure / non-int.

    Tk may raise TclError for winfo_screenheight in some abnormal states, and
    under mocks the return value is not an int; callers skip the below-flip
    check in that case.
    """
    try:
        value = root.winfo_screenheight()
    except tk.TclError:
        return None
    if isinstance(value, int):
        return value
    return None


def bind_tooltip(
    widget,
    string_key: str,
    *,
    root: tk.Misc | None = None,
    position: _TooltipPosition = 'below',
    **fmt,
) -> ToolTip:
    """Bind a tooltip with text from strings.json to a widget."""
    return ToolTip(
        widget, get_string(string_key, **fmt), root=root, position=position,
    )

"""
treeing/gui/app.py

Defines the GUI main window and interaction logic.
Handles input editing, tree preview, generation confirmation, warning
display, drag-and-drop import, and settings persistence.
"""

import sys
import tkinter as tk
from contextlib import contextmanager
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .. import __version__
from ..config import get_string, get_ui_string
from ..core.constants import DOT_ROOT, VIRTUAL_NODE_NAMES
from ..core.generator import create_from_tree, iter_nodes
from ..core.parser import build_tree
from ..path_checks import verify_output_is_directory, verify_output_writable
from .dnd import bind_file_drop
from .icon import apply_window_icon, set_window_icon
from .preview import format_preview_label
from .settings import (
    get_font_size,
    get_import_encoding,
    get_import_encodings,
    get_last_generate_dir,
    load_settings,
    save_settings,
)
from .tooltip import bind_tooltip

_WARNINGS_DIALOG_LIMIT = 8
_DEFAULT_FONT_FAMILY = 'Courier'
_TREE_TOGGLE_PX = 22
_TREE_TOGGLE_ICON_PX = 10
_PANE_MINSIZE = 220
_DEFAULT_SASH_RATIO = 0.5
_DEFAULT_WIDTH = 950
_DEFAULT_HEIGHT = 650
_MIN_WIDTH = 720
_MIN_HEIGHT = 520
_SCREEN_MARGIN = 16
# Vertically around 2/5 of the available height (still horizontally centred),
# to reduce obstruction by the taskbar / Dock at the bottom.
_VERTICAL_ALIGN_NUM = 2
_VERTICAL_ALIGN_DEN = 5


def compute_initial_window_geometry(
    *,
    screen_width: int,
    screen_height: int,
    default_width: int = _DEFAULT_WIDTH,
    default_height: int = _DEFAULT_HEIGHT,
    min_width: int = _MIN_WIDTH,
    min_height: int = _MIN_HEIGHT,
    margin: int = _SCREEN_MARGIN,
) -> str:
    """
    Compute the window geometry for first display.

    Centred horizontally; vertically around 2/5 of the available height (to
    reduce obstruction by the taskbar / Dock at the bottom). Width and height
    are clamped to the available screen area and never exceed it.
    """
    max_w = max(min_width, screen_width - margin * 2)
    max_h = max(min_height, screen_height - margin * 2)
    w = max(min_width, min(default_width, max_w))
    h = max(min_height, min(default_height, max_h))
    x = max(0, (screen_width - w) // 2)
    free_h = screen_height - h
    if free_h <= 0:
        y = 0
    else:
        y = max(margin, free_h * _VERTICAL_ALIGN_NUM // _VERTICAL_ALIGN_DEN)
        y = min(y, free_h)
    return f'{w}x{h}+{x}+{y}'


_ABOUT_DIALOG_WIDTH = 520
_ABOUT_DIALOG_HEIGHT = 400
_WARNINGS_DIALOG_WIDTH = 640
_WARNINGS_DIALOG_HEIGHT = 360


def center_toplevel_over_parent(
    parent: tk.Misc,
    win: tk.Misc,
    *,
    width: int,
    height: int,
) -> None:
    """Centre a Toplevel inside the parent window's client area."""
    parent.update_idletasks()
    win.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + max(0, (pw - width) // 2)
    y = py + max(0, (ph - height) // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')


def create_dialog_toplevel(
    parent: tk.Misc,
    *,
    title: str,
    icon_source: tk.Misc | None = None,
    minsize: tuple[int, int] | None = None,
) -> tk.Toplevel:
    """Create a hidden dialogue first, to avoid it flashing in the top-left before being moved."""
    win = tk.Toplevel(parent)
    win.withdraw()
    win.title(title)
    win.transient(parent)
    if minsize is not None:
        win.minsize(*minsize)
    if icon_source is not None:
        apply_window_icon(win, icon_source=icon_source)
    return win


def reveal_centered_toplevel(
    parent: tk.Misc,
    win: tk.Misc,
    *,
    width: int,
    height: int,
) -> None:
    """Centre the dialogue over the parent before showing it, then grab focus modally."""
    center_toplevel_over_parent(parent, win, width=width, height=height)
    win.deiconify()
    win.lift(parent)
    win.grab_set()
    win.focus_force()


def _tree_toggle_icon_font() -> tuple[str, int]:
    """
    Return the icon font used by the expand/collapse button.

    Symbol-font support varies by platform, so MING picks a common font per
    platform to make sure ▼/▶ render.
    """
    if sys.platform.startswith('win'):
        return ('Segoe UI Symbol', _TREE_TOGGLE_ICON_PX)
    if sys.platform == 'darwin':
        return ('Apple Symbols', _TREE_TOGGLE_ICON_PX + 1)
    return ('DejaVu Sans', _TREE_TOGGLE_ICON_PX)


class TreeingApp:
    """
    Main GUI application class.

    Handles window layout, widget binding, the parse/generate flow,
    drag-and-drop import, and settings persistence. MING split window
    initialisation into __init__, create_widgets and _present_window so the
    layout is ready before display, avoiding the window jumping from its
    default size to the target size.
    """

    def __init__(self, root, *, show: bool = True):
        """
        Initialise the app: load settings, create widgets, bind events.

        With show=False (used in tests) the window is not actually shown.
        """
        self.root = root
        if show:
            root.withdraw()

        self.root.title(get_string("app_title"))
        set_window_icon(self.root)
        self.root.minsize(_MIN_WIDTH, _MIN_HEIGHT)
        self.root.geometry(f'{_DEFAULT_WIDTH}x{_DEFAULT_HEIGHT}')

        self._settings = load_settings()
        self._font_size = get_font_size(self._settings)
        self._last_generate_dir = get_last_generate_dir(self._settings)

        self.current_tree: list = []
        self.warnings: list[str] = []
        self._tooltips: list = []
        self._action_buttons: list[ttk.Button] = []
        self._busy = False
        self._preview_all_expanded = True

        self.create_widgets()
        self._bind_shortcuts()
        self._bind_close_protocol()
        bind_file_drop(self.text_input, self._on_file_dropped)

        if show:
            self._present_window()

    # ------------------------------------------------------------------ UI build

    def _tip(self, widget, string_key: str, *, above: bool = False) -> None:
        """Bind a tooltip to a widget and keep a reference so it is not collected early."""
        self._tooltips.append(
            bind_tooltip(
                widget, string_key, root=self.root,
                position='above' if above else 'below',
            )
        )

    def create_widgets(self):
        """
        Build the main interface layout.

        Two panes (input + preview) on the left and right; below them the
        options bar, action bar and status bar.
        """
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(left_frame, weight=1)
        self._build_input_pane(left_frame)

        right_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(right_frame, weight=1)
        self._build_preview_pane(right_frame)

        self._build_options_bar()
        self._build_action_bar()
        self._build_status_bar()

    def _present_window(self) -> None:
        """
        Show the window only after layout is ready.

        Avoids flashing a small default window at startup.
        """
        self.root.update_idletasks()
        self._balance_main_pane()
        self.root.geometry(compute_initial_window_geometry(
            screen_width=self.root.winfo_screenwidth(),
            screen_height=self.root.winfo_screenheight(),
        ))
        self.root.deiconify()

    def _balance_main_pane(self) -> None:
        """
        At startup, try to split the input and preview panes evenly.

        Stops the Text default column width from pushing the sash too far.
        """
        self.root.update_idletasks()
        total = self.main_pane.winfo_width()
        if total < 2 * _PANE_MINSIZE:
            return
        self.main_pane.sashpos(0, int(total * _DEFAULT_SASH_RATIO))

    def _mono_font(self) -> tuple[str, int]:
        """Return the monospace font for the current font size, used by the input box and warning dialogue."""
        return (_DEFAULT_FONT_FAMILY, self._font_size)

    def _build_input_pane(self, parent: ttk.Frame) -> None:
        """
        Build the left input area: a label plus a horizontally/vertically scrollable Text.
        """
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        input_label = ttk.Label(parent, text=get_string("gui_label_input"))
        input_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self._tip(input_label, "gui_tooltip_input")

        text_frame = ttk.Frame(parent)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        self.text_input = tk.Text(
            text_frame, wrap=tk.NONE, font=self._mono_font(), width=1, height=1,
        )
        text_vsb = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_input.yview)
        text_hsb = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text_input.xview)
        self.text_input.configure(yscrollcommand=text_vsb.set, xscrollcommand=text_hsb.set)
        self.text_input.grid(row=0, column=0, sticky="nsew")
        text_vsb.grid(row=0, column=1, sticky="ns")
        text_hsb.grid(row=1, column=0, sticky="ew")

    def _build_preview_pane(self, parent: ttk.Frame) -> None:
        """
        Build the right preview area: a toolbar (expand/collapse button + label) and a Treeview.
        """
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky='w', pady=(0, 2))

        toggle_wrap = tk.Frame(toolbar, width=_TREE_TOGGLE_PX, height=_TREE_TOGGLE_PX)
        toggle_wrap.pack(side=tk.LEFT, padx=(0, 4))
        toggle_wrap.pack_propagate(False)
        self.tree_toggle_btn = tk.Button(
            toggle_wrap,
            command=self.toggle_tree_expand,
            font=_tree_toggle_icon_font(),
            relief=tk.GROOVE,
            borderwidth=1,
            padx=0,
            pady=0,
            highlightthickness=0,
            cursor='hand2',
        )
        self.tree_toggle_btn.place(
            relx=0.5, rely=0.5, anchor='center',
            width=_TREE_TOGGLE_PX - 2, height=_TREE_TOGGLE_PX - 2,
        )
        self._tip(self.tree_toggle_btn, "gui_tooltip_toggle_tree")
        self._sync_tree_toggle_btn()

        preview_label = ttk.Label(toolbar, text=get_string("gui_label_preview"))
        preview_label.pack(side=tk.LEFT, anchor=tk.W)
        self._tip(preview_label, "gui_tooltip_preview")

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, sticky='nsew')
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree_view = ttk.Treeview(tree_frame)
        tree_vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_view.yview)
        tree_hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree_view.xview)
        self.tree_view.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
        self.tree_view.grid(row=0, column=0, sticky='nsew')
        tree_vsb.grid(row=0, column=1, sticky='ns')
        tree_hsb.grid(row=1, column=0, sticky='ew')

    def _build_options_bar(self) -> None:
        """
        Build the options bar (second-version layout): indent unit, encoding, font size, allow nested, abort on conflict, strict directories, disable auto-repair.
        """
        self.options_frame = ttk.Frame(self.root)
        self.options_frame.pack(fill=tk.X, padx=5, pady=(0, 2))

        row1 = ttk.Frame(self.options_frame)
        row1.pack(fill=tk.X)
        row2 = ttk.Frame(self.options_frame)
        row2.pack(fill=tk.X, pady=(2, 0))

        indent_label = ttk.Label(row1, text=get_string("gui_label_indent_unit"))
        indent_label.pack(side=tk.LEFT, padx=(0, 4))
        self._tip(indent_label, "gui_tooltip_indent_unit", above=True)
        self.indent_unit_var = tk.StringVar(value="")
        indent_entry = ttk.Entry(row1, textvariable=self.indent_unit_var, width=6)
        indent_entry.pack(side=tk.LEFT, padx=(0, 12))

        encoding_label = ttk.Label(row1, text=get_string("gui_label_encoding"))
        encoding_label.pack(side=tk.LEFT, padx=(0, 4))
        self._tip(encoding_label, "gui_tooltip_encoding", above=True)
        self._import_encodings = get_import_encodings(self._settings)
        self.encoding_var = tk.StringVar(value=get_import_encoding(self._settings))
        self.encoding_combo = ttk.Combobox(
            row1,
            textvariable=self.encoding_var,
            values=self._import_encodings,
            width=10,
        )
        self.encoding_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.encoding_combo.bind('<<ComboboxSelected>>', lambda _e: self._on_encoding_changed())
        self.encoding_combo.bind('<FocusOut>', lambda _e: self._on_encoding_changed())

        font_label = ttk.Label(row1, text=get_string("gui_label_font_size"))
        font_label.pack(side=tk.LEFT, padx=(0, 4))
        self._tip(font_label, "gui_tooltip_font_size", above=True)
        self.font_size_var = tk.StringVar(value=str(self._font_size))
        font_spin = ttk.Spinbox(
            row1, from_=8, to=24, width=4, textvariable=self.font_size_var,
            command=self._apply_font_size,
        )
        font_spin.pack(side=tk.LEFT, padx=2)
        font_spin.bind('<Return>', lambda _e: self._apply_font_size())
        font_spin.bind('<FocusOut>', lambda _e: self._apply_font_size())

        self.allow_nested_var = tk.BooleanVar(value=False)
        allow_nested_cb = ttk.Checkbutton(
            row2, text=get_string("gui_label_allow_nested"), variable=self.allow_nested_var,
        )
        allow_nested_cb.pack(side=tk.LEFT, padx=2)
        self._tip(allow_nested_cb, "gui_tooltip_allow_nested", above=True)

        self.fail_on_conflict_var = tk.BooleanVar(value=False)
        fail_on_conflict_cb = ttk.Checkbutton(
            row2, text=get_string("gui_label_fail_on_conflict"), variable=self.fail_on_conflict_var,
        )
        fail_on_conflict_cb.pack(side=tk.LEFT, padx=2)
        self._tip(fail_on_conflict_cb, "gui_tooltip_fail_on_conflict", above=True)

        self.strict_dirs_var = tk.BooleanVar(value=False)
        strict_dirs_cb = ttk.Checkbutton(
            row2, text=get_string("gui_label_strict_dirs"), variable=self.strict_dirs_var,
        )
        strict_dirs_cb.pack(side=tk.LEFT, padx=2)
        self._tip(strict_dirs_cb, "gui_tooltip_strict_dirs", above=True)

        self.no_fix_var = tk.BooleanVar(value=False)
        no_fix_cb = ttk.Checkbutton(
            row2, text=get_string("gui_label_no_fix"), variable=self.no_fix_var,
        )
        no_fix_cb.pack(side=tk.LEFT, padx=2)
        self._tip(no_fix_cb, "gui_tooltip_no_fix", above=True)

    def _build_action_bar(self) -> None:
        """
        Build the action bar (second-version layout): import, clear, parse, generate, view warnings, exit, about.
        """
        self.action_frame = ttk.Frame(self.root)
        self.action_frame.pack(fill=tk.X, padx=5, pady=5)

        import_btn = ttk.Button(self.action_frame, text=get_string("gui_btn_import"), command=self.import_file)
        import_btn.pack(side=tk.LEFT, padx=2)
        self._tip(import_btn, "gui_tooltip_import", above=True)
        self._action_buttons.append(import_btn)

        clear_btn = ttk.Button(self.action_frame, text=get_string("gui_btn_clear"), command=self.clear_input)
        clear_btn.pack(side=tk.LEFT, padx=(2, 8))
        self._tip(clear_btn, "gui_tooltip_clear", above=True)
        self._action_buttons.append(clear_btn)

        parse_btn = ttk.Button(self.action_frame, text=get_string("gui_btn_parse"), command=self.parse_tree)
        parse_btn.pack(side=tk.LEFT, padx=2)
        self._tip(parse_btn, "gui_tooltip_parse", above=True)
        self._action_buttons.append(parse_btn)

        generate_btn = ttk.Button(self.action_frame, text=get_string("gui_btn_generate"), command=self.generate_fs)
        generate_btn.pack(side=tk.LEFT, padx=2)
        self._tip(generate_btn, "gui_tooltip_generate", above=True)
        self._action_buttons.append(generate_btn)

        self.warnings_btn = ttk.Button(
            self.action_frame, text=get_string("gui_btn_view_warnings"),
            command=self.show_all_warnings, state=tk.DISABLED,
        )
        self.warnings_btn.pack(side=tk.LEFT, padx=2)
        self._tip(self.warnings_btn, "gui_tooltip_view_warnings", above=True)

        exit_btn = ttk.Button(self.action_frame, text=get_string("gui_btn_exit"), command=self._on_exit)
        exit_btn.pack(side=tk.RIGHT, padx=2)
        self._tip(exit_btn, "gui_tooltip_exit", above=True)

        about_btn = ttk.Button(self.action_frame, text=get_string("gui_btn_about"), command=self.show_about)
        about_btn.pack(side=tk.RIGHT, padx=2)
        self._tip(about_btn, "gui_tooltip_about", above=True)

    def _build_status_bar(self) -> None:
        """Build the status bar (second-version layout); double-click opens the warning list."""
        self.status_var = tk.StringVar()
        self.status_var.set(get_string("gui_status_ready"))
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(2, 5))
        status_bar.bind('<Double-Button-1>', lambda _e: self.show_all_warnings())

    # ------------------------------------------------------------------ binding & state

    def _bind_shortcuts(self) -> None:
        """Bind common shortcuts: Ctrl+O import, Ctrl+Enter parse, Ctrl+G generate, Ctrl+L clear."""
        self.root.bind('<Control-o>', lambda _e: self.import_file())
        self.root.bind('<Control-O>', lambda _e: self.import_file())
        self.root.bind('<Control-Return>', lambda _e: self.parse_tree())
        self.root.bind('<Control-g>', lambda _e: self.generate_fs())
        self.root.bind('<Control-G>', lambda _e: self.generate_fs())
        self.root.bind('<Control-l>', lambda _e: self.clear_input())
        self.root.bind('<Control-L>', lambda _e: self.clear_input())

    def _bind_close_protocol(self) -> None:
        """Bind the window close protocol; ask first when there is unsaved input."""
        self.root.protocol('WM_DELETE_WINDOW', self._on_exit)

    @contextmanager
    def _busy_guard(self):
        """Context manager: set busy on entry, restore on exit, to prevent re-entry during parse/generate."""
        self._set_busy(True)
        try:
            yield
        finally:
            self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        """Set the busy state, disabling/enabling the action buttons and the warnings button."""
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in self._action_buttons:
            btn.configure(state=state)
        self._update_warnings_button()

    def _update_warnings_button(self) -> None:
        """Update the "view warnings" button state based on the busy state and whether warnings exist."""
        if self._busy:
            self.warnings_btn.configure(state=tk.DISABLED)
        elif self.warnings:
            self.warnings_btn.configure(state=tk.NORMAL)
        else:
            self.warnings_btn.configure(state=tk.DISABLED)

    def _persist_settings(self) -> None:
        """Write the current font size, last generate directory and import encoding back to settings.json."""
        self._settings['font_size'] = self._font_size
        if self._last_generate_dir:
            self._settings['last_generate_dir'] = self._last_generate_dir
        enc = self.encoding_var.get().strip()
        if isinstance(enc, str) and enc:
            self._settings['import_encoding'] = enc
        save_settings(self._settings)

    def _on_encoding_changed(self) -> None:
        """Save the encoding dropdown change immediately, so it persists across launches."""
        enc = self.encoding_var.get().strip()
        if isinstance(enc, str) and enc:
            self._settings['import_encoding'] = enc
            save_settings(self._settings)

    def _read_import_encoding(self) -> str:
        """Read the currently selected import encoding, falling back to utf-8 when empty."""
        return self.encoding_var.get().strip() or 'utf-8'

    def _apply_font_size(self) -> None:
        """Apply the font-size input, update the input box font, and persist."""
        self._font_size = get_font_size({'font_size': self.font_size_var.get()})
        self.font_size_var.set(str(self._font_size))
        self.text_input.configure(font=self._mono_font())
        self._persist_settings()

    def _read_input_text(self) -> str:
        """Read the input box content, stripping trailing newlines."""
        raw = self.text_input.get(1.0, tk.END)
        if raw.endswith('\n'):
            raw = raw[:-1]
        return raw

    def _has_unsaved_input(self) -> bool:
        """Return whether the input box still has unsaved / uncleared text."""
        return bool(self._read_input_text().strip())

    def _on_exit(self) -> None:
        """Check for unsaved input before closing; on confirm, persist settings and exit."""
        if self._has_unsaved_input():
            if not messagebox.askyesno(
                get_string("gui_title_close_confirm"),
                get_string("gui_msg_close_confirm"),
            ):
                return
        self._persist_settings()
        self.root.quit()

    def _on_file_dropped(self, path: str, extra_files: int = 0) -> None:
        """Drag-and-drop import: read the first file's content; ignore the rest with a notice."""
        if self._busy:
            return
        dropped = Path(path)
        if not dropped.is_file():
            return
        try:
            encoding = self._read_import_encoding()
            content = dropped.read_text(encoding=encoding)
        except Exception as e:
            messagebox.showerror(get_string("gui_title_import_error"), str(e))
            return
        self.text_input.delete(1.0, tk.END)
        self.text_input.insert(tk.END, content)
        status = get_string("gui_status_imported", filename=dropped.name)
        if extra_files > 0:
            status += get_string("gui_status_drop_extra_ignored", count=extra_files)
        self.status_var.set(status)
        if messagebox.askyesno(
            get_string("gui_title_import_parse"),
            get_string("gui_msg_import_parse"),
        ):
            self.parse_tree()

    # ------------------------------------------------------------------ file & input

    def import_file(self) -> None:
        """Open a file chooser, read the text file into the input box, and ask whether to parse."""
        if self._busy:
            return
        filetypes = [
            (get_string("gui_filetype_text"), get_string("gui_filetype_text_pattern")),
            (get_string("gui_filetype_all"), get_string("gui_filetype_all_pattern")),
        ]
        file_path = filedialog.askopenfilename(
            title=get_string("gui_file_dialog_title_open"),
            filetypes=filetypes,
        )
        if not file_path:
            return
        try:
            encoding = self._read_import_encoding()
            with open(file_path, encoding=encoding) as f:
                content = f.read()
            self.text_input.delete(1.0, tk.END)
            self.text_input.insert(tk.END, content)
            self.status_var.set(get_string("gui_status_imported", filename=Path(file_path).name))
        except Exception as e:
            messagebox.showerror(get_string("gui_title_import_error"), str(e))
            return

        if messagebox.askyesno(
            get_string("gui_title_import_parse"),
            get_string("gui_msg_import_parse"),
        ):
            self.parse_tree()

    def clear_input(self) -> None:
        """Clear the input box, preview area, current tree and warning state."""
        if self._busy:
            return
        self.text_input.delete(1.0, tk.END)
        self.tree_view.delete(*self.tree_view.get_children())
        self.current_tree = []
        self.warnings = []
        self._update_warnings_button()
        self.status_var.set(get_string("gui_status_cleared"))

    # ------------------------------------------------------------------ parse & preview

    def _build_tree_from_input(self) -> tuple[list, list[str]]:
        """
        Parse the tree from the input box.

        Empty input returns an empty tree and an empty warning list; an empty
        indent-unit field triggers auto-detection.
        """
        raw = self._read_input_text()
        if not raw.strip():
            return [], []
        indent_raw = self.indent_unit_var.get().strip()
        indent_unit = int(indent_raw) if indent_raw.isdigit() and int(indent_raw) > 0 else None
        return build_tree(
            raw.splitlines(),
            auto_fix=not self.no_fix_var.get(),
            indent_unit=indent_unit,
            strict_dirs=self.strict_dirs_var.get(),
        )

    def show_about(self) -> None:
        """Pop up the about dialogue, showing version and project information."""
        win = create_dialog_toplevel(
            self.root,
            title=get_string("gui_title_about"),
            icon_source=self.root,
            minsize=(400, 300),
        )

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('', 10))
        text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        text.insert(tk.END, get_ui_string("gui_msg_about", version=__version__))
        text.configure(state=tk.DISABLED)

        ttk.Button(frame, text=get_string("gui_btn_close"), command=win.destroy).pack()
        reveal_centered_toplevel(
            self.root, win,
            width=_ABOUT_DIALOG_WIDTH, height=_ABOUT_DIALOG_HEIGHT,
        )

    def show_all_warnings(self) -> None:
        """Pop up a dialogue with all current warnings; show a notice when there are none."""
        if not self.warnings:
            messagebox.showinfo(
                get_string("gui_title_warnings"),
                get_string("gui_msg_no_warnings"),
            )
            return
        win = create_dialog_toplevel(
            self.root,
            title=get_string("gui_title_warnings"),
            icon_source=self.root,
            minsize=(480, 280),
        )

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=self._mono_font())
        text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        text.insert(tk.END, '\n'.join(self.warnings))
        text.configure(state=tk.DISABLED)

        ttk.Button(frame, text=get_string("gui_btn_close"), command=win.destroy).pack()
        reveal_centered_toplevel(
            self.root, win,
            width=_WARNINGS_DIALOG_WIDTH, height=_WARNINGS_DIALOG_HEIGHT,
        )

    def _show_warning_dialog(self, title_key: str, msg_key: str, warnings: list[str], **fmt) -> None:
        """Show the first N warnings via messagebox; prompt for the "view all warnings" dialogue for the rest."""
        if not warnings:
            return
        warn_msg = get_string(
            msg_key, count=len(warnings),
            warnings_text='\n'.join(warnings[:_WARNINGS_DIALOG_LIMIT]), **fmt,
        )
        extra = len(warnings) - _WARNINGS_DIALOG_LIMIT
        if extra > 0:
            warn_msg += '\n' + get_string("gui_msg_parse_warning_more", extra=extra)
            warn_msg += '\n' + get_string("gui_msg_view_all_warnings_hint")
        messagebox.showwarning(get_string(title_key), warn_msg)

    def parse_tree(self) -> None:
        """Parse the input box content, refresh the preview tree and warnings button, and pop up warnings as needed."""
        if self._busy:
            return
        with self._busy_guard():
            if not self._read_input_text().strip():
                self.tree_view.delete(*self.tree_view.get_children())
                self.current_tree = []
                self.warnings = []
                self._update_warnings_button()
                messagebox.showinfo(
                    get_string("gui_title_no_input"), get_string("gui_msg_no_input_content"),
                )
                return

            tree, warnings = self._build_tree_from_input()
            self.current_tree = tree
            self.warnings = warnings
            self._update_warnings_button()

            if not tree:
                self.current_tree = []
                self.tree_view.delete(*self.tree_view.get_children())
                messagebox.showinfo(
                    get_string("gui_title_no_input"), get_string("core_warn_empty_input"),
                )
                return

            self._show_warning_dialog("gui_title_parse_warning", "gui_msg_parse_warning", warnings)
            self.display_tree(tree)
            node_count = sum(1 for _ in iter_nodes(tree))
            self.status_var.set(get_string("gui_status_parsed", count=node_count, warnings=len(warnings)))

    def display_tree(self, tree, parent="") -> None:
        """Clear the preview area and refill it from tree, fully expanded by default."""
        self.tree_view.delete(*self.tree_view.get_children())
        self._populate_tree(tree, parent)
        self._preview_all_expanded = True
        self._sync_tree_toggle_btn()

    def _sync_tree_toggle_btn(self) -> None:
        """Icon for the current expand state: ▼ expanded, ▶ collapsed."""
        key = (
            "gui_btn_tree_icon_expanded" if self._preview_all_expanded
            else "gui_btn_tree_icon_collapsed"
        )
        self.tree_toggle_btn.configure(text=get_string(key))

    def toggle_tree_expand(self) -> None:
        """Toggle the preview area between fully expanded and fully collapsed."""
        if self._preview_all_expanded:
            self.collapse_all_tree()
            self._preview_all_expanded = False
        else:
            self.expand_all_tree()
            self._preview_all_expanded = True
        self._sync_tree_toggle_btn()

    def expand_all_tree(self) -> None:
        """Expand every node in the preview tree."""
        def walk(item: str) -> None:
            self.tree_view.item(item, open=True)
            for child in self.tree_view.get_children(item):
                walk(child)
        for item in self.tree_view.get_children():
            walk(item)

    def _populate_tree(self, tree, parent) -> None:
        """Recursively insert nodes into the Treeview; virtual nodes get a grey italic label."""
        if not hasattr(self, '_tag_configured'):
            self.tree_view.tag_configure('virtual', foreground='grey', font=('', 9, 'italic'))
            self._tag_configured = True

        allow_nested = self.allow_nested_var.get()
        for node in tree:
            name = node['name']
            is_virtual = name in VIRTUAL_NODE_NAMES
            display_name = format_preview_label(node, allow_nested=allow_nested)
            item = self.tree_view.insert(parent, 'end', text=display_name, open=True)
            if is_virtual or name == DOT_ROOT:
                self.tree_view.item(item, tags=('virtual',))
            self._populate_tree(node.get('children', []), item)

    def collapse_all_tree(self) -> None:
        """Collapse every node in the preview tree."""
        def walk(item: str) -> None:
            for child in self.tree_view.get_children(item):
                walk(child)
            self.tree_view.item(item, open=False)
        for item in self.tree_view.get_children():
            walk(item)

    # ------------------------------------------------------------------ generate

    def generate_fs(self) -> None:
        """Open a directory chooser, then create directories and files on disk after confirmation."""
        if self._busy:
            return
        tree, parse_warnings = self._build_tree_from_input()
        if not tree:
            if parse_warnings:
                messagebox.showinfo(
                    get_string("gui_title_no_input"), get_string("core_warn_empty_input"),
                )
            else:
                messagebox.showinfo(
                    get_string("gui_title_no_input"), get_string("gui_msg_no_input_content"),
                )
            return

        with self._busy_guard():
            self.current_tree = tree
            self.warnings = parse_warnings
            self._update_warnings_button()
            self.display_tree(tree)

            dialog_kw: dict = {'title': get_string("gui_file_dialog_title_generate")}
            if self._last_generate_dir:
                dialog_kw['initialdir'] = self._last_generate_dir
            target_dir = filedialog.askdirectory(**dialog_kw)
            if not target_dir:
                return

            root_path = Path(target_dir)
            output_err = verify_output_is_directory(root_path)
            if output_err:
                messagebox.showerror(get_string("gui_title_generate_error"), output_err)
                self.status_var.set(get_string("gui_status_gen_failed", error=output_err))
                return

            writable_err = verify_output_writable(root_path)
            if writable_err:
                messagebox.showerror(get_string("gui_title_generate_error"), writable_err)
                self.status_var.set(get_string("gui_status_gen_failed", error=writable_err))
                return

            node_count = sum(1 for _ in iter_nodes(self.current_tree))
            if not messagebox.askyesno(
                get_string("gui_title_generate_confirm"),
                get_string("gui_msg_generate_confirm", path=root_path, count=node_count),
            ):
                return

            try:
                self._last_generate_dir = str(root_path)
                self._persist_settings()

                gen_warnings: list[str] = []
                create_from_tree(
                    self.current_tree,
                    root_path,
                    dry_run=False,
                    warnings=gen_warnings,
                    allow_nested_names=self.allow_nested_var.get(),
                    fail_on_conflict=self.fail_on_conflict_var.get(),
                )
                self.warnings = list(parse_warnings) + gen_warnings
                self._update_warnings_button()

                if gen_warnings:
                    self._show_warning_dialog(
                        "gui_title_gen_warning", "gui_msg_gen_warning", gen_warnings, path=root_path,
                    )
                    summary = gen_warnings[0]
                    if len(gen_warnings) > 1:
                        summary += get_string("gui_msg_parse_warning_more", extra=len(gen_warnings) - 1)
                    self.status_var.set(get_string(
                        "gui_status_generated_with_warnings",
                        path=root_path, count=len(self.warnings), summary=summary,
                    ))
                else:
                    messagebox.showinfo(
                        get_string("gui_title_gen_success"),
                        get_string("gui_msg_gen_success_content", path=root_path),
                    )
                    self.status_var.set(get_string("gui_status_generated", path=root_path))
            except Exception as e:
                messagebox.showerror(get_string("gui_title_generate_error"), str(e))
                self.status_var.set(get_string("gui_status_gen_failed", error=str(e)))

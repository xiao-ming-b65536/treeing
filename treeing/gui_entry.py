"""treeing/gui_entry.py

PyInstaller GUI entry point.
Creates the Tk root and starts TreeingApp, catching ConfigError so the packaged app still exits cleanly.
"""
import sys

from treeing.config import ConfigError, get_ui_string


def run_gui() -> int:
    """
    Create the Tk main window and run TreeingApp.

    If the current environment is missing Tcl/Tk, print an error message and
    return 1, rather than raising an opaque TclError.
    """
    import tkinter as tk

    from treeing.gui.app import TreeingApp

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(get_ui_string('gui_err_tcl_missing'), file=sys.stderr)
        print(f"Underlying error: {exc}", file=sys.stderr)
        return 1

    TreeingApp(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(run_gui())
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

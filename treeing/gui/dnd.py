"""
treeing/gui/dnd.py

Defines the Windows file drag-and-drop binding.
Currently effective on Windows only; on other platforms bind_file_drop is a no-op.
"""

import sys


def bind_file_drop(widget, callback) -> None:
    """
    Bind a file drop event to a Tk widget.

    On drop, calls callback(path: str, extra_files: int). No-op on non-Windows
    platforms.
    """
    if not sys.platform.startswith('win'):
        return
    try:
        _bind_windows_file_drop(widget, callback)
    except (OSError, AttributeError, ValueError):
        pass


def _bind_windows_file_drop(widget, callback) -> None:
    """
    Implement file drop on Windows by subclassing the window procedure.

    Uses the WM_DROPFILES message and the DragQueryFileW API.
    """
    import ctypes
    from ctypes import wintypes

    WM_DROPFILES = 0x0233
    GWL_WNDPROC = -4

    widget.update_idletasks()
    hwnd = widget.winfo_id()

    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32

    WNDPROC = ctypes.WINFUNCTYPE(
        wintypes.LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    if hasattr(user32, 'GetWindowLongPtrW'):
        get_wndproc = user32.GetWindowLongPtrW
        set_wndproc = user32.SetWindowLongPtrW
    else:
        get_wndproc = user32.GetWindowLongW
        set_wndproc = user32.SetWindowLongW

    old_wndproc = get_wndproc(hwnd, GWL_WNDPROC)

    def py_drop_handler(hwnd, msg, wparam, lparam):
        """Handle WM_DROPFILES: extract the dropped file paths and callback with the first one."""
        if msg == WM_DROPFILES:
            count = shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
            paths: list[str] = []
            for i in range(count):
                buf = ctypes.create_unicode_buffer(260)
                needed = shell32.DragQueryFileW(wparam, i, buf, len(buf))
                if needed >= len(buf) - 1:
                    buf = ctypes.create_unicode_buffer(needed + 1)
                    shell32.DragQueryFileW(wparam, i, buf, len(buf))
                paths.append(buf.value)
            shell32.DragFinish(wparam)
            if paths:
                callback(paths[0], max(0, len(paths) - 1))
            return 0
        return user32.CallWindowProcW(old_wndproc, hwnd, msg, wparam, lparam)

    new_wndproc = WNDPROC(py_drop_handler)
    set_wndproc(hwnd, GWL_WNDPROC, new_wndproc)
    shell32.DragAcceptFiles(hwnd, True)

    widget._treeing_drop_old_wndproc = old_wndproc
    widget._treeing_drop_wndproc = new_wndproc
    widget._treeing_drop_hwnd = hwnd
    widget._treeing_drop_user32 = user32
    widget._treeing_drop_shell32 = shell32
    widget._treeing_drop_gwl = GWL_WNDPROC

    def _on_destroy(event) -> None:
        """On window destruction, restore the original WNDPROC and revoke drag-drop to avoid dangling callbacks."""
        w = event.widget
        drop_hwnd = getattr(w, '_treeing_drop_hwnd', None)
        if drop_hwnd is None:
            return
        try:
            drop_user32 = w._treeing_drop_user32
            drop_shell32 = w._treeing_drop_shell32
            if hasattr(drop_user32, 'SetWindowLongPtrW'):
                set_proc = drop_user32.SetWindowLongPtrW
                get_proc = drop_user32.GetWindowLongPtrW
            else:
                set_proc = drop_user32.SetWindowLongW
                get_proc = drop_user32.GetWindowLongW
            current = get_proc(drop_hwnd, w._treeing_drop_gwl)
            if current == w._treeing_drop_wndproc:
                set_proc(drop_hwnd, w._treeing_drop_gwl, w._treeing_drop_old_wndproc)
            drop_shell32.DragAcceptFiles(drop_hwnd, False)
        except (OSError, AttributeError, ValueError):
            pass
        for attr in (
            '_treeing_drop_old_wndproc',
            '_treeing_drop_wndproc',
            '_treeing_drop_hwnd',
            '_treeing_drop_user32',
            '_treeing_drop_shell32',
            '_treeing_drop_gwl',
        ):
            try:
                delattr(w, attr)
            except AttributeError:
                pass

    widget.bind('<Destroy>', _on_destroy, add='+')

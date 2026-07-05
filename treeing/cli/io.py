"""
treeing/cli/io.py

Defines CLI standard-stream configuration and safe writing.
Provides `configure_stdio` (UTF-8 + replace) and the cli_out / cli_warn /
cli_err helpers, so Windows legacy-codepage consoles do not crash on output.
"""

import sys

_configured = False


def configure_stdio() -> None:
    """
    At startup, set stdout/stderr to UTF-8 + replace mode.

    Runs once; later calls return immediately.
    """
    global _configured
    if _configured:
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (OSError, ValueError, AttributeError):
                pass
    _configured = True


def _safe_write(stream, text: str, *, end: str = '\n') -> None:
    """
    Safe write: try a direct write first, then fall back to buffer + replace encoding.
    """
    msg = text + end
    try:
        stream.write(msg)
        stream.flush()
    except UnicodeEncodeError:
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        if hasattr(stream, 'buffer'):
            stream.buffer.write(msg.encode(encoding, errors='replace'))
            stream.buffer.flush()
        else:
            raise


def cli_out(text: str, *, end: str = '\n') -> None:
    """
    Success summaries and [WARN] warnings go to stdout.

    Easier for pipes / agents to parse, and friendlier under PowerShell.
    """
    _safe_write(sys.stdout, text, end=end)


def cli_warn(text: str, *, end: str = '\n') -> None:
    """
    Warning prompts go to stdout (same stream as cli_out).

    MING routes warnings through stdout so agents / scripts get stable
    structured output via a pipe, leaving genuine errors for stderr.
    """
    _safe_write(sys.stdout, text, end=end)


def cli_err(text: str, *, end: str = '\n') -> None:
    """
    Errors and interactive prompts go to stderr ([ERR] and confirm prompts).
    """
    _safe_write(sys.stderr, text, end=end)

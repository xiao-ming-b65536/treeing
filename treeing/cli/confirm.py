"""
treeing/cli/confirm.py

Defines the pre-write confirmation logic: interactive --confirm, headless
--yes, and the TREEING_YES environment variable. Provides
`gate_before_write` as the unified entry point, handling TTY detection,
confirmation prompts and mode resolution.
"""

from __future__ import annotations

import os
import sys

from ..config import get_string
from .io import cli_err, cli_out, cli_warn

ENV_ASSUME_YES = 'TREEING_YES'


def assume_yes_from_env() -> bool:
    """
    Check whether the TREEING_YES environment variable is truthy (1/true/yes/on).

    Used by gate_before_write to auto-confirm in non-interactive or CI
    environments; the check is case-insensitive.
    """
    val = os.environ.get(ENV_ASSUME_YES, '').strip().lower()
    if not val:
        return False
    return val in ('1', 'true', 'yes', 'on')


def is_interactive_tty() -> bool:
    """
    Return whether the current session is an interactive TTY (both stdin and stderr are ttys).

    Only treats the session as interactive when both are ttys; returns False
    under pipes or redirection.
    """
    return bool(sys.stdin.isatty() and sys.stderr.isatty())


def read_yes_no(*, default: bool = False) -> bool:
    """
    Read a y/n answer from the user; the default is controlled by `default`.

    Windows uses msvcrt; Unix uses /dev/tty.
    """
    suffix = '[Y/n] ' if default else '[y/N] '
    cli_err(get_string('cli_confirm_prompt', suffix=suffix), end='')
    if sys.platform == 'win32':
        return _read_yes_no_windows(default=default)
    return _read_yes_no_unix(default=default)


def _read_yes_no_windows(*, default: bool) -> bool:
    """
    Read a single y/n character on Windows (no Enter needed).

    Accepts only y/n; Enter falls back to the default; other keys keep waiting.
    """
    import msvcrt

    while True:
        ch = msvcrt.getwch()
        if ch in '\r\n':
            cli_err('')
            return default
        lower = ch.lower()
        if lower in ('y', 'n'):
            cli_err(ch)
            return lower == 'y'


def _read_yes_no_unix(*, default: bool) -> bool:
    """
    Read a line on Unix (via /dev/tty to avoid pipe interference).

    Returns the default on a blank line or read failure; only the first
    character is consulted.
    """
    try:
        with open('/dev/tty', encoding='utf-8', errors='replace') as tty:
            line = tty.readline()
    except OSError:
        return default
    answer = line.strip().lower()
    if not answer:
        return default
    return answer in ('y', 'yes')


def warn_confirm_ignored_on_dry_run() -> None:
    """
    Warn that --confirm is ignored under --dry-run.

    Because dry-run writes nothing, asking the user to confirm is pointless.
    """
    cli_warn(get_string('cli_confirm_dry_run_ignored'))


def audit_yes_confirmed(*, path: str, node_count: int, quiet: bool) -> None:
    """
    In headless mode (--yes / env), print a confirmation summary.

    Even though the interactive prompt is skipped, the log still shows
    "confirmed: N nodes will be created".
    """
    if quiet:
        return
    cli_out(get_string('cli_confirm_yes_audit', count=node_count, path=path))


def prompt_generate_confirm(
    *,
    path: str,
    node_count: int,
    fail_on_conflict: bool,
    warn_count: int,
) -> bool:
    """
    In interactive mode, print the generation confirmation prompt and read the user's answer.

    Returns True if the user confirms, False if cancelled.
    """
    cli_err(get_string(
        'cli_msg_generate_confirm',
        path=path,
        count=node_count,
        conflict_hint=get_string(
            'cli_confirm_conflict_enabled' if fail_on_conflict
            else 'cli_confirm_conflict_disabled',
        ),
        warn_hint=get_string(
            'cli_confirm_warn_count', count=warn_count,
        ) if warn_count else get_string('cli_confirm_no_warnings'),
    ))
    return read_yes_no(default=False)


def resolve_confirm_mode(args) -> str | None:
    """
    Resolve the confirmation mode from the arguments: yes / env / interactive / None.

    Priority: --yes > TREEING_YES > --confirm.
    """
    if getattr(args, 'yes', False):
        return 'yes'
    if assume_yes_from_env():
        return 'env'
    if getattr(args, 'confirm', False):
        return 'interactive'
    return None


def gate_before_write(
    args,
    *,
    path: str,
    node_count: int,
    fail_on_conflict: bool,
    warn_count: int,
) -> tuple[int | None, str | None]:
    """
    Pre-write confirmation entry point.

    Returns (early_exit_code, confirm_mode). A non-None early_exit_code means
    the run should exit early and skip writing.
    """
    if args.dry_run:
        if args.confirm:
            warn_confirm_ignored_on_dry_run()
        return None, None

    mode = resolve_confirm_mode(args)
    if mode in ('yes', 'env'):
        audit_yes_confirmed(path=path, node_count=node_count, quiet=args.quiet)
        return None, mode

    if not args.confirm:
        return None, None

    if not is_interactive_tty():
        cli_err(get_string('cli_error_confirm_not_tty'))
        return 1, None

    if not prompt_generate_confirm(
        path=path,
        node_count=node_count,
        fail_on_conflict=fail_on_conflict,
        warn_count=warn_count,
    ):
        cli_err(get_string('cli_confirm_cancelled'))
        return 0, None

    return None, 'interactive'

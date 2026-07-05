"""
treeing/cli/main.py

Defines the CLI main entry point and command dispatch.
Handles argument parsing, path validation, the parse/generate flow, warning
output, JSON results and exit codes.
"""

import os
import sys
from pathlib import Path

from ..config import get_string
from ..core.generator import create_from_tree, iter_nodes
from ..core.parser import build_tree
from ..core.preview import render_text_tree
from ..path_checks import verify_output_is_directory, verify_output_writable
from .confirm import gate_before_write
from .help_text import build_parser, dispatch_help_argv
from .io import cli_err, cli_out, cli_warn, configure_stdio
from .report import (
    DEFAULT_WARN_LIMIT,
    EXIT_FAILURE,
    build_json_result,
    emit_json,
    resolve_exit_code,
    write_warnings_file,
)

_FORMAT_TEXT = 'text'
_FORMAT_TREE = 'tree'


def _ensure_utf8_console() -> None:
    """
    Switch the Windows console (default legacy codepage) to UTF-8 to avoid garbled output.

    Best effect under cmd and the PyInstaller exe; under PowerShell prefer the
    scripts/treeing-cli.ps1 launcher, since the host encoding is not controlled
    by this process.
    """
    if sys.platform != 'win32':
        return

    # Force the Python standard-stream environment variable.
    if 'PYTHONIOENCODING' not in os.environ:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

    # Set the current process console code page to UTF-8.
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:  # nosec B110 - safe fallback when the console code page switch fails
        pass


def _print_warning_sections(
    sections: list[tuple[str, list[str]]],
    *,
    limit: int | None,
    quiet: bool,
) -> None:
    """
    Print warning lists by stage (parse / generate).

    With limit=None nothing is truncated; otherwise truncation is followed by
    an "N more" line.
    """
    if quiet:
        return

    non_empty = [(title_key, ws) for title_key, ws in sections if ws]
    if not non_empty:
        return

    tagged: list[tuple[str, str]] = []
    for title_key, ws in non_empty:
        for w in ws:
            tagged.append((title_key, w))

    total = len(tagged)
    effective_limit = total if limit is None else limit
    shown = tagged[:effective_limit]
    if limit is not None and total > len(shown):
        cli_warn(get_string("cli_warning_header_truncated", count=total, shown=len(shown)))
    else:
        cli_warn(get_string("cli_warning_header", count=total))

    current_section: str | None = None
    section_totals = {tk: len(ws) for tk, ws in non_empty}
    for title_key, warning in shown:
        if title_key != current_section:
            cli_warn(get_string(
                "cli_warning_section",
                title=get_string(title_key),
                count=section_totals[title_key],
            ))
            current_section = title_key
        cli_warn(get_string("cli_warning_item", warning=warning))

    if limit is not None and total > len(shown):
        cli_warn(get_string("cli_warning_more", extra=total - len(shown)))


def _warn_display_limit(args) -> int | None:
    """
    Decide the terminal warning display cap from the arguments.

    --no-warn-limit means no cap; --warn-limit=0 also means no cap; otherwise
    the default DEFAULT_WARN_LIMIT is used.
    """
    if args.no_warn_limit:
        return None
    if args.warn_limit is not None:
        return args.warn_limit if args.warn_limit > 0 else None
    return DEFAULT_WARN_LIMIT


def _maybe_write_warnings_file(
    path: str | None,
    parse_warnings: list[str],
    gen_warnings: list[str],
) -> str | None:
    """
    When the user passes --warnings-file, write the warnings there.

    Returns None on success; returns an error message string on write failure.
    """
    if not path:
        return None
    try:
        write_warnings_file(Path(path), parse_warnings, gen_warnings)
    except OSError as e:
        return get_string('cli_err_warnings_file_write', path=path, error=e)
    return None


def _emit_tree_preview(tree: list[dict], *, allow_nested: bool) -> list[str]:
    """Render the parsed tree into text-tree lines for --format tree."""
    return render_text_tree(tree, allow_nested=allow_nested)


def _print_tree_preview(lines: list[str]) -> None:
    """Print text-tree lines to stdout, one per line."""
    for line in lines:
        cli_out(line)


def _emit_failure(
    *,
    args,
    error: str,
    parse_warnings: list[str] | None = None,
    gen_warnings: list[str] | None = None,
    dry_run: bool = False,
    node_count: int = 0,
    tree_preview: list[str] | None = None,
    implicit_output_warning: str | None = None,
) -> int:
    """
    Emit a failure result uniformly.

    Output format follows --json / --quiet; with --warnings-file the warnings
    gathered so far are still written before reporting the failure.
    """
    parse_warnings = parse_warnings or []
    gen_warnings = gen_warnings or []
    warn_file_err = _maybe_write_warnings_file(args.warnings_file, parse_warnings, gen_warnings)
    exit_code = EXIT_FAILURE

    if args.json:
        emit_json(build_json_result(
            ok=False,
            dry_run=dry_run,
            node_count=node_count,
            output=args.output,
            parse_warnings=parse_warnings,
            gen_warnings=gen_warnings,
            error=error,
            exit_code=exit_code,
            tree_preview=tree_preview,
            implicit_output_warning=implicit_output_warning,
        ))
    else:
        if not args.quiet:
            _print_warning_sections([
                ('cli_warning_section_parse', parse_warnings),
                ('cli_warning_section_generate', gen_warnings),
            ], limit=_warn_display_limit(args), quiet=False)
        cli_err(error)
        if warn_file_err and not args.quiet:
            cli_warn(warn_file_err)

    return exit_code


def _emit_success(
    *,
    args,
    tree: list[dict],
    parse_warnings: list[str],
    gen_warnings: list[str],
    node_count: int,
    confirm_mode: str | None = None,
    implicit_output_warning: str | None = None,
) -> int:
    """
    Emit a success result uniformly.

    Handles the warnings file, tree preview, success summary, JSON output and
    the exit code 2 from --warn-exit-code.
    """
    warn_file_err = _maybe_write_warnings_file(args.warnings_file, parse_warnings, gen_warnings)
    has_warnings = bool(parse_warnings or gen_warnings)
    exit_code = resolve_exit_code(
        ok=True,
        has_warnings=has_warnings,
        warn_exit_code=args.warn_exit_code,
    )
    tree_preview = (
        _emit_tree_preview(tree, allow_nested=args.allow_nested_names)
        if args.format == _FORMAT_TREE
        else None
    )

    if args.json:
        emit_json(build_json_result(
            ok=True,
            dry_run=args.dry_run,
            node_count=node_count,
            output=args.output,
            parse_warnings=parse_warnings,
            gen_warnings=gen_warnings,
            exit_code=exit_code,
            tree_preview=tree_preview,
            confirm_mode=confirm_mode,
            implicit_output_warning=implicit_output_warning,
        ))
    else:
        _print_warning_sections([
            ('cli_warning_section_parse', parse_warnings),
            ('cli_warning_section_generate', gen_warnings),
        ], limit=_warn_display_limit(args), quiet=args.quiet)
        if tree_preview is not None:
            _print_tree_preview(tree_preview)
        if not args.quiet and args.format == _FORMAT_TEXT:
            if args.dry_run:
                cli_out(get_string("cli_dry_run_msg", count=node_count))
            else:
                cli_out(get_string("cli_generate_success", count=node_count, path=args.output))
        if warn_file_err and not args.quiet:
            cli_warn(warn_file_err)

    return exit_code


def _resolve_output(args) -> str:
    """
    Resolve the final output directory.

    Priority: -o > the directory remembered via --use-settings > the current
    working directory. MING folds the GUI's recent directory in here so the
    CLI and GUI share one set of habits.
    """
    if args.output is not None:
        return args.output
    if args.use_settings:
        from ..gui.settings import get_last_generate_dir
        return get_last_generate_dir() or '.'
    return '.'


def _implicit_output_warning_message(*, output_explicit: bool, args) -> str | None:
    """
    Return the warning text when no explicit -o is given and the current working directory will be written to.

    Covers the --use-settings fallback to the current directory; dry-run does
    not warn.
    """
    if args.dry_run or output_explicit:
        return None
    try:
        if Path(args.output).resolve() != Path.cwd().resolve():
            return None
    except OSError:
        return None
    return get_string('cli_warn_implicit_output', path=args.output)


def cli_main() -> int:
    """
    CLI main entry point.

    Flow: handle help / about -> parse arguments -> read input -> parse tree
    -> validate path -> confirm -> generate filesystem -> emit result / JSON.

    MING routes every error path through _emit_failure so the output structure
    stays consistent across JSON and non-JSON modes.
    """
    _ensure_utf8_console()
    configure_stdio()

    help_code = dispatch_help_argv(sys.argv)
    if help_code is not None:
        return help_code

    parser = build_parser()
    args = parser.parse_args()

    if args.strict:
        args.no_fix = True
        args.fail_on_conflict = True

    output_explicit = args.output is not None
    args.output = _resolve_output(args)
    fail_on_conflict = args.fail_on_conflict or args.fail_on_duplicate

    output_dir_err = verify_output_is_directory(args.output)
    if output_dir_err:
        return _emit_failure(args=args, error=output_dir_err)

    if args.paste and args.input:
        parser.error(get_string("cli_error_input_conflict"))

    if args.confirm and args.json:
        parser.error(get_string("cli_error_confirm_json"))

    if args.paste:
        if not args.quiet and not args.json:
            cli_err(get_string("cli_prompt_paste"))
        try:
            text = sys.stdin.buffer.read().decode(args.encoding)
        except UnicodeDecodeError as e:
            msg = get_string("cli_reading_stdin_error", error=e)
            return _emit_failure(args=args, error=msg)
    elif args.input:
        try:
            with open(args.input, encoding=args.encoding) as f:
                text = f.read()
        except Exception as e:
            msg = get_string("cli_reading_error", error=e)
            return _emit_failure(args=args, error=msg)
    else:
        parser.print_help()
        return 0

    lines = text.splitlines()
    tree, parse_warnings = build_tree(
        lines,
        auto_fix=not args.no_fix,
        indent_unit=args.indent_unit,
        strict_dirs=args.strict_dirs,
    )

    if not tree:
        return _emit_failure(
            args=args,
            error=get_string("cli_empty_tree"),
            parse_warnings=parse_warnings,
        )

    implicit_output_warning = _implicit_output_warning_message(
        output_explicit=output_explicit, args=args,
    )

    if args.check_writable:
        writable_err = verify_output_writable(args.output)
        if writable_err:
            return _emit_failure(
                args=args,
                error=writable_err,
                parse_warnings=parse_warnings,
                implicit_output_warning=implicit_output_warning,
            )

    node_count = sum(1 for _ in iter_nodes(tree))
    warn_count = len(parse_warnings)

    if implicit_output_warning and not (args.json and args.quiet):
        cli_warn(implicit_output_warning)

    early_exit, confirm_mode = gate_before_write(
        args,
        path=args.output,
        node_count=node_count,
        fail_on_conflict=fail_on_conflict,
        warn_count=warn_count,
    )
    if early_exit is not None:
        return early_exit

    gen_warnings: list[str] = []
    try:
        create_from_tree(
            tree,
            Path(args.output),
            dry_run=args.dry_run,
            warnings=gen_warnings,
            allow_nested_names=args.allow_nested_names,
            fail_on_conflict=fail_on_conflict,
            rollback_on_error=args.rollback_on_error,
        )
        return _emit_success(
            args=args,
            tree=tree,
            parse_warnings=parse_warnings,
            gen_warnings=gen_warnings,
            node_count=node_count,
            confirm_mode=confirm_mode,
            implicit_output_warning=implicit_output_warning,
        )
    except Exception as e:
        return _emit_failure(
            args=args,
            error=get_string("cli_generate_failed", error=e),
            parse_warnings=parse_warnings,
            gen_warnings=gen_warnings,
            dry_run=args.dry_run,
            node_count=sum(1 for _ in iter_nodes(tree)),
            tree_preview=(
                _emit_tree_preview(tree, allow_nested=args.allow_nested_names)
                if args.format == _FORMAT_TREE
                else None
            ),
            implicit_output_warning=implicit_output_warning,
        )

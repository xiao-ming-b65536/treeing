"""
treeing/cli/report.py

Defines the CLI result-reporting logic: JSON output, warnings-file writing,
and exit-code resolution. Provides helpers such as `build_json_result`,
`emit_json` and `resolve_exit_code`.
"""

import json
from pathlib import Path

from ..config import get_string
from .io import cli_out

DEFAULT_WARN_LIMIT = 10
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_WARNINGS = 2


def resolve_exit_code(*, ok: bool, has_warnings: bool, warn_exit_code: bool) -> int:
    """
    Decide the exit code from the run result and warnings.

    With warn_exit_code set, a successful run with warnings returns 2
    (EXIT_WARNINGS); a failure always returns 1.
    """
    if not ok:
        return EXIT_FAILURE
    if has_warnings and warn_exit_code:
        return EXIT_WARNINGS
    return EXIT_SUCCESS


def write_warnings_file(
    path: Path,
    parse_warnings: list[str],
    gen_warnings: list[str],
) -> None:
    """
    Write parse and generation warnings to the given file, prefixed by stage.

    Edge cases: write failures are caught by the caller; an empty list still
    writes a trailing newline.
    """
    lines: list[str] = []
    parse_title = get_string('cli_warning_section_parse')
    gen_title = get_string('cli_warning_section_generate')
    for w in parse_warnings:
        lines.append(f'[{parse_title}] {w}')
    for w in gen_warnings:
        lines.append(f'[{gen_title}] {w}')
    path.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')


def build_json_result(
    *,
    ok: bool,
    dry_run: bool = False,
    node_count: int = 0,
    output: str = '',
    parse_warnings: list[str],
    gen_warnings: list[str],
    error: str | None = None,
    exit_code: int = EXIT_SUCCESS,
    tree_preview: list[str] | None = None,
    confirm_mode: str | None = None,
    implicit_output_warning: str | None = None,
) -> dict:
    """
    Assemble the JSON result dictionary for --json output.

    Optional fields are only included when not None.
    """
    result: dict = {
        'ok': ok,
        'dry_run': dry_run,
        'node_count': node_count,
        'output': output,
        'parse_warnings': parse_warnings,
        'generate_warnings': gen_warnings,
        'exit_code': exit_code,
    }
    if error is not None:
        result['error'] = error
    if tree_preview is not None:
        result['tree_preview'] = tree_preview
    if confirm_mode is not None:
        result['confirmed'] = True
        result['confirm_mode'] = confirm_mode
    if implicit_output_warning is not None:
        result['implicit_output_warning'] = True
        result['implicit_output_warning_message'] = implicit_output_warning
    return result


def emit_json(data: dict) -> None:
    """
    Print the result dictionary as a single-line JSON object to stdout.

    Uses ensure_ascii=False so non-ASCII text stays readable in the JSON
    rather than being escaped to \\uXXXX.
    """
    cli_out(json.dumps(data, ensure_ascii=False))

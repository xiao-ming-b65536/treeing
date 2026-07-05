"""
treeing/cli/help_text.py

Defines the layered CLI help system: short help, full help, topic help, and about.
Provides `build_parser` and `dispatch_help_argv` as entry points.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from .. import __version__
from ..config import get_string, get_ui_string
from .io import cli_out

# topic name -> (title string key, body string key or None to use gui_tooltip_*)
TOPIC_SPECS: dict[str, tuple[str, str | None, str | None]] = {
    # name: (title_key, body_key, tooltip_fallback_key)
    'input': ('cli_help_topic_title_input', 'cli_help_topic_input', 'gui_tooltip_input'),
    'output': ('cli_help_topic_title_output', 'cli_help_topic_output', None),
    'encoding': ('cli_help_topic_title_encoding', None, 'gui_tooltip_encoding'),
    'parse': ('cli_help_topic_title_parse', 'cli_help_topic_parse', None),
    'no-fix': ('cli_help_topic_title_no_fix', None, 'gui_tooltip_no_fix'),
    'strict-dirs': ('cli_help_topic_title_strict_dirs', None, 'gui_tooltip_strict_dirs'),
    'indent-unit': ('cli_help_topic_title_indent_unit', None, 'gui_tooltip_indent_unit'),
    'dry-run': ('cli_help_topic_title_dry_run', 'cli_help_topic_dry_run', None),
    'allow-nested': ('cli_help_topic_title_allow_nested', None, 'gui_tooltip_allow_nested'),
    'fail-on-conflict': ('cli_help_topic_title_fail_on_conflict', None, 'gui_tooltip_fail_on_conflict'),
    'rollback-on-error': ('cli_help_topic_title_rollback_on_error', 'cli_help_topic_rollback_on_error', None),
    'format': ('cli_help_topic_title_format', 'cli_help_topic_format', 'gui_tooltip_preview'),
    'json': ('cli_help_topic_title_json', 'cli_help_topic_json', None),
    'automation': ('cli_help_topic_title_automation', 'cli_help_topic_automation', None),
    'windows': ('cli_help_topic_title_windows', 'cli_help_topic_windows', None),
    'warnings': ('cli_help_topic_title_warnings', None, 'gui_tooltip_view_warnings'),
    'strict': ('cli_help_topic_title_strict', 'cli_help_topic_strict', None),
    'confirm': ('cli_help_topic_title_confirm', 'cli_help_topic_confirm', None),
    'about': ('cli_help_topic_title_about', None, None),
}

# P3: topic index groups (section_key, [topic names])
TOPIC_INDEX: list[tuple[str, list[str]]] = [
    ('cli_help_topics_section_input', ['input', 'output', 'encoding']),
    ('cli_help_topics_section_parse', ['parse', 'no-fix', 'strict-dirs', 'indent-unit']),
    ('cli_help_topics_section_generate', [
        'dry-run', 'allow-nested', 'fail-on-conflict', 'rollback-on-error',
        'format', 'strict', 'confirm',
    ]),
    ('cli_help_topics_section_automation', ['json', 'automation', 'warnings']),
    ('cli_help_topics_section_platform', ['windows']),
    ('cli_help_topics_section_meta', ['about']),
]

TOPIC_ALIASES: dict[str, str] = {
    'i': 'input',
    'o': 'output',
    'p': 'paste',
    'paste': 'input',
    'nested': 'allow-nested',
    'conflict': 'fail-on-conflict',
    'rollback': 'rollback-on-error',
    'yes': 'confirm',
    'y': 'confirm',
    'topics': 'topics',
}


def _body_for_topic(name: str) -> str:
    """
    Fetch the body text for a help topic.

    Prefer the dedicated body_key; otherwise fall back to the gui_tooltip_*
    text. The `about` topic is special-cased and prints the about text.
    """
    if name == 'about':
        return get_ui_string('gui_msg_about', version=__version__)
    spec = TOPIC_SPECS.get(name)
    if not spec:
        return ''
    _, body_key, tooltip_key = spec
    if body_key:
        text = get_string(body_key)
        if text != body_key:
            return text
    if tooltip_key:
        return get_string(tooltip_key)
    return ''


def print_about() -> None:
    """Print the --about content (shares the same text as the GUI about dialogue)."""
    cli_out(get_ui_string('gui_msg_about', version=__version__))


def print_topics_index() -> None:
    """Print the topic index for `treeing help`, grouped by section."""
    cli_out(get_ui_string('cli_help_topics_intro'))
    cli_out('')
    for section_key, names in TOPIC_INDEX:
        cli_out(get_string(section_key))
        for name in names:
            title_key = TOPIC_SPECS[name][0]
            cli_out(get_string('cli_help_topics_item', topic=name, title=get_string(title_key)))
        cli_out('')
    cli_out(get_ui_string('cli_help_topics_footer'))


def print_topic(name: str) -> int:
    """
    Print detailed help for a single topic.

    Supports aliases (e.g. nested -> allow-nested); an unknown topic prints an
    error first, then lists the available topics.
    """
    canonical = TOPIC_ALIASES.get(name, name)
    if canonical == 'topics':
        print_topics_index()
        return 0
    if canonical not in TOPIC_SPECS:
        cli_out(get_string('cli_help_unknown_topic', topic=name))
        cli_out('')
        print_topics_index()
        return 1
    title = get_string(TOPIC_SPECS[canonical][0])
    body = _body_for_topic(canonical)
    cli_out(title)
    cli_out('')
    cli_out(body)
    cli_out('')
    cli_out(get_ui_string('cli_help_topic_see_also'))
    return 0


def dispatch_help_argv(argv: list[str]) -> int | None:
    """
    Handle help / --about / --help-full requests before formal argument parsing.

    Returns an exit code when handled; returns None when this is not a help
    request and normal flow should continue.
    """
    if len(argv) == 2 and argv[1] == '--about':
        print_about()
        return 0
    if len(argv) == 2 and argv[1] == '--help-full':
        print_help_full()
        return 0
    try:
        idx = argv.index('help')
    except ValueError:
        return None
    if idx != 1:
        return None
    topic = argv[idx + 1] if len(argv) > idx + 1 else None
    if topic is None:
        print_topics_index()
        return 0
    return print_topic(topic)


def _add_group(parser: argparse.ArgumentParser, title_key: str, add_fn: Callable) -> None:
    """Add an argument group to the parser; the group title comes from the string resources."""
    group = parser.add_argument_group(get_string(title_key))
    add_fn(group)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser; all text comes from strings.json."""
    parser = argparse.ArgumentParser(
        description=get_string('cli_help_desc'),
        epilog=get_ui_string('cli_help_epilog'),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--version', action='version',
        version=get_string('cli_version_fmt', version=__version__),
    )
    parser.add_argument(
        '--about', action='store_true',
        help=get_string('cli_about_flag'),
    )
    parser.add_argument(
        '--help-full', action='store_true',
        help=get_string('cli_help_full_flag'),
    )

    def add_input(g):
        """Register input-related arguments: -i/--input, -p/--paste, --encoding."""
        g.add_argument('-i', '--input', help=get_string('cli_input_file'))
        g.add_argument('-p', '--paste', action='store_true', help=get_string('cli_paste'))
        g.add_argument(
            '--encoding', default='utf-8', metavar='ENC',
            help=get_string('cli_encoding'),
        )

    def add_output(g):
        """Register output-related arguments: -o/--output, --use-settings, --check-writable."""
        g.add_argument('-o', '--output', default=None, help=get_string('cli_output_dir'))
        g.add_argument(
            '--use-settings', action='store_true',
            help=get_string('cli_use_settings'),
        )
        g.add_argument(
            '--check-writable', action='store_true',
            help=get_string('cli_check_writable'),
        )

    def add_parse(g):
        """Register parse-related arguments: --no-fix, --strict-dirs, --indent-unit."""
        g.add_argument('--no-fix', action='store_true', help=get_string('cli_no_fix'))
        g.add_argument(
            '--strict-dirs', action='store_true',
            help=get_string('cli_strict_dirs'),
        )
        g.add_argument(
            '--indent-unit', type=int, default=None, metavar='N',
            help=get_string('cli_indent_unit'),
        )

    def add_generate(g):
        """Register generation-related arguments: dry-run, nested names, conflict handling, confirmation mode, etc."""
        g.add_argument('--dry-run', action='store_true', help=get_string('cli_dry_run'))
        g.add_argument(
            '--allow-nested-names', action='store_true',
            help=get_string('cli_allow_nested_names'),
        )
        g.add_argument(
            '--fail-on-conflict', action='store_true',
            help=get_string('cli_fail_on_conflict'),
        )
        g.add_argument(
            '--fail-on-duplicate', action='store_true',
            help=get_string('cli_fail_on_duplicate'),
        )
        g.add_argument(
            '--strict', action='store_true',
            help=get_string('cli_strict'),
        )
        g.add_argument(
            '--rollback-on-error', action='store_true',
            help=get_string('cli_rollback_on_error'),
        )
        confirm = g.add_mutually_exclusive_group()
        confirm.add_argument(
            '--confirm', action='store_true',
            help=get_string('cli_confirm'),
        )
        confirm.add_argument(
            '-y', '--yes', action='store_true',
            help=get_string('cli_yes'),
        )

    def add_automation(g):
        """Register automation-related arguments: --json, --quiet, --warn-exit-code, --warnings-file, --format, warning cap."""
        g.add_argument('--json', action='store_true', help=get_string('cli_json'))
        g.add_argument('--quiet', action='store_true', help=get_string('cli_quiet'))
        g.add_argument(
            '--warn-exit-code', action='store_true',
            help=get_string('cli_warn_exit_code'),
        )
        g.add_argument(
            '--warnings-file', metavar='PATH',
            help=get_string('cli_warnings_file'),
        )
        g.add_argument(
            '--format', choices=['text', 'tree'], default='text',
            help=get_string('cli_format'),
        )
        warn_limit = g.add_mutually_exclusive_group()
        warn_limit.add_argument(
            '--no-warn-limit', action='store_true',
            help=get_string('cli_no_warn_limit'),
        )
        warn_limit.add_argument(
            '--warn-limit', type=int, default=None, metavar='N',
            help=get_string('cli_warn_limit'),
        )

    _add_group(parser, 'cli_help_group_input', add_input)
    _add_group(parser, 'cli_help_group_output', add_output)
    _add_group(parser, 'cli_help_group_parse', add_parse)
    _add_group(parser, 'cli_help_group_generate', add_generate)
    _add_group(parser, 'cli_help_group_automation', add_automation)
    return parser


def print_help_full() -> None:
    """Full help: short help plus an expanded description for each option."""
    parser = build_parser()
    parser.print_help()
    cli_out('')
    cli_out(get_string('cli_help_full_header'))
    cli_out('')
    sections = [
        ('cli_help_full_section_input', ['input', 'output', 'encoding']),
        ('cli_help_full_section_parse', ['parse', 'no-fix', 'strict-dirs', 'indent-unit']),
        ('cli_help_full_section_generate', [
            'dry-run', 'allow-nested', 'fail-on-conflict', 'rollback-on-error', 'format', 'strict', 'confirm',
        ]),
        ('cli_help_full_section_automation', ['json', 'automation', 'warnings']),
        ('cli_help_full_section_platform', ['windows']),
    ]
    for section_key, topics in sections:
        cli_out(get_string(section_key))
        for topic in topics:
            title = get_string(TOPIC_SPECS[topic][0])
            body = _body_for_topic(topic)
            cli_out(get_string('cli_help_full_topic_line', topic=topic, title=title))
            for line in body.splitlines():
                cli_out(f'  {line}')
            cli_out('')
    cli_out(get_ui_string('cli_help_topics_footer'))

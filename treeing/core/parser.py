"""
treeing/core/parser.py

Defines the ASCII tree-text parsing logic.
Handles indent detection, branch symbols, file/directory inference,
auto-repair and edge cases, producing a structured node tree for the generator.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import reduce
from math import gcd

from ..config import get_string
from .constants import DOT_ROOT, TRANSPARENT_NODE_NAMES, VIRTUAL_AUTO, VIRTUAL_ROOT

# Matches tree branch characters (├└┤┬┴┼) and various horizontal lines
# (ASCII and Unicode box-drawing characters).
# MING includes all of these so the parser copes with tree output from
# different systems and tools.
_BRANCH_CHARS = r'[├└┤┬┴┼+\-`\\|]'
_HORIZ_CHARS = r'[-—─━┄┅┈┉]+'
PREFIX_PATTERN = re.compile(rf'^{_BRANCH_CHARS}\s*{_HORIZ_CHARS}\s*')

# Vertical continuation line: │ or | followed by 3 spaces, repeatable.
# This matches the `tree` command output format, hence the dedicated regex.
INDENT_PATTERN = re.compile(r'^(?:(?:[│|])\s{3})*')
SPACE_INDENT_PATTERN = re.compile(r'^ +')

# Lines made up only of separators (---, ===, *** and the like) are not tree
# content and are skipped.
_SEPARATOR_ONLY = re.compile(r'^[\-=_*·…\.]+$')

# Default indent unit: 4 spaces.
_TREE_STANDARD_UNIT = 4

# Filenames without an extension that everyone still recognises as files.
# MING lists the common ones (LICENSE, README, Makefile) here to avoid
# misclassifying them as directories.
_KNOWN_FILE_NAMES = frozenset({
    'license', 'copying', 'authors', 'contributors', 'readme',
    'changelog', 'makefile', 'dockerfile', 'procfile', 'gemfile',
    'rakefile', 'vagrantfile', 'brewfile', 'justfile', 'notice',
})


def _looks_like_file(name: str, *, strict_dirs: bool = False) -> bool:
    """
    Decide whether a name looks like a file or a directory.

    By default MING uses a fairly aggressive heuristic: if the name contains an
    uppercase letter, treat it as a file, because the Windows `tree` command
    usually prints directories in lower case while files (especially source
    files) often contain capitals.

    This rule misclassifies some hand-written directory names, so the
    `--strict-dirs` option turns it off and only trusts extensions, dotfiles
    and the known extension-less filenames.
    """
    if name.lower() in _KNOWN_FILE_NAMES:
        return True
    if name.startswith('.') and len(name) > 1:
        return True
    if '.' in name and not name.startswith('.'):
        return True
    if strict_dirs:
        return False
    return any(c.isupper() for c in name)


def _is_noise_line(stripped: str) -> bool:
    """
    Decide whether a line is "noise", i.e. not tree content.

    Comment lines (starting with # or //) and pure separator lines (---, ===,
    etc.) are skipped. A lone '.' is a legal root marker and is not noise.
    """
    if stripped == DOT_ROOT:
        return False
    if stripped.startswith('#') or stripped.startswith('//'):
        return True
    return _SEPARATOR_ONLY.match(stripped) is not None


def _is_root_garbage(indent: int, has_branch: bool, name: str) -> bool:
    """
    Decide whether a root-level line is "garbage", i.e. clearly not tree content.

    If the line has no branch prefix, no indent, contains a space and is not a
    recognised file form, it is most likely prose the user pasted by accident
    (e.g. "random garbage line").
    """
    if has_branch or indent > 0:
        return False
    if name.endswith('/') or name == DOT_ROOT:
        return False
    if _looks_like_file(name):
        return False
    return ' ' in name


def _measure_indent(line: str) -> int:
    """
    Measure the indent length of a line.

    The indent can come from two sources:
    1. A tree continuation line (│   or |   followed by 3 spaces, repeatable).
    2. Plain space indent (hand-written trees may just use spaces).

    MING handles both so the parser copes with all sorts of odd input formats.
    """
    pos_match = INDENT_PATTERN.match(line)
    pos = pos_match.end() if pos_match else 0
    space_match = SPACE_INDENT_PATTERN.match(line[pos:])
    if space_match:
        pos += space_match.end()
    return pos


def parse_line(
    line: str, *, strict_dirs: bool = False,
) -> tuple[int, str, bool, bool, bool] | None:
    """
    Parse a single tree-text line, extracting indent, name, directory flag, etc.

    Returns a 5-tuple: (indent, name, is_dir, has_branch_prefix, is_heuristic_dir).

    Returns None for blank lines or lines that fail to parse.
    """
    line = line.expandtabs(4)
    line = line.rstrip('\n')
    if not line.strip():
        return None

    indent = _measure_indent(line)
    rest = line[indent:]

    prefix_match = PREFIX_PATTERN.match(rest)
    has_branch_prefix = prefix_match is not None
    if prefix_match:
        name = rest[prefix_match.end():].strip()
    else:
        name = rest.strip()

    if not name:
        return None

    heuristic_dir = False
    is_dir = name.endswith('/')
    if is_dir:
        name = name[:-1]
    elif has_branch_prefix and not _looks_like_file(name, strict_dirs=strict_dirs):
        is_dir = True
        heuristic_dir = True

    return indent, name, is_dir, has_branch_prefix, heuristic_dir


def _gcd_of_list(values: list[int]) -> int:
    """
    Compute the greatest common divisor of a list of positive integers.

    Used by detect_indent_unit: if every indent value is a multiple of some
    number, prefer that multiple as the indent unit. Accepts positive integers
    only; an empty list returns 0.
    """
    return reduce(gcd, values)


def _most_common_diff(positive: list[int]) -> int:
    """
    Find the most common "adjacent difference" among a list of indent values.

    One of MING's heuristics for guessing the indent unit: if, in a hand-written
    tree, most children are indented 2 spaces more than their parent, the unit
    is probably 2.
    """
    diff_counts: Counter = Counter()
    for i in range(1, len(positive)):
        diff = positive[i] - positive[i - 1]
        if diff > 0:
            diff_counts[diff] += 1
    if diff_counts:
        return diff_counts.most_common(1)[0][0]
    return positive[0]


def detect_indent_unit(indents: list[int]) -> int:
    """
    Infer the most likely indent unit from a set of indent values.

    MING applies three rules in priority order:
    1. If every indent value is a multiple of some number >= 4, use that number.
    2. If the smallest positive indent is >= 4, use that smallest value.
    3. Otherwise take the larger of "greatest common divisor" and "most common
       difference".

    Returns the default 4 when there are no positive indents at all.
    """
    if not indents:
        return _TREE_STANDARD_UNIT
    positive = sorted(set(i for i in indents if i > 0))
    if not positive:
        return _TREE_STANDARD_UNIT
    if len(positive) == 1:
        return positive[0]

    gcd_unit = _gcd_of_list(positive)
    diff_unit = _most_common_diff(positive)

    if gcd_unit >= _TREE_STANDARD_UNIT:
        return gcd_unit
    if min(positive) >= _TREE_STANDARD_UNIT:
        return min(positive)
    return max(gcd_unit, diff_unit)


def _compute_level(indent: int, unit: int, has_branch_prefix: bool) -> int:
    """
    Compute a node's tree level from its indent value and the indent unit.

    A node with a branch prefix is one level deeper than a plain-indent node at
    the same column (the branch itself occupies a level).
    """
    if has_branch_prefix:
        return indent // unit + 1 if unit > 0 else 1
    return indent // unit if unit > 0 else 0


def auto_fix_indent(
    parsed: list[tuple[int, str, bool, bool, bool, int]], unit: int
) -> tuple[list[tuple[int, str, bool, bool, bool, int]], list[str]]:
    """
    Snap parsed indent values onto the inferred indent unit.

    If a line's indent is not a multiple of the unit, round it to the nearest
    multiple. Each fix produces a warning telling the user "I fixed line X's
    indent".

    MING added this auto-repair so that hand-written trees with messy indents
    still parse into a reasonable structure.
    """
    fixed = []
    warnings = []
    for indent, name, is_dir, has_branch, heuristic_dir, line_no in parsed:
        if unit == 0:
            new_indent = 0
        else:
            quotient = round(indent / unit)
            new_indent = quotient * unit
            if new_indent < 0:
                new_indent = 0
        if new_indent != indent:
            warn = get_string(
                "core_warn_indent_fixed",
                line=line_no, old=indent, new=new_indent, unit=unit,
            )
            warnings.append(warn)
        fixed.append((new_indent, name, is_dir, has_branch, heuristic_dir, line_no))
    return fixed, warnings


def _infer_directories(tree: list[dict], warnings: list[str]) -> None:
    """
    Walk the tree and mark entries that have children but no trailing slash as directories.

    This copes with the Windows `tree` command, which does not add a trailing
    slash to directories, so we infer directory-ness from "has children".

    MING missed this in an early version, so Windows users often had their
    directories treated as files, which then broke generation.
    """

    def walk(node: dict) -> None:
        """Recursively walk nodes, correcting entries that have children but are still flagged as files into directories."""
        for child in node.get('children', []):
            walk(child)
        if (
            node.get('children')
            and not node.get('is_dir', False)
            and node['name'] not in TRANSPARENT_NODE_NAMES
            and not _looks_like_file(node['name'])
        ):
            node['is_dir'] = True
            warnings.append(get_string("core_warn_inferred_dir", name=node['name']))

    for root in tree:
        walk(root)


def build_tree(
    lines: list[str],
    auto_fix: bool = True,
    indent_unit: int | None = None,
    strict_dirs: bool = False,
) -> tuple[list[dict], list[str]]:
    """
    Parse multi-line ASCII tree text into a structured node tree.

    This is the entry point of the parser module. It:
    1. Strips the BOM (some editors prepend \ufeff).
    2. Parses line by line, skipping blank lines, comments, separators and
       garbage lines.
    3. Auto-detects the indent unit, or uses the user-supplied one.
    4. Auto-repairs misaligned indents (when auto_fix is on).
    5. Builds the tree, handling indent jumps, virtual roots, multiple roots
       and other edge cases.
    6. Infers directories that lack a trailing slash.
    7. Collects warnings and returns them to the caller for display.

    MING kept this function long on purpose: tree-text parsing has many edge
    cases, and splitting it into tiny helpers makes it easy for callers to
    forget handling some of them.
    """
    warnings: list[str] = []
    lines = [
        line.lstrip('\ufeff') if line.startswith('\ufeff') else line
        for line in lines
    ]
    parsed = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_noise_line(stripped):
            preview = stripped if len(stripped) <= 60 else stripped[:57] + '...'
            warnings.append(get_string("core_warn_unrecognized_line", line=idx, content=preview))
            continue
        result = parse_line(line, strict_dirs=strict_dirs)
        if result is None:
            preview = stripped if len(stripped) <= 60 else stripped[:57] + '...'
            warnings.append(get_string("core_warn_unrecognized_line", line=idx, content=preview))
            continue
        indent, name, is_dir, has_branch, heuristic_dir = result
        if _is_root_garbage(indent, has_branch, name):
            preview = stripped if len(stripped) <= 60 else stripped[:57] + '...'
            warnings.append(get_string("core_warn_unrecognized_line", line=idx, content=preview))
            continue
        parsed.append((indent, name, is_dir, has_branch, heuristic_dir, idx))

    if not parsed:
        return [], warnings + [get_string("core_warn_empty_input")]

    indents = [p[0] for p in parsed if p[0] > 0]
    unit = indent_unit if indent_unit and indent_unit > 0 else detect_indent_unit(indents)

    fix_warnings: list[str] = []
    if auto_fix:
        parsed, fix_warnings = auto_fix_indent(parsed, unit)
        warnings.extend(fix_warnings)
        if indent_unit is None:
            indents = [p[0] for p in parsed if p[0] > 0]
            if indents:
                unit = detect_indent_unit(indents)

    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []

    for indent, name, is_dir, has_branch, heuristic_dir, line_no in parsed:
        level = _compute_level(indent, unit, has_branch)

        while len(stack) > level:
            stack.pop()
        while len(stack) < level:
            if stack:
                parent = stack[-1][1]
                dummy = {'name': VIRTUAL_AUTO, 'is_dir': True, 'children': []}
                parent['children'].append(dummy)
                stack.append((len(stack), dummy))
                warnings.append(get_string("core_warn_indent_jump", parent=parent['name']))
            else:
                virtual = {'name': VIRTUAL_ROOT, 'is_dir': True, 'children': []}
                roots.append(virtual)
                stack.append((0, virtual))
                warnings.append(get_string("core_warn_virtual_root"))

        node = {'name': name, 'is_dir': is_dir, 'children': []}
        if name == DOT_ROOT:
            warnings.append(get_string("core_warn_dot_root"))
        if heuristic_dir:
            warnings.append(get_string("core_warn_inferred_dir_heuristic", name=name))
        if level == 0:
            roots.append(node)
            stack = [(0, node)]
        else:
            if stack:
                parent = stack[-1][1]
                parent['children'].append(node)
            else:
                roots.append(node)
                warnings.append(get_string("core_warn_orphan", line=line_no, name=name))
            stack.append((level, node))

    _infer_directories(roots, warnings)

    real_roots = [r for r in roots if r['name'] not in TRANSPARENT_NODE_NAMES]
    multiple_roots = len(real_roots) > 1
    if multiple_roots:
        names = ', '.join(r['name'] for r in real_roots)
        warnings.append(get_string("core_warn_multiple_roots", count=len(real_roots), names=names))

    if indent_unit is not None and indent_unit > 0 and (fix_warnings or multiple_roots):
        warnings.append(get_string("core_hint_indent_unit_check"))

    return roots, warnings

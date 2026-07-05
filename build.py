"""
build.py

PyInstaller packaging script.
Outputs per platform to dist/<platform>/; supports separate CLI / GUI builds.
"""

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

from treeing.config import get_string

TARGETS = frozenset({'cli', 'gui', 'all'})
TARGET_SPECS: dict[str, tuple[str, str]] = {
    'cli': ('treeing-cli', 'treeing/cli_entry.py'),
    'gui': ('treeing-gui', 'treeing/gui_entry.py'),
}

_COMMON_EXCLUDES = ('matplotlib', 'numpy', 'pandas')
_CLI_EXCLUDES = ('tkinter', '_tkinter', 'PIL', 'PIL.Image', 'PIL.ImageTk')
_PROJECT_ROOT = Path(__file__).resolve().parent


def platform_dist_name() -> str:
    """Return the dist subdirectory name for the current platform (windows / macos-arm64 / macos-x86_64 / linux)."""
    if sys.platform.startswith('win'):
        return 'windows'
    if sys.platform == 'darwin':
        # macOS splits arm64 (Apple Silicon) and x86_64 (Intel) into separate artifacts.
        return 'macos-arm64' if platform.machine() == 'arm64' else 'macos-x86_64'
    return 'linux'


def dist_dir() -> Path:
    """Return the output directory for the current platform (dist/<platform>)."""
    return Path('dist') / platform_dist_name()


def executable_name(base: str) -> str:
    """Append the .exe suffix on Windows."""
    return f'{base}.exe' if sys.platform.startswith('win') else base


def clean_build(*, dist: bool = True) -> None:
    """Remove build/ and dist/<platform>/, plus any leftover .spec files."""
    build_root = Path('build')
    if build_root.is_dir():
        shutil.rmtree(build_root)

    if dist:
        platform_dir = dist_dir()
        if platform_dir.is_dir():
            shutil.rmtree(platform_dir)

    for spec in Path('.').glob('treeing*.spec'):
        spec.unlink(missing_ok=True)


def _pyinstaller_icon() -> str | None:
    """Return the icon path for the current platform, or None when no matching icon file exists."""
    assets = _PROJECT_ROOT / 'treeing' / 'assets'
    if sys.platform == 'darwin':
        path = assets / 'icon.icns'
    elif sys.platform.startswith('win'):
        path = assets / 'icon.ico'
    else:
        return None
    return str(path) if path.is_file() else None


def _string_data_args() -> list[str]:
    """Build the --add-data arguments for strings.json / strings.bootstrap.json."""
    sep = os.pathsep
    entries = (
        (_PROJECT_ROOT / 'treeing/strings.json', 'treeing'),
        (_PROJECT_ROOT / 'treeing/strings.bootstrap.json', 'treeing'),
    )
    args: list[str] = []
    for src, dest in entries:
        if not src.exists():
            raise FileNotFoundError(get_string('build_resource_missing', path=src))
        args.extend(['--add-data', f'{src}{sep}{dest}'])
    return args


def _assets_data_args() -> list[str]:
    """Build the --add-data argument for the assets directory (GUI builds need the icons)."""
    sep = os.pathsep
    src = _PROJECT_ROOT / 'treeing' / 'assets'
    if not src.is_dir():
        raise FileNotFoundError(get_string('build_resource_missing', path=src))
    return ['--add-data', f'{src}{sep}treeing/assets']


def _pyinstaller_data_args(target: str) -> list[str]:
    """Combine the resource arguments needed for the given target."""
    args = _string_data_args()
    if target == 'gui':
        args.extend(_assets_data_args())
    return args


def _resolve_targets(target: str) -> list[str]:
    """Expand 'all' into ['cli', 'gui']; return a single target as a one-element list."""
    if target == 'all':
        return ['cli', 'gui']
    return [target]


def _build_pyinstaller_args(target: str, name: str, entry: str) -> list[str]:
    """Assemble the PyInstaller command-line arguments."""
    out = dist_dir()
    args = [
        '--onefile',
        '--name', name,
        '--distpath', str(out),
        '--workpath', f'build/{name}',
        '--specpath', 'build/specs',
        *_pyinstaller_data_args(target),
    ]
    if platform_dist_name() == 'linux':
        args.append('--strip')
    for mod in _COMMON_EXCLUDES:
        args.extend(['--exclude-module', mod])
    if target == 'cli':
        for mod in _CLI_EXCLUDES:
            args.extend(['--exclude-module', mod])
    if target == 'gui':
        args.append('--windowed')
    args.append(str(_PROJECT_ROOT / entry))
    return args


def build_target(target: str) -> Path:
    """Build a single target (cli or gui) and return the path to the produced executable."""
    import PyInstaller.__main__

    name, entry = TARGET_SPECS[target]
    print(get_string('build_start_target', target=name))

    pyinstaller_args = _build_pyinstaller_args(target, name, entry)

    icon = _pyinstaller_icon()
    if icon:
        pyinstaller_args[0:0] = ['--icon', icon]
        print(get_string('build_using_icon', icon=icon))
    elif target == 'gui':
        print(get_string('build_skip_icon'))

    PyInstaller.__main__.run(pyinstaller_args)

    exe_path = dist_dir() / executable_name(name)
    print(get_string('build_done', exe=f'{platform_dist_name()}/{executable_name(name)}'))
    return exe_path


MIN_ARTIFACT_BYTES = 100_000


def verify_artifacts(built: list[Path]) -> None:
    """Check that each built executable exists and is large enough, to catch silent PyInstaller failures."""
    for path in built:
        if not path.is_file():
            raise FileNotFoundError(get_string('build_artifact_missing', path=path))
        size = path.stat().st_size
        if size < MIN_ARTIFACT_BYTES:
            raise RuntimeError(
                get_string('build_artifact_too_small', path=path, size=size, min_size=MIN_ARTIFACT_BYTES),
            )


def build(target: str = 'all', *, clean: bool = True) -> list[Path]:
    """Build and verify artifacts for the target; when clean=True, clear old build dirs first."""
    targets = _resolve_targets(target)
    if clean:
        clean_build()
    built: list[Path] = []
    for t in targets:
        built.append(build_target(t))
    verify_artifacts(built)
    return built


def main(argv: list[str] | None = None) -> None:
    """CLI entry: parse --target and --no-clean, then call build."""
    parser = argparse.ArgumentParser(description='Build treeing CLI/GUI executables with PyInstaller.')
    parser.add_argument(
        '--target',
        choices=sorted(TARGETS),
        default='all',
        help='cli, gui, or all (default: all)',
    )
    parser.add_argument(
        '--no-clean',
        action='store_true',
        help='do not remove build/ and dist/<platform>/ before packaging',
    )
    args = parser.parse_args(argv)
    build(args.target, clean=not args.no_clean)


if __name__ == '__main__':
    main()

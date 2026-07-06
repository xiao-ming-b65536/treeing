# Changelog

All notable releases of Treeing are listed here. Tags follow `vX.Y.Z`.

## v1.0.1

- First release on PyPI — `pip install treeing`.
- Added `treeing` and `treeing-gui` console entry points.
- Declared build backend (setuptools) and PyPI classifiers.
- Linux: GUI needs `tkinter` (`sudo apt-get install python3-tk`); CLI does not.

## v1.0.0

- First public release.
- GUI and CLI for turning ASCII tree text into real directories and empty files.
- Supports Unicode box-drawing, pipe style, Windows `tree`, and space-indented trees.
- Auto indent repair, strict directory inference, abort-on-conflict, nested path names.
- CLI supports JSON output, dry-run, warnings file, and non-interactive confirmation.
- Prebuilt binaries for Windows, Linux, macOS ARM, and macOS x86.

# Treeing — ASCII tree → directory/file generator

Turn directory-tree text (e.g. output from the `tree` command) into real folders and empty files.

## Features

- Common `tree` output formats: Unicode box-drawing, pipe style, Windows `tree`, space-indented trees.
- Automatic indent repair (disable with `--no-fix` or the GUI checkbox).
- Both a GUI and a CLI.
- Cross-platform: Windows, macOS, Linux.
- User-visible strings live in `treeing/strings.json` (bootstrap errors in `treeing/strings.bootstrap.json`).

## Quick start

### Run from source

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\pip install -r requirements-build.txt
# Unix:    .venv/bin/pip install -r requirements-build.txt

python -m treeing.main                       # GUI
python -m treeing.main -i tree.txt -o ./out  # CLI
python -m treeing.main --help                # CLI help
```

### Run a prebuilt executable

Prebuilt binaries are attached to each [release](https://github.com/xiao-ming-b65536/treeing/releases) (Windows, Linux, macOS ARM, macOS x86). Pick the archive for your platform (replace `vX.Y.Z` with the actual version):

| Platform | Archives |
|---|---|
| Windows | `treeing-cli-windows-vX.Y.Z.zip`, `treeing-gui-windows-vX.Y.Z.zip` |
| Linux | `treeing-cli-linux-vX.Y.Z.tar.gz`, `treeing-gui-linux-vX.Y.Z.tar.gz` |
| macOS (Apple Silicon) | `treeing-cli-macos-arm64-vX.Y.Z.tar.gz`, `treeing-gui-macos-arm64-vX.Y.Z.tar.gz` |
| macOS (Intel) | `treeing-cli-macos-x86_64-vX.Y.Z.tar.gz`, `treeing-gui-macos-x86_64-vX.Y.Z.tar.gz` |

CLI and GUI are packaged separately; download whichever you need. Verify against `SHA256SUMS.txt` in the same release.

```bash
treeing-gui                           # GUI — Linux / macOS
treeing-gui.exe                       # GUI — Windows

treeing-cli -i tree.txt -o ./out      # CLI — Linux / macOS
treeing-cli.exe -i tree.txt -o ./out  # CLI — Windows
treeing-cli --help                    # CLI help — Linux / macOS
treeing-cli.exe --help                # CLI help — Windows
```

### Build executables yourself

```bash
pip install -r requirements-build.txt
python build.py --target all          # outputs to dist/<platform>/
```

## Documentation

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for a unified guide covering source runs and prebuilt executables on Windows, macOS ARM, macOS x86, and Linux.

## Legal

- **Licence** — MIT; see [LICENSE](LICENSE).
- **Privacy Policy** — see [PRIVACY.md](PRIVACY.md).
- **Terms of Use** — see [TERMS.md](TERMS.md).

## AI Disclosure

Parts of this source code were written with assistance from AI coding tools.

# Treeing — User Guide

Treeing turns ASCII directory-tree text (for example the output of the `tree` command) into real folders and empty files.

This guide covers two ways of running Treeing:

- **Prebuilt executables** (no Python needed) for Windows, Linux, macOS ARM, and macOS x86.
- **From source** with Python 3.11+.

Both the **GUI** and the **CLI** are described below.

---

## 1. Get the app

### Option A — Download a prebuilt executable

1. Go to the [releases page](https://github.com/xiao-ming-b65536/treeing/releases).
2. Pick the archive that matches your platform:
   - `treeing-gui-windows-vX.Y.Z.zip` / `treeing-cli-windows-vX.Y.Z.zip` — Windows
   - `treeing-gui-linux-vX.Y.Z.tar.gz` / `treeing-cli-linux-vX.Y.Z.tar.gz` — Linux
   - `treeing-gui-macos-arm64-vX.Y.Z.tar.gz` / `treeing-cli-macos-arm64-vX.Y.Z.tar.gz` — macOS (Apple Silicon)
   - `treeing-gui-macos-x86_64-vX.Y.Z.tar.gz` / `treeing-cli-macos-x86_64-vX.Y.Z.tar.gz` — macOS (Intel)
3. Verify the download against `SHA256SUMS.txt` in the same release.

### Option B — Run from source

You need Python 3.11 or newer.

```bash
git clone https://github.com/xiao-ming-b65536/treeing.git
cd treeing
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Unix:    .venv/bin/activate
pip install -r requirements-build.txt   # only needed if you plan to build executables
```

Running from source needs no third-party packages — only the Python standard library (Tk for the GUI).

---

## 2. Run the GUI

### From source

```bash
python -m treeing.main
```

### Prebuilt executable

| Platform | Command |
|---|---|
| Windows | double-click `treeing-gui.exe`, or run `treeing-gui.exe` in a terminal |
| Linux | `./treeing-gui` |
| macOS ARM | `./treeing-gui` |
| macOS x86 | `./treeing-gui` |

#### macOS first-run note

macOS may block an unsigned binary with "Treeing cannot be opened because it is from an unidentified developer." To allow it:

```bash
xattr -dr com.apple.quarantine /path/to/treeing-gui
```

Then run it again.

#### Linux first-run note

```bash
chmod +x treeing-gui
./treeing-gui
```

If the GUI fails to start with a Tk error, install Tk:

```bash
sudo apt-get install python3-tk
```

### GUI basics

1. Paste or write an ASCII tree into the left box (or **Import text file** / drag-and-drop a `.txt`).
2. Click **🔍 Parse tree** (or press `Ctrl+Enter`). The recognised structure appears on the right.
3. Adjust options below the input box as needed (indent unit, strict directory inference, abort on conflict, etc.).
4. Click **📁 Generate directories/files** (or press `Ctrl+G`), choose the target folder, and confirm.

Grey italic items in the preview are *virtual* nodes and will not be written to disk.

---

## 3. Run the CLI

### From source

```bash
python -m treeing.main -i tree.txt -o ./out
```

### Prebuilt executable

| Platform | Command |
|---|---|
| Windows | `treeing-cli.exe -i tree.txt -o ./out` |
| Linux | `./treeing-cli -i tree.txt -o ./out` |
| macOS ARM | `./treeing-cli -i tree.txt -o ./out` |
| macOS x86 | `./treeing-cli -i tree.txt -o ./out` |

(On Unix, `chmod +x treeing-cli` once first; on macOS you may also need `xattr -dr com.apple.quarantine treeing-cli`.)

### Common commands

```bash
# Preview without writing anything
treeing-cli -i tree.txt -o ./out --dry-run

# Generate with interactive confirmation
treeing-cli -i tree.txt -o ./out --confirm

# Generate non-interactively (CI / scripts)
treeing-cli -i tree.txt -o ./out --yes --fail-on-conflict

# ASCII preview tree on stdout
treeing-cli -i tree.txt -o ./out --dry-run --format tree

# JSON output for scripts / agents
treeing-cli -i tree.txt -o ./out --yes --json --quiet

# Read from standard input
echo "project\n  src\n    main.py" | treeing-cli -p -o ./out --yes

# Help
treeing-cli --help           # short option list
treeing-cli --help-full      # full option details
treeing-cli help             # help topic list
treeing-cli help confirm     # a specific topic
treeing-cli --about          # about dialogue
```

### Reading a Windows `tree` dump

```cmd
tree /F /A > mytree.txt
treeing-cli.exe -i mytree.txt -o ./out --encoding cp1252
```

Use `--encoding cp1252` for legacy Windows (non-UTF-8) files; otherwise the default is UTF-8.

### Exit codes

- `0` — success (or user-cancelled with `--confirm`)
- `1` — failure
- `2` — success with parse/generation warnings (only with `--warn-exit-code`)

---

## 4. Build your own executables

If you want native binaries built from this source tree:

```bash
pip install -r requirements-build.txt
python build.py --target all          # builds both CLI and GUI
# outputs:
#   dist/windows/treeing-cli.exe, treeing-gui.exe       (Windows)
#   dist/linux/treeing-cli, treeing-gui                 (Linux)
#   dist/macos-arm64/treeing-cli, treeing-gui           (macOS Apple Silicon)
#   dist/macos-x86_64/treeing-cli, treeing-gui          (macOS Intel)
```

`python build.py --target cli` or `--target gui` builds only one of them.

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| GUI won't start: "could not initialise the GUI … Tcl/Tk runtime incomplete" | Install a full Tcl/Tk (e.g. `sudo apt-get install python3-tk` on Linux), or use the CLI instead. |
| Imported file shows garbled characters | Pick the right `--encoding` (CLI) or **File import encoding** (GUI), e.g. `cp1252`, `iso-8859-1`. |
| "Output directory is not writable" | Choose a folder you have write permission for, or pass a writable `-o` path. |
| Same name created twice | Enable **Abort on path conflict** (GUI) or `--fail-on-conflict` (CLI) to stop and roll back on duplicates. |
| Indentation looks wrong in the preview | Set the **Indent unit** (GUI) or `--indent-unit N` (CLI) to match the input, or leave it blank for auto-detect. |

---

## 6. Privacy

Treeing is a fully local, offline tool. It does not connect to the network, upload anything, or collect personal data. It only stores UI preferences (font size, last output directory, import encoding) under `~/.treeing/settings.json` in your home directory, to restore them on the next launch. Delete that file at any time to reset to defaults.

Full policy: [PRIVACY.md](../PRIVACY.md).

---

## 7. Licence

MIT — see [LICENSE](../LICENSE) in the repository root. Terms of Use: [TERMS.md](../TERMS.md).

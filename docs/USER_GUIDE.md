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

---

## Reference

### CLI options

| Option | Description |
|---|---|
| `-i`, `--input` | Input file path (ASCII tree text). Mutually exclusive with `-p` |
| `-o`, `--output` | Output root directory (default `.`; in scripts, specify it explicitly) |
| `-p`, `--paste` | Read from standard input (mutually exclusive with `-i`; prompt on stderr) |
| `--encoding ENC` | Input encoding (applies to both `-i` and `-p`; default `utf-8`) |
| `--no-fix` | Disable indentation auto-repair (same as GUI "Disable auto-repair") |
| `--strict-dirs` | Strict directory inference (same as GUI; branch lines default to directories) |
| `--indent-unit N` | Indent unit in characters (default: auto-detect) |
| `--allow-nested-names` | Treat `/` `\` in names as path segments and create levels (trusted input only) |
| `--fail-on-conflict` | Abort and roll back on duplicate paths or type conflicts (same as GUI) |
| `--fail-on-duplicate` | Deprecated; same as `--fail-on-conflict` |
| `--rollback-on-error` | Roll back files/directories created this run on write failure (default: keep partial results) |
| `--dry-run` | Preview only, do not write to disk (recommended for first use) |
| `--check-writable` | Extra check that the output directory is writable before generation |
| `--use-settings` | When `-o` is not given, read `last_generate_dir` from `~/.treeing/settings.json` |
| `--confirm` | Interactive confirm `[y/N]` before writing (needs TTY; mutually exclusive with `--yes`) |
| `-y`, `--yes` | Skip confirmation, treat as confirmed (CI / agent; mutually exclusive with `--confirm`) |
| `--json` | Output the result as a single-line JSON object to stdout |
| `--quiet` | Suppress stdout warnings and text summary (common with `--json`) |
| `--format {text,tree}` | `text` summary (default) or `tree` ASCII preview (same semantics as the GUI preview) |
| `--warn-exit-code` | Exit with code 2 when successful but with parse/generation warnings |
| `--warnings-file PATH` | Write all warnings to a UTF-8 file (one per line, prefixed `[parse]`/`[generate]`) |
| `--warn-limit N` | Maximum number of warnings shown in the terminal (default 10) |
| `--no-warn-limit` | Show all warnings in the terminal without truncation |
| `--strict` | Strict mode: equivalent to `--fail-on-conflict --no-fix` |
| `--version` | Show version |
| `--about` | Show about info (version, overview, licence, etc.) |
| `--help` | Short option list |
| `--help-full` | Detailed description of each option |
| `help <topic>` | Help on a topic (e.g. `help confirm`, `help json`) |

### Exit codes and automation

| Code | Meaning |
|---|---|
| `0` | Success; a `--confirm` answer of "no" (cancelled) also counts as `0` |
| `1` | Failure (read error, empty tree, generation exception, `--confirm` used without a TTY, etc.) |
| `2` | Success with parse/generation warnings (only with `--warn-exit-code`) |

Recommended pipeline: run `--dry-run --json --quiet` first, then `--yes` for the real run; always pass `-o` explicitly. In non-interactive environments use `--yes` or `TREEING_YES=1`, never `--confirm`.

### Output streams (stdout / stderr)

| Stream | Content |
|---|---|
| **stdout** | `[OK]` / `[DRY-RUN]` summary, `[WARN]` block, the implicit `-o` notice, and the single-line JSON when `--json` is set |
| **stderr** | The paste prompt, `[ERR]` errors, and the `--confirm` interaction |

When `-o` is not given and the current directory is the write target, a `[WARN]` line is printed to stdout before writing (suppressed under `--dry-run`); with `--json --quiet` it goes into the JSON's `implicit_output_warning` / `implicit_output_warning_message` fields.

### Parsing rules

**Supported input formats**

- **Unicode tree** — `├──`, `└──`, `│   ` (Linux/macOS `tree` default output).
- **Pipe style** — `|--`, `` `-- ``, etc.
- **Windows `tree`** — `+---`, `\---` (usually no trailing slash; inferred as directories heuristically).
- **Space-indented** — hand-written trees with no branch prefix (e.g. `  child/`).

**Directory vs file**

1. Explicit trailing slash: `src/` → directory.
2. Has children: any node with children is inferred as a directory.
3. Branch-line heuristic (default): a name with a `├──`-style prefix and no extension is treated as a directory unless it looks like a file — it has an extension (`a.py`), is a dotfile (`.gitignore`), or is a common filename (`Makefile`, `README`, `LICENSE`); names containing uppercase letters may be treated as files (e.g. `SubDir`).
4. Strict mode (`--strict-dirs` / GUI "Strict directory inference"): branch lines default to directories and the uppercase-letter rule is dropped; only extensions, dotfiles, and common filenames count as files.

**Skipped lines**

- Empty lines.
- Comment lines starting with `#` or `//`.
- Pure separator lines (`---`, `===`, etc.).
- Unrecognised lines (emitted as a warning and skipped).
- Root-level prose with no tree features.

**Path and generation behaviour**

- `.` root node: means the current directory; contents are generated directly under the target path.
- Multiple root nodes: allowed, with a warning.
- Duplicate paths, file/directory type conflicts, and children created under a file all produce warnings; `--fail-on-conflict` aborts and rolls back.
- Nested path names: by default `foo/bar` is flattened into a single name; `--allow-nested-names` creates the intermediate levels.
- Name cleaning: illegal characters are replaced; on Windows, overlong paths may use the `\\?\` prefix.

### CLI vs GUI

| Capability | CLI | GUI |
|---|---|---|
| Input encoding | `--encoding` applies to both file and paste | Encoding setting applies to **file import** only; pasted content is UTF-8 |
| Disable auto-repair | `--no-fix` | "Disable auto-repair" checkbox |
| Strict directory inference | `--strict-dirs` | "Strict directory inference" checkbox |
| Abort on path conflict | `--fail-on-conflict` | "Abort on path conflict" |
| Roll back on write failure | `--rollback-on-error` | None (partial results are kept) |
| Output writable check | `--check-writable` (opt-in) | Always checked before generation |
| Nested path names | `--allow-nested-names` | "Allow nested path names" |
| Preview | `--dry-run` + `--format tree` | Tree preview on the right after parsing |
| Generation confirmation | `--confirm` / `--yes` / `TREEING_YES` | Directory picker + confirm dialogue |
| Multi-file drag-and-drop | Not supported | Windows: only the **first** file is imported; the rest are noted as ignored in the status bar |

### Known limitations

- **`foo.txt` and `foo/` coexist**: each is independent at parse time; at generation the later one overwrites or triggers a conflict warning — they are not merged into one node.
- **Empty directory leaf**: a childless `emptydir` (no trailing slash) is still heuristically inferred as a directory in the default mode; add an extension or disable the heuristic if you want a file (strict mode only affects the uppercase rule; leaf inference still applies).
- **Whitelist filenames**: extensionless names such as `README` and `Makefile` are always treated as files, even on branch lines.
- **Hand-written indentation**: use multiples of 2 or 4; irregular indentation triggers auto-repair or virtual-node insertion.

### Settings file

GUI preferences (font size, last output directory, import encoding) are stored in `~/.treeing/settings.json` (UTF-8 text).

| OS | Path |
|---|---|
| Windows | `C:\Users\<user>\.treeing\settings.json` |
| macOS | `/Users/<user>/.treeing/settings.json` |
| Linux | `/home/<user>/.treeing/settings.json` |

You may edit the file directly with a text editor, but only while the application is closed — a running app will overwrite it on exit. Editable fields: `font_size` (8–24), `last_generate_dir` (also read by the CLI's `--use-settings`), `import_encoding` (default encoding), `import_encodings` (the drop-down presets; add or remove entries). Deleting the file resets to defaults.

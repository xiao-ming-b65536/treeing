"""treeing/cli_entry.py

PyInstaller CLI entry point.
Does not import tkinter, which suits a minimal build; calls cli_main directly and handles ConfigError.
"""
import sys

from treeing.cli.main import cli_main
from treeing.config import ConfigError

if __name__ == '__main__':
    try:
        sys.exit(cli_main())
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

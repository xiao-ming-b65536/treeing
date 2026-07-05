#!/usr/bin/env python3
"""treeing/main.py

Unified entry script for development.
Starts the GUI with no arguments, or runs the CLI with arguments; a ConfigError is caught and reported with a non-zero exit code.
"""
import sys

from treeing.cli.main import cli_main
from treeing.config import ConfigError
from treeing.gui_entry import run_gui

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            sys.exit(cli_main())
        else:
            run_gui()
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

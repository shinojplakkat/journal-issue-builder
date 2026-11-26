"""Command-line entry point: `python -m issuebuilder <command>`."""

import argparse
import sys

from . import __version__
from .doctor import run_doctor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="issuebuilder", description="Journal Issue Builder")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("doctor", help="check that the required programs and libraries are installed")

    commands.add_parser("gui", help="open the program window (the default)")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return run_doctor()
    from .gui.app import main as gui_main  # Qt is loaded only when the window is needed

    return gui_main()


if __name__ == "__main__":
    sys.exit(main())

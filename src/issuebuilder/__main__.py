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

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return run_doctor()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

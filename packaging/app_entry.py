"""Start-up script for the packaged program (PyInstaller)."""

import sys
import tempfile
import traceback
from pathlib import Path

if __name__ == "__main__":
    args = sys.argv[1:] or ["gui"]
    try:
        from issuebuilder.__main__ import main

        sys.exit(main(args))
    except SystemExit:
        raise
    except BaseException:
        # The Windows program has no console: keep the error in a file so it can be reported.
        text = traceback.format_exc()
        target = Path(args[args.index("--report") + 1]) if "--report" in args[:-1] else \
            Path(tempfile.gettempdir()) / "journal-issue-builder-error.txt"
        target.write_text(text, encoding="utf-8")
        if args[0] != "gui":
            sys.exit(2)
        raise

"""
Allows `python3 -m cda <command>` as a fallback when the `cda` binary
is not yet on PATH (e.g. immediately after `pip install code-data-ark`).

    python3 -m cda setup
"""
from cda.ui.cli import main

if __name__ == "__main__":
    main()

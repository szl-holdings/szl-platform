"""Module entry point so ``python -m szl_alignment`` works.

Keep this file trivial: all logic lives in :mod:`szl_alignment.cli`.
"""

from szl_alignment.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

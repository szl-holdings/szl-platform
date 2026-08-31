"""Module entry point: ``python -m szl_payload [stage] [--json]``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

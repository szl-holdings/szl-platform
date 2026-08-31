"""Entry point for ``python -m szl_beacon``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

"""Compatibility alias so the doctrine's documented invocation works verbatim.

The builder contract (Phase B / Codex hand-off) names the entry point
``python -m szl_payload.build [generate|compile|extract|export|verify|all]``.
The implementation lives in :mod:`szl_payload.cli`; this module only forwards.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

"""Test bootstrap: make the src-layout package importable without installing.

Tests must run offline straight from a clone (python -m pytest
packages/szl-iso42001), before any `pip install -e`. Inserting src/ here keeps
that true; it is a no-op once the package is properly installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

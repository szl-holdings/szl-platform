"""szl-iso42001 — free, offline ISO/IEC 42001 + EU AI Act Art. 50 readiness checker.

Public API surface. Everything here is re-exported from the module that owns
it, so `from szl_iso42001 import X` always works and internal structure stays
refactorable. No import-time side effects beyond parsing (the corpus parses
lazily on first load_controls() call).
"""

from __future__ import annotations

__version__ = "0.1.0"

from .controls import (
    ANSWER_KINDS,
    BANDS,
    DISCLAIMER,
    INSTRUMENTS,
    Control,
    controls_by_domain,
    controls_by_id,
    instruments,
    load_controls,
)
from .report import render_report
from .score import (
    BAND_NOT_READY,
    BAND_PARTIAL,
    BAND_READY,
    ScoreResult,
    score_answers,
)

__all__ = [
    "ANSWER_KINDS",
    "BANDS",
    "BAND_NOT_READY",
    "BAND_PARTIAL",
    "BAND_READY",
    "DISCLAIMER",
    "INSTRUMENTS",
    "Control",
    "ScoreResult",
    "__version__",
    "controls_by_domain",
    "controls_by_id",
    "instruments",
    "load_controls",
    "render_report",
    "score_answers",
]

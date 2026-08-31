"""Shared fixtures: the sample claims file and store/app builders over it."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_CLAIMS = FIXTURES / "claims.sample.json"


@pytest.fixture
def sample_claims_path() -> Path:
    """The checked-in sample claims file: one PASS, one DRIFT, one UNKNOWN."""
    return SAMPLE_CLAIMS


@pytest.fixture
def missing_claims_path(tmp_path: Path) -> Path:
    """A path where no claims file exists."""
    return tmp_path / "no-such-dir" / "claims.json"

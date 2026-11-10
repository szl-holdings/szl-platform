from __future__ import annotations

from pathlib import Path


MAKEFILE = Path(__file__).resolve().parents[3] / "Makefile"


def _target_body(name: str) -> str:
    lines = MAKEFILE.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"{name}:")
    body = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(("\t", " ")):
            break
        body.append(line)
    return "\n".join(body)


def test_audit_propagates_failures() -> None:
    body = _target_body("audit")
    assert "szl_estate.audit" in body
    assert "|| true" not in body


def test_doctor_propagates_failures() -> None:
    body = _target_body("doctor")
    assert "szl_estate.doctor" in body
    assert "|| true" not in body

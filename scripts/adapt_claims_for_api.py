#!/usr/bin/env python3
"""Adapt szl-estate verify-claims output to the szl-claims-api store schema.

The estate tool writes {"results": [...], "findings": [...]} with quoted
expectations; the API store wants a bare list with typed `expected` plus
`last_run`. This is the documented boundary between the recomputation engine
and the serving layer — run it after every verify-claims pass.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "artifacts" / "claims" / "claims.json"
DST = ROOT / "run" / "artifacts" / "claims" / "claims.json"


def main() -> int:
    e = json.loads(SRC.read_text())
    mtime = (
        datetime.datetime.fromtimestamp(os.path.getmtime(SRC), datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    out = [
        {
            "claim_id": r["claim_id"],
            "description": r["description"],
            "source": r["source"],
            "expected": r.get("expected_quoted") or r.get("expected"),
            "observed": r["observed"],
            "verdict": r["verdict"],
            "evidence": r["evidence"],
            # last_run is honest: set only for claims actually recomputed in that run
            "last_run": mtime if r["observed"] is not None else None,
        }
        for r in e["results"]
    ]
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, indent=2))
    print(f"adapted {len(out)} claims -> {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

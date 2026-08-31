#!/usr/bin/env python3
"""Link check for the proof surface: every internal asset referenced by
index.html (fetch() paths in assets/app.js, href/src attributes, anchors)
must resolve on the local server. External links are reported, not fetched.
Run: python3 scripts/check_links.py [--base http://localhost:8137/]
Exits non-zero on any 404 or unresolved internal reference."""
from __future__ import annotations

import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "http://localhost:8137/"

failures: list[str] = []
local_hits: list[str] = []


def check_url(url: str, why: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            code = res.status
    except Exception as exc:
        code = str(exc)
    if code != 200:
        failures.append(f"{url}  -> {code}  ({why})")
    else:
        local_hits.append(f"{url}  ({why})")


def check_file(rel: str, why: str) -> None:
    p = SITE / rel
    if not p.is_file():
        failures.append(f"missing on disk: {rel}  ({why})")


html = (SITE / "index.html").read_text(encoding="utf-8")
js = (SITE / "assets" / "app.js").read_text(encoding="utf-8")

# 1. fetch() paths in app.js
for m in sorted(set(re.findall(r'"(data/[A-Za-z0-9._\-/]+)"', js))):
    check_url(BASE + m, "fetch() in app.js")
check_url(BASE + "index.html", "page digest fetch")

# 2. href/src in index.html
class P(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ("href", "src") and v:
                if v.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                if ".." in v:
                    # repo-browsing relative link (out of the served tree):
                    # verify it exists on disk relative to index.html
                    target = (SITE / v.split("#")[0]).resolve()
                    if not target.is_file():
                        failures.append(f"missing on disk: {v} ({tag} {k})")
                    else:
                        local_hits.append(f"{v} (Disk OK, repo-relative)")
                    continue
                check_url(BASE + v, f"{tag} {k}")

P().feed(html)

# 3. in-page anchors resolve to ids
anchors = set(re.findall(r'href="#([^"]+)"', html))
ids = set(re.findall(r'id="([^"]+)"', html))
for a in sorted(anchors):
    if a not in ids:
        failures.append(f"anchor #{a} has no matching id in index.html")

# 4. every section anchor fetched with fragment
for sec in ["#proof-explorer", "#estate-audit", "#kids", "#standards", "#doctrine"]:
    if sec[1:] in ids:
        check_url(BASE + "index.html" + sec, "section anchor")
    else:
        failures.append(f"missing section id {sec}")

print(f"checked {len(local_hits)} internal references")
for f in failures:
    print("FAIL:", f)
print("ALL INTERNAL REFERENCES RESOLVE" if not failures else f"{len(failures)} FAILURES")
sys.exit(1 if failures else 0)

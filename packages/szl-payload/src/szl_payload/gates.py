"""Compile gates — everything the build must prove before it may emit.

Four gate classes run over the sections and/or the built output:

1. ``must_contain`` — every per-section token assertion must be present in
   the section text.
2. Forbidden patterns — regexes from ``lint/forbidden.txt`` scanned over the
   built output, plus the compound ``proxied_pages_apex`` rule (a proxy flag
   near a ``185.199.*`` Pages address) enforced in code, by contract.
3. Banned claims — regexes from ``lint/banned_claims.txt`` (matched
   case-insensitively), plus the proximity rule: the standalone word
   "signed" within 200 characters of an ``unsigned.json`` reference.
4. ``require_dns_first`` — ``phase_neg1_dns`` must precede every section
   whose id contains ``train``.

Every finding carries a human-readable location (file:line where one exists)
because a gate that cannot point at its evidence trains operators to ignore
gates.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from .manifest import Manifest, ManifestError

# ---------------------------------------------------------------------------
# Compound-rule constants (by contract: enforced in code, not in lint files)
# ---------------------------------------------------------------------------

#: Forbidden-domain regex — compiled here so verify() can grep all of dist/.
#: The negative lookbehind keeps hyphen-prefixed canonical labels such as
#: a-11oy.com and a-11-oy.com from tripping the gate.
FORBIDDEN_DOMAIN_PATTERN = r"(?<!-)a11oy\.com"
FORBIDDEN_DOMAIN_RE = re.compile(FORBIDDEN_DOMAIN_PATTERN)

#: proxied_pages_apex component patterns kept as string literals so this
#: source file itself never trips the forbidden-patterns gate. Matches
#: proxied:true, proxied = true, and the JSON form with a quoted key.
PROXIED_FLAG_RE = re.compile(r'"?proxied"?' + r"\s*[:=]\s*" + r"true", re.IGNORECASE)
PAGES_APEX_RE = re.compile(r"185\.199\.")

#: Proximity window (characters) for the proxied_pages_apex compound rule.
PROXIED_APEX_WINDOW = 200


@dataclasses.dataclass(frozen=True)
class Finding:
    """One gate finding: where, which gate, what was found."""

    gate: str
    location: str  # "file:line" when known, otherwise a section/file label
    message: str

    def render(self) -> str:
        return f"[{self.gate}] {self.location}: {self.message}"


class GateViolation(Exception):
    """Raised when any gate fails. Carries every finding from the run."""

    def __init__(self, findings: list[Finding]) -> None:
        self.findings = list(findings)
        summary = "\n".join(f.render() for f in self.findings)
        super().__init__(
            f"{len(self.findings)} gate finding(s):\n{summary}"
            if self.findings
            else "gate violation with no findings"
        )


def _line_number(text: str, offset: int) -> int:
    """1-based line number of character *offset* in *text*."""
    return text.count("\n", 0, offset) + 1


def check_must_contain(
    section_id: str, path: str, tokens: tuple[str, ...], text: str
) -> list[Finding]:
    """Assert every must_contain token is present verbatim in *text*."""
    findings = []
    for token in tokens:
        if token not in text:
            findings.append(
                Finding(
                    gate="must_contain",
                    location=f"{path} (section {section_id})",
                    message=f"missing required token: {token!r}",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# lint-file loading
# ---------------------------------------------------------------------------


def load_lint_lines(path: Path) -> list[str]:
    """Load a lint file: one rule per line, '#' comments and blanks ignored."""
    if not path.is_file():
        raise ManifestError(f"lint file not found: {path}")
    rules = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            rules.append(line)
    return rules


def split_banned_claims(lines: list[str]) -> tuple[list[str], int | None]:
    """Split banned-claims rules into plain regexes and the proximity rule.

    The proximity directive — ``signed within 200 chars of unsigned\\.json``
    — is enforced in code per the contract; it is recognized by literal
    prefix and its window parsed from the digits in the rule. Returns
    ``(regexes, proximity_window_or_None)``.
    """
    regexes = []
    proximity: int | None = None
    for line in lines:
        match = re.match(r"^signed within (\d+) chars of unsigned", line)
        if match:
            proximity = int(match.group(1))
        else:
            regexes.append(line)
    return regexes, proximity


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------


def check_regexes(
    text: str,
    label: str,
    rules: list[str],
    gate: str,
    *,
    flags: int = 0,
) -> list[Finding]:
    """Scan *text* for every regex in *rules*; one finding per match."""
    findings = []
    for rule in rules:
        try:
            pattern = re.compile(rule, flags)
        except re.error as exc:
            # A broken lint rule is a defect in the gate itself — fail closed.
            findings.append(
                Finding(gate=gate, location=label, message=f"invalid lint regex {rule!r}: {exc}")
            )
            continue
        for match in pattern.finditer(text):
            line = _line_number(text, match.start())
            snippet = match.group(0)
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            findings.append(
                Finding(
                    gate=gate,
                    location=f"{label}:{line}",
                    message=f"pattern {rule!r} matched {snippet!r}",
                )
            )
    return findings


def check_proxied_pages_apex(text: str, label: str) -> list[Finding]:
    """Compound rule: a proxied flag near a 185.199.* Pages apex address.

    Enforced in code (per the builder contract) because it is a two-pattern
    conjunction: the orange-cloud-on-apex bug exists only when a record sets
    the proxy flag AND points at a GitHub Pages apex address. Either pattern
    alone — a proxied record elsewhere, or a grey-cloud Pages record — is
    legitimate and must not fire.
    """
    findings = []
    proxied_positions = [m.start() for m in PROXIED_FLAG_RE.finditer(text)]
    apex_positions = [m.start() for m in PAGES_APEX_RE.finditer(text)]
    if not proxied_positions or not apex_positions:
        return findings
    for pos in proxied_positions:
        for a_pos in apex_positions:
            if abs(pos - a_pos) <= PROXIED_APEX_WINDOW:
                line = _line_number(text, pos)
                apex_line = _line_number(text, a_pos)
                findings.append(
                    Finding(
                        gate="proxied_pages_apex",
                        location=f"{label}:{line}",
                        message=(
                            "proxied flag near 185.199.* Pages apex address "
                            f"(address at line {apex_line}) — orange-cloud-on-apex bug"
                        ),
                    )
                )
                break
    return findings


def check_signed_unsigned_proximity(text: str, label: str, window: int) -> list[Finding]:
    """'signed' (standalone word) must not appear within *window* chars of
    an unsigned.json reference — an unattested artifact must never be
    described as carrying a signature."""
    findings = []
    signed_positions = [m.start() for m in re.finditer(r"\bsigned\b", text, re.IGNORECASE)]
    unsigned_positions = [m.start() for m in re.finditer(r"unsigned\.json", text)]
    if not signed_positions or not unsigned_positions:
        return findings
    for pos in signed_positions:
        for u_pos in unsigned_positions:
            if abs(pos - u_pos) < window:
                line = _line_number(text, pos)
                findings.append(
                    Finding(
                        gate="banned_claims_proximity",
                        location=f"{label}:{line}",
                        message=(
                            f"'signed' appears {abs(pos - u_pos)} chars from an "
                            f"unsigned.json reference (limit {window})"
                        ),
                    )
                )
                break
    return findings


def check_dns_first(section_ids: tuple[str, ...]) -> list[Finding]:
    """require_dns_first: phase_neg1_dns precedes every 'train' section."""
    if "phase_neg1_dns" not in section_ids:
        return [
            Finding(
                gate="require_dns_first",
                location="manifest.toml",
                message="section 'phase_neg1_dns' is absent from the manifest",
            )
        ]
    dns_index = section_ids.index("phase_neg1_dns")
    findings = []
    for index, section_id in enumerate(section_ids):
        if "train" in section_id and index < dns_index:
            findings.append(
                Finding(
                    gate="require_dns_first",
                    location="manifest.toml",
                    message=(
                        f"train section {section_id!r} (position {index}) precedes "
                        f"phase_neg1_dns (position {dns_index}) — DNS-first is doctrine"
                    ),
                )
            )
    return findings


def require_clean(findings: list[Finding]) -> None:
    """Raise GateViolation if *findings* is non-empty."""
    if findings:
        raise GateViolation(findings)


def run_output_gates(manifest: Manifest, document: str, label: str) -> list[Finding]:
    """Run every gate that operates on the built output document.

    Returns the full finding list (empty when clean); callers decide whether
    to report or raise so verify() can inspect findings without aborting.
    """
    findings: list[Finding] = []
    forbidden = load_lint_lines(manifest.root / manifest.forbidden_patterns_path)
    findings += check_regexes(document, label, forbidden, gate="forbidden")
    findings += check_proxied_pages_apex(document, label)

    banned_lines = load_lint_lines(manifest.root / manifest.banned_claims_path)
    banned_regexes, proximity = split_banned_claims(banned_lines)
    findings += check_regexes(
        document, label, banned_regexes, gate="banned_claims", flags=re.IGNORECASE
    )
    if proximity is not None:
        findings += check_signed_unsigned_proximity(document, label, proximity)
    return findings


def run_section_gates(
    manifest: Manifest, section_texts: dict[str, tuple[str, str]]
) -> list[Finding]:
    """Run gates tied to section structure: must_contain + require_dns_first.

    *section_texts* maps section id → (source path, text).
    """
    findings: list[Finding] = []
    for section in manifest.sections:
        path, text = section_texts[section.id]
        findings += check_must_contain(section.id, path, section.must_contain, text)
    if manifest.require_dns_first:
        findings += check_dns_first(manifest.section_ids)
    return findings

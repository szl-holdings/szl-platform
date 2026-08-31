"""Extract — turn ``<!-- extract: ... -->`` tags in the payload into files.

The built document carries scaffold files inline as extract tags: an HTML
comment of the form::

    <!-- extract: <relpath> mode=<octal> -->

immediately followed by a fenced code block. This module writes each block
to ``dist/extracted/<relpath>`` with the given mode and reports a sha256 per
written file.

SECURITY: this document gets fed to agents. The extract path is a trust
boundary, so validation runs over ALL tags before ANY byte is written:

* ``..`` anywhere in the path parts → rejected (directory escape).
* absolute paths → rejected.
* mode outside 0o000..0o777 → rejected.
* duplicate target paths → rejected (ambiguous document).

A rejected tag aborts the whole extract with ExtractError; partial scaffolds
are never left on disk by a poisoned document.
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path, PurePosixPath

from .builder import sha256_bytes

#: Tag syntax: <!-- extract: <relpath> mode=<octal> --> then a fenced block.
#: The body is everything between the opening fence line and the line that
#: closes it; the closing fence must start at the beginning of a line.
EXTRACT_RE = re.compile(
    r"<!--\s*extract:\s*(?P<path>\S+?)\s+mode=(?P<mode>[0-7]{3,4})\s*-->\s*\n"
    r"```[^\n]*\n"
    r"(?P<body>.*?)"
    r"\n```[ \t]*(?=\n|$)",
    re.DOTALL,
)

EXTRACT_DIR_NAME = "extracted"


class ExtractError(Exception):
    """Extract failure — path escape, bad mode, duplicate target, or I/O."""


@dataclasses.dataclass(frozen=True)
class ExtractedFile:
    """One written scaffold file: its relative path, mode, and sha256."""

    relpath: str
    mode: int
    sha256: str


@dataclasses.dataclass(frozen=True)
class _Tag:
    """A parsed extract tag before validation."""

    relpath: str
    mode_text: str
    body: str


def find_tags(document: str) -> list[_Tag]:
    """Parse every extract tag in *document* (no validation, no I/O)."""
    return [
        _Tag(relpath=m.group("path"), mode_text=m.group("mode"), body=m.group("body"))
        for m in EXTRACT_RE.finditer(document)
    ]


def _validate_tag(tag: _Tag) -> int:
    """Validate one tag; return its mode as an int. Raises ExtractError."""
    pure = PurePosixPath(tag.relpath)
    # Extract-path escape check: this document gets fed to agents, so any
    # attempt to climb out of dist/extracted or to write an absolute path is
    # a hard rejection, not a sanitize-and-continue.
    if ".." in pure.parts:
        raise ExtractError(f"extract path escape rejected ('..' in path): {tag.relpath!r}")
    if pure.is_absolute():
        raise ExtractError(f"extract path escape rejected (absolute path): {tag.relpath!r}")
    if not tag.relpath or tag.relpath.endswith("/"):
        raise ExtractError(f"extract path must name a file: {tag.relpath!r}")
    mode = int(tag.mode_text, 8)
    if mode > 0o777:
        raise ExtractError(f"extract mode {tag.mode_text!r} exceeds 0o777: {tag.relpath!r}")
    return mode


def extract_document(document: str, dest_dir: Path) -> list[ExtractedFile]:
    """Validate all tags, then write all scaffold files under *dest_dir*.

    Returns one ExtractedFile per tag, in document order. Writes are
    deterministic: the file body is the fenced block verbatim plus a single
    trailing newline.
    """
    tags = find_tags(document)
    # Validate everything before writing anything — a poisoned document must
    # not leave a partial scaffold behind.
    modes = [_validate_tag(tag) for tag in tags]
    seen: set[str] = set()
    for tag in tags:
        if tag.relpath in seen:
            raise ExtractError(f"duplicate extract target: {tag.relpath!r}")
        seen.add(tag.relpath)

    written: list[ExtractedFile] = []
    for tag, mode in zip(tags, modes, strict=True):
        target = dest_dir.joinpath(*PurePosixPath(tag.relpath).parts)
        body_bytes = (tag.body + "\n").encode("utf-8")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body_bytes)
            os.chmod(target, mode)
        except OSError as exc:
            raise ExtractError(f"cannot write {target}: {exc}") from exc
        written.append(
            ExtractedFile(relpath=tag.relpath, mode=mode, sha256=sha256_bytes(body_bytes))
        )
    return written


def extract_payload(payload_path: Path, dist_dir: Path) -> list[ExtractedFile]:
    """Extract every scaffold file from the built payload into dist/extracted/."""
    if not payload_path.is_file():
        raise ExtractError(f"payload not found: {payload_path} — run compile first")
    document = payload_path.read_text(encoding="utf-8")
    return extract_document(document, dist_dir / EXTRACT_DIR_NAME)

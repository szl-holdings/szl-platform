"""Fleet configuration schema + validator.

Ships with ``fleet/fleet.yaml``: a 50-unit REFERENCE fleet across maritime,
disaster, and legal groupings. Reference only. Zero units deployed. Not a
claim of fielded hardware.

Schema:

  * ``node_id``            unique string
  * ``role``               FIELD | RELAY | OPERATOR
  * ``region``             grouping string (maritime | disaster | legal, or
                           another declared region)
  * ``sync_window_minutes``integer, 5..120 — how often the node tries to
                           sync; offline-first means this is a window, not
                           a guarantee
  * ``witness_groups``     list of witness group names the node belongs to

Validator rules (fail closed):

  * node ids unique;
  * every role in {FIELD, RELAY, OPERATOR};
  * every FIELD node is in >= 1 witness group, and across its groups has
    >= 2 DISTINCT witness classes available (it cannot serve outcome
    verification otherwise);
  * every referenced witness group is defined;
  * sync windows in 5..120 minutes.

YAML SUBSET PARSER — READ THIS.
    This package is stdlib-only, so :func:`parse_yaml_subset` implements a
    deliberately small YAML subset: block mappings, block sequences,
    inline flow lists, plain/quoted scalars, integers, and comments. It is
    sufficient for ``fleet/fleet.yaml`` and configs of the same shape; it
    is NOT a YAML 1.2 parser. Production deployments load the same files
    with a conformant parser (e.g. PyYAML/ruamel). Anything outside the
    subset raises ``YamlSubsetError`` — fail closed, never a silent
    mis-parse.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .witness import WitnessClass

__all__ = [
    "ROLES",
    "SYNC_WINDOW_MAX",
    "SYNC_WINDOW_MIN",
    "YamlSubsetError",
    "load_fleet",
    "parse_yaml_subset",
    "validate_fleet",
]

ROLES = frozenset({"FIELD", "RELAY", "OPERATOR"})
SYNC_WINDOW_MIN = 5
SYNC_WINDOW_MAX = 120

_INT_RE = re.compile(r"-?\d+$")


class YamlSubsetError(ValueError):
    """The input is outside the supported YAML subset. Fail closed."""


# ------------------------------------------------------------------- parser


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment unless inside brackets or quotes."""

    depth = 0
    quote: str | None = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        elif char == "#" and depth == 0 and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _scalar(text: str) -> Any:
    text = text.strip()
    if not text:
        raise YamlSubsetError("empty scalar value")
    if text[0] in "\"'":
        if len(text) < 2 or text[-1] != text[0]:
            raise YamlSubsetError(f"unterminated quoted scalar: {text!r}")
        return text[1:-1]
    if _INT_RE.match(text):
        return int(text)
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~"):
        return None
    return text


def _flow_list(text: str) -> list[Any]:
    """Parse ``[a, b, c]`` — flat scalar flow lists only."""

    text = text.strip()
    if not (text.startswith("[") and text.endswith("]")):
        raise YamlSubsetError(f"not a flow list: {text!r}")
    inner = text[1:-1].strip()
    if not inner:
        return []
    return [_scalar(part) for part in inner.split(",")]


def _value(text: str) -> Any:
    text = text.strip()
    if text.startswith("["):
        return _flow_list(text)
    return _scalar(text)


class _Line:
    __slots__ = ("indent", "content", "lineno")

    def __init__(self, indent: int, content: str, lineno: int) -> None:
        self.indent = indent
        self.content = content
        self.lineno = lineno


def _tokenize(text: str) -> list[_Line]:
    lines: list[_Line] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise YamlSubsetError(f"line {lineno}: tabs not allowed for indentation")
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        lines.append(_Line(indent, stripped.strip(), lineno))
    return lines


def parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the supported YAML subset. Raises :class:`YamlSubsetError`."""

    lines = _tokenize(text)
    if not lines:
        return {}
    result, pos = _parse_block(lines, 0, lines[0].indent)
    if pos != len(lines):
        raise YamlSubsetError(f"unexpected content at line {lines[pos].lineno}")
    if not isinstance(result, dict):
        raise YamlSubsetError("top level of a fleet config must be a mapping")
    return result


def _parse_block(lines: list[_Line], pos: int, indent: int) -> tuple[Any, int]:
    if not lines or pos >= len(lines) or lines[pos].indent < indent:
        return {}, pos
    if lines[pos].content.startswith("- "):
        return _parse_sequence(lines, pos, lines[pos].indent)
    return _parse_mapping(lines, pos, lines[pos].indent)


def _parse_sequence(lines: list[_Line], pos: int, indent: int) -> tuple[list, int]:
    items: list[Any] = []
    while (
        pos < len(lines)
        and lines[pos].indent == indent
        and lines[pos].content.startswith("- ")
    ):
        line = lines[pos]
        rest = line.content[2:].strip()
        pos += 1
        if not rest:
            item, pos = _parse_block(lines, pos, indent + 1)
            items.append(item)
            continue
        if ":" in rest and not rest.startswith(("'", '"')):
            # Inline mapping start: "- key: value" with continuation keys
            # indented under the dash.
            key, _, value = rest.partition(":")
            item: dict[str, Any] = {}
            if value.strip():
                item[key.strip()] = _value(value)
            else:
                nested, pos = _parse_block(lines, pos, indent + 2)
                item[key.strip()] = nested
            while (
                pos < len(lines)
                and lines[pos].indent > indent
                and not lines[pos].content.startswith("- ")
            ):
                cont = lines[pos]
                ckey, sep, cvalue = cont.content.partition(":")
                if not sep:
                    raise YamlSubsetError(f"line {cont.lineno}: expected 'key: value'")
                if cvalue.strip():
                    item[ckey.strip()] = _value(cvalue)
                else:
                    nested, pos = _parse_block(lines, pos, cont.indent + 2)
                    item[ckey.strip()] = nested
                    continue
                pos += 1
            items.append(item)
        else:
            items.append(_value(rest))
    return items, pos


def _parse_mapping(lines: list[_Line], pos: int, indent: int) -> tuple[dict, int]:
    result: dict[str, Any] = {}
    while pos < len(lines) and lines[pos].indent == indent:
        line = lines[pos]
        if line.content.startswith("- "):
            break
        key, sep, value = line.content.partition(":")
        if not sep:
            raise YamlSubsetError(f"line {line.lineno}: expected 'key: value'")
        key = key.strip()
        if not key:
            raise YamlSubsetError(f"line {line.lineno}: empty mapping key")
        pos += 1
        if value.strip():
            result[key] = _value(value)
        else:
            if pos < len(lines) and lines[pos].indent > indent:
                nested, pos = _parse_block(lines, pos, lines[pos].indent)
                result[key] = nested
            else:
                result[key] = None
    return result, pos


# --------------------------------------------------------------- validation


def load_fleet(path: Path | str) -> dict[str, Any]:
    """Load a fleet YAML file (subset parser). Raises on read/parse errors."""

    text = Path(path).read_text(encoding="utf-8")
    return parse_yaml_subset(text)


def _catalog_classes(groups: dict[str, Any]) -> dict[str, set[str]]:
    catalog: dict[str, set[str]] = {}
    for name, classes in (groups or {}).items():
        catalog[name] = {str(c) for c in (classes or [])}
    return catalog


def validate_fleet(config: dict[str, Any]) -> dict[str, Any]:
    """Validate a parsed fleet config. Returns a report; never raises.

    Report::

        {"ok": bool, "node_count": int, "findings": [{"code", "detail"}]}
    """

    findings: list[dict[str, str]] = []

    def fail(code: str, detail: str) -> None:
        findings.append({"code": code, "detail": detail})

    nodes = config.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail("NO_NODES", "fleet config must define a non-empty 'nodes' list")
        nodes = []

    groups = config.get("witness_groups")
    if not isinstance(groups, dict) or not groups:
        fail("NO_WITNESS_GROUPS", "fleet config must define 'witness_groups'")
        groups = {}

    class_catalog = _catalog_classes(groups)
    for name in groups:
        unknown = class_catalog[name] - {c.value for c in WitnessClass}
        if unknown:
            fail("UNKNOWN_WITNESS_CLASS", f"group {name}: unknown classes {sorted(unknown)}")
        if len(class_catalog[name]) < 2:
            fail(
                "WITNESS_GROUP_TOO_THIN",
                f"group {name}: fewer than 2 distinct witness classes",
            )

    seen_ids: set[str] = set()
    field_nodes = 0
    for index, node in enumerate(nodes):
        tag = node.get("node_id", f"<index {index}>") if isinstance(node, dict) else f"<{index}>"
        if not isinstance(node, dict):
            fail("BAD_NODE", f"node #{index} is not a mapping")
            continue
        node_id = node.get("node_id")
        if not node_id or not isinstance(node_id, str):
            fail("BAD_NODE_ID", f"node #{index}: missing/invalid node_id")
            continue
        if node_id in seen_ids:
            fail("DUPLICATE_NODE_ID", f"duplicate node_id {node_id!r}")
        seen_ids.add(node_id)

        role = node.get("role")
        if role not in ROLES:
            fail("BAD_ROLE", f"node {tag}: role must be one of {sorted(ROLES)}, got {role!r}")

        if not node.get("region") or not isinstance(node.get("region"), str):
            fail("BAD_REGION", f"node {tag}: region must be a non-empty string")

        window = node.get("sync_window_minutes")
        if not isinstance(window, int) or isinstance(window, bool):
            fail("BAD_SYNC_WINDOW", f"node {tag}: sync_window_minutes must be an integer")
        elif not (SYNC_WINDOW_MIN <= window <= SYNC_WINDOW_MAX):
            fail(
                "BAD_SYNC_WINDOW",
                f"node {tag}: sync_window_minutes {window} outside "
                f"{SYNC_WINDOW_MIN}..{SYNC_WINDOW_MAX}",
            )

        membership = node.get("witness_groups") or []
        if isinstance(membership, str):
            membership = [membership]
        if not isinstance(membership, list):
            fail("BAD_WITNESS_GROUPS", f"node {tag}: witness_groups must be a list")
            membership = []
        for group in membership:
            if group not in class_catalog:
                fail("UNKNOWN_WITNESS_GROUP", f"node {tag}: unknown witness group {group!r}")

        if role == "FIELD":
            field_nodes += 1
            available: set[str] = set()
            for group in membership:
                available |= class_catalog.get(group, set())
            if not membership:
                fail(
                    "FIELD_WITHOUT_GROUP",
                    f"FIELD node {tag}: must belong to >= 1 witness group",
                )
            elif len(available) < 2:
                fail(
                    "FIELD_WITHOUT_DIVERSITY",
                    f"FIELD node {tag}: only {len(available)} distinct witness "
                    "class(es) available; >= 2 required",
                )

    return {
        "ok": not findings,
        "node_count": len(nodes),
        "field_nodes": field_nodes,
        "witness_groups": sorted(class_catalog),
        "findings": findings,
    }

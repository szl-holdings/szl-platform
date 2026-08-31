"""Evidence labels for the A11oy Beacon REALITY PROTOCOL.

Every Reality Protocol event MUST carry exactly one evidence label. Labels are
the honesty surface of the protocol: they tell a reader — human or machine —
what kind of authority stands behind a record. A label is metadata about
provenance; it is never a verdict computed from content.

Honesty doctrine (non-negotiable):
  * Unknown, unavailable, unverified, and failed states stay explicit.
    Nothing here ever promotes a weaker label to a stronger one.
  * Machine-originated content is HARD-TYPED ``MACHINE_INFERENCE`` and is
    never rendered as, or merged into, official authority content.
  * ``CONFLICTING_EVIDENCE`` and ``UNVERIFIED`` are first-class labels, not
    error states to be hidden.

The label enum mirrors the Rev A UX requirement in the Beacon RFQ: every
consequential record is labeled VERIFIED SOURCE / AUTHORIZED OPERATOR /
COMMUNITY REPORT / MACHINE INFERENCE / CONFLICTING EVIDENCE / UNVERIFIED /
OUTCOME VERIFIED.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "Label",
    "MACHINE_LABEL",
    "AUTHORITY_LABELS",
    "WEAK_LABELS",
    "coerce_label",
    "is_machine_label",
    "validate_event_label",
    "render_labeled",
]


class Label(StrEnum):
    """The evidence label enum. Every event carries exactly one."""

    VERIFIED_SOURCE = "VERIFIED_SOURCE"
    AUTHORIZED_OPERATOR = "AUTHORIZED_OPERATOR"
    COMMUNITY_REPORT = "COMMUNITY_REPORT"
    MACHINE_INFERENCE = "MACHINE_INFERENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNVERIFIED = "UNVERIFIED"
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"


#: The one and only label machine-originated content may carry.
MACHINE_LABEL = Label.MACHINE_INFERENCE

#: Labels that represent human/institutional authority. Machine content must
#: never be rendered with the styling of these labels.
AUTHORITY_LABELS = frozenset(
    {
        Label.VERIFIED_SOURCE,
        Label.AUTHORIZED_OPERATOR,
        Label.OUTCOME_VERIFIED,
    }
)

#: Labels that explicitly mean "not established". These must stay visible;
#: nothing may silently re-label them.
WEAK_LABELS = frozenset(
    {
        Label.COMMUNITY_REPORT,
        Label.MACHINE_INFERENCE,
        Label.CONFLICTING_EVIDENCE,
        Label.UNVERIFIED,
    }
)


class LabelError(ValueError):
    """Raised when an event carries a missing, unknown, or forbidden label."""


def coerce_label(value: object) -> Label:
    """Coerce ``value`` to a :class:`Label` or raise :class:`LabelError`.

    Accepts a ``Label`` or its exact string value. Anything else — including
    None, empty strings, and lookalike spellings — is refused. Fail closed.
    """

    if isinstance(value, Label):
        return value
    if isinstance(value, str):
        try:
            return Label(value)
        except ValueError:
            raise LabelError(f"unknown evidence label: {value!r}") from None
    raise LabelError(f"evidence label must be a string or Label, got {type(value).__name__}")


def is_machine_label(label: Label) -> bool:
    """True iff ``label`` is the machine-inference label."""

    return label is Label.MACHINE_INFERENCE


def validate_event_label(label_value: object, *, origin: str | None = None) -> Label:
    """Validate the label carried by an event.

    Rules enforced:
      * every event MUST carry exactly one known label;
      * events declared machine-originated (``origin == "machine"``) MUST be
        hard-typed ``MACHINE_INFERENCE`` — a machine record wearing an
        authority label is a protocol violation, refused fail-closed;
      * non-machine origins may carry any label, including
        ``MACHINE_INFERENCE`` (an operator may quote a model, but the quote is
        still labeled as machine inference).

    Returns the coerced :class:`Label`. Raises :class:`LabelError` on any
    violation.
    """

    label = coerce_label(label_value)
    if origin == "machine" and label is not Label.MACHINE_INFERENCE:
        raise LabelError(
            "machine-originated content is hard-typed MACHINE_INFERENCE; "
            f"refusing label {label.value!r}"
        )
    return label


def render_labeled(event: dict) -> str:
    """Render an event as one labeled display line.

    Machine-inference content is styled DISTINCTLY from authority content —
    prefixed ``[machine inference — not authority]`` and wrapped so it can
    never be mistaken for an official record. Weak labels are rendered
    explicitly (no fake green). Authority labels are rendered plainly.

    The function accepts any mapping with ``label`` and (optionally)
    ``payload.summary`` / ``payload.text`` fields; missing fields render as
    explicit placeholders rather than blanks.
    """

    label = coerce_label(event.get("label"))
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    summary = payload.get("summary") or payload.get("text") or "(no summary recorded)"
    event_id = event.get("event_id")
    short_id = f"#{str(event_id)[:12]}" if event_id else "#(uncommitted)"

    if label is Label.MACHINE_INFERENCE:
        return f"[machine inference — not authority] {summary} {short_id}"
    if label is Label.VERIFIED_SOURCE:
        return f"[VERIFIED SOURCE] {summary} {short_id}"
    if label is Label.AUTHORIZED_OPERATOR:
        return f"[AUTHORIZED OPERATOR] {summary} {short_id}"
    if label is Label.OUTCOME_VERIFIED:
        return f"[OUTCOME VERIFIED] {summary} {short_id}"
    if label is Label.COMMUNITY_REPORT:
        return f"[community report — unverified] {summary} {short_id}"
    if label is Label.CONFLICTING_EVIDENCE:
        return f"[CONFLICTING EVIDENCE — unresolved] {summary} {short_id}"
    # UNVERIFIED
    return f"[UNVERIFIED] {summary} {short_id}"

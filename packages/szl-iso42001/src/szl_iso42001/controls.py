"""The control corpus for szl-iso42001.

DESIGN DECISION (for engineers and auditors): the corpus lives in an *embedded YAML
string* below, not in Python literals scattered through code. Three reasons:

1. DATA, NOT CODE. A control corpus is content. Keeping it as YAML makes it readable
   by a non-programmer reviewer (a compliance lead can diff a PR that changes one
   question's wording without reading Python).
2. DIFFABLE. Standards evolve. When ISO/IEC 42001 guidance or EU AI Act implementing
   acts shift, the change is a one-file YAML diff, reviewable line-by-line.
3. VALIDATED AT LOAD. ``load_controls()`` parses the YAML and runs it through a strict
   validator (unique ids, weights in {1,2,3}, allowed enum values, no empty strings).
   A malformed corpus is a hard error, never a silent mis-score.

The module exposes pure data + pure functions. No I/O, no clock, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import yaml

# ---------------------------------------------------------------------------
# Legal honesty constant. This string is printed in EVERY report and is part of
# the product's core promise: this tool is a self-assessment, nothing more.
# ---------------------------------------------------------------------------
DISCLAIMER: str = (
    "Readiness self-assessment only. Not legal advice. Not certification. "
    "Only an accredited body certifies ISO/IEC 42001."
)

# The four answers a control can receive. `unknown` is a first-class citizen:
# the platform doctrine is "UNKNOWN is never PASS", so an unanswered control is
# an evidence gap, never an assumed pass.
ANSWER_KINDS: tuple[str, ...] = ("yes", "partial", "no", "unknown")

# The three readiness outcome bands. The words "certified" and "compliant" are
# deliberately absent from this enum and from the entire package.
BANDS: tuple[str, ...] = ("NOT_READY", "PARTIAL", "READY_FOR_STAGE1_AUDIT")

# The two instruments this checker covers.
INSTRUMENTS: tuple[str, ...] = ("ISO42001", "AIACT-A50")


# ---------------------------------------------------------------------------
# The corpus itself. Keys are kept short on purpose (id/title/question/...
# spelled out in full for review clarity).
#
# Mapping notes for reviewers:
#   * ISO42001 controls are grouped by ISO/IEC 42001 clause (4-10) and by
#     Annex A theme (A.2-A.10). The id encodes the theme: ISO42001-A5-01 is the
#     first control under the "AI system impact assessment" theme. Clause-level
#     controls carry the clause number: ISO42001-C4-01.
#   * AIACT-A50 controls map to Regulation (EU) 2024/1689 Article 50
#     paragraphs: A50-01/02 -> par. 1 (provider machine-readable marking),
#     A50-03 -> par. 1 (AI-interaction disclosure), A50-04/05 -> par. 2
#     (synthetic content disclosure), A50-06/07 -> par. 4 (deepfake labelling),
#     A50-08..10 -> par. 3 (emotion recognition / biometric categorisation
#     disclosure + caveats).
# Weights: 3 = audit-blocking / legally load-bearing, 2 = important, 1 = hygiene.
# ---------------------------------------------------------------------------
CONTROLS_YAML: str = """\
# ===========================================================================
# szl-iso42001 control corpus. Edit this YAML, run the tests, done.
# Every control MUST have: id, title, question, evidence_hint, domain, weight.
# ===========================================================================

- id: ISO42001-C4-01
  title: Organizational context for AI
  question: >-
    Have you identified and documented the internal and external issues
    (regulatory, market, technical, societal) that affect your ability to
    achieve the intended outcomes of your AI management system?
  evidence_hint: >-
    A context-of-organization document or SWOT/PESTLE that explicitly covers
    AI-specific issues such as data protection law, sectoral AI rules, and
    model-risk exposure.
  domain: Clause 4 — Context of the Organization
  weight: 2

- id: ISO42001-C4-02
  title: Interested parties and their AI requirements
  question: >-
    Have you identified the interested parties relevant to your AI systems
    (users, affected persons, regulators, partners) and documented their
    requirements and expectations?
  evidence_hint: >-
    A stakeholder register naming affected-person groups and regulators, with
    their stated requirements mapped to controls.
  domain: Clause 4 — Context of the Organization
  weight: 2

- id: ISO42001-C4-03
  title: AIMS scope definition
  question: >-
    Is the scope of your AI management system documented, including which AI
    systems, business units, and jurisdictions it covers?
  evidence_hint: >-
    A scope statement listing in-scope AI systems by name and version, plus
    explicit out-of-scope justifications.
  domain: Clause 4 — Context of the Organization
  weight: 3

- id: ISO42001-C5-01
  title: Top-management commitment
  question: >-
    Does top management demonstrably take accountability for the AI management
    system (reviewing it, resourcing it, and owning its outcomes)?
  evidence_hint: >-
    Management-review minutes that discuss AI-system performance, incidents,
    and risk, signed by an executive owner.
  domain: Clause 5 — Leadership
  weight: 2

- id: ISO42001-C6-01
  title: AI risk and opportunity planning
  question: >-
    Is there a documented, repeatable process to identify, assess, and treat
    AI-specific risks and opportunities (not just generic IT risk)?
  evidence_hint: >-
    An AI risk register with likelihood/impact scoring, treatment owners, and
    review dates; distinct from the corporate IT risk register.
  domain: Clause 6 — Planning
  weight: 3

- id: ISO42001-C6-02
  title: Measurable AI objectives
  question: >-
    Are AI objectives defined, measurable, assigned to owners, and reviewed on
    a schedule?
  evidence_hint: >-
    An objectives register (e.g. fairness-metric thresholds, incident-rate
    targets) with owners, deadlines, and last-review dates.
  domain: Clause 6 — Planning
  weight: 2

- id: ISO42001-C7-01
  title: AIMS resources and budget
  question: >-
    Are adequate resources (people, tooling, budget) allocated to run and
    improve the AI management system?
  evidence_hint: >-
    A budget line or staffing plan naming the AIMS owner(s) and the tooling
    they operate.
  domain: Clause 7 — Support
  weight: 2

- id: ISO42001-C7-02
  title: AI competence and training
  question: >-
    Do people who develop, deploy, or oversee AI systems have documented
    competence requirements and completed training?
  evidence_hint: >-
    A competence matrix per role plus training-completion records covering AI
    risk, data handling, and model limitations.
  domain: Clause 7 — Support
  weight: 2

- id: ISO42001-C7-03
  title: AIMS communication and awareness
  question: >-
    Are staff made aware of the AI policy, their role in it, and the
    consequences of not conforming?
  evidence_hint: >-
    Onboarding materials and periodic internal communications referencing the
    AI policy, with acknowledgment tracking.
  domain: Clause 7 — Support
  weight: 1

- id: ISO42001-C7-04
  title: Documented information control
  question: >-
    Is AIMS documentation (policies, assessments, logs) controlled — versioned,
    access-managed, and retained on a schedule?
  evidence_hint: >-
    A document-control procedure with version history and a retention schedule
    covering AI assessments and decision logs.
  domain: Clause 7 — Support
  weight: 2

- id: ISO42001-C8-01
  title: Operational planning and control of AI
  question: >-
    Are AI-related processes (development, procurement, deployment, change)
    planned and carried out under controlled conditions?
  evidence_hint: >-
    Defined stage gates in the AI delivery process (e.g. no production deploy
    without an approved impact assessment).
  domain: Clause 8 — Operation
  weight: 3

- id: ISO42001-C8-02
  title: AI risk assessment in operation
  question: >-
    Is an AI risk assessment performed before significant deployment or change,
    and are its results acted on?
  evidence_hint: >-
    Pre-deployment risk-assessment records linked to go/no-go decisions for at
    least the most recent releases.
  domain: Clause 8 — Operation
  weight: 3

- id: ISO42001-C9-01
  title: Monitoring and measurement of the AIMS
  question: >-
    Do you monitor and measure AI-system and AIMS performance against defined
    criteria, on a schedule?
  evidence_hint: >-
    A metrics dashboard or periodic report covering accuracy/fairness drift,
    incident counts, and control-health indicators.
  domain: Clause 9 — Performance Evaluation
  weight: 2

- id: ISO42001-C9-02
  title: Internal AIMS audit
  question: >-
    Are internal audits of the AI management system planned and performed by
    people independent of the area audited?
  evidence_hint: >-
    An internal-audit programme with completed audit reports, findings, and
    tracked corrective actions.
  domain: Clause 9 — Performance Evaluation
  weight: 2

- id: ISO42001-C9-03
  title: Management review of the AIMS
  question: >-
    Does top management review the AIMS at planned intervals, covering audit
    results, incidents, risks, and improvement opportunities?
  evidence_hint: >-
    Management-review minutes with a standing AI agenda and recorded decisions
    and action items.
  domain: Clause 9 — Performance Evaluation
  weight: 2

- id: ISO42001-C10-01
  title: Nonconformity and corrective action
  question: >-
    Is there a working process to record nonconformities and AI incidents,
    correct them, and prevent recurrence?
  evidence_hint: >-
    A corrective-action log linking AI incidents or audit findings to root
    causes and verified fixes.
  domain: Clause 10 — Improvement
  weight: 2

- id: ISO42001-C10-02
  title: Continual improvement
  question: >-
    Can you show that the AI management system itself has been improved over
    time based on evaluation results?
  evidence_hint: >-
    Changelog or retrospective records showing policy/process updates traced
    back to audits, incidents, or metric trends.
  domain: Clause 10 — Improvement
  weight: 1

- id: ISO42001-A2-01
  title: Documented AI policy
  question: >-
    Is there a documented AI policy, approved by leadership, that states your
    principles for responsible development and use of AI?
  evidence_hint: >-
    A signed AI policy document, published internally, with an owner and a
    review date.
  domain: Annex A.2 — AI Policies
  weight: 3

- id: ISO42001-A2-02
  title: AI policy review and communication
  question: >-
    Is the AI policy reviewed at planned intervals and communicated to everyone
    it applies to?
  evidence_hint: >-
    Policy version history showing periodic review, plus distribution or
    acknowledgment records.
  domain: Annex A.2 — AI Policies
  weight: 1

- id: ISO42001-A3-01
  title: AI governance roles and responsibilities
  question: >-
    Are roles and responsibilities for AI governance (including a named,
    accountable AI owner) defined and assigned?
  evidence_hint: >-
    A RACI or org chart naming the accountable executive and the operators of
    each AIMS process.
  domain: Annex A.3 — Roles and Responsibilities
  weight: 2

- id: ISO42001-A3-02
  title: Reporting and escalation of AI concerns
  question: >-
    Is there a channel through which anyone can report AI-related concerns or
    harms, with a defined escalation path?
  evidence_hint: >-
    A published reporting channel (internal and, where relevant, external) with
    SLA and escalation-owner documentation.
  domain: Annex A.3 — Roles and Responsibilities
  weight: 2

- id: ISO42001-A4-01
  title: Competence criteria for AI roles
  question: >-
    Are competence criteria defined for each AI-affecting role, and are hiring
    and promotion decisions checked against them?
  evidence_hint: >-
    Role descriptions listing required AI/data competencies and evidence they
    are applied in hiring and review.
  domain: Annex A.4 — Resources and Competence
  weight: 1

- id: ISO42001-A5-01
  title: AI system impact assessment process
  question: >-
    Is there a documented process for assessing the impacts of AI systems on
    individuals and groups, applied before deployment?
  evidence_hint: >-
    An impact-assessment template covering affected groups, harms, and
    mitigations, plus completed assessments for in-scope systems.
  domain: Annex A.5 — AI System Impact Assessment
  weight: 3

- id: ISO42001-A5-02
  title: Impact-assessment triggers and records
  question: >-
    Are impact assessments triggered on defined events (new system, material
    change, new use context) and retained as records?
  evidence_hint: >-
    Trigger criteria written into the change process, with a register of
    completed assessments including dates and outcomes.
  domain: Annex A.5 — AI System Impact Assessment
  weight: 2

- id: ISO42001-A6-01
  title: Defined AI system lifecycle
  question: >-
    Is the AI system lifecycle (from concept and data acquisition through
    deployment, operation, and retirement) defined and followed?
  evidence_hint: >-
    A lifecycle document with stage entry/exit criteria that matches how your
    systems actually ship.
  domain: Annex A.6 — AI System Lifecycle
  weight: 2

- id: ISO42001-A6-02
  title: Verified and validated deployment
  question: >-
    Is each AI system verified and validated against its intended-purpose
    requirements before deployment, with acceptance criteria recorded?
  evidence_hint: >-
    Test/validation reports per release, including acceptance thresholds for
    accuracy, robustness, and fairness.
  domain: Annex A.6 — AI System Lifecycle
  weight: 2

- id: ISO42001-A6-03
  title: Monitoring, incident response, and decommissioning
  question: >-
    Are deployed AI systems monitored for drift and failure, is there an
    incident-response path, and is decommissioning defined?
  evidence_hint: >-
    Production monitoring configuration, an AI incident runbook, and a
    retirement procedure for at least one past system or model version.
  domain: Annex A.6 — AI System Lifecycle
  weight: 2

- id: ISO42001-A7-01
  title: Data quality and provenance for AI
  question: >-
    Are data-quality requirements defined for AI training and inference data,
    and is provenance (source, licence, lineage) recorded?
  evidence_hint: >-
    Dataset documentation (datasheets) with source, licence, consent basis,
    and quality metrics for each training corpus.
  domain: Annex A.7 — Data for AI
  weight: 2

- id: ISO42001-A7-02
  title: Bias assessment of AI data
  question: >-
    Are datasets assessed for bias and representativeness relative to the
    populations the AI system affects?
  evidence_hint: >-
    Bias/representativeness analysis reports with remediation actions where
    gaps were found.
  domain: Annex A.7 — Data for AI
  weight: 2

- id: ISO42001-A8-01
  title: Information for users of AI systems
  question: >-
    Do users of your AI systems receive documented information about intended
    purpose, capabilities, and limitations?
  evidence_hint: >-
    User-facing documentation or system cards that state what the system is
    for, what it cannot do, and known failure modes.
  domain: Annex A.8 — Information for Interested Parties
  weight: 2

- id: ISO42001-A8-02
  title: Information for affected persons
  question: >-
    Do people affected by your AI systems have a way to learn that AI is
    involved, understand its impact on them, and contest outcomes?
  evidence_hint: >-
    Public notices or disclosures, plus a documented contestation/appeal route
    with handling records.
  domain: Annex A.8 — Information for Interested Parties
  weight: 2

- id: ISO42001-A9-01
  title: Responsible-use rules and human oversight
  question: >-
    Are rules for the responsible use of AI systems defined (including where
    human oversight is mandatory), and are they enforced in operation?
  evidence_hint: >-
    An acceptable-use policy for AI, plus operational evidence of human
    oversight for high-impact decisions (review queues, sign-offs).
  domain: Annex A.9 — Use of AI Systems
  weight: 3

- id: ISO42001-A10-01
  title: Third-party AI responsibility allocation
  question: >-
    For third-party AI systems, models, and data, are responsibilities and
    accountabilities allocated contractually between you and the supplier?
  evidence_hint: >-
    Contracts or DPAs with AI-specific clauses (use restrictions, incident
    notification, audit rights) for each AI supplier.
  domain: Annex A.10 — Third-Party Relationships
  weight: 2

- id: ISO42001-A10-02
  title: Third-party AI risk assessment
  question: >-
    Are third-party AI components assessed for risk before adoption and
    re-assessed on material change?
  evidence_hint: >-
    Vendor-assessment records for each third-party model/API in use, with
    review triggers on version or terms changes.
  domain: Annex A.10 — Third-Party Relationships
  weight: 2

- id: AIACT-A50-01
  title: Machine-readable marking of synthetic output
  question: >-
    Are the outputs of your AI systems that generate synthetic content marked
    in a machine-readable way as artificially generated or manipulated?
  evidence_hint: >-
    Technical documentation of the marking mechanism (metadata, watermark, or
    provenance credential) applied to generated content, e.g. C2PA manifests.
  domain: AI Act Art. 50 — Provider Obligations (par. 1)
  weight: 3

- id: AIACT-A50-02
  title: Marking robustness and interoperability
  question: >-
    Is the machine-readable marking technically robust, effective, and
    interoperable, to the extent technically feasible?
  evidence_hint: >-
    Test evidence that markings survive common transformations and follow a
    recognized standard (e.g. C2PA / IPTC), with known-limitation notes.
  domain: AI Act Art. 50 — Provider Obligations (par. 1)
  weight: 2

- id: AIACT-A50-03
  title: AI-interaction disclosure for chatbots
  question: >-
    When people interact directly with your AI system (e.g. a chatbot), are
    they informed in a clear and timely manner that they are interacting with
    AI?
  evidence_hint: >-
    Screenshots or UX copy of the disclosure shown at the start of interaction,
    unless it is obvious from context.
  domain: AI Act Art. 50 — Deployer Obligations (par. 1)
  weight: 3

- id: AIACT-A50-04
  title: Disclosure of AI-generated content
  question: >-
    Is AI-generated or AI-manipulated content you publish disclosed as such in
    a clear and distinguishable manner?
  evidence_hint: >-
    Publication workflow showing the disclosure step, and examples of published
    content carrying visible AI-origin disclosure.
  domain: AI Act Art. 50 — Deployer Obligations (par. 2)
  weight: 3

- id: AIACT-A50-05
  title: Synthetic-content marking technical standards
  question: >-
    Have you assessed which marking/disclosure technical standards apply to
    your content types and aligned your implementation with them?
  evidence_hint: >-
    A standards-mapping note (per content type: text, image, audio, video) and
    the implementation choices made against it.
  domain: AI Act Art. 50 — Deployer Obligations (par. 2)
  weight: 2

- id: AIACT-A50-06
  title: Deepfake labelling
  question: >-
    Is content that constitutes a deep fake (realistic synthetic depiction of
    real persons or events) labelled visibly as artificially generated or
    manipulated?
  evidence_hint: >-
    Labelling policy for realistic synthetic media plus rendered examples of
    the visible label on shipped content.
  domain: AI Act Art. 50 — Deepfakes (par. 4)
  weight: 3

- id: AIACT-A50-07
  title: Synthetic text disclosure for public information
  question: >-
    Is AI-generated text published to inform the public on matters of public
    interest disclosed as AI-generated (unless human editorial control with
    responsibility applies)?
  evidence_hint: >-
    Editorial policy stating when the AI-generated-text disclosure applies and
    who holds editorial responsibility.
  domain: AI Act Art. 50 — Deepfakes (par. 4)
  weight: 2

- id: AIACT-A50-08
  title: Emotion-recognition disclosure
  question: >-
    Where you deploy an emotion-recognition system, are the people exposed to
    it informed of its operation, and have you checked whether its use is even
    permitted in that context (e.g. workplace and education bans)?
  evidence_hint: >-
    Deployment inventory showing any emotion-recognition use, the prohibition
    screening performed (Art. 5), and the disclosure text shown to exposed
    persons.
  domain: AI Act Art. 50 — Emotion Recognition & Biometrics (par. 3)
  weight: 3

- id: AIACT-A50-09
  title: Biometric-categorization disclosure
  question: >-
    Where you deploy a biometric-categorization system, are the people exposed
    informed of its operation, and have you screened it against prohibited
    inferences (e.g. sensitive-attribute categorization bans)?
  evidence_hint: >-
    Deployment inventory, the Art. 5 prohibition screening for each biometric
    use, and the disclosure shown to exposed persons.
  domain: AI Act Art. 50 — Emotion Recognition & Biometrics (par. 3)
  weight: 3

- id: AIACT-A50-10
  title: Personal-data processing caveat for par. 3 systems
  question: >-
    For emotion-recognition or biometric-categorization systems, is the
    personal-data processing basis assessed and documented in line with GDPR
    (the Art. 50 par. 3 caveat)?
  evidence_hint: >-
    A DPIA or lawful-basis assessment covering each par. 3 system, referencing
    GDPR Art. 9 where special-category data is inferred.
  domain: AI Act Art. 50 — Emotion Recognition & Biometrics (par. 3)
  weight: 2
"""


@dataclass(frozen=True, slots=True)
class Control:
    """One assessable control from the corpus.

    Immutable and hashable so controls can live in sets/dicts and the corpus is
    safe to share across threads. All fields are validated at corpus load time,
    so by the time you hold a ``Control`` its invariants are guaranteed.
    """

    id: str  # e.g. "ISO42001-A5-01" or "AIACT-A50-03"
    title: str
    question: str  # must be answerable with yes/partial/no/unknown
    evidence_hint: str  # what an auditor would ask to see
    domain: str  # grouping label shown in reports, e.g. "Annex A.5 — ..."
    weight: int  # 1 (hygiene), 2 (important), 3 (audit-blocking / load-bearing)

    #: Controls whose id starts with one of these prefixes count toward the
    #: "no answer allowed on weight-3" gate for READY_FOR_STAGE1_AUDIT — i.e.
    #: all of them. Kept explicit so a future instrument can opt out.
    ALLOWED_ANSWERS: ClassVar[tuple[str, ...]] = ANSWER_KINDS

    @property
    def instrument(self) -> str:
        """Which instrument this control belongs to: 'ISO42001' or 'AIACT-A50'."""
        if self.id.startswith("AIACT-A50"):
            return "AIACT-A50"
        if self.id.startswith("ISO42001"):
            return "ISO42001"
        # Unreachable for the shipped corpus (validator enforces the prefixes),
        # but fail loudly rather than mis-classify if someone hand-edits it.
        raise ValueError(f"control id {self.id!r} matches no known instrument")


def _validate_control(raw: object, index: int) -> Control:
    """Turn one YAML mapping into a validated Control, or raise ValueError.

    Validation is strict on purpose: a silently truncated corpus would produce
    a silently wrong readiness verdict. Fail fast, fail loud.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"control #{index}: expected a mapping, got {type(raw).__name__}")

    required = ("id", "title", "question", "evidence_hint", "domain", "weight")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"control #{index}: missing required keys: {missing}")

    cid = raw["id"]
    if not isinstance(cid, str) or not cid.strip():
        raise ValueError(f"control #{index}: id must be a non-empty string")
    if not (cid.startswith("ISO42001-") or cid.startswith("AIACT-A50-")):
        raise ValueError(
            f"control {cid!r}: id must start with 'ISO42001-' or 'AIACT-A50-'"
        )

    for key in ("title", "question", "evidence_hint", "domain"):
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"control {cid!r}: {key} must be a non-empty string")

    weight = raw["weight"]
    # bool is a subclass of int in Python — reject it explicitly so a YAML
    # `weight: yes` can't smuggle through as weight=1.
    if isinstance(weight, bool) or not isinstance(weight, int) or weight not in (1, 2, 3):
        raise ValueError(f"control {cid!r}: weight must be one of 1, 2, 3, got {weight!r}")

    return Control(
        id=cid.strip(),
        title=raw["title"].strip(),
        question=raw["question"].strip(),
        evidence_hint=raw["evidence_hint"].strip(),
        domain=raw["domain"].strip(),
        weight=weight,
    )


def load_controls() -> list[Control]:
    """Parse CONTROLS_YAML and return the validated control corpus.

    Ordering is corpus order (YAML document order) — deterministic, and the
    same order used by reports, templates, and the `list` command.

    Raises:
        ValueError: if the corpus YAML is malformed, has duplicate ids, or any
            control fails validation. This is a programming-error path, not a
            user-input path — the corpus ships inside the package.
    """
    raw = yaml.safe_load(CONTROLS_YAML)
    if not isinstance(raw, list):
        raise ValueError("corpus root must be a YAML list of controls")

    controls = [_validate_control(item, i) for i, item in enumerate(raw)]

    seen: set[str] = set()
    duplicates: set[str] = set()
    for c in controls:
        if c.id in seen:
            duplicates.add(c.id)
        seen.add(c.id)
    if duplicates:
        raise ValueError(f"corpus contains duplicate control ids: {sorted(duplicates)}")

    return controls


def controls_by_id() -> dict[str, Control]:
    """Return the corpus indexed by control id (fresh dict each call)."""
    return {c.id: c for c in load_controls()}


def controls_by_domain() -> dict[str, list[Control]]:
    """Return the corpus grouped by domain, preserving corpus order within each
    domain and first-appearance order across domains (dicts are insertion-ordered)."""
    grouped: dict[str, list[Control]] = {}
    for c in load_controls():
        grouped.setdefault(c.domain, []).append(c)
    return grouped


def instruments() -> dict[str, list[Control]]:
    """Return the corpus grouped by instrument ('ISO42001', 'AIACT-A50')."""
    grouped: dict[str, list[Control]] = {name: [] for name in INSTRUMENTS}
    for c in load_controls():
        grouped[c.instrument].append(c)
    return grouped

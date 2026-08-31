#!/usr/bin/env python3
"""Build draft-lutar-governed-action-receipt-00.

Single source of truth: the structured document below is rendered twice,
once as kramdown-rfc Markdown (the editable source) and once as classic
RFC-format plain text (72 columns, page headers, form feeds, ToC with page
numbers).  All worked-example values are read from
/home/user/workspace/gar-example/example_output.json, which is produced by
the installed szl-receipts 14.0.0 library — nothing here is hand-typed.
"""
import json
import textwrap
from pathlib import Path

EX = json.loads(Path("/home/user/workspace/gar-example/example_output.json").read_text())
OUT = Path("/home/user/workspace/szl-platform/docs/standards")

DOCNAME = "draft-lutar-governed-action-receipt-00"
TITLE = "Governed Action Receipt (GAR): A Canonical, Verifiable Record of Policy-Governed Actions"
TITLE_SHORT = "Governed Action Receipt (GAR)"
DATE = "August 31, 2026"
EXPIRES = "March 4, 2027"

# ---------------------------------------------------------------------------
# Document content model
# ---------------------------------------------------------------------------
# Blocks: ("para", text) | ("art", lines) | ("ul", [items]) |
#         ("ol", [items]) | ("dl", [(term, text)]) | ("note", text)
# Sections: {"h": display heading, "toc": toc label, "b": [blocks],
#            "sub": [ {"h","b"} ]}
# front keys: abstract, sotm, copyright, sections, ack, refs_norm, refs_info

def W(text):
    """Normalize a paragraph source string."""
    return " ".join(text.split())


ART_CANON = textwrap.wrap(EX["canon_bytes_text"], 64)
ART_PAYLOAD = textwrap.wrap(EX["envelope_payload_b64"], 64)

art_receipt = EX["receipt_pretty"].splitlines()
art_entry1 = EX["entry1_pretty"].splitlines()

art_envelope = (
    ["{", '  "payload":']
    + ['      "' + l + ('"' if i == len(ART_PAYLOAD) - 1 else "") for i, l in enumerate(ART_PAYLOAD)]
    + ["", '  "payloadType": "application/gar+json",',
       '  "signatures": [',
       "    {",
       f'      "keyid": "{EX["example_keyid"]}",',
       f'      "sig": "{EX["example_sig_b64"]}"',
       "    }",
       "  ]",
       "}"]
)

art_pub = EX["example_pub_pem"].strip().splitlines()

reproduce_script = (OUT / "reproduce-appendix-b.py").read_text().splitlines()

front = {}
front["abstract"] = [
    W("""This document specifies the Governed Action Receipt (GAR), a compact
       JSON record that binds an actor, an action, a governing policy
       (identified by identifier, version, and the SHA-256 digest of the
       policy document), a decision outcome drawn from a closed vocabulary,
       the digests of the bytes of the artifacts acted upon, and references
       to supporting evidence.  Receipts are canonicalized with the JSON
       Canonicalization Scheme (RFC 8785); the identity of a receipt is the
       SHA-256 digest of its own canonical body with the identity field
       removed, so any field-level modification is detectable by any
       verifier without trusting a registry."""),
    W("""Receipts are signed by carrying their canonical form as the payload
       of a DSSE envelope under Ed25519, or are published unsigned under a
       mandatory honest-naming convention that makes the absence of a
       signature legible from the filename alone.  Receipts may be linked
       into append-only hash chains whose entries commit to their
       predecessors; the document states explicitly that silent truncation
       of the tail of such a chain is undetectable without an external
       anchor, and defines the anchor interface.  This document describes
       the format exactly as implemented in the open szl-receipts library
       and includes a fully reproducible worked example."""),
]

front["sotm"] = [
    W("""This Internet-Draft is submitted in full conformance with the
       provisions of BCP 78 and BCP 79."""),
    W("""Internet-Drafts are working documents of the Internet Engineering
       Task Force (IETF).  Note that other groups may also distribute
       working documents as Internet-Drafts.  The list of current
       Internet-Drafts is at https://datatracker.ietf.org/drafts/current/."""),
    W("""Internet-Drafts are draft documents valid for a maximum of six
       months and may be updated, replaced, or obsoleted by other documents
       at any time.  It is inappropriate to use Internet-Drafts as reference
       material or to cite them other than as "work in progress"."""),
    W(f"""This Internet-Draft will expire on {EXPIRES}."""),
]

front["copyright"] = [
    W("""Copyright (c) 2026 IETF Trust and the persons identified as the
       document authors.  All rights reserved."""),
    W("""This document is subject to BCP 78 and the IETF Trust's Legal
       Provisions Relating to IETF Documents
       (https://trustee.ietf.org/license-info) in effect on the date of
       publication of this document.  Please review these documents
       carefully, as they describe your rights and restrictions with respect
       to this document.  Code Components extracted from this document must
       include Revised BSD License text as described in Section 4.e of the
       Trust Legal Provisions and are provided without warranty as described
       in the Revised BSD License."""),
]

S = []  # sections

S.append({"h": "1.  Introduction", "toc": "1.  Introduction", "b": [
    ("para", W("""Automated systems increasingly perform actions with
       operational consequences: building software, deploying
       infrastructure, admitting or rejecting artifacts, approving changes.
       Each such action is typically justified by a policy, and each such
       justification evaporates the moment the pipeline finishes, unless a
       record is kept.  The records that are kept are usually prose logs:
       greppable, mutable, and impossible to verify independently.""")),
    ("para", W("""This document specifies the Governed Action Receipt
       (GAR).  A receipt is a small JSON object that records that a named
       actor performed a named action under a named policy, with a stated
       outcome, over stated artifacts.  The policy is identified not only
       by name and version but by the SHA-256 digest of the policy document
       itself; the artifacts are identified by the SHA-256 digests of
       their bytes, never by filename alone.  The receipt's own identity
       (receipt_id) is the SHA-256 digest of its canonical form, so a
       receipt is content-addressed: two parties that agree on the bytes
       agree on the identity, and any party that alters a byte produces a
       different identity.""")),
    ("para", W("""The design follows three rules, enforced by the reference
       implementation rather than left to convention:

       (1) Bytes, not names: every digest in a receipt covers artifact
       bytes, never path strings; a name is a claim and bytes are ground
       truth.

       (2) Honest names: an unsigned artifact is named *.unsigned.json;
       an empty signatures array is not a signature, and a filename that
       lies about the signature state is a verification failure
       (Section 8).

       (3) UNKNOWN is never passing: the outcome vocabulary is closed
       (Section 9), the absence of a verdict is not a verdict, and a
       promotion gate MUST NOT promote what it cannot characterize.""")),
    ("para", W("""A receipt is verifiable offline with nothing but the
       document bytes, a SHA-256 implementation, and (for signed receipts)
       an Ed25519 implementation.  No online service, trusted registry, or
       specific vendor is required.  Where a deployment wants third-party
       witnesses, receipts compose with existing transparency and
       attestation infrastructure (Section 7.3).""")),
    ("para", W("""Every normative statement in this document describes
       behavior that the reference implementation, szl-receipts 14.0.0
       (Section 4.6), executes; Appendix B contains a worked example whose
       every byte is reproducible from the commands given there.  Where
       this document and an implementation disagree, the disagreement is a
       defect in one of them and should be reported.""")),
]})

S.append({"h": "2.  Terminology", "toc": "2.  Terminology", "b": [
    ("dl", [
        ("Receipt", W("""A JSON object of receipt_type "GovernedAction/v1"
            as defined in Section 4.""")),
        ("GAR", "The Governed Action Receipt format specified by this document."),
        ("Actor", W("""The entity that performed the governed action; a
            non-empty string whose semantics are deployment-defined (a CI
            runner name, a person, a service account).""")),
        ("Action", "A non-empty string naming the governed operation."),
        ("Policy", W("""The rule set under which the action was governed,
            identified by an identifier string, a version string, and the
            SHA-256 digest of the policy document's bytes.""")),
        ("Subject", W("""An artifact the action operated upon, identified by
            a name (a label) and the SHA-256 digest of its bytes.""")),
        ("Evidence", W("""A URI pointing at supporting material (build logs,
            attestations, run records), optionally pinned by SHA-256.""")),
        ("Outcome", W("""The verdict of the governed action, drawn from the
            closed vocabulary of Section 9.""")),
        ("Receipt identity", W("""The value of the receipt_id field: the
            SHA-256 digest, in lowercase hexadecimal, of the canonical form
            of the receipt with the receipt_id field removed
            (Section 4.5).""")),
        ("Canonical form", W("""The serialization of a JSON value under the
            JSON Canonicalization Scheme [RFC8785]; see Section 5.""")),
        ("DSSE envelope", W("""The wrapping structure defined by [DSSE]:
            payload, payloadType, signatures; see Section 6.""")),
        ("PAE", W("""The Pre-Authentication Encoding defined by [DSSE]: the
            domain-separated byte string over which signatures are computed;
            see Section 6.2.""")),
        ("Chain entry", W("""A record binding a receipt to a sequence number
            and to the digest of the preceding entry; see Section 7.""")),
        ("Chain head", "The entry_digest of the final entry of a chain."),
        ("External anchor", W("""A value (an expected entry count, an
            expected head digest, or a witnessed inclusion proof) obtained
            from outside the chain itself; see Section 7.3.""")),
        ("in-toto Statement", W("""The attestation container of [INTOTO],
            type "https://in-toto.io/Statement/v1", which a receipt can be
            carried in (Section 6.4).""")),
    ]),
]})

S.append({"h": "3.  Conventions and Definitions", "toc": "3.  Conventions and Definitions", "b": [
    ("para", W("""The key words "MUST", "MUST NOT", "REQUIRED", "SHALL",
       "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT
       RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
       interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and
       only when, they appear in all capitals, as shown here.""")),
    ("para", W("""Hexadecimal digests in this document are lowercase SHA-256
       hex strings of exactly 64 characters, matching the regular
       expression [0-9a-f]{64}.  The hash function is SHA-256 [FIPS202]
       throughout; digest agility is deliberately out of scope for this
       version (Section 11).""")),
    ("para", W("""Timestamps are ISO 8601 strings with a mandatory timezone
       designator (Section 4.2).  JSON member names are shown in
       monospace-equivalent quoting in prose (for example, "receipt_id")
       and appear literally in artwork.""")),
]})

S.append({"h": "4.  Receipt Format", "toc": "4.  Receipt Format", "b": [], "sub": [
    {"h": "4.1.  Receipt Members", "b": [
        ("para", W("""A receipt is a JSON object [RFC8259] containing
           exactly the following ten members.  No additional members are
           permitted: a verifier MUST reject a receipt carrying any member
           outside this set, and MUST reject a receipt missing any of them.
           A closed member set means a producer cannot smuggle
           un-verified semantics past a verifier in extension fields.""")),
        ("dl", [
            ("receipt_id", W("""REQUIRED.  String.  The receipt identity as
                defined in Section 4.5: 64 lowercase hexadecimal
                characters.""")),
            ("receipt_type", W("""REQUIRED.  String.  MUST be exactly
                "GovernedAction/v1".""")),
            ("schema_version", W("""REQUIRED.  Non-empty string.  For this
                version of the specification the value is "1.0".""")),
            ("created_at", W("""REQUIRED.  String.  An ISO 8601 timestamp
                with mandatory timezone (Section 4.2).  This is a real
                wall-clock value: receipts are runtime artifacts recording
                that something happened at a moment in time; determinism
                lives in the canonical form and the digests, and the
                timestamp is data.""")),
            ("actor", W("""REQUIRED.  Non-empty string.  The entity that
                performed the action.""")),
            ("action", W("""REQUIRED.  Non-empty string.  The operation
                performed.""")),
            ("policy", W("""REQUIRED.  Object with exactly the members
                "id" (non-empty string), "version" (non-empty string), and
                "digest_sha256" (64 lowercase hex characters: the SHA-256
                of the policy document's bytes).  The policy is identified
                by its bytes, so a policy that changes while keeping its
                name and version is detectably a different policy.""")),
            ("decision", W("""REQUIRED.  Object with members "outcome"
                (string from the closed vocabulary of Section 9) and
                "rationale" (string; MAY be empty).""")),
            ("subjects", W("""REQUIRED.  Array, possibly empty.  Each
                element is an object with exactly the members "name"
                (non-empty string; a label) and "sha256" (64 lowercase hex
                characters: the SHA-256 of the artifact's bytes).
                Digests cover bytes, never path strings (Section 11).""")),
            ("evidence", W("""REQUIRED.  Array, possibly empty.  Each
                element is an object with member "uri" (non-empty string)
                and OPTIONAL member "sha256" (64 lowercase hex characters
                when present), pinning the bytes behind the URI.""")),
        ]),
    ]},
    {"h": "4.2.  Timestamp Grammar", "b": [
        ("para", W("""The created_at member MUST match the grammar:""")),
        ("art", [r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"]),
        ("para", W("""and MUST additionally denote a real calendar moment:
           the grammar alone accepts impossible dates such as a month of
           13, and a verifier MUST reject a created_at that matches the
           grammar but fails to parse as a valid date and time.  A
           timestamp without a timezone designator has no place in an
           audit log: "14:00" in whose timezone?""")),
    ]},
    {"h": "4.3.  Example", "b": [
        ("para", W("""The following receipt records a governed build.  It
           is reproduced byte-for-byte in Appendix B, which also gives the
           commands to regenerate it.""")),
        ("art", art_receipt),
    ]},
    {"h": "4.4.  Canonical Form of the Example", "b": [
        ("para", W("""The canonical form (Section 5) of the example
           receipt is the following 650 bytes (wrapped for display; the
           canonical form itself contains no whitespace):""")),
        ("art", ART_CANON),
        ("para", W(f"""The SHA-256 of the full canonical form above is
           {EX['canon_sha256']}.  The SHA-256 of the canonical form of the
           body with "receipt_id" removed (570 bytes) is
           {EX['receipt_id']}, which is the receipt_id; see Section
           4.5.""")),
    ]},
    {"h": "4.5.  Receipt Identity", "b": [
        ("para", W("""The receipt_id of a receipt MUST be computed as
           follows: remove the "receipt_id" member from the receipt
           object; canonicalize the remaining nine members per Section 5;
           compute the SHA-256 digest of the resulting bytes; encode it as
           64 lowercase hexadecimal characters.""")),
        ("para", W("""Because canonicalization absorbs member ordering, two
           producers with different serialization habits compute the same
           identity for the same content; that is the whole point.  A
           verifier MUST recompute the identity and MUST report a finding
           when the declared receipt_id differs from the recomputed value.
           Because the identity is a digest, a forged identifier of the
           form "important-receipt-final-v2" is structurally impossible:
           identifiers are never human-chosen strings.""")),
    ]},
    {"h": "4.6.  Reference Implementation", "b": [
        ("para", W("""The reference implementation is the Python package
           szl-receipts 14.0.0, in which the constructor build_receipt and
           the verifier verify_receipt implement exactly the rules of this
           section; Appendix B reproduces the example above with it.  The
           verifier is deliberately non-throwing on bad data: every defect
           is returned as a finding string, and an empty finding list
           means the receipt is well-formed and its identity checks out.
           An implementation-independent description of verifier behavior
           is given in Section 10.""")),
    ]},
]})

S.append({"h": "5.  Canonicalization", "toc": "5.  Canonicalization", "b": [
    ("para", W("""All digest computations in this document (receipt
       identity, chain entry digests, envelope payload digests) are
       performed over the canonical form of the relevant JSON value.  The
       canonical form MUST be the JSON Canonicalization Scheme (JCS)
       defined by [RFC8785].  JCS removes every serialization degree of
       freedom so that semantic equality becomes byte equality.""")),
    ("para", W("""The points of [RFC8785] most consequential for
       implementers of this document are:""")),
    ("ul", [
        W("""Object members are ordered by the UTF-16 code units of their
           names, not by Unicode code points; for astral characters the
           two orders differ (RFC 8785, Section 3.2.3)."""),
        W("""Numbers are formatted as ECMAScript Number::toString
           (RFC 8785, Section 3.2.2.3): shortest round-trip digits, fixed
           notation inside the standard exponent window, exponential
           notation outside it, and a sign always present on the
           exponent."""),
        W("""Strings are escaped minimally and never normalized (RFC 8785,
           Section 3.2.2.2): canonically equivalent but code-point-distinct
           strings canonicalize to different bytes, by design."""),
    ]),
    ("para", W("""A receipt producer MUST NOT emit values that are not
       interoperable JSON [RFC7493]: no NaN or infinities, and no integer
       with magnitude greater than or equal to 2^53, because a parser may
       route such integers through an IEEE-754 double and silently lose
       precision; a canonicalizer MUST reject such values rather than emit
       bytes a reader cannot hold exactly.  The reference implementation's
       canonicalizer raises IJsonError in these cases.""")),
]})

S.append({"h": "6.  Signing and Envelopes", "toc": "6.  Signing and Envelopes", "b": [
    ("para", W("""A receipt proves its own integrity via its identity, but
       integrity is not authenticity: anyone can construct a valid-looking
       receipt.  Authenticity is provided by wrapping the canonical form
       of the receipt in a DSSE envelope [DSSE] and signing with Ed25519
       [RFC8032], or by publishing the receipt unsigned under the honest
       naming convention of Section 8.  A receipt MUST NOT be presented in
       any state in between: either at least one signature is present, or
       the artifact is named unsigned.""")),
], "sub": [
    {"h": "6.1.  Envelope", "b": [
        ("para", W("""The signed artifact is a DSSE envelope [DSSE]: a JSON
           object with members "payload" (base64 of the payload bytes),
           "payloadType" (string), and "signatures" (array of objects with
           members "keyid" and "sig", the latter base64 of the signature
           bytes).  Base64 is the standard alphabet with strict decoding:
           a verifier MUST reject non-canonical base64 at the structural
           stage, before any cryptography is attempted.""")),
        ("para", W("""The payload of a GAR envelope MUST be the canonical
           form (Section 5) of the complete receipt, including receipt_id.
           Signing the canonical form, rather than whatever bytes a
           producer happened to serialize, means the signature verifies
           even if the envelope travels through JSON tooling that
           reserializes whitespace or reorders members: the bytes under
           the signature are semantic, not incidental.""")),
        ("para", W("""The payloadType of a GAR envelope SHOULD be
           "application/gar+json" (Section 12).  Producers using another
           payload type MUST choose a value distinct from any payload type
           they use for any other signed purpose, so that the
           domain separation of Section 6.2 is preserved.""")),
    ]},
    {"h": "6.2.  Pre-Authentication Encoding", "b": [
        ("para", W("""Signatures are computed over the Pre-Authentication
           Encoding of the (payloadType, payload) pair, exactly as defined
           by [DSSE]:""")),
        ("art", [
            "PAE = b\"DSSEv1\" SP len(payloadType) SP payloadType",
            "          SP len(payload) SP payload",
        ]),
        ("para", W("""where SP is a single space (0x20) and the lengths are
           decimal ASCII byte counts.  Every field is length-prefixed
           before concatenation, so no pair (type, payload) can encode to
           the same bytes as a different pair: the separator positions are
           fixed by the lengths, and an attacker cannot smear bytes across
           the boundary.  This domain separation prevents a signature over
           a receipt from being replayed as a signature over any other
           kind of object that happens to share bytes (the classic
           type-confusion attack).  A minimal example:
           PAE("a", "bc") is the byte string "DSSEv1 1 a 2 bc".  For the
           example receipt of Section 4.3 the encoding begins
           "DSSEv1 20 application/gar+json 650 {" and runs 696 bytes in
           total.""")),
    ]},
    {"h": "6.3.  Signature Algorithm and Keys", "b": [
        ("para", W("""The signature algorithm MUST be Ed25519 [RFC8032].
           Ed25519 is chosen for its small fixed-size keys and signatures,
           deterministic signing (no per-signature nonce to leak), and
           wide deployment.  One Ed25519 signature occupies 64 bytes,
           88 characters base64.""")),
        ("para", W("""The keyid of a signature SHOULD be the SHA-256 of the
           raw 32-byte public key, in lowercase hex, so that keys are
           identified by content rather than by filename; deployments MAY
           override keyid to match an external key registry.  Key
           distribution and trust-root selection are out of scope for this
           document; Section 7.3 notes where witnessed key material can be
           anchored.""")),
    ]},
    {"h": "6.4.  in-toto Statements", "b": [
        ("para", W("""Deployments that already produce in-toto attestations
           [INTOTO] MAY carry a receipt as the predicate of an in-toto
           Statement v1 (type "https://in-toto.io/Statement/v1").  In this
           mapping the Statement's subject list holds (name, sha256)
           pairs for the artifacts attested, with digests in the digest
           map under the "sha256" key, and the receipt appears verbatim as
           the predicate.  The Statement is then signed as the payload of
           a DSSE envelope exactly as in Section 6.1.  This mapping is
           optional; a bare GAR envelope carries no less integrity than a
           Statement-wrapped one.""")),
    ]},
    {"h": "6.5.  Example Envelope", "b": [
        ("para", W("""The canonical bytes of Section 4.4, signed under the
           example key of Appendix B (a non-secret test vector), yield the
           following envelope.  The payload member is wrapped for display;
           it is a single base64 string of the 650 canonical bytes.  The
           envelope verifies under the public key printed in Appendix B
           and is reproducible byte-for-byte.""")),
        ("art", art_envelope),
    ]},
]})

S.append({"h": "7.  Hash-Chained Logs and External Anchors", "toc": "7.  Hash-Chained Logs and External Anchors", "b": [
    ("para", W("""Receipts gain operational value when they are ordered.
       A chain binds each receipt to a sequence number and to its
       predecessor, producing an append-only log whose every entry
       authenticates the entire history before it.""")),
], "sub": [
    {"h": "7.1.  Chain Entry Format", "b": [
        ("para", W("""A chain entry is a JSON object with exactly the
           members "seq" (integer, 1 for the first entry), "receipt" (a
           receipt object per Section 4), "prev" (the entry_digest of the
           preceding entry, or null for the genesis entry), and
           "entry_digest" (64 lowercase hex characters).  The binding
           digest is:""")),
        ("art", [
            'entry_digest = SHA-256(JCS({"seq": n,',
            '                           "receipt": <receipt>,',
            '                           "prev": <hex string or null>}))',
        ]),
        ("para", W("""computed over the canonical form of exactly those
           three identity-defining members.  Because the embedded receipt
           is itself content-addressed by receipt_id, one digest
           recomputation authenticates the receipt, its position, and its
           linkage.  An appender MUST validate the receipt per Section 10
           before it touches the chain: a chain containing an invalid
           receipt is a chain that lies with confidence.""")),
        ("para", W("""The genesis entry of the example chain of Appendix B
           is:""")),
        ("art", art_entry1),
        ("para", W(f"""The second entry has seq 2, prev
           {EX['genesis_entry_digest']} (the digest above), and
           entry_digest {EX['entry2_digest']}.""")),
    ]},
    {"h": "7.2.  What the Chain Detects", "b": [
        ("para", W("""A chain verifier re-derives every entry_digest and
           cross-checks every linkage.  The following attack classes are
           detectable from the chain alone, and each MUST be reported as a
           distinct finding (the reference implementation assigns the
           stable codes shown):""")),
        ("dl", [
            ("digest-mismatch", "entry content does not hash to its declared entry_digest."),
            ("reorder", "seq numbers not strictly increasing along the log."),
            ("gap", "a forward jump in seq: middle entries are missing."),
            ("replay", "the same seq reappears with an identical digest."),
            ("fork", "the same seq reappears with two different digests."),
            ("broken-prev-link", "an entry's prev is not the digest of the preceding entry."),
            ("genesis-prev-not-null", "the first entry does not anchor at null."),
            ("malformed-entry", "missing members, a bad seq, or a non-canonicalizable entry."),
        ]),
    ]},
    {"h": "7.3.  External Anchors and the Truncation Limitation", "b": [
        ("para", W("""This section states the honest limit of any
           self-verifying log, because a specification that omits it would
           oversell the mechanism.""")),
        ("para", W("""A hash chain verified without external information
           proves integrity of the presented history from genesis to the
           presented head.  It cannot prove completeness: an operator who
           silently drops the newest entries yields a shorter chain that
           is perfectly valid.  Tail truncation is undetectable from the
           chain alone.  No hashing scheme removes this limitation; it is
           a property of self-authenticating logs, not of this design.""")),
        ("para", W("""The mitigation is an external anchor: information
           about the chain obtained from outside the chain.  This document
           defines two anchor inputs to the verifier, which a deployment
           MUST treat as untrusted-chain/trusted-anchor:""")),
        ("dl", [
            ("expected_entries", W("""an integer; if the chain holds fewer
                entries, the verifier reports "truncated".""")),
            ("expected_head", W("""a 64-hex digest; if the digest of the
                final entry differs, the verifier reports
                "head-mismatch".""")),
        ]),
        ("para", W("""Anchors can be published out of band (a head digest
           in a release announcement, a count in a ticket) or witnessed by
           a transparency service.  GAR chains are deliberately compatible
           with the SCITT architecture [SCITT]: a signed GAR envelope is a
           signed statement in SCITT terms, and a transparency service can
           return an inclusion receipt for a chain head, converting the
           head into a witnessed anchor.  Sigstore-style transparency logs
           [SIGSTORE] (for example Rekor) provide the same function for
           the envelope itself.  Deployments that cannot anchor MUST state
           in their own audit narrative that tail truncation is outside
           the verified envelope.""")),
    ]},
]})

S.append({"h": "8.  Honest Unsigned Naming", "toc": "8.  Honest Unsigned Naming", "b": [
    ("para", W("""A file's name MUST tell the truth about its signature
       state.  The convention:""")),
    ("ul", [
        W("""An envelope carrying one or more signatures is written as
           <base>.json, for example build/report.json."""),
        W("""An envelope carrying zero signatures is written as
           <base>.unsigned.json, for example
           build/report.unsigned.json."""),
    ]),
    ("para", W("""An empty signatures array is not a signature.  The rule
       exists because consumers pattern-match on extensions: an envelope
       with "signatures": [] written to report.json presents as a
       signed-looking artifact that anyone could have produced.  Honest
       naming makes the trust state legible from the directory listing
       alone.""")),
    ("para", W("""Verification is bidirectional and MUST fail in both
       directions: a *.unsigned.json file that contains one or more
       signatures is a tampered rename, and any other .json artifact whose
       signatures array is empty is a tampered rename.  Both MUST be
       reported as verification failures (the reference implementation
       raises NamingError and its CLI exits with status 2).  Renaming a
       file MUST NOT change what the world believes about it.""")),
    ("para", W("""A missing signatures member is not an unsigned artifact;
       it is a malformed envelope, and MUST be reported as such.  Absent
       is different from empty, and conflating them is how quiet
       forgeries pass review.""")),
    ("para", W("""The naming convention applies to artifacts on disk and
       to attachments in transit; it is orthogonal to the cryptographic
       checks of Section 6 and is always applied first (Section 10).""")),
]})

S.append({"h": "9.  Outcome Vocabulary", "toc": "9.  Outcome Vocabulary", "b": [
    ("para", W("""The decision.outcome member MUST take exactly one of the
       following five values.  The vocabulary is closed deliberately: a
       free-text status field drifts ("ok", "green", "mostly fine") until
       nothing can be gated on it.""")),
    ("dl", [
        ("PASS", "the governed action completed and met policy."),
        ("WARN", W("""the action completed with a recorded concern; not a
            pass.""")),
        ("FAIL", "the governed action failed."),
        ("BLOCKED", W("""the action was prevented from running by policy or
            by the environment.""")),
        ("UNKNOWN", W("""no verdict was recorded; the absence of a verdict
            is itself the record.""")),
    ]),
    ("para", W("""A verifier MUST reject a receipt whose outcome is
       outside this vocabulary, and a producer MUST fail at build time
       rather than emit one: shipping a receipt with an un-gateable
       outcome is worse than crashing the builder.""")),
    ("para", W("""UNKNOWN MUST NOT be promoted to PASS.  More precisely:
       absence of a verdict is not a verdict; a promotion gate MUST admit
       PASS and MUST refuse FAIL, BLOCKED, and UNKNOWN unconditionally;
       WARN MAY be admitted only by an explicit, recorded override (in the
       reference implementation, promotion_gate(outcome, allow_warn=True);
       the override is itself an auditable decision).  Code that treats
       "no verdict" as "passed" is how silent corruption ships; "we don't
       know" is informationally worse than "it failed", because failure at
       least tells you where to look.""")),
]})

S.append({"h": "10.  Verifier Behavior", "toc": "10.  Verifier Behavior", "b": [
    ("para", W("""This section specifies what a conforming verifier checks.
       Verification is fail-closed throughout: any malformed input, any
       unexpected member, any mismatch yields a negative result, never an
       exception that a caller might mistake for success.""")),
    ("para", W("""Receipt verification, given a parsed JSON value:""")),
    ("ol", [
        W("""The value MUST be an object containing exactly the ten
           members of Section 4.1; missing or extra members are
           findings."""),
        W("""receipt_type MUST be "GovernedAction/v1"; schema_version MUST
           be a non-empty string."""),
        W("""created_at MUST match the grammar of Section 4.2 and parse as
           a real calendar moment."""),
        W("""actor and action MUST be non-empty strings."""),
        W("""policy MUST have non-empty string id and version, and
           digest_sha256 MUST be 64 lowercase hex characters."""),
        W("""decision.outcome MUST be within the vocabulary of Section 9;
           decision.rationale MUST be a string."""),
        W("""Every subject MUST have a non-empty name and a 64-hex sha256,
           and no other members.  Where the artifact is available, the
           verifier SHOULD re-hash the artifact's bytes (in bounded
           chunks, so artifact size is immaterial) and compare."""),
        W("""Every evidence item MUST have a non-empty uri, and sha256
           when present MUST be 64 lowercase hex characters."""),
        W("""The declared receipt_id MUST be 64 lowercase hex characters
           and MUST equal the identity recomputed per Section 4.5.  Any
           mismatch MUST be reported: the body was tampered with or was
           produced by a non-canonical builder."""),
    ]),
    ("para", W("""Envelope verification, given a parsed JSON value and
       optionally a public key, proceeds in stages:""")),
    ("ol", [
        W("""Naming: the artifact's filename MUST satisfy Section 8 for
           the envelope's actual signature state.  Failure here is a
           verification failure, not a warning."""),
        W("""Structure: payloadType MUST be a non-empty string; payload
           MUST decode under strict base64; signatures MUST be an
           array."""),
        W("""Signature: if a public key was supplied, at least one
           signature entry MUST verify over the PAE (Section 6.2) of the
           embedded (payloadType, payload) pair under that key; malformed
           entries are skipped, and the result is boolean: authentic
           under this key, or not.  If no key was supplied, the signature
           stage is skipped and MUST be reported as not checked, never as
           passed."""),
        W("""Payload: the decoded payload of a GAR envelope SHOULD itself
           be verified as a receipt per the first list."""),
    ]),
    ("para", W("""Chain verification consumes a complete chain from
       genesis and reports each defect of Section 7.2 as a distinct,
       codeable finding, then applies the external anchors of
       Section 7.3 when supplied.  A chain verifier MUST accept
       expected_entries and expected_head inputs; a chain verified
       without anchors MUST be reported with the truncation caveat
       stated.""")),
    ("para", W("""The reference implementation's command-line verifier
       maps these outcomes onto exit codes: 0 for success, 2 for
       verification failure (the artifact is reachable but untrustworthy:
       tamper, dishonest naming, chain break), and 3 for usage or I/O
       error.  The distinction between 2 and 3 is the difference between
       an incident and a retry, and integrations SHOULD preserve it.""")),
]})

S.append({"h": "11.  Security Considerations", "toc": "11.  Security Considerations", "b": [
    ("para", W("""Digest agility.  SHA-256 [FIPS202] is hard-coded for
       this version.  A future revision that admits another hash function
       MUST do so by changing the receipt_type version string, not by
       overloading field contents; the closed member set and the
       content-addressed identity mean an algorithm change produces a
       different format, and should be named like one.""")),
    ("para", W("""Canonicalization failures are security failures.  A
       verifier that canonicalizes differently from the producer will
       either reject valid receipts (availability) or, worse, accept a
       receipt under an identity the producer never computed.  The
       UTF-16 member ordering and ECMAScript number formatting of
       Section 5 are the two places independent implementations diverge;
       the worked example of Appendix B is a conformance test: an
       implementation that cannot reproduce its receipt_id is not a GAR
       implementation.""")),
    ("para", W("""Unsigned receipts carry no authenticity.  An honest
       unsigned receipt (Section 8) proves only integrity of its own
       bytes.  Verifiers MUST NOT report an unsigned receipt as
       authenticated, and pipelines SHOULD treat unsigned receipts as
       inadmissible for promotion decisions.""")),
    ("para", W("""Key custody.  Ed25519 private keys are offline,
       operator-held artifacts.  The reference implementation writes
       private keys unencrypted with file mode 0600 and refuses to
       overwrite an existing key, because accidental key rotation is a
       silent audit gap; deliberate rotation is an operator decision.  Key
       compromise revokes nothing automatically: verifiers pin keys
       directly, and a compromised key's receipts remain verifiable
       forgeries until the verifier's key set is updated.""")),
    ("para", W("""Log completeness requires anchors.  As stated in
       Section 7.3, tail truncation of a chain is undetectable without an
       external anchor, and deployments MUST obtain anchors out of band or
       from a transparency service [SCITT] [SIGSTORE].  Forks (two chains
       with a common prefix) are detectable only by comparing heads or by
       a witness that refuses double-booking; the chain format makes such
       comparison cheap, it does not perform it.""")),
    ("para", W("""Timestamps are claims.  created_at is supplied by the
       producer's clock.  A receipt authenticates that the signer
       asserted a time, not that the assertion was true.  Deployments
       requiring trustworthy time SHOULD anchor chain heads with a
       timestamping or transparency service, as Section 7.3
       describes.""")),
    ("para", W("""Denial of service.  Receipts are small by construction,
       but envelope and chain parsing MUST bound memory: artifact hashing
       is streamed (the reference implementation reads 1 MiB chunks),
       and verifiers SHOULD bound accepted file sizes for chain
       inputs.""")),
]})

S.append({"h": "12.  IANA Considerations", "toc": "12.  IANA Considerations", "b": [
    ("para", W("""This document requests registration of the following
       media type in the "Application Media Types" registry.  At the time
       of writing the type is unregistered and provisional; this section
       serves as the registration template per RFC 6838 [RFC6838].  Until
       registration is confirmed, the type MUST be regarded as
       provisional and unregistered.""")),
    ("dl", [
        ("Type name", "application"),
        ("Subtype name", "gar+json"),
        ("Required parameters", "none"),
        ("Optional parameters", "none"),
        ("Encoding considerations", W("""binary (JSON text in UTF-8).  The
            payload of a signed artifact is a DSSE envelope whose payload
            member carries base64-encoded canonical JSON.""")),
        ("Security considerations", W("""See Section 11 of this document.
            Content may be signed per Section 6; unsigned content follows
            the naming convention of Section 8.  Verifiers MUST apply the
            behavior of Section 10.""")),
        ("Interoperability considerations", W("""All digest-bearing fields
            depend on RFC 8785 canonicalization; see Section 5.""")),
        ("Published specification", "this document"),
        ("Applications that use this media type", W("""governance,
            build-system, and audit tooling producing or consuming
            Governed Action Receipts.""")),
        ("Intended usage", "COMMON"),
        ("Change controller", "Stephen Lutar <stephen@szlholdings.com>"),
    ]),
    ("para", W("""A registry for outcome values is not requested: the
       vocabulary of Section 9 is closed by design and can be extended
       only by a revision of this document, so that no deployment can
       unilaterally add an outcome that gates cannot interpret.""")),
]})

front["ack"] = [
    W("""The format specified here is implemented and exercised daily by
       the szl-receipts library within the SZL Holdings estate; its test
       suite, which drives truncation, reorder, replay, fork,
       broken-link, payload bit-flip, wrong-key, PAE prefix-collision,
       and dishonest-rename cases, served as the executable adversarial
       review for this document.  The DSSE specification, the in-toto
       project, and the SCITT working group's architecture draft provided
       the substrate this format composes with."""),
]

front["refs_norm"] = [
    ("DSSE", "Santiago Torres-Arias et al., \"Dead Simple Signing Envelope\", Secure Systems Lab, https://github.com/secure-systems-lab/dsse"),
    ("FIPS202", "NIST, \"SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions\", FIPS PUB 202, August 2015, DOI 10.6028/NIST.FIPS.202, https://doi.org/10.6028/NIST.FIPS.202"),
    ("RFC2119", "Bradner, S., \"Key words for use in RFCs to Indicate Requirement Levels\", BCP 14, RFC 2119, DOI 10.17487/RFC2119, March 1997, https://www.rfc-editor.org/info/rfc2119"),
    ("RFC7493", "Bray, T., Ed., \"The I-JSON Message Format\", RFC 7493, DOI 10.17487/RFC7493, March 2015, https://www.rfc-editor.org/info/rfc7493"),
    ("RFC8032", "Josefsson, S. and I. Liusvaara, \"Edwards-Curve Digital Signature Algorithm (EdDSA)\", RFC 8032, DOI 10.17487/RFC8032, January 2017, https://www.rfc-editor.org/info/rfc8032"),
    ("RFC8174", "Leiba, B., \"Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words\", BCP 14, RFC 8174, DOI 10.17487/RFC8174, May 2017, https://www.rfc-editor.org/info/rfc8174"),
    ("RFC8259", "Bray, T., Ed., \"The JavaScript Object Notation (JSON) Data Interchange Format\", STD 90, RFC 8259, DOI 10.17487/RFC8259, December 2017, https://www.rfc-editor.org/info/rfc8259"),
    ("RFC8785", "Rundgren, A., Jordan, B., and S. Erdtman, \"JSON Canonicalization Scheme (JCS)\", RFC 8785, DOI 10.17487/RFC8785, June 2020, https://www.rfc-editor.org/info/rfc8785"),
]

front["refs_info"] = [
    ("AAT", "Sharif, R., \"Agent Audit Trail: A Standard Logging Format for Autonomous AI Systems\", Work in Progress, Internet-Draft, draft-sharif-agent-audit-trail-01, August 19, 2026, https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/"),
    ("INTOTO", "Torres-Arias, S. et al., \"in-toto: Providing farm-to-table guarantees for bits and bytes\", USENIX Security 2019; in-toto Attestation Framework, https://in-toto.io/"),
    ("RFC6838", "Freed, N., Klensin, J., and T. Hansen, \"Media Type Specifications and Registration Procedures\", BCP 13, RFC 6838, DOI 10.17487/RFC6838, January 2013, https://www.rfc-editor.org/info/rfc6838"),
    ("SCITT", "Birkholz, H., Delignat-Lavaud, A., Fournet, C., Deshpande, Y., and S. Lasker, \"An Architecture for Trustworthy and Transparent Digital Supply Chains\", Work in Progress, Internet-Draft, draft-ietf-scitt-architecture, https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/"),
    ("SIGSTORE", "The Sigstore Project, \"Sigstore: Software Signing and Transparency\", https://www.sigstore.dev/"),
    ("SZLR", "SZL Holdings, \"szl-receipts 14.0.0: reference implementation of this document\", Python package, https://github.com/szl-holdings (search: szl-receipts)"),
]

S.append({"h": "Appendix A.  Reference Implementation Map", "toc": "Appendix A.  Reference Implementation Map", "b": [
    ("para", W("""For reviewers cross-checking this document against code:
       szl-receipts 14.0.0, package szl_receipts.""")),
    ("dl", [
        ("Section 4", "receipt.py: build_receipt, verify_receipt, compute_receipt_id"),
        ("Section 5", "jcs.py: jcs_canon_bytes, serialize, number_to_js_str"),
        ("Section 6", "dsse.py: pae, sign_bytes, verify_envelope, statement, keygen"),
        ("Section 7", "chain.py: append, entry_digest_for, verify_chain"),
        ("Section 8", "naming.py: write_envelope, verify_honest_naming, NamingError"),
        ("Section 9", "outcome.py: Outcome, is_passing, promotion_gate"),
        ("Section 10", "receipt.py and chain.py verifiers; cli.py exit-code contract"),
        ("digests", "digests.py: sha256_file (1 MiB chunks), sha256_hex, sha256_bytes"),
    ]),
]})

S.append({"h": "Appendix B.  Worked Example and Reproduction", "toc": "Appendix B.  Worked Example and Reproduction", "b": [], "sub": [
    {"h": "B.1.  Inputs", "b": [
        ("para", W("""Two files are created with fixed content:""")),
        ("art", [
            "mkdir -p policies dist",
            "printf 'SZL Build Policy v14\\nAll governed builds must be \\",
            "  reproducible and receipted.\\n' > policies/szl.build.v14.md",
            "printf 'SZL MASTER PAYLOAD V14\\n' > dist/SZL_MASTER_PAYLOAD_V14.md",
        ]),
        ("para", W(f"""Their SHA-256 digests are {EX['policy_digest']}
           (policy) and {EX['subject_digest']} (payload artifact).  The
           example Ed25519 key is derived from the fixed seed
           SHA-256("draft-lutar-governed-action-receipt example key") via
           Ed25519PrivateKey.from_private_bytes; it is a public test
           vector and MUST NOT be used operationally.  Its public key
           is:""")),
        ("art", art_pub),
    ]},
    {"h": "B.2.  Reproduction Script", "b": [
        ("para", W("""With szl-receipts installed (pip install -e
           ./szl-receipts, version 14.0.0, on Python >= 3.11 with the
           cryptography library >= 42), the following script regenerates
           every value in Sections 4.3, 4.4, 6.5, and 7.1.  Output is
           deterministic: created_at is fixed and the key is fixed.""")),
        ("art", reproduce_script),
    ]},
    {"h": "B.3.  Expected Digests", "b": [
        ("art", [
            f"receipt_id:           {EX['receipt_id']}",
            "canonical bytes:      650",
            f"sha256(canonical):    {EX['canon_sha256']}",
            f"keyid:                {EX['example_keyid']}",
            f"genesis entry_digest: {EX['genesis_entry_digest']}",
            f"entry 2 entry_digest: {EX['entry2_digest']}",
            f"chain head:           {EX['chain_head']}",
        ]),
        ("para", W("""An implementation that reproduces these digests from
           these inputs implements Sections 4, 5, 6, and 7 correctly.
           The verification chain for the signed example also holds:
           verify_envelope on the envelope of Section 6.5 under the
           public key of B.1 returns true; verify_chain on the two-entry
           chain with expected_entries=2 and expected_head equal to the
           chain head above reports ok.""")),
    ]},
]})

front["author_addr"] = [
    "Stephen Lutar",
    "SZL Holdings",
    "Email: stephen@szlholdings.com",
]

# ---------------------------------------------------------------------------
# Plain-text renderer (RFC format: 72 cols, page headers, form feeds)
# ---------------------------------------------------------------------------

LW = 72  # line width
BODY = 53  # body lines per page (matches RFC 8032 pagination)


def wrap_para(text, indent=3, width=LW):
    return textwrap.wrap(text, width=width - indent, initial_indent=" " * indent,
                         subsequent_indent=" " * indent) or [" " * indent]


def wrap_cont(text, first_indent, cont_indent, width=LW):
    return textwrap.wrap(text, width=width - first_indent,
                         initial_indent=" " * first_indent,
                         subsequent_indent=" " * cont_indent) or [" " * first_indent]


def render_blocks(blocks):
    lines = []
    for kind, payload in blocks:
        if lines:
            lines.append("")
        if kind == "para":
            lines += wrap_para(payload)
        elif kind == "art":
            lines.append("")
            lines += payload
            lines.append("")
        elif kind == "ul":
            for i, item in enumerate(payload):
                seg = wrap_cont(item, 5, 7)
                seg[0] = "   * " + seg[0][5:]
                lines += seg
                if i < len(payload) - 1:
                    lines.append("")
        elif kind == "ol":
            for i, item in enumerate(payload):
                marker = f"{i+1}. "
                seg = wrap_cont(item, 5, 7)
                seg[0] = "   " + marker + seg[0][5:]
                lines += seg
                if i < len(payload) - 1:
                    lines.append("")
        elif kind == "dl":
            for i, (term, text) in enumerate(payload):
                seg = wrap_cont(text, 6, 9)
                lines.append("   " + term)
                lines += seg
                if i < len(payload) - 1:
                    lines.append("")
    return lines


def render_heading(h):
    return [h, ""]


def build_flow():
    """All lines before pagination (no ToC page numbers yet)."""
    flow = []
    flow += render_heading("Abstract")
    for p in front["abstract"]:
        flow += wrap_para(p)
        flow.append("")
    flow = flow[:-1]
    flow += ["", ""]
    flow += render_heading("Status of This Memo")
    for p in front["sotm"]:
        flow += wrap_para(p)
        flow.append("")
    flow = flow[:-1]
    flow += ["", ""]
    flow += render_heading("Copyright Notice")
    for p in front["copyright"]:
        flow += wrap_para(p)
        flow.append("")
    flow = flow[:-1]
    flow += ["", ""]
    for sec in S:
        flow += render_heading(sec["h"])
        flow += render_blocks(sec["b"])
        if sec["b"] and sec.get("sub"):
            flow.append("")
        for sub in sec.get("sub", []):
            flow += render_heading(sub["h"])
            flow += render_blocks(sub["b"])
        flow += ["", ""]
    flow += render_heading("Acknowledgements")
    for p in front["ack"]:
        flow += wrap_para(p)
        flow.append("")
    flow = flow[:-1]
    flow += ["", ""]
    flow += render_heading("References")
    flow += ["", "Normative References", ""]
    for tag, cit in front["refs_norm"]:
        seg = wrap_cont(cit, 9, 9)
        tagpart = f'   [{tag}]'
        seg[0] = tagpart + " " * (9 - len(tagpart)) + seg[0][9:]
        flow += seg
        flow.append("")
    flow = flow[:-1]
    flow += ["", "Informative References", ""]
    for tag, cit in front["refs_info"]:
        seg = wrap_cont(cit, 9, 9)
        tagpart = f'   [{tag}]'
        seg[0] = tagpart + " " * (9 - len(tagpart)) + seg[0][9:]
        flow += seg
        flow.append("")
    flow = flow[:-1]
    flow += ["", ""]
    flow += render_heading("Author's Address")
    flow += ["   " + a for a in front["author_addr"]]
    return flow


def heading_positions(flow):
    """Map display heading -> index in flow (1-based)."""
    pos = {}
    for i, line in enumerate(flow, start=1):
        for sec in S:
            if line == sec["h"]:
                pos[sec["h"]] = i
            for sub in sec.get("sub", []):
                if line == sub["h"]:
                    pos[sub["h"]] = i
    return pos


def paginate(flow):
    """Split flow (1-based logical lines) into pages of BODY lines.
    Pages are 1-based: page 1 is the front page (no header)."""
    pages = []
    cur = []
    for line in flow:
        if len(cur) == BODY:
            pages.append(cur)
            cur = []
        cur.append(line)
    pages.append(cur)
    return pages


def page_of(pos, flow_pages):
    """pos is a 1-based index into the flow; front page occupies
    (len(page1)) flow lines; page n>1 occupies BODY lines starting at
    flow line len(page1)+1 + (n-2)*BODY."""
    p1 = len(flow_pages[0])
    if pos <= p1:
        return 1
    return 2 + (pos - p1 - 1) // BODY


def toc_entries(pos, flow_pages):
    entries = []
    entries.append((0, "Abstract", 1))
    entries.append((0, "Status of This Memo", 1))
    entries.append((0, "Copyright Notice", 1))
    for sec in S:
        entries.append((0, sec["toc"], page_of(pos[sec["h"]], flow_pages)))
        for sub in sec.get("sub", []):
            entries.append((1, sub["h"], page_of(pos[sub["h"]], flow_pages)))
    entries.append((0, "Acknowledgements",
                    page_of(next(i for i, l in _enum_flow(flow_pages) if l == "Acknowledgements"), flow_pages)))
    entries.append((0, "References",
                    page_of(next(i for i, l in _enum_flow(flow_pages) if l == "References"), flow_pages)))
    entries.append((0, "Author's Address",
                    page_of(next(i for i, l in _enum_flow(flow_pages) if l == "Author's Address"), flow_pages)))
    return entries


def _enum_flow(flow_pages):
    idx = 0
    for page in flow_pages:
        for line in page:
            idx += 1
            yield idx, line


def toc_line(level, label, page):
    if level == 0:
        left = f"   {label}"
    else:
        left = f"     {label}"
    if label.startswith("Appendix"):
        # no dot leaders for appendices (xml2rfc convention)
        return left + " " * (69 - len(left)) + str(page)
    dots = 69 - len(left) - 3
    return left + "  ." + " ." * (dots // 2) + (" ." if dots % 2 else "") + "   " + str(page)


def render_toc(entries):
    lines = ["", "", "Table of Contents", ""]
    for level, label, page in entries:
        lines.append(toc_line(level, label, page))
    return lines


def header_line(page):
    if page == 1:
        return None
    return "Lutar                       Expires 4 March 2027".ljust(50) + f"[Page {page}]"


def page_footer(page):
    return ("Lutar".ljust(29) + "Expires 4 March 2027".ljust(22) + f"[Page {page}]").rstrip()


def render_txt(flow, entries):
    pages = paginate(flow)
    out = []
    # ---- front page ----
    p1 = pages[0]
    out += ["", "", ""]
    out.append("Internet Engineering Task Force" + " " * 34 + "S. Lutar")
    out.append("Internet-Draft" + " " * 46 + "SZL Holdings")
    out.append("Intended status: Informational" + " " * 15 + DATE)
    out.append(f"Expires: {EXPIRES}" + " " * 55 + "")
    out += ["", ""]
    out += [" " * ((LW - len(TITLE)) // 2) + TITLE if len(TITLE) <= LW else TITLE]
    out.append(" " * ((LW - len(DOCNAME)) // 2) + DOCNAME)
    out += ["", ""]
    out += p1
    # pad page 1 to BODY+? front page: title block consumed some lines
    out += [""] * (BODY + 2 - len(out))  # placeholder; fixed below
    out = out[:BODY + 2]
    out.append(page_footer(1))
    out.append("\f")
    # ---- page 2: ToC ----
    toc = render_toc(entries)
    out.append(header_line(2))
    out += ["", ""]
    out += toc
    out += [""] * (BODY + 2 - (1 + 2 + len(toc)))
    out.append(page_footer(2))
    out.append("\f")
    # ---- subsequent pages ----
    for pnum in range(2, len(pages) + 1):
        body = pages[pnum - 1]
        display = pnum + 1
        out.append(header_line(display))
        out += ["", ""]
        out += body
        out += [""] * (BODY + 2 - (3 + len(body)))
        out.append(page_footer(display))
        if pnum != len(pages):
            out.append("\f")
    out.append("")
    return "\n".join(out)


# The flow begins after the ToC; but front page contains abstract start...
# Simplify: front page = title block + start of flow (abstract etc.).
# Rebuild properly below.

def build_txt():
    flow = build_flow()
    pages = paginate(flow)
    pos = heading_positions(flow)
    entries = toc_entries(pos, pages)

    lines = []

    def emit_page(body_lines, page_num, is_front=False):
        if is_front:
            lines.extend(["", "", ""])
            lines.append("Internet Engineering Task Force".ljust(65) + "S. Lutar")
            lines.append("Internet-Draft".ljust(60) + "SZL Holdings")
            lines.append("Intended status: Informational".ljust(45) + DATE)
            lines.append(f"Expires: {EXPIRES}")
            lines.extend(["", ""])
            for tline in textwrap.wrap(TITLE, 60):
                lines.append(tline.center(LW).rstrip())
            lines.append(DOCNAME.center(LW).rstrip())
            lines.extend(["", ""])
        else:
            lines.append(header_line(page_num))
            lines.extend(["", ""])
        lines.extend(body_lines)
        # pad to 56 content lines
        content = len(lines) - (0 if not lines else 0)
        return

    # Front page: title block (13 lines incl. leading blanks) + body start
    front_body = pages[0]
    emit_page([], 1, is_front=True)
    lines.extend(front_body)
    lines.extend([""] * (69 - len(lines)))
    lines.append(page_footer(1))
    lines.append("\f")

    # ToC on page 2
    lines.append(header_line(2))
    lines.extend(["", ""])
    toc = render_toc(entries)
    lines.extend(toc)
    lines.extend([""] * (59 - (4 + len(toc))))
    lines.append(page_footer(2))
    lines.append("\f")

    # Remaining pages
    for pnum in range(2, len(pages) + 1):
        display = pnum + 1
        lines.append(header_line(display))
        lines.extend(["", ""])
        body = pages[pnum - 1]
        lines.extend(body)
        lines.extend([""] * (56 - (4 + len(body))))
        lines.append(page_footer(display))
        if pnum != len(pages):
            lines.append("\f")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown (kramdown-rfc style) renderer
# ---------------------------------------------------------------------------

def md_blocks(blocks, indent=0):
    out = []
    for kind, payload in blocks:
        if kind == "para":
            out.append(textwrap.fill(payload, 80))
        elif kind == "art":
            out.append("~~~")
            out += payload
            out.append("~~~")
        elif kind == "ul":
            out += ["* " + textwrap.fill(i, 76, subsequent_indent="  ") for i in payload]
        elif kind == "ol":
            out += [f"{n}. " + textwrap.fill(i, 75, subsequent_indent="   ")
                    for n, i in enumerate(payload, 1)]
        elif kind == "dl":
            for term, text in payload:
                out.append(f"{term}:")
                out.append(textwrap.fill(text, 76, initial_indent=":   ",
                                         subsequent_indent="    "))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def build_md():
    p = []
    p.append("---")
    p.append("title: " + TITLE)
    p.append("abbrev: Governed Action Receipt")
    p.append("docname: " + DOCNAME)
    p.append("category: info")
    p.append("submissiontype: IETF")
    p.append("ipr: trust200902")
    p.append("date: 2026-08-31")
    p.append("author:")
    p.append("  -")
    p.append("    fullname: Stephen Lutar")
    p.append("    organization: SZL Holdings")
    p.append("    email: stephen@szlholdings.com")
    p.append("")
    p.append("normative:")
    for tag, cit in front["refs_norm"]:
        p.append(f"  {tag}:")
        if tag.startswith("RFC"):
            p.append("    target: https://www.rfc-editor.org/info/" + tag.lower())
        elif tag == "DSSE":
            p.append("    title: \"Dead Simple Signing Envelope\"")
            p.append("    author:")
            p.append("      - org: Secure Systems Lab")
            p.append("    target: https://github.com/secure-systems-lab/dsse")
        elif tag == "FIPS202":
            p.append("    title: \"SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions\"")
            p.append("    author:")
            p.append("      - org: NIST")
            p.append("    date: 2015-08")
            p.append("    target: https://doi.org/10.6028/NIST.FIPS.202")
    p.append("")
    p.append("informative:")
    info_meta = {
        "AAT": ("Agent Audit Trail: A Standard Logging Format for Autonomous AI Systems",
                "R. Sharif", "2026-08-19",
                "https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/"),
        "INTOTO": ("in-toto: Providing farm-to-table guarantees for bits and bytes",
                   "S. Torres-Arias et al.", "2019", "https://in-toto.io/"),
        "SCITT": ("An Architecture for Trustworthy and Transparent Digital Supply Chains",
                  "H. Birkholz et al.", None,
                  "https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/"),
        "SIGSTORE": ("Sigstore: Software Signing and Transparency",
                     "The Sigstore Project", None, "https://www.sigstore.dev/"),
        "SZLR": ("szl-receipts 14.0.0: reference implementation of this document",
                 "SZL Holdings", "2026", "https://github.com/szl-holdings"),
    }
    for tag, cit in front["refs_info"]:
        if tag.startswith("RFC"):
            p.append(f"  {tag}:")
            p.append("    target: https://www.rfc-editor.org/info/" + tag.lower())
            continue
        title, author, date, target = info_meta[tag]
        p.append(f"  {tag}:")
        p.append(f'    title: "{title}"')
        p.append("    author:")
        p.append(f"      - name: {author}")
        if date:
            p.append(f"    date: {date}")
        p.append(f"    target: {target}")
    p.append("")
    p.append("--- abstract")
    p.append("")
    for para in front["abstract"]:
        p.append(textwrap.fill(para, 80))
        p.append("")
    p.append("--- middle")
    p.append("")
    for sec in S:
        mdh = sec["toc"]
        if mdh.startswith("Appendix"):
            # appendices are emitted later in back matter
            continue
        p.append("# " + re_split_heading(mdh))
        p.append("")
        if sec["b"]:
            p.append(md_blocks(sec["b"]))
        for sub in sec.get("sub", []):
            p.append("## " + re_split_heading(sub["h"]))
            p.append("")
            p.append(md_blocks(sub["b"]))
    p.append("# Acknowledgements")
    p.append("")
    for para in front["ack"]:
        p.append(textwrap.fill(para, 80))
        p.append("")
    p.append("--- back")
    p.append("")
    for sec in S:
        if not sec["toc"].startswith("Appendix"):
            continue
        p.append("# " + re_split_heading(sec["toc"]))
        p.append("")
        if sec["b"]:
            p.append(md_blocks(sec["b"]))
        for sub in sec.get("sub", []):
            p.append("## " + re_split_heading(sub["h"]))
            p.append("")
            p.append(md_blocks(sub["b"]))
    return "\n".join(p)


def re_split_heading(h):
    """'4.  Receipt Format' -> 'Receipt Format {#receipt-format}'"""
    import re as _re
    m = _re.match(r"^([\d.]+)\.\s+(.*)$", h)
    if m and not h.startswith("Appendix"):
        title = m.group(2).strip()
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return title
    if h.startswith("Appendix"):
        return h.split(".  ", 1)[1]
    return h


# ---------------------------------------------------------------------------

md = build_md()
(OUT / f"{DOCNAME}.md").write_text(md)

txt = build_txt()
(OUT / f"{DOCNAME}.txt").write_text(txt)

# validation
lines = txt.split("\n")
over = [(i + 1, l) for i, l in enumerate(lines) if len(l) > 72]
print("lines > 72 cols:", len(over))
for i, l in over[:10]:
    print("  ", i, len(l), l[:80])
print("form feeds:", txt.count("\f"))
print("total lines:", len(lines))
print("total pages:", txt.count("\f") + 1)

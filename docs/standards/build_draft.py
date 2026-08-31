#!/usr/bin/env python3
"""Build draft-lutar-governed-action-receipt-00.{md,txt} from one source.

The document is authored once (DOC below) and rendered twice:

  * .md  -- kramdown-rfc2629 source (the submission source format)
  * .txt -- RFC-style plain text: 72 columns, page headers and footers,
            form feeds between pages, a Table of Contents with page
            numbers, and RFC 8792 single-backslash folding for figure
            lines that would exceed the column limit.

All worked-example bytes and digests are computed HERE, at build time, by
the installed szl-receipts 14.0.0 library -- nothing is transcribed by
hand, so the document cannot drift from the implementation it specifies.
"""
import json
import re
import textwrap
from pathlib import Path

from szl_receipts import (
    Outcome, append, build_receipt, compute_receipt_id, jcs_canon_bytes,
    pae, sha256_file, sha256_hex, sign_bytes, verify_chain,
    verify_envelope, verify_receipt,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = Path("/home/user/workspace/szl-platform/docs/standards")
GAR = Path("/home/user/workspace/gar-example")

DOCNAME = "draft-lutar-governed-action-receipt-00"
TITLE = "The Governed Action Receipt (GAR) Format"
ABBREV = "Governed Action Receipt"
AUTHOR_FULL = "Stephen Lutar"
AUTHOR_SHORT = "Lutar"
AUTHOR_INITIALS = "S. Lutar"
ORG = "SZL Holdings"
EMAIL = "stephen@szlholdings.com"
DATE_ISO = "2026-08-31"
DATE_TEXT = "31 August 2026"
MONTH_YEAR = "August 2026"
EXPIRES_TEXT = "4 March 2027"  # 2026-08-31 + 185 days (xml2rfc convention)
VERSION = "00"

# ---------------------------------------------------------------------------
# Compute the worked example with the real library (deterministic inputs)
# ---------------------------------------------------------------------------

POLICY_FILE = GAR / "policies" / "szl.build.v14.md"
SUBJECT_FILE = GAR / "dist" / "SZL_MASTER_PAYLOAD_V14.md"
POLICY_DIGEST = sha256_file(POLICY_FILE)
SUBJECT_DIGEST = sha256_file(SUBJECT_FILE)

RECEIPT = build_receipt(
    actor="ci-runner-7",
    action="build-master-payload",
    policy={"id": "szl.build.v14", "version": "14.0.0",
            "digest_sha256": POLICY_DIGEST},
    outcome=Outcome.PASS,
    rationale="deterministic rebuild verified byte-identical",
    subjects=[{"name": "dist/SZL_MASTER_PAYLOAD_V14.md",
               "sha256": SUBJECT_DIGEST}],
    evidence=[{"uri": "https://ci.szl.example/runs/2026-08-31-001"}],
    created_at="2026-08-31T18:00:00Z",
)
assert verify_receipt(RECEIPT) == []
assert RECEIPT["receipt_id"] == compute_receipt_id(RECEIPT)
RECEIPT_PRETTY = json.dumps(RECEIPT, indent=2, sort_keys=True)
CANON = jcs_canon_bytes(dict(RECEIPT))
CANON_TEXT = CANON.decode("utf-8")
CANON_SHA = sha256_hex(CANON)
IDLESS = {k: v for k, v in RECEIPT.items() if k != "receipt_id"}
IDLESS_LEN = len(jcs_canon_bytes(IDLESS))
assert sha256_hex(jcs_canon_bytes(IDLESS)) == RECEIPT["receipt_id"]

SEED = bytes.fromhex(sha256_hex(b"draft-lutar-governed-action-receipt example key"))
EXAMPLE_KEY = Ed25519PrivateKey.from_private_bytes(SEED)
EXAMPLE_PUB_PEM = EXAMPLE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo).decode().strip()
ENVELOPE = sign_bytes(CANON, "application/gar+json", EXAMPLE_KEY)
assert verify_envelope(ENVELOPE, EXAMPLE_KEY.public_key())
ENVELOPE_PRETTY = json.dumps(ENVELOPE, indent=2, sort_keys=True)
KEYID = ENVELOPE["signatures"][0]["keyid"]
SIG_B64 = ENVELOPE["signatures"][0]["sig"]
PAE_DEMO = pae(b"a", b"bc").decode("ascii")
PAE_EXAMPLE = pae(b"application/gar+json", CANON)
PAE_PREFIX = PAE_EXAMPLE[:40].decode("ascii")
PAE_TOTAL = len(PAE_EXAMPLE)

RECEIPT2 = build_receipt(
    actor="ci-runner-7",
    action="promote-master-payload",
    policy={"id": "szl.build.v14", "version": "14.0.0",
            "digest_sha256": POLICY_DIGEST},
    outcome=Outcome.PASS,
    rationale="promotion gate passed on PASS receipt",
    subjects=[{"name": "dist/SZL_MASTER_PAYLOAD_V14.md",
               "sha256": SUBJECT_DIGEST}],
    evidence=[{"uri": "https://ci.szl.example/runs/2026-08-31-001"}],
    created_at="2026-08-31T18:05:00Z",
)
CHAIN = []
ENTRY1 = append(CHAIN, RECEIPT)
ENTRY2 = append(CHAIN, RECEIPT2)
REPORT = verify_chain(CHAIN, expected_entries=2,
                      expected_head=ENTRY2["entry_digest"])
assert REPORT.ok
ENTRY1_PRETTY = json.dumps(ENTRY1, indent=2, sort_keys=True)
CHAIN_PRETTY = json.dumps(CHAIN, indent=2, sort_keys=True)

REPRO_SCRIPT = (HERE / "reproduce-appendix-b.py").read_text().rstrip("\n")

# ---------------------------------------------------------------------------
# Content model
# ---------------------------------------------------------------------------
# block = ("p", text) | ("art", [lines]) | ("ul", [items]) | ("ol", [items])
#       | ("dl", [(term, text)])
# In text, citations are written [TAG].

def t(text):
    return " ".join(text.split())


ABSTRACT = [
    t("""This document specifies the Governed Action Receipt (GAR), a
       compact, tamper-evident record that binds an actor, an action, a
       governing policy identified by the SHA-256 digest of the policy
       document, a decision outcome drawn from a closed vocabulary, the
       subjects of the action identified by digests of their bytes, and
       references to evidence.  A receipt is canonicalized with the JSON
       Canonicalization Scheme [RFC8785] and is self-identifying: its
       receipt_id is the SHA-256 digest of its canonical body with the
       identity field removed, so any field-level modification is
       detectable by any verifier without trusting a registry."""),
    t("""Receipts are carried in DSSE envelopes [DSSE] signed with Ed25519
       [RFC8032], or are published honestly unsigned under a naming
       convention that makes the absence of a signature legible from the
       filename.  Receipts may be linked into an append-only hash-chained
       log in which each entry commits to its predecessor; the limits of
       that construction, in particular the undetectability of tail
       truncation without an external anchor, are stated explicitly.  The
       outcome vocabulary forbids promoting an unknown verdict to a
       passing one.  This document specifies the receipt format,
       canonicalization, signing, chaining, naming, outcomes, and
       verifier behavior, and matches the reference implementation
       (szl-receipts 14.0.0 [SZLR]) statement for statement."""),
]

SOTM = [
    "This Internet-Draft is submitted in full conformance with the "
    "provisions of BCP 78 and BCP 79.",
    t("""Internet-Drafts are working documents of the Internet Engineering
       Task Force (IETF).  Note that other groups may also distribute
       working documents as Internet-Drafts.  The list of current
       Internet-Drafts is at https://datatracker.ietf.org/drafts/current/."""),
    t("""Internet-Drafts are draft documents valid for a maximum of six
       months and may be updated, replaced, or obsoleted by other documents
       at any time.  It is inappropriate to use Internet-Drafts as reference
       material or to cite them other than as "work in progress"."""),
    f"This Internet-Draft will expire on {EXPIRES_TEXT}.",
]

COPYRIGHT = [
    t("""Copyright (c) 2026 IETF Trust and the persons identified as the
       document authors.  All rights reserved."""),
    t("""This document is subject to BCP 78 and the IETF Trust's Legal
       Provisions Relating to IETF Documents
       (https://trustee.ietf.org/license-info) in effect on the date of
       publication of this document.  Please review these documents
       carefully, as they describe your rights and restrictions with respect
       to this document.  Code Components extracted from this document must
       include Revised BSD License text as described in Section 4.e of the
       Trust Legal Provisions and are provided without warranty as described
       in the Revised BSD License."""),
]

# Sections: (anchor, number-or-None, title, blocks)
# Subsections are encoded inline via ("h2", title) block markers.
S1 = ("intro", "1.", "Introduction", [
    ("p", t("""Automated systems increasingly perform actions with
       operational consequences: building software, deploying
       infrastructure, admitting or rejecting artifacts, approving
       changes.  Each such action is justified by a policy, and each
       justification evaporates when the pipeline finishes unless a record
       is kept.  The records that are kept are usually prose logs:
       greppable, mutable, and impossible to verify independently.""")),
    ("p", t("""This document specifies the Governed Action Receipt (GAR).
       A receipt is a small JSON object [RFC8259] recording that a named
       actor performed a named action under a named policy, with a stated
       outcome, over stated artifacts.  The policy is identified by
       identifier, version, and the SHA-256 digest of the policy
       document's bytes; the artifacts (subjects) are identified by the
       SHA-256 digests of their bytes, never by filename alone.  The
       receipt's own identity, receipt_id, is the SHA-256 digest of its
       canonical form with the identity field removed, so a receipt is
       content-addressed: parties that agree on the bytes agree on the
       identity, and any party that alters a byte produces a different
       identity.""")),
    ("p", t("""Three design rules, taken from the doctrine of the estate
       that operates the reference implementation, bind everything that
       follows:""")),
    ("ul", [
        t("""Bytes, not names.  Every digest in a receipt covers artifact
           bytes, never path strings; a name is a claim and bytes are
           ground truth."""),
        t("""Honest names.  An empty signatures array is not a signature.
           An unsigned artifact is named *.unsigned.json, and a filename
           that lies about the signature state is a verification failure
           (Section 8).  Renaming a file must never change what the world
           believes about it."""),
        t("""UNKNOWN is never passing.  The outcome vocabulary is closed
           (Section 9); the absence of a verdict is not a verdict; a
           promotion gate must not promote what it cannot
           characterize."""),
    ]),
    ("p", t("""A receipt is verifiable offline with nothing but the
       document bytes, a SHA-256 implementation, and, for signed receipts,
       an Ed25519 implementation.  No online service, trusted registry, or
       vendor is required.  Where a deployment wants third-party
       witnessing, receipts compose with transparency and attestation
       infrastructure (Section 7.3).""")),
    ("p", t("""This document is an individual submission to the IETF and
       is published as Informational.  Every normative statement in it
       describes behavior that the reference implementation, szl-receipts
       14.0.0 [SZLR], executes; Appendix B contains a complete worked
       example whose every byte is reproducible from the commands given
       there.  Where this document and the implementation disagree, the
       disagreement is a defect in one of them.""")),
    ("p", t("""Related work: [AAT] specifies a JSON logging format for
       autonomous AI agents with hash chaining; like this document, it is
       an individual Internet-Draft with no formal standing in the IETF
       standards process.  The SCITT architecture [SCITT] defines
       transparency services for supply-chain statements; Section 7.3
       describes how GAR chains obtain external anchors from such
       services.  Sigstore [SIGSTORE] provides public signing and
       transparency infrastructure, and in-toto [INTOTO] the attestation
       container with which Section 6.4 composes.""")),
])

S2 = ("terms", "2.", "Terminology", [
    ("dl", [
        ("receipt", t("""A JSON object of receipt_type "GovernedAction/v1"
            as defined in Section 4.""")),
        ("GAR", "The Governed Action Receipt format specified here."),
        ("actor", t("""The entity that performed the governed action; a
            non-empty string whose semantics are deployment-defined (a CI
            runner name, a person, a service account).""")),
        ("action", "A non-empty string naming the governed operation."),
        ("policy", t("""The rule set under which the action was governed,
            identified by an identifier string, a version string, and the
            SHA-256 digest of the policy document's bytes.""")),
        ("subject", t("""An artifact the action operated upon, identified
            by a name (a label) and the SHA-256 digest of its bytes.""")),
        ("evidence", t("""A URI pointing at supporting material (build
            logs, attestations, run records), optionally pinned by a
            SHA-256 digest of the bytes behind the URI.""")),
        ("outcome", t("""The verdict of the governed action, drawn from
            the closed vocabulary of Section 9.""")),
        ("receipt identity", t("""The value of the receipt_id member: the
            SHA-256 digest, in lowercase hexadecimal, of the canonical
            form of the receipt with the receipt_id member removed
            (Section 4.5).""")),
        ("canonical form", t("""The serialization of a JSON value under
            the JSON Canonicalization Scheme [RFC8785]; see
            Section 5.""")),
        ("DSSE envelope", t("""The wrapping structure defined by [DSSE]:
            payload, payloadType, signatures; see Section 6.""")),
        ("PAE", t("""The Pre-Authentication Encoding defined by [DSSE]:
            the domain-separated byte string over which signatures are
            computed; see Section 6.2.""")),
        ("chain entry", t("""A record binding a receipt to a sequence
            number and to the digest of the preceding entry; see
            Section 7.""")),
        ("chain head", "The entry_digest of the final entry of a chain."),
        ("external anchor", t("""Information about a chain obtained from
            outside the chain: an expected entry count, an expected head
            digest, or a witnessed inclusion proof; see Section 7.3.""")),
        ("finding", t("""A problem report emitted by a verifier.  An empty
            findings list is the only success signal (Section 10).""")),
    ]),
])

S3 = ("conventions", "3.", "Conventions and Definitions", [
    ("p", t("""The key words "MUST", "MUST NOT", "REQUIRED", "SHALL",
       "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT
       RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
       interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and
       only when, they appear in all capitals, as shown here.""")),
    ("p", t("""The following notation is used throughout:""")),
    ("ul", [
        t("""hex64: a string of exactly 64 lowercase hexadecimal
           characters (matching the regular expression [0-9a-f]{64}),
           encoding a 32-byte digest."""),
        t("""SHA-256(x): the SHA-256 digest [FIPS180-4] of byte string x,
           rendered as hex64."""),
        t("""JCS(x): the canonical serialization of JSON value x per
           [RFC8785], as UTF-8 bytes (Section 5)."""),
        t("""JSON text: text conforming to [RFC8259].  Input to
           canonicalization MUST also conform to I-JSON [RFC7493]."""),
        t("""The reference implementation: szl-receipts 14.0.0 [SZLR], a
           Python package whose only runtime dependency beyond the
           standard library is the "cryptography" package."""),
    ]),
    ("p", t("""Timestamps use the ISO 8601 profile of Section 4.2.  JSON
       member names appear in double quotes in prose (for example,
       "receipt_id") and appear literally in artwork.""")),
])

S4 = ("format", "4.", "Receipt Format", [
    ("h2", "Receipt Members"),
    ("p", t("""A receipt is a JSON object [RFC8259] containing exactly the
       ten members defined below.  A verifier MUST report any missing
       member and any additional member; the set is closed so that a
       producer cannot smuggle un-verified semantics past a verifier in
       extension fields.  Member order is insignificant: every integrity
       computation operates on the canonical form (Section 5), which
       absorbs ordering and whitespace.""")),
    ("dl", [
        ("receipt_id", t("""REQUIRED.  String, hex64.  The receipt
            identity, computed as specified in Section 4.5.""")),
        ("receipt_type", t("""REQUIRED.  String.  MUST be exactly
            "GovernedAction/v1".""")),
        ("schema_version", t("""REQUIRED.  Non-empty string.  Receipts
            conforming to this document carry "1.0".  This version's
            verifier checks only that the value is a non-empty string;
            the pair (receipt_type, schema_version) is the versioning
            hook for future revisions.""")),
        ("created_at", t("""REQUIRED.  String.  An ISO 8601 timestamp
            per Section 4.2.  This is a real wall-clock value: a receipt
            records that something happened at a moment in time, and the
            timestamp is data, not formatting.  It is asserted by the
            producer and is not witnessed; see Section 11.""")),
        ("actor", t("""REQUIRED.  Non-empty string.  The entity that
            performed the action.""")),
        ("action", t("""REQUIRED.  Non-empty string.  The operation
            performed.""")),
        ("policy", t("""REQUIRED.  Object.  MUST contain "id" (non-empty
            string), "version" (non-empty string), and "digest_sha256"
            (hex64; the SHA-256 of the policy document's bytes).  Policy
            identity is content-based: a policy that changes while
            keeping its name and version is detectably a different
            policy.  This version's verifier does not flag additional
            policy members, but producers SHOULD limit "policy" to these
            three members.""")),
        ("decision", t("""REQUIRED.  Object.  MUST contain "outcome"
            (string from the closed vocabulary of Section 9) and
            "rationale" (string; MAY be empty).""")),
        ("subjects", t("""REQUIRED.  Array, possibly empty.  Each element
            is an object with exactly the members "name" (non-empty
            string; a label) and "sha256" (hex64; the SHA-256 of the
            artifact's bytes).  Digests cover bytes, never path strings;
            see Section 11.""")),
        ("evidence", t("""REQUIRED.  Array, possibly empty.  Each element
            is an object with member "uri" (non-empty string) and
            OPTIONAL member "sha256" (hex64 when present), pinning the
            bytes behind the URI.""")),
    ]),
    ("p", t("""Bytes, not names: producers MUST compute subject digests
       over the artifact's bytes.  The reference implementation reads
       files in bounded 1 MiB chunks, so multi-gigabyte artifacts hash in
       constant memory; its in-memory digest helper accepts byte strings
       only, so passing a path string where bytes belong fails loudly
       instead of hashing the name.""")),
    ("h2", "Timestamp Grammar"),
    ("p", t("""The "created_at" member MUST match the following grammar
       (seconds and timezone designator mandatory, fractional seconds
       optional):""")),
    ("art", [
        r"YYYY-MM-DD \"T\" HH:MM:SS [.fff...] (\"Z\" | (+|-)hh:mm)",
        "",
        "Regular expression:",
        r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})\Z",
    ]),
    ("p", t("""and MUST denote a real calendar moment: the grammar alone
       accepts impossible values (a month of 13 matches it), so a verifier
       MUST additionally parse the value and reject impossible dates.  A
       timestamp without a timezone designator has no place in an audit
       log.  Producers MUST normalize timestamps to UTC and use the "Z"
       designator; verifiers MUST accept the offset forms as
       well.""")),
    ("h2", "Example Receipt"),
    ("p", t("""The following receipt records a governed build.  Every
       byte of it, and every digest quoted in this document, is produced
       by the reference implementation and is reproduced by the commands
       in Appendix B.  (In the plain-text rendering, figure lines longer
       than the column limit are folded per [RFC8792].)""")),
    ("art", RECEIPT_PRETTY.splitlines()),
    ("h2", "Canonical Form of the Example"),
    ("p", t(f"""The canonical form (Section 5) of the example receipt is
       the following {len(CANON)} bytes, shown folded; the canonical form
       itself contains no whitespace:""")),
    ("art", [CANON_TEXT]),
    ("p", t(f"""The SHA-256 of the canonical form above is
       {CANON_SHA}.  The canonical form of the body with "receipt_id"
       removed is {IDLESS_LEN} bytes, and its SHA-256 is
       {RECEIPT['receipt_id']} -- the receipt_id of the example, per the
       computation of Section 4.5.""")),
    ("h2", "Receipt Identity"),
    ("p", t("""The receipt_id of a receipt MUST be computed as
       follows:""")),
    ("art", [
        "receipt_id = SHA-256(JCS(body))",
        "",
        "where body is the receipt object with the \"receipt_id\" member",
        "removed.",
    ]),
    ("p", t("""Identity is a function of content, never a chosen string.
       Because canonicalization absorbs member ordering, producers with
       different serialization habits compute the same identity for the
       same content; that is the whole point.  Because the grammar is
       hex64 and the value is computed, a forged identifier of the form
       "important-receipt-final-v2" is structurally impossible: receipt
       identifiers are never human-chosen strings.""")),
    ("p", t("""A verifier MUST recompute the identity from the received
       object and MUST report a finding on any mismatch; a mismatch means
       the body was tampered with or was produced by a non-canonical
       builder.""")),
    ("h2", "Reference Implementation"),
    ("p", t("""The reference implementation is the Python package
       szl-receipts 14.0.0 [SZLR]: its build_receipt constructor and
       verify_receipt verifier implement exactly the rules of this
       section, and Appendix B reproduces the example above with it.  The
       verifier is deliberately non-throwing on bad data: every defect is
       returned as a finding string, and an empty findings list means the
       receipt is well-formed and its identity checks out.  Raising is
       reserved for programmer error (arguments of the wrong type), which
       is a bug in the caller, not in the receipt.  Section 10 specifies
       verifier behavior implementation-independently.""")),
])

S5 = ("canon", "5.", "Canonicalization", [
    ("p", t("""Every digest computation in this document -- receipt
       identity, chain entry digests, envelope payload digests -- is
       performed over the canonical form of the relevant JSON value.  The
       canonical form MUST be the JSON Canonicalization Scheme (JCS)
       defined by [RFC8785].  JSON itself offers no inter-serializer byte
       stability: member order, whitespace, number formatting, string
       escaping, and Unicode normalization are all serializer choices.
       JCS removes every degree of freedom so that equality becomes byte
       equality.  Input to canonicalization MUST conform to I-JSON
       [RFC7493].""")),
    ("p", t("""The points of [RFC8785] most consequential for
       implementers of this document:""")),
    ("ul", [
        t("""Object members are ordered by the UTF-16 code units of their
           names, not by Unicode code points.  The orders coincide in the
           Basic Multilingual Plane but differ for astral characters: an
           astral character encodes as a surrogate pair whose first code
           unit sorts below U+FFFF, so ordering by code point is
           observably wrong."""),
        t("""Numbers follow ECMAScript Number::toString: 1e20 serializes
           as 100000000000000000000 while 1e21 serializes as 1e+21;
           0.000001 stays in fixed notation while 0.0000001 becomes
           1e-7; exponents carry an explicit sign and no leading zeros;
           negative zero canonicalizes to 0."""),
        t("""Strings are escaped minimally (the two mandatory escapes, the
           seven single-character control escapes, and other C0 controls
           as \\u00xx with lowercase hex) and are never normalized:
           canonically equivalent but code-point-distinct strings
           canonicalize to different bytes, by design."""),
    ]),
    ("p", t("""A canonicalizer MUST reject values that are not
       interoperable across JSON implementations: NaN and infinities have
       no JSON representation, and any integer with magnitude greater
       than or equal to 2^53 MUST be rejected, because a parser may route
       such a value through an IEEE-754 double and silently lose
       precision; a canonicalizer must never emit bytes a reader cannot
       hold exactly.  (The reference implementation raises IJsonError in
       these cases.)  The numeric content defined by this document --
       chain sequence numbers -- stays far below that bound, but the
       bound MUST still be enforced: a digest is only meaningful when
       every implementation agrees on the bytes.""")),
    ("p", t("""Any [RFC8785]-conformant implementation produces identical
       bytes; the reference implementation's canonicalizer is
       standard-library-only Python [SZLR].  The worked example of
       Appendix B doubles as a conformance test: an implementation that
       cannot reproduce its receipt_id from the given inputs is not a GAR
       implementation.""")),
])

S6 = ("signing", "6.", "Signing and Envelopes", [
    ("p", t("""A receipt's identity proves its own integrity, but
       integrity is not authenticity: anyone can construct a well-formed
       receipt.  Authenticity is provided by carrying the canonical form
       of the receipt as the payload of a DSSE envelope [DSSE] signed
       with Ed25519 [RFC8032]; the honest alternative is to publish the
       receipt unsigned under the naming convention of Section 8.  A
       receipt MUST NOT be presented in any state in between: either at
       least one signature is present, or the artifact is named
       unsigned.""")),
    ("h2", "Envelope"),
    ("p", t("""The signed artifact is a DSSE envelope [DSSE]: a JSON
       object with members "payload" (base64 of the payload bytes),
       "payloadType" (non-empty string), and "signatures" (array of
       objects with members "keyid" (string) and "sig" (base64 of the
       signature bytes)).  Base64 uses the standard alphabet and strict
       decoding: a verifier MUST reject non-canonical base64 at the
       structural stage, before any cryptography is attempted.  The
       payload is embedded verbatim, so the envelope is self-contained:
       anyone can verify authenticity and read the content from one
       file.""")),
    ("p", t("""The payload of a GAR envelope MUST be the canonical form
       (Section 5) of the complete receipt, including receipt_id.
       Signing the canonical form, rather than whatever bytes a producer
       happened to serialize, means the signature verifies even if the
       envelope travels through JSON tooling that reserializes whitespace
       or reorders members: the bytes under the signature are semantic,
       not incidental.""")),
    ("p", t("""The payloadType of a GAR envelope SHOULD be
       "application/gar+json" (Section 12).  The reference
       implementation's command-line signer defaults to "application/json"
       and accepts an explicit payload-type override [SZLR].  Whatever
       value is used, a producer MUST NOT reuse one payloadType for two
       different signed meanings, so that the domain separation of
       Section 6.2 is preserved.""")),
    ("h2", "Pre-Authentication Encoding"),
    ("p", t("""The bytes being signed must carry their own type, so that
       a signature over "a receipt" can never be replayed as a signature
       over "an authorization" that happens to share bytes -- the classic
       type-confusion, or chosen-protocol, attack.  DSSE prevents it with
       the Pre-Authentication Encoding (PAE) [DSSE].  Signatures MUST be
       computed over:""")),
    ("art", [
        'PAE = b"DSSEv1" SP len(payloadType) SP payloadType SP',
        "      len(payload) SP payload",
        "",
        "where SP is a single space (0x20) and the lengths are decimal",
        "ASCII byte counts.",
    ]),
    ("p", t(f"""Every field is length-prefixed before concatenation, so no
       pair (payloadType, payload) can encode to the same bytes as a
       different pair: the separator positions are fixed by the lengths,
       and an attacker cannot smear bytes across the boundary.  Minimal
       example: PAE("a", "bc") is the byte string "{PAE_DEMO}".  For the
       example receipt of Section 4.3, the encoding begins
       "{PAE_PREFIX}" and runs to {PAE_TOTAL} bytes in total.  Verifiers
       MUST recompute the PAE from the envelope's embedded (payloadType,
       payload) pair after decoding, never from values supplied
       alongside the envelope.  The reference implementation's test suite
       exercises a prefix-collision (type-confusion) attack against this
       construction directly [SZLR].""")),
    ("h2", "Signature Algorithm and Keys"),
    ("p", t("""The signature algorithm for this version is Ed25519
       [RFC8032], chosen for its small fixed-size keys and signatures (a
       signature is 64 bytes, 88 characters base64), deterministic
       signing (no per-signature nonce to leak), and constant-time
       verification in common backends.  An envelope MAY carry multiple
       signatures; verification is boolean, "authentic under this key or
       not", and succeeds if at least one entry verifies (Section
       10).""")),
    ("p", t("""The keyid of a signature SHOULD default to the SHA-256,
       rendered as hex64, of the raw 32-byte public key: keys are
       identified by content, not by filename, because filenames move and
       bytes do not.  Signers MAY override keyid to match an external key
       registry.  Key distribution and trust-root selection are out of
       scope; Section 7.3 notes where witnessed key material can be
       anchored, and Section 11 discusses custody.""")),
    ("h2", "in-toto Statements"),
    ("p", t("""Deployments that already produce in-toto attestations
       [INTOTO] MAY carry a receipt inside an in-toto Statement v1, whose
       "_type" member is the constant
       "https://in-toto.io/Statement/v1".  In this mapping the
       Statement's "subject" list holds objects of the form {"name":
       label, "digest": {"sha256": hex64}} pinning each subject to the
       digest of its bytes, and the receipt appears as the Statement's
       "predicate" under a deployment-chosen "predicateType".  The
       Statement is then signed as the payload of a DSSE envelope exactly
       as in Section 6.1.  The mapping is optional; a bare GAR envelope
       carries no less integrity than a Statement-wrapped one.""")),
    ("h2", "Example Envelope"),
    ("p", t(f"""The canonical bytes of Section 4.4, signed under the
       example key of Appendix B (a public, non-secret test vector),
       yield the following envelope, shown with its payload line folded
       per [RFC8792].  Its signature entry has keyid {KEYID}.  The
       envelope verifies under the example public key printed in
       Appendix B.1 and is reproducible byte-for-byte.""")),
    ("art", ENVELOPE_PRETTY.splitlines()),
])

S7 = ("chains", "7.", "Hash-Chained Logs and External Anchors", [
    ("p", t("""Receipts gain operational value when they are ordered.  A
       chain binds each receipt to a sequence number and to its
       predecessor, producing an append-only log in which each entry
       authenticates the entire history before it.""")),
    ("h2", "Chain Entry Format"),
    ("p", t("""A chain entry is a JSON object with exactly the members
       "seq" (integer; 1 for the genesis entry, thereafter strictly
       increasing by 1), "receipt" (a receipt object per Section 4),
       "prev" (the entry_digest of the preceding entry, or null for the
       genesis entry), and "entry_digest" (hex64).  The binding digest
       is:""")),
    ("art", [
        'entry_digest = SHA-256(JCS({"seq": n,',
        '                           "receipt": receipt,',
        '                           "prev": prev}))',
        "",
        "computed over the canonical form of exactly the three members",
        "that define the entry's identity.",
    ]),
    ("p", t("""Because the embedded receipt is itself content-addressed
       by receipt_id, one digest recomputation authenticates the receipt,
       its position, and its linkage; the chain is only as mutable as
       SHA-256's collision resistance.  An appender MUST validate the
       receipt per Section 10 before it touches the chain: a chain
       containing an invalid receipt is a chain that lies with
       confidence.  The chain structure is storage-agnostic -- one JSON
       file per entry, a JSONL stream, or database rows; persistence is
       the deployment's choice.""")),
    ("p", t(f"""The genesis entry of the example chain of Appendix B is
       shown below (digest lines folded).  Its entry_digest is
       {ENTRY1['entry_digest']}.""")),
    ("art", ENTRY1_PRETTY.splitlines()),
    ("p", t(f"""The example's second entry has seq 2, prev equal to the
       genesis digest above, and entry_digest {ENTRY2['entry_digest']};
       the full two-entry chain appears in Appendix B.3.""")),
    ("h2", "What the Chain Detects"),
    ("p", t("""A chain verifier checks a complete chain from genesis:
       re-deriving every entry_digest and cross-checking every linkage.
       The following attack classes are detectable from the chain alone,
       and each MUST be reported as a distinct finding (the reference
       implementation assigns the stable codes shown, so tooling can
       match attack classes without parsing prose):""")),
    ("dl", [
        ("malformed-entry", t("""an entry is not an object with the four
            members, has a bad seq or non-string entry_digest, or cannot
            be canonicalized.""")),
        ("digest-mismatch", t("""entry content does not hash to its
            declared entry_digest (field-level tamper inside an
            entry).""")),
        ("reorder", "seq numbers are not strictly increasing along the log."),
        ("gap", t("""seq jumps forward: entries are missing from the
            middle.""")),
        ("replay", "the same seq reappears with an identical digest."),
        ("fork", "the same seq reappears with two different digests."),
        ("broken-prev-link", t("""an entry's prev is not the digest of the
            preceding entry (or the predecessor is malformed, leaving the
            link unverifiable).""")),
        ("genesis-prev-not-null", t("""the first entry does not anchor at
            null.""")),
    ]),
    ("p", t("""The verification report is a boolean ok (true exactly when
       the findings list is empty), the chain length, and the head (the
       final entry's entry_digest).  The reference implementation's test
       suite builds a five-entry chain and detects truncation, reorder,
       replay, fork, and broken-prev-link attacks as separate cases
       [SZLR].""")),
    ("h2", "External Anchors and the Truncation Limitation"),
    ("p", t("""This section states the honest limit of any self-verifying
       log, because a specification that omits it would oversell the
       mechanism.""")),
    ("p", t("""A hash chain verified without external information proves
       the integrity of the presented history from genesis to the
       presented head.  It cannot prove completeness: an operator who
       silently drops the newest entries yields a shorter chain that is
       perfectly valid, and no finding fires.  Tail truncation is
       undetectable from the chain alone.  No hashing scheme removes this
       limitation; it is a property of self-authenticating logs, not of
       this design.""")),
    ("p", t("""The mitigation is an external anchor: information about
       the chain obtained from outside the chain, which a deployment MUST
       treat as trusted-anchor / untrusted-chain.  This document defines
       two anchor inputs to the verifier:""")),
    ("dl", [
        ("expected_entries", t("""an integer; the verifier reports
            "truncated" when the chain holds fewer entries than the
            anchor.  (A chain longer than the anchor is not, by itself, a
            finding: the anchor pins a minimum length.)""")),
        ("expected_head", t("""hex64; the verifier reports "head-mismatch"
            when the digest of the final entry differs from the
            anchor.""")),
    ]),
    ("p", t("""Anchors can be published out of band (a head digest in a
       release announcement, an entry count in a change ticket) or
       witnessed by a transparency service.  GAR composes with the SCITT
       architecture [SCITT]: a signed GAR envelope is a signed statement
       in SCITT terms, and a transparency service can issue an inclusion
       receipt for a chain head, converting it into a witnessed anchor.
       Sigstore's public transparency log [SIGSTORE] (Rekor) provides the
       same function for envelopes.  Anchoring converts self-consistency
       into completeness; deployments that cannot anchor MUST state in
       their own audit narrative that tail truncation is outside the
       verified envelope.""")),
])

S8 = ("naming", "8.", "Honest Unsigned Naming", [
    ("p", t("""A file's name MUST tell the truth about its signature
       state.  The convention:""")),
    ("ul", [
        t("""an envelope carrying one or more signatures is written as
           <base>.json (a signed artifact), for example
           build/report.json;"""),
        t("""an envelope carrying zero signatures is written as
           <base>.unsigned.json (an unsigned artifact), for example
           build/report.unsigned.json."""),
    ]),
    ("p", t("""An empty signatures array is not a signature.  The rule
       exists because consumers pattern-match on extensions: an envelope
       with "signatures": [] written to report.json presents as a
       signed-looking artifact that anyone could have produced.  Honest
       naming makes the trust state legible from the directory listing
       alone.""")),
    ("p", t("""Verification is bidirectional and MUST fail in both
       directions: a *.unsigned.json file that contains one or more
       signatures is a tampered rename, and any other .json artifact
       whose signatures array is empty is a tampered rename.  Both MUST
       be reported as verification failures.  (The reference
       implementation raises NamingError; its command-line verifier exits
       with status 2 [SZLR].)  Renaming a file MUST NOT change what the
       world believes about it.""")),
    ("p", t("""A missing "signatures" member is not an unsigned artifact;
       it is a malformed envelope, and MUST be reported as such.  Absent
       is different from empty, and conflating them is how quiet
       forgeries pass review.""")),
    ("p", t("""The naming check is orthogonal to the cryptographic checks
       of Section 6 and is always applied first (Section 10).  Note that
       the on-disk serialization of an envelope (member order,
       indentation) is for human review; the bytes that are hashed and
       signed are always the canonical form (Section 5).""")),
])

S9 = ("outcomes", "9.", "Outcome Vocabulary", [
    ("p", t("""The decision.outcome member MUST take exactly one of the
       following five values.  The vocabulary is closed deliberately: a
       free-text status field drifts ("ok", "green", "mostly fine")
       until nothing can be gated on it.  Values serialize as their plain
       text, so receipts stay plain JSON.""")),
    ("dl", [
        ("PASS", t("""the governed action completed and met policy.  This
            is the only passing outcome.""")),
        ("WARN", t("""the action completed with a recorded concern.  A
            recorded concern is not a pass.""")),
        ("FAIL", "the governed action failed."),
        ("BLOCKED", t("""the action was prevented from running by policy
            or by the environment.""")),
        ("UNKNOWN", t("""no verdict was recorded; the absence of a
            verdict is itself the record.""")),
    ]),
    ("p", t("""Normative rules:""")),
    ("ul", [
        t("""A producer MUST reject an outcome outside this vocabulary at
           build time rather than emit an un-gateable receipt; a verifier
           MUST report an out-of-vocabulary decision.outcome as a
           finding."""),
        t("""The predicate is_passing(outcome) is true if and only if
           outcome is PASS."""),
        t("""A promotion gate MUST admit PASS and MUST refuse FAIL,
           BLOCKED, and UNKNOWN unconditionally.  It MAY admit WARN only
           under an explicit, recorded override (in the reference
           implementation, promotion_gate(outcome, allow_warn=True); the
           override is itself an auditable decision)."""),
        t("""UNKNOWN MUST NOT be promoted to PASS, and MUST NOT be
           treated as passing by any gate, report, or dashboard.
           Absence of a verdict is not a verdict: "we don't know" is
           informationally worse than "it failed", because failure at
           least tells you where to look."""),
    ]),
])

S10 = ("verifier", "10.", "Verifier Behavior", [
    ("p", t("""This section collects the normative verification
       procedure.  The design principle: a malformed or tampered receipt
       is an everyday operational event, not an exception.  A verifier
       MUST NOT crash on bad data; it reports findings, and an empty
       findings list is the only success signal.  A verifier SHOULD
       report every defect it can determine; it MAY stop early only when
       required members are absent, because type-checking absent members
       is meaningless.""")),
    ("p", t("""Receipt verification, given a parsed JSON value:""")),
    ("ol", [
        t("""Parse: callers parse untrusted text as JSON [RFC8259]
           themselves; verification operates on the parsed value, and a
           wrong argument type is programmer error, not a finding."""),
        t("""Shape: the value MUST be an object containing exactly the
           ten members of Section 4.1; report each missing and each
           unexpected member."""),
        t("""receipt_type MUST equal "GovernedAction/v1"; schema_version
           MUST be a non-empty string."""),
        t("""created_at MUST match the grammar of Section 4.2 and MUST
           denote a real calendar moment."""),
        t("""actor and action MUST be non-empty strings."""),
        t("""policy MUST be an object; id and version MUST be non-empty
           strings; digest_sha256 MUST be hex64."""),
        t("""decision MUST be an object; outcome MUST be inside the
           vocabulary of Section 9; rationale MUST be a string."""),
        t("""subjects MUST be an array; each element MUST be an object
           with a non-empty name and a hex64 sha256 and no other
           members."""),
        t("""evidence MUST be an array; each element MUST be an object
           with a non-empty uri; a sha256 member, when present, MUST be
           hex64."""),
        t("""Identity: the declared receipt_id MUST be hex64 and MUST
           equal the identity recomputed per Section 4.5; any mismatch
           MUST be reported -- the body was tampered with or produced by
           a non-canonical builder."""),
    ]),
    ("p", t("""Envelope verification, given a parsed JSON value and
       optionally a trusted public key, proceeds in stages:""")),
    ("ol", [
        t("""Naming: the artifact's filename MUST satisfy Section 8 for
           the envelope's actual signature state.  Failure here is a
           verification failure, not a warning."""),
        t("""Structure: payloadType MUST be a non-empty string; payload
           MUST decode under strict base64; signatures MUST be an array.
           An empty array passes this stage; honesty about it is enforced
           by the naming stage, and authenticity fails closed at the next
           stage."""),
        t("""Signature: when a public key is supplied, the verifier
           recomputes the PAE (Section 6.2) from the embedded
           (payloadType, payload) pair and returns authentic if and only
           if at least one signature entry verifies under that key.
           Malformed entries, wrong keys, and cryptographic failures MUST
           fail closed: they are skipped, never treated as errors that
           abort the scan, and never as successes.  When no key is
           supplied, the signature stage is skipped and MUST be reported
           as not checked, never as passed."""),
        t("""Payload: when the payloadType indicates a GAR receipt, the
           decoded payload SHOULD additionally be verified as a receipt
           per the procedure above."""),
    ]),
    ("p", t("""Chain verification consumes a complete chain from genesis,
       reports each defect of Section 7.2 as a distinct, codeable
       finding, and then applies the external anchors of Section 7.3 when
       supplied.  A chain verifier MUST accept expected_entries and
       expected_head inputs; a chain verified without anchors MUST be
       reported with the truncation caveat stated.  Promotion gates MUST
       consume decision.outcome per Section 9.""")),
    ("p", t("""The reference implementation's command-line verifier maps
       these outcomes onto exit codes: 0 for success, 2 for verification
       failure (the artifact is reachable but untrustworthy: tamper,
       dishonest naming, chain break), and 3 for usage or I/O error.  The
       distinction between 2 and 3 is the difference between an incident
       and a retry; integrations SHOULD preserve it.""")),
])

S11 = ("security", "11.", "Security Considerations", [
    ("p", t("""Field-level integrity.  Any modification of any receipt
       member changes the canonical bytes and therefore the recomputed
       receipt_id; detection requires no trusted registry.  The closed
       member set means an attacker cannot hide semantics in extension
       members that a verifier would skip.""")),
    ("p", t("""Type confusion.  Signatures cover PAE(payloadType,
       payload), so a signature over a receipt cannot be replayed as a
       signature over a different type that happens to share bytes; the
       length-prefixing of Section 6.2 fixes the separator positions.
       Producers MUST NOT reuse one payloadType for two signed
       meanings.""")),
    ("p", t("""Renaming forgery.  Honest naming (Section 8) makes an
       artifact's signature state legible from its filename and is
       enforced on the verify side in both directions; consumers MUST NOT
       treat a *.unsigned.json artifact as authenticated.""")),
    ("p", t("""Log attacks.  Reorder, gap, replay, fork, broken-prev-link,
       and genesis-anchor violations are detectable from the chain alone
       (Section 7.2).  Tail truncation is not: as Section 7.3 states,
       without an external anchor a shortened chain is perfectly valid.
       Any security claim of completeness therefore requires the anchors
       of Section 7.3; self-consistency is not completeness.  Forks (two
       valid chains with a common prefix) are detectable only by
       comparing heads or by a witness that refuses double-booking; the
       format makes such comparison cheap, it does not perform it.""")),
    ("p", t("""Time.  created_at is asserted by the producer's clock and
       is not witnessed; a signer can backdate a receipt.  A receipt
       authenticates that the signer asserted a time, not that the
       assertion was true.  Deployments requiring trustworthy time SHOULD
       anchor chain heads with a timestamping or transparency service, as
       Section 7.3 describes.""")),
    ("p", t("""Key custody.  Ed25519 private keys are offline,
       operator-held artifacts.  The reference implementation writes
       private keys unencrypted with file mode 0600 and refuses to
       overwrite an existing private key, because accidental key rotation
       is a silent audit gap; deliberate rotation is an operator
       decision.  This version defines no revocation mechanism: verifiers
       pin keys directly, and receipts made under a compromised key
       remain verifiable forgeries until the verifier's key set is
       updated.  Rotation and revocation are deployment matters, out of
       scope here.""")),
    ("p", t("""Evidence custody.  An evidence uri is a reference, not
       custody.  When sha256 is present the referenced bytes are pinned;
       when absent, the integrity and availability of the evidence are
       the deployment's concern.""")),
    ("p", t("""Digest algorithm.  SHA-256 [FIPS180-4] is the load-bearing
       assumption everywhere: receipt_id, subject digests, policy
       digests, entry digests, and keyids.  This version deliberately
       fixes one algorithm; there is no negotiation to downgrade, and
       mixing digest algorithms within this version MUST NOT be done
       (every hex64 position in this document is assigned to SHA-256).
       If SHA-256 is ever weakened, the SHA-3 family [FIPS202] is the
       designated agility path, and a future revision MUST introduce it
       by changing the (receipt_type, schema_version) versioning hook
       rather than by overloading member contents: an algorithm change
       produces a different format and should be named like one.""")),
    ("p", t("""Canonicalization correctness is security-critical.  A
       verifier that canonicalizes differently from the producer will
       reject valid receipts (an availability failure) or, worse, accept
       a receipt under an identity the producer never computed.  The
       UTF-16 member ordering and the ECMAScript number formatting of
       Section 5 are where independent implementations diverge, and the
       I-JSON exactness bound keeps digests meaningful across
       implementations.""")),
    ("p", t("""Denial of service.  Receipts are small by construction.
       Verifiers SHOULD bound the size of accepted chain inputs, and
       artifact hashing MUST be streamed in bounded chunks (the reference
       implementation reads 1 MiB per read) so that multi-gigabyte
       subjects verify in constant memory.""")),
])

S12 = ("iana", "12.", "IANA Considerations", [
    ("p", t("""This document requests registration of the following media
       type in the "Media Types" registry
       (https://www.iana.org/assignments/media-types/), following the
       procedures of [RFC6838]:""")),
    ("art", [
        "Type name: application",
        "Subtype name: gar+json",
        "Required parameters: none",
        "Optional parameters: none",
        "Encoding considerations: binary",
        "   (UTF-8 JSON text [RFC8259]; the canonical form used for",
        "   digests and signatures is defined by [RFC8785])",
        "Security considerations: see Section 11 of this document.",
        "   Content may be signed per Section 6; unsigned content",
        "   follows the naming convention of Section 8.  Receivers MUST",
        "   verify per Section 10 before trusting content.",
        "Interoperability considerations: all digest-bearing members",
        "   depend on [RFC8785] canonicalization; member order and",
        "   whitespace are insignificant (see Section 5 of this",
        "   document).",
        "Published specification: this document.",
        "Applications that use this media type: governance, build,",
        "   deployment, and audit tooling producing or consuming",
        "   Governed Action Receipts; transparency logs anchoring",
        "   receipt chains.",
        "Fragment identifier considerations: none; JSON documents do",
        "   not define fragment identifiers.",
        "Additional information: none.",
        "Person & email address to contact for further information:",
        f"   {AUTHOR_FULL} <{EMAIL}>",
        "Intended usage: COMMON",
        "Restrictions on usage: none.",
        f"Author: {AUTHOR_FULL}, {ORG}",
        f"Change controller: {AUTHOR_FULL}, {ORG} <{EMAIL}>",
        "Provisional registration? (standards tree only): yes",
    ]),
    ("p", t("""As of this writing, the registration has NOT been made:
       "application/gar+json" is provisional and unregistered.  Until the
       type appears in the IANA registry, implementations MUST treat it
       as unregistered and MUST be prepared for the registered
       definition to evolve.  The DSSE payloadType value
       "application/gar+json" (Section 6.1) is usable immediately:
       payloadType is an envelope-scoped type hint whose utility does
       not depend on registry completion.""")),
    ("p", t("""No registry is requested for outcome values: the
       vocabulary of Section 9 is closed by design and can be extended
       only by a revision of this document, so that no deployment can
       unilaterally add an outcome its gates cannot interpret.""")),
])

ACK = [
    t("""The format specified here is implemented and exercised daily by
       the szl-receipts package within the SZL Holdings estate; its test
       suite, which drives truncation, reorder, replay, fork, and
       broken-link attacks against chains, payload bit-flip, wrong-key,
       and PAE prefix-collision attacks against envelopes, and dishonest
       renames against the naming convention, served as the executable
       adversarial review for this document.  The Secure Systems Lab's
       DSSE specification and in-toto framework, the IETF SCITT working
       group's architecture draft, and the Sigstore project provided the
       substrate this format composes with.  Raza Sharif's individual
       Internet-Draft [AAT] showed that this problem space is under
       active exploration at the IETF and that individual submission is
       the correct first step."""),
]

APPENDIX_A = ("appa", None, "Appendix A.", [
    ("h2a", "Reference Implementation Map"),
    ("p", t("""For reviewers cross-checking this document against code:
       the reference implementation is szl-receipts 14.0.0 [SZLR],
       importable as the Python package szl_receipts.""")),
    ("dl", [
        ("Section 4", "receipt.py: build_receipt, verify_receipt, compute_receipt_id"),
        ("Section 5", "jcs.py: jcs_canon_bytes, serialize, number_to_js_str"),
        ("Section 6", "dsse.py: pae, sign_bytes, verify_envelope, keygen, statement"),
        ("Section 7", "chain.py: append, entry_digest_for, verify_chain"),
        ("Section 8", "naming.py: write_envelope, verify_honest_naming, NamingError"),
        ("Section 9", "outcome.py: Outcome, is_passing, promotion_gate"),
        ("Section 10", "the verifiers above; cli.py: canon, keygen, sign, verify, chain-verify and the exit-code contract"),
        ("byte digests", "digests.py: sha256_file (1 MiB chunks), sha256_bytes, sha256_hex"),
    ]),
])

APPENDIX_B = ("appb", None, "Appendix B.", [
    ("h2a", "Worked Example and Reproduction: Inputs"),
    ("p", t("""Reproduction requires Python 3.11 or newer, the
       szl-receipts package at version 14.0.0, and the "cryptography"
       package (version 42 or newer).  The following commands create the
       two input files; the digests quoted throughout this document are
       the SHA-256 of their bytes:""")),
    ("art", [
        "pip install -e ./szl-receipts        # szl-receipts 14.0.0",
        "mkdir -p policies dist",
        "printf 'SZL Build Policy v14\\nAll governed builds must be reproducible and receipted.\\n' > policies/szl.build.v14.md",
        "printf 'SZL MASTER PAYLOAD V14\\n' > dist/SZL_MASTER_PAYLOAD_V14.md",
    ]),
    ("p", t(f"""The digests are {POLICY_DIGEST} (policy document) and
       {SUBJECT_DIGEST} (payload artifact).  The example Ed25519 key is
       derived from the fixed seed SHA-256("draft-lutar-governed-action-
       receipt example key") via Ed25519PrivateKey.from_private_bytes; it
       is a public, non-secret test vector and MUST NOT be used
       operationally.  The example public key is:""")),
    ("art", EXAMPLE_PUB_PEM.splitlines()),
    ("h2a", "Reproduction Script"),
    ("p", t("""The following script (also distributed alongside this
       document as reproduce-appendix-b.py) regenerates every value in
       Sections 4.3, 4.4, 6.5, and 7.1.  Output is deterministic:
       created_at is fixed and the key is fixed.  (Long lines are folded
       per [RFC8792] in the plain-text rendering; the distributed script
       file is authoritative.)""")),
    ("art", REPRO_SCRIPT.splitlines()),
    ("h2a", "Expected Results"),
    ("art", [
        f"receipt_id:            {RECEIPT['receipt_id']}",
        f"canonical length:      {len(CANON)} bytes",
        f"sha256(canonical):     {CANON_SHA}",
        f"keyid:                 {KEYID}",
        f"signature (base64):    {SIG_B64}",
        f"genesis entry_digest:  {ENTRY1['entry_digest']}",
        f"entry 2 entry_digest:  {ENTRY2['entry_digest']}",
        f"chain head:            {REPORT.head}",
    ]),
    ("p", t("""An implementation that reproduces these digests from these
       inputs implements Sections 4, 5, 6, and 7 correctly.  The
       verification chain also holds: verify_envelope applied to the
       envelope of Section 6.5 under the public key of B.1 returns true,
       and verify_chain applied to the two-entry chain with
       expected_entries 2 and expected_head equal to the chain head above
       reports ok with zero findings.  The complete two-entry chain as
       produced by the script is:""")),
    ("art", CHAIN_PRETTY.splitlines()),
])

SECTIONS = [S1, S2, S3, S4, S5, S6, S7, S8, S9, S10, S11, S12]
BACK = [APPENDIX_A, APPENDIX_B]

REFS_NORM = [
    ("DSSE", "Secure Systems Lab, \"Dead Simple Signing Envelope (DSSE)\", "
     "A specification for signing methods and formats used by Secure "
     "Systems Lab projects, <https://github.com/secure-systems-lab/dsse>."),
    ("FIPS180-4", "National Institute of Standards and Technology, "
     "\"Secure Hash Standard (SHS)\", FIPS PUB 180-4, "
     "DOI 10.6028/NIST.FIPS.180-4, August 2015, "
     "<https://doi.org/10.6028/NIST.FIPS.180-4>."),
    ("FIPS202", "National Institute of Standards and Technology, \"SHA-3 "
     "Standard: Permutation-Based Hash and Extendable-Output Functions\", "
     "FIPS PUB 202, DOI 10.6028/NIST.FIPS.202, August 2015, "
     "<https://doi.org/10.6028/NIST.FIPS.202>."),
    ("RFC2119", "Bradner, S., \"Key words for use in RFCs to Indicate "
     "Requirement Levels\", BCP 14, RFC 2119, DOI 10.17487/RFC2119, March "
     "1997, <https://www.rfc-editor.org/info/rfc2119>."),
    ("RFC7493", "Bray, T., Ed., \"The I-JSON Message Format\", RFC 7493, "
     "DOI 10.17487/RFC7493, March 2015, "
     "<https://www.rfc-editor.org/info/rfc7493>."),
    ("RFC8032", "Josefsson, S. and I. Liusvaara, \"Edwards-Curve Digital "
     "Signature Algorithm (EdDSA)\", RFC 8032, DOI 10.17487/RFC8032, "
     "January 2017, <https://www.rfc-editor.org/info/rfc8032>."),
    ("RFC8174", "Leiba, B., \"Ambiguity of Uppercase vs Lowercase in RFC "
     "2119 Key Words\", BCP 14, RFC 8174, DOI 10.17487/RFC8174, May 2017, "
     "<https://www.rfc-editor.org/info/rfc8174>."),
    ("RFC8259", "Bray, T., Ed., \"The JavaScript Object Notation (JSON) "
     "Data Interchange Format\", STD 90, RFC 8259, DOI 10.17487/RFC8259, "
     "December 2017, <https://www.rfc-editor.org/info/rfc8259>."),
    ("RFC8785", "Rundgren, A., Jordan, B., and S. Erdtman, \"JSON "
     "Canonicalization Scheme (JCS)\", RFC 8785, DOI 10.17487/RFC8785, "
     "June 2020, <https://www.rfc-editor.org/info/rfc8785>."),
]

REFS_INFO = [
    ("AAT", "Sharif, R., \"Agent Audit Trail: A Standard Logging Format "
     "for Autonomous AI Systems\", Work in Progress, Internet-Draft, "
     "draft-sharif-agent-audit-trail-01, 19 August 2026, "
     "<https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/>.  "
     "Individual submission; not adopted by any IETF working group; no "
     "formal standing in the IETF standards process."),
    ("INTOTO", "Torres-Arias, S., Ammon, W., Kuppusamy, T.K., "
     "Cappos, J., et al., \"in-toto: Providing farm-to-table guarantees "
     "for bits and bytes\", USENIX Security Symposium, August 2019, "
     "<https://in-toto.io/>."),
    ("RFC6838", "Freed, N., Klensin, J., and T. Hansen, \"Media Type "
     "Specifications and Registration Procedures\", BCP 13, RFC 6838, "
     "DOI 10.17487/RFC6838, January 2013, "
     "<https://www.rfc-editor.org/info/rfc6838>."),
    ("RFC8792", "Watsen, K., Auerswald, E., Farrel, A., and Q. Wu, "
     "\"Handling Long Lines in Content of Internet-Drafts and RFCs\", "
     "RFC 8792, DOI 10.17487/RFC8792, June 2020, "
     "<https://www.rfc-editor.org/info/rfc8792>."),
    ("SCITT", "Birkholz, H., Delignat-Lavaud, A., Fournet, C., "
     "Deshpande, Y., and S. Lasker, \"An Architecture for Trustworthy and "
     "Transparent Digital Supply Chains\", Work in Progress, "
     "Internet-Draft, draft-ietf-scitt-architecture, "
     "<https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/>."),
    ("SIGSTORE", "The Sigstore Project, \"Sigstore: software signing and "
     "transparency infrastructure\", <https://www.sigstore.dev/>."),
    ("SZLR", "SZL Holdings, \"szl-receipts: cryptographic receipt core "
     "for the SZL Holdings estate\", Version 14.0.0 (reference "
     "implementation of this document), August 2026.  Available from the "
     "author."),
]

AUTHOR_ADDR = [f"{AUTHOR_FULL}", f"{ORG}", "", f"Email: {EMAIL}"]

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SUB_COUNT = {}  # heading numbering state, set during emit

CITE_TAGS = {tag for tag, _ in REFS_NORM} | {tag for tag, _ in REFS_INFO}


def md_cite(text):
    """[TAG] -> {{TAG}} for kramdown citation syntax."""
    def repl(m):
        tag = m.group(1)
        if tag in CITE_TAGS:
            return "{{" + tag + "}}"
        return m.group(0)
    return re.sub(r"\[([A-Z][A-Za-z0-9.-]*)\]", repl, text)


# ---------------------------------------------------------------------------
# Plain-text (RFC style) rendering
# ---------------------------------------------------------------------------

LW = 72          # column limit
PAGE_H = 58      # total lines per page, including header zone and footer
FIG_INDENT = 3
FOLD_W = 66      # max figure content columns after indentation

HEADINGS_TXT = []  # filled during flow construction: list of heading labels


def wrap(text, indent=3):
    return textwrap.wrap(text, width=LW - indent,
                         initial_indent=" " * indent,
                         subsequent_indent=" " * indent,
                         break_long_words=False,
                         break_on_hyphens=False)


def wrap2(text, first_indent, cont_indent):
    return textwrap.wrap(text, width=LW - first_indent,
                         initial_indent=" " * first_indent,
                         subsequent_indent=" " * cont_indent,
                         break_long_words=False,
                         break_on_hyphens=False)


def fold_figure(lines):
    """Indent artwork by FIG_INDENT and fold content beyond FOLD_W with a
    trailing backslash (RFC 8792 single-backslash strategy).  Returns
    figure lines; if any folding happened, a NOTE line is prepended."""
    out = []
    folded = False
    for raw in lines:
        if raw == "":
            out.append("")
            continue
        line = raw
        while len(line) > FOLD_W:
            out.append(" " * FIG_INDENT + line[:FOLD_W] + "\\")
            line = line[FOLD_W:]
            folded = True
        out.append(" " * FIG_INDENT + line)
    if folded:
        out = [" " * FIG_INDENT + "NOTE: '\\' line wrapping per RFC 8792",
               ""] + out
    return out


def txt_blocks(blocks, flow, keep):
    """Append rendered blocks to (flow, keep) parallel lists."""
    for bi, (kind, payload) in enumerate(blocks):
        if kind in ("h2", "h2a"):
            if kind == "h2":
                num = SUB_COUNT["n"]
                SUB_COUNT["n"] += 1
                label = f"{SUB_COUNT['sec']}.{num}.  {payload}"
            else:
                label = payload  # appendix subheadings: plain text
            # if the next block is a page-fitting figure, reserve room
            # for the whole figure so the heading cannot be orphaned
            keep_n = 3
            if bi + 1 < len(blocks) and blocks[bi + 1][0] == "art":
                figlen = len(fold_figure(blocks[bi + 1][1]))
                if figlen <= PAGE_H - 4:
                    keep_n = figlen + 2
            _emit_heading(flow, keep, label, keep_n=keep_n)
            continue
        if flow:
            flow.append("")
            keep.append(0)
        if kind == "p":
            for line in wrap(payload):
                flow.append(line)
                keep.append(0)
        elif kind == "art":
            flow.append("")
            keep.append(0)
            fig = fold_figure(payload)
            # keep a figure on one page when it fits (body capacity on
            # pages >= 2 is PAGE_H - 4 lines)
            group = len(fig) - 1 if len(fig) <= PAGE_H - 4 else 0
            for k, line in enumerate(fig):
                flow.append(line)
                keep.append(group if k == 0 else 0)
            flow.append("")
            keep.append(0)
        elif kind == "ul":
            for i, item in enumerate(payload):
                seg = wrap2(item, 6, 6)
                seg[0] = "   o  " + seg[0][6:]
                flow.extend(seg)
                keep.extend([0] * len(seg))
                if i < len(payload) - 1:
                    flow.append("")
                    keep.append(0)
        elif kind == "ol":
            for i, item in enumerate(payload):
                marker = f"{i + 1}. "
                seg = wrap2(item, 6, 6)
                seg[0] = "   " + marker + seg[0][6:]
                flow.extend(seg)
                keep.extend([0] * len(seg))
                if i < len(payload) - 1:
                    flow.append("")
                    keep.append(0)
        elif kind == "dl":
            for i, (term, text) in enumerate(payload):
                flow.append("   " + term)
                keep.append(2)
                seg = wrap(text, 6)
                flow.extend(seg)
                keep.extend([0] * len(seg))
                if i < len(payload) - 1:
                    flow.append("")
                    keep.append(0)


def _emit_heading(flow, keep, label, keep_n=3):
    if flow:
        flow.append("")
        keep.append(0)
        flow.append("")
        keep.append(0)
    flow.append(label)
    keep.append(keep_n)  # heading + following lines kept on one page
    flow.append("")
    keep.append(0)  # the heading's keep already reserved this line's room
    HEADINGS_TXT.append(label)


def build_flow(toc_lines):
    """The full body flow: front matter sections, ToC, sections, back
    matter, references, author address.  Returns (flow, keep, headings)."""
    del HEADINGS_TXT[:]
    flow, keep = [], []

    def heading(label):
        _emit_heading(flow, keep, label)

    heading("Abstract")
    for p in ABSTRACT:
        for line in wrap(p):
            flow.append(line)
            keep.append(0)
        flow.append("")
        keep.append(0)
    flow.pop(); keep.pop()

    heading("Status of This Memo")
    for p in SOTM:
        for line in wrap(p):
            flow.append(line)
            keep.append(0)
        flow.append("")
        keep.append(0)
    flow.pop(); keep.pop()

    heading("Copyright Notice")
    for p in COPYRIGHT:
        for line in wrap(p):
            flow.append(line)
            keep.append(0)
        flow.append("")
        keep.append(0)
    flow.pop(); keep.pop()

    heading("Table of Contents")
    for line in toc_lines:
        flow.append(line)
        keep.append(0)

    cur = 0
    for anchor, num, title, blocks in SECTIONS:
        cur = int(num.rstrip("."))
        SUB_COUNT["sec"] = cur
        SUB_COUNT["n"] = 1
        heading(f"{num}  {title}")
        txt_blocks(blocks, flow, keep)

    heading("Acknowledgements")
    for p in ACK:
        for line in wrap(p):
            flow.append(line)
            keep.append(0)
        flow.append("")
        keep.append(0)
    flow.pop(); keep.pop()

    heading("References")
    flow.append("")
    keep.append(0)
    flow.append("   Normative References")
    keep.append(2)
    flow.append("")
    keep.append(0)
    for tag, cit in REFS_NORM:
        _emit_ref(flow, keep, tag, cit)
    flow.pop(); keep.pop()
    flow.append("")
    keep.append(0)
    flow.append("   Informative References")
    keep.append(2)
    flow.append("")
    keep.append(0)
    for tag, cit in REFS_INFO:
        _emit_ref(flow, keep, tag, cit)
    flow.pop(); keep.pop()

    for anchor, num, title, blocks in BACK:
        SUB_COUNT["sec"] = title.rstrip(".")[-1]  # "A" / "B"
        SUB_COUNT["n"] = 1
        heading(f"{title}  {blocks[0][1] if False else ''}".rstrip())
        # replace the just-added empty-titled heading with the real title
        flow[-2] = APPENDIX_TITLES[title]
        HEADINGS_TXT[-1] = APPENDIX_TITLES[title]
        txt_blocks(blocks[1:], flow, keep)

    heading("Author's Address")
    for line in AUTHOR_ADDR:
        flow.append("   " + line if line else "")
        keep.append(0)

    return flow, keep, list(HEADINGS_TXT)


APPENDIX_TITLES = {
    "Appendix A.": "Appendix A.  Reference Implementation Map",
    "Appendix B.": "Appendix B.  Worked Example and Reproduction",
}


def _emit_ref(flow, keep, tag, cit):
    # references may break long URLs at hyphens to stay within 72 cols
    seg = textwrap.wrap(cit, width=LW - 14, initial_indent=" " * 14,
                        subsequent_indent=" " * 14,
                        break_long_words=False, break_on_hyphens=True)
    label = f"   [{tag}]"
    if len(label) <= 13:
        seg[0] = label.ljust(14) + seg[0][14:]
        flow.extend(seg)
        keep.extend([2] + [0] * (len(seg) - 1))
    else:
        flow.append(label)
        keep.append(2)
        flow.extend(seg)
        keep.extend([0] * len(seg))
    flow.append("")
    keep.append(0)


def paginate(flow, keep, cap1, capn):
    """Greedy pagination with keep-with-next.  Returns list of pages,
    each a list of flow lines.  cap1 = capacity of page 1 body,
    capn = capacity of later pages."""
    pages = []
    cur = []
    cap = cap1
    i = 0
    n = len(flow)
    while i < n:
        need = 1 + keep[i]
        if len(cur) + need > cap and cur:
            pages.append(cur)
            cur = []
            cap = capn
            continue
        cur.append(flow[i])
        i += 1
    if cur:
        pages.append(cur)
    return pages


def toc_render(headings_pages):
    """headings_pages: list of (label, page).  Returns ToC lines."""
    lines = []
    for label, page in headings_pages:
        # indentation: subsections ("4.1.") indented, top-level flush
        if re.match(r"^\d+\.\d+\.", label):
            left = "      " + label
        else:
            left = "   " + label
        num = str(page)
        dots_w = LW - len(left) - 3 - len(num)
        if dots_w < 4:
            dots_w = 4
        dots = ""
        while len(dots) < dots_w:
            dots += " ." if dots else "."
        dots = dots[:dots_w]
        line = left + " " * 2 + dots
        line = line + " " * (LW - len(num) - len(line)) + num
        lines.append(line)
    return lines


def col72(left, right):
    return left + " " * (LW - len(left) - len(right)) + right


def page_header():
    mid = ABBREV
    start = (LW - len(mid)) // 2
    line = "Internet-Draft"
    line += " " * (start - len(line)) + mid
    line += " " * (LW - len(MONTH_YEAR) - len(line)) + MONTH_YEAR
    return line


def page_footer(pnum):
    left = AUTHOR_SHORT
    mid = f"Expires {EXPIRES_TEXT}"
    right = f"[Page {pnum}]"
    start = (LW - len(mid)) // 2
    line = left
    line += " " * (start - len(line)) + mid
    line += " " * (LW - len(right) - len(line)) + right
    return line


def front_block():
    lines = ["", "", ""]
    lines.append(col72("Internet Engineering Task Force", AUTHOR_INITIALS))
    lines.append(col72("Internet-Draft", ORG))
    lines.append(col72("Intended status: Informational", DATE_TEXT))
    lines.append(f"Expires: {EXPIRES_TEXT}")
    lines.append("")
    lines.append("")
    for tl in textwrap.wrap(TITLE, 56):
        lines.append(tl.center(LW).rstrip())
    lines.append((DOCNAME).center(LW).rstrip())
    lines.append("")
    lines.append("")
    return lines


def render_txt():
    # build once with a dummy ToC to learn the heading set
    flow0, keep0, heads0 = build_flow(dummy_toc_from_heads(None))
    heads = heads0  # heading labels in order
    toc0 = toc_render([(h, 1) for h in heads])
    flow1, keep1, heads1 = build_flow(toc0)
    pages1 = paginate(flow1, keep1, cap1=PAGE_H - len(front_block()) - 1,
                      capn=PAGE_H - 4)
    # find page of each heading by scanning pages in order
    hpages = []
    remaining = list(heads1)
    for pnum, page in enumerate(pages1, start=1):
        for line in page:
            if remaining and line == remaining[0]:
                hpages.append((line, pnum))
                remaining.pop(0)
    if remaining:
        raise RuntimeError(f"headings not found in pages: {remaining}")
    # pass 2 with real page numbers
    toc1 = toc_render(hpages)
    flow2, keep2, heads2 = build_flow(toc1)
    pages2 = paginate(flow2, keep2, cap1=PAGE_H - len(front_block()) - 1,
                      capn=PAGE_H - 4)
    # recompute heading pages; iterate once more if they shifted
    hpages2 = []
    remaining = list(heads2)
    for pnum, page in enumerate(pages2, start=1):
        for line in page:
            if remaining and line == remaining[0]:
                hpages2.append((line, pnum))
                remaining.pop(0)
    if [p for _, p in hpages2] != [p for _, p in hpages]:
        toc2 = toc_render(hpages2)
        flow2, keep2, heads2 = build_flow(toc2)
        pages2 = paginate(flow2, keep2, cap1=PAGE_H - len(front_block()) - 1,
                          capn=PAGE_H - 4)
        hpages3 = []
        remaining = list(heads2)
        for pnum, page in enumerate(pages2, start=1):
            for line in page:
                if remaining and line == remaining[0]:
                    hpages3.append((line, pnum))
                    remaining.pop(0)
        assert [p for _, p in hpages3] == [p for _, p in hpages2], \
            "ToC pagination did not converge"

    # assemble output
    out = []
    fb = front_block()
    for pnum, page in enumerate(pages2, start=1):
        if pnum == 1:
            out.extend(fb)
        else:
            out.append(page_header())
            out.append("")
            out.append("")
        out.extend(page)
        # pad: page occupies fb-or-3 header lines + body + footer = PAGE_H
        header_lines = len(fb) if pnum == 1 else 3
        pad = PAGE_H - 1 - header_lines - len(page)
        out.extend([""] * max(pad, 0))
        out.append(page_footer(pnum))
        if pnum != len(pages2):
            out.append("\f")
    out.append("")
    return "\n".join(out)


def dummy_toc_from_heads(heads):
    """A ToC with the right number of lines (page numbers irrelevant for
    line count).  On the first call heads is None: use the static heading
    list assembled from the content model."""
    labels = static_heading_labels()
    return toc_render([(h, 1) for h in labels])


def static_heading_labels():
    labels = ["Abstract", "Status of This Memo", "Copyright Notice",
              "Table of Contents"]
    for anchor, num, title, blocks in SECTIONS:
        sec = num.rstrip(".")
        labels.append(f"{num}  {title}")
        sub = 0
        for kind, payload in blocks:
            if kind == "h2":
                sub += 1
                labels.append(f"{sec}.{sub}.  {payload}")
            elif kind == "h2a":
                labels.append(payload)
    labels.append("Acknowledgements")
    labels.append("References")
    for anchor, num, title, blocks in BACK:
        labels.append(APPENDIX_TITLES[title])
        for kind, payload in blocks:
            if kind == "h2a":
                labels.append(payload)
    labels.append("Author's Address")
    return labels


# ---------------------------------------------------------------------------
# Markdown (kramdown-rfc2629) rendering
# ---------------------------------------------------------------------------

def md_art(lines):
    out = ["~~~"]
    out += lines
    out.append("~~~")
    return out


def md_blocks(blocks, secnum=None):
    out = []
    sub = 0
    for kind, payload in blocks:
        if kind == "h2":
            sub += 1
            out.append(f"## {payload}")
            out.append("")
            continue
        if kind == "h2a":
            out.append(f"## {payload}")
            out.append("")
            continue
        if kind == "p":
            out.append(textwrap.fill(md_cite(payload), 80))
            out.append("")
        elif kind == "art":
            out += md_art(payload)
            out.append("")
        elif kind == "ul":
            for item in payload:
                out.append("* " + textwrap.fill(md_cite(item), 76,
                                                  subsequent_indent="  "))
            out.append("")
        elif kind == "ol":
            for i, item in enumerate(payload, 1):
                out.append(f"{i}. " + textwrap.fill(md_cite(item), 75,
                                                      subsequent_indent="   "))
            out.append("")
        elif kind == "dl":
            for term, text in payload:
                out.append(f"{term}")
                out.append(":   " + textwrap.fill(md_cite(text), 75,
                                                    subsequent_indent="    "))
                out.append("")
    return out


def build_md():
    L = []
    A = L.append
    A("---")
    A(f'title: "{TITLE}"')
    A(f"abbrev: {ABBREV}")
    A(f"docname: {DOCNAME}-latest")
    A("submissiontype: IETF")
    A("number: 0")
    A("category: info")
    A("ipr: trust200902")
    A(f"date: {DATE_ISO}")
    A("area: Security")
    A("keyword:")
    A("  - receipt")
    A("  - audit")
    A("  - DSSE")
    A("  - Ed25519")
    A("  - RFC 8785")
    A("stand_alone: true")
    A("v: 3")
    A("author:")
    A("  -")
    A(f'    ins: "{AUTHOR_INITIALS}"')
    A(f'    name: "{AUTHOR_FULL}"')
    A(f'    organization: "{ORG}"')
    A(f'    email: "{EMAIL}"')
    A("")
    A("normative:")
    for tag, cit in REFS_NORM:
        if tag.startswith("RFC"):
            A(f"  {tag}:")
        elif tag == "DSSE":
            A("  DSSE:")
            A('    title: "Dead Simple Signing Envelope (DSSE)"')
            A("    author:")
            A("      -")
            A('        org: "Secure Systems Lab"')
            A("    target: https://github.com/secure-systems-lab/dsse")
        elif tag == "FIPS180-4":
            A("  FIPS180-4:")
            A('    title: "Secure Hash Standard (SHS)"')
            A("    author:")
            A("      -")
            A('        org: "National Institute of Standards and Technology"')
            A("    date: 2015-08")
            A("    seriesinfo:")
            A("      FIPS: PUB 180-4")
            A("      DOI: 10.6028/NIST.FIPS.180-4")
            A("    target: https://doi.org/10.6028/NIST.FIPS.180-4")
        elif tag == "FIPS202":
            A("  FIPS202:")
            A('    title: "SHA-3 Standard: Permutation-Based Hash and '
              'Extendable-Output Functions"')
            A("    author:")
            A("      -")
            A('        org: "National Institute of Standards and Technology"')
            A("    date: 2015-08")
            A("    seriesinfo:")
            A("      FIPS: PUB 202")
            A("      DOI: 10.6028/NIST.FIPS.202")
            A("    target: https://doi.org/10.6028/NIST.FIPS.202")
    A("")
    A("informative:")
    for tag, cit in REFS_INFO:
        if tag.startswith("RFC"):
            A(f"  {tag}:")
    # I-D references resolve from the datatracker by convention
    A("  I-D.sharif-agent-audit-trail:")
    A("  I-D.ietf-scitt-architecture:")
    A("  INTOTO:")
    A('    title: "in-toto: Providing farm-to-table guarantees for bits and bytes"')
    A("    author:")
    A("      -")
    A('        ins: "S. Torres-Arias"')
    A('        name: "Santiago Torres-Arias"')
    A('        org: "New York University"')
    A("    date: 2019-08")
    A("    seriesinfo:")
    A("      USENIX: Security Symposium")
    A("    target: https://in-toto.io/")
    A("  SIGSTORE:")
    A('    title: "Sigstore: software signing and transparency infrastructure"')
    A("    author:")
    A("      -")
    A('        org: "The Sigstore Project"')
    A("    target: https://www.sigstore.dev/")
    A("  SZLR:")
    A('    title: "szl-receipts: cryptographic receipt core for the SZL Holdings estate (reference implementation of this document)"')
    A("    author:")
    A("      -")
    A(f'        org: "{ORG}"')
    A("    date: 2026-08")
    A("    note: Version 14.0.0. Available from the author.")
    A("")
    A("--- abstract")
    A("")
    for p in ABSTRACT:
        A(textwrap.fill(md_cite(p), 80))
        A("")
    A("--- middle")
    A("")
    # replace citation tags for AAT/SCITT: in md body they must be the
    # kramdown keys I-D.sharif-agent-audit-trail / I-D.ietf-scitt-architecture
    for anchor, num, title, blocks in SECTIONS:
        A(f"# {title}")
        A("")
        for line in md_blocks(blocks):
            A(md_id_cite(line))
    A("# Acknowledgements")
    A("{:numbered=\"false\"}")
    A("")
    for p in ACK:
        A(md_id_cite(textwrap.fill(md_cite(p), 80)))
        A("")
    A("--- back")
    A("")
    for anchor, num, title, blocks in BACK:
        heading = APPENDIX_TITLES[title]
        A(f"# {heading}")
        A("{:numbered=\"false\"}")
        A("")
        # drop blocks[0]: its heading duplicates the appendix title
        for line in md_blocks(blocks[1:]):
            A(md_id_cite(line))
    return "\n".join(L) + "\n"


def md_id_cite(text):
    """Map our [AAT]/[SCITT] tags to kramdown I-D citation keys."""
    return (text.replace("{{AAT}}", "{{I-D.sharif-agent-audit-trail}}")
                .replace("{{SCITT}}", "{{I-D.ietf-scitt-architecture}}"))


# ---------------------------------------------------------------------------

md = build_md()
(HERE / f"{DOCNAME}.md").write_text(md)

txt = render_txt()
(HERE / f"{DOCNAME}.txt").write_text(txt)

lines = txt.split("\n")
over = [(i + 1, l) for i, l in enumerate(lines) if len(l) > LW]
print("lines over 72 cols:", len(over))
for i, l in over[:8]:
    print(f"  line {i} ({len(l)}): {l[:76]}")
print("form feeds:", txt.count("\f"))
print("pages:", txt.count("\f") + 1)
print("total lines:", len(lines))
print("wrote", HERE / f"{DOCNAME}.md")
print("wrote", HERE / f"{DOCNAME}.txt")

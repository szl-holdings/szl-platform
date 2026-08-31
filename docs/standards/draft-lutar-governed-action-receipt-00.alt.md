---
title: Governed Action Receipt (GAR): A Canonical, Verifiable Record of Policy-Governed Actions
abbrev: Governed Action Receipt
docname: draft-lutar-governed-action-receipt-00
category: info
submissiontype: IETF
ipr: trust200902
date: 2026-08-31
author:
  -
    fullname: Stephen Lutar
    organization: SZL Holdings
    email: stephen@szlholdings.com

normative:
  DSSE:
    title: "Dead Simple Signing Envelope"
    author:
      - org: Secure Systems Lab
    target: https://github.com/secure-systems-lab/dsse
  FIPS202:
    title: "SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions"
    author:
      - org: NIST
    date: 2015-08
    target: https://doi.org/10.6028/NIST.FIPS.202
  RFC2119:
    target: https://www.rfc-editor.org/info/rfc2119
  RFC7493:
    target: https://www.rfc-editor.org/info/rfc7493
  RFC8032:
    target: https://www.rfc-editor.org/info/rfc8032
  RFC8174:
    target: https://www.rfc-editor.org/info/rfc8174
  RFC8259:
    target: https://www.rfc-editor.org/info/rfc8259
  RFC8785:
    target: https://www.rfc-editor.org/info/rfc8785

informative:
  AAT:
    title: "Agent Audit Trail: A Standard Logging Format for Autonomous AI Systems"
    author:
      - name: R. Sharif
    date: 2026-08-19
    target: https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/
  INTOTO:
    title: "in-toto: Providing farm-to-table guarantees for bits and bytes"
    author:
      - name: S. Torres-Arias et al.
    date: 2019
    target: https://in-toto.io/
  RFC6838:
    target: https://www.rfc-editor.org/info/rfc6838
  SCITT:
    title: "An Architecture for Trustworthy and Transparent Digital Supply Chains"
    author:
      - name: H. Birkholz et al.
    target: https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/
  SIGSTORE:
    title: "Sigstore: Software Signing and Transparency"
    author:
      - name: The Sigstore Project
    target: https://www.sigstore.dev/
  SZLR:
    title: "szl-receipts 14.0.0: reference implementation of this document"
    author:
      - name: SZL Holdings
    date: 2026
    target: https://github.com/szl-holdings

--- abstract

This document specifies the Governed Action Receipt (GAR), a compact JSON record
that binds an actor, an action, a governing policy (identified by identifier,
version, and the SHA-256 digest of the policy document), a decision outcome
drawn from a closed vocabulary, the digests of the bytes of the artifacts acted
upon, and references to supporting evidence. Receipts are canonicalized with the
JSON Canonicalization Scheme (RFC 8785); the identity of a receipt is the
SHA-256 digest of its own canonical body with the identity field removed, so any
field-level modification is detectable by any verifier without trusting a
registry.

Receipts are signed by carrying their canonical form as the payload of a DSSE
envelope under Ed25519, or are published unsigned under a mandatory honest-
naming convention that makes the absence of a signature legible from the
filename alone. Receipts may be linked into append-only hash chains whose
entries commit to their predecessors; the document states explicitly that silent
truncation of the tail of such a chain is undetectable without an external
anchor, and defines the anchor interface. This document describes the format
exactly as implemented in the open szl-receipts library and includes a fully
reproducible worked example.

--- middle

# Introduction

Automated systems increasingly perform actions with operational consequences:
building software, deploying infrastructure, admitting or rejecting artifacts,
approving changes. Each such action is typically justified by a policy, and each
such justification evaporates the moment the pipeline finishes, unless a record
is kept. The records that are kept are usually prose logs: greppable, mutable,
and impossible to verify independently.

This document specifies the Governed Action Receipt (GAR). A receipt is a small
JSON object that records that a named actor performed a named action under a
named policy, with a stated outcome, over stated artifacts. The policy is
identified not only by name and version but by the SHA-256 digest of the policy
document itself; the artifacts are identified by the SHA-256 digests of their
bytes, never by filename alone. The receipt's own identity (receipt_id) is the
SHA-256 digest of its canonical form, so a receipt is content-addressed: two
parties that agree on the bytes agree on the identity, and any party that alters
a byte produces a different identity.

The design follows three rules, enforced by the reference implementation rather
than left to convention: (1) Bytes, not names: every digest in a receipt covers
artifact bytes, never path strings; a name is a claim and bytes are ground
truth. (2) Honest names: an unsigned artifact is named *.unsigned.json; an empty
signatures array is not a signature, and a filename that lies about the
signature state is a verification failure (Section 8). (3) UNKNOWN is never
passing: the outcome vocabulary is closed (Section 9), the absence of a verdict
is not a verdict, and a promotion gate MUST NOT promote what it cannot
characterize.

A receipt is verifiable offline with nothing but the document bytes, a SHA-256
implementation, and (for signed receipts) an Ed25519 implementation. No online
service, trusted registry, or specific vendor is required. Where a deployment
wants third-party witnesses, receipts compose with existing transparency and
attestation infrastructure (Section 7.3).

Every normative statement in this document describes behavior that the reference
implementation, szl-receipts 14.0.0 (Section 4.6), executes; Appendix B contains
a worked example whose every byte is reproducible from the commands given there.
Where this document and an implementation disagree, the disagreement is a defect
in one of them and should be reported.

# Terminology

Receipt:
:   A JSON object of receipt_type "GovernedAction/v1" as defined in Section
    4.
GAR:
:   The Governed Action Receipt format specified by this document.
Actor:
:   The entity that performed the governed action; a non-empty string whose
    semantics are deployment-defined (a CI runner name, a person, a service
    account).
Action:
:   A non-empty string naming the governed operation.
Policy:
:   The rule set under which the action was governed, identified by an
    identifier string, a version string, and the SHA-256 digest of the
    policy document's bytes.
Subject:
:   An artifact the action operated upon, identified by a name (a label) and
    the SHA-256 digest of its bytes.
Evidence:
:   A URI pointing at supporting material (build logs, attestations, run
    records), optionally pinned by SHA-256.
Outcome:
:   The verdict of the governed action, drawn from the closed vocabulary of
    Section 9.
Receipt identity:
:   The value of the receipt_id field: the SHA-256 digest, in lowercase
    hexadecimal, of the canonical form of the receipt with the receipt_id
    field removed (Section 4.5).
Canonical form:
:   The serialization of a JSON value under the JSON Canonicalization Scheme
    [RFC8785]; see Section 5.
DSSE envelope:
:   The wrapping structure defined by [DSSE]: payload, payloadType,
    signatures; see Section 6.
PAE:
:   The Pre-Authentication Encoding defined by [DSSE]: the domain-separated
    byte string over which signatures are computed; see Section 6.2.
Chain entry:
:   A record binding a receipt to a sequence number and to the digest of the
    preceding entry; see Section 7.
Chain head:
:   The entry_digest of the final entry of a chain.
External anchor:
:   A value (an expected entry count, an expected head digest, or a
    witnessed inclusion proof) obtained from outside the chain itself; see
    Section 7.3.
in-toto Statement:
:   The attestation container of [INTOTO], type "https://in-
    toto.io/Statement/v1", which a receipt can be carried in (Section 6.4).

# Conventions and Definitions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when,
and only when, they appear in all capitals, as shown here.

Hexadecimal digests in this document are lowercase SHA-256 hex strings of
exactly 64 characters, matching the regular expression [0-9a-f]{64}. The hash
function is SHA-256 [FIPS202] throughout; digest agility is deliberately out of
scope for this version (Section 11).

Timestamps are ISO 8601 strings with a mandatory timezone designator (Section
4.2). JSON member names are shown in monospace-equivalent quoting in prose (for
example, "receipt_id") and appear literally in artwork.

# Receipt Format

## Receipt Members

A receipt is a JSON object [RFC8259] containing exactly the following ten
members. No additional members are permitted: a verifier MUST reject a receipt
carrying any member outside this set, and MUST reject a receipt missing any of
them. A closed member set means a producer cannot smuggle un-verified semantics
past a verifier in extension fields.

receipt_id:
:   REQUIRED. String. The receipt identity as defined in Section 4.5: 64
    lowercase hexadecimal characters.
receipt_type:
:   REQUIRED. String. MUST be exactly "GovernedAction/v1".
schema_version:
:   REQUIRED. Non-empty string. For this version of the specification the
    value is "1.0".
created_at:
:   REQUIRED. String. An ISO 8601 timestamp with mandatory timezone (Section
    4.2). This is a real wall-clock value: receipts are runtime artifacts
    recording that something happened at a moment in time; determinism lives
    in the canonical form and the digests, and the timestamp is data.
actor:
:   REQUIRED. Non-empty string. The entity that performed the action.
action:
:   REQUIRED. Non-empty string. The operation performed.
policy:
:   REQUIRED. Object with exactly the members "id" (non-empty string),
    "version" (non-empty string), and "digest_sha256" (64 lowercase hex
    characters: the SHA-256 of the policy document's bytes). The policy is
    identified by its bytes, so a policy that changes while keeping its name
    and version is detectably a different policy.
decision:
:   REQUIRED. Object with members "outcome" (string from the closed
    vocabulary of Section 9) and "rationale" (string; MAY be empty).
subjects:
:   REQUIRED. Array, possibly empty. Each element is an object with exactly
    the members "name" (non-empty string; a label) and "sha256" (64
    lowercase hex characters: the SHA-256 of the artifact's bytes). Digests
    cover bytes, never path strings (Section 11).
evidence:
:   REQUIRED. Array, possibly empty. Each element is an object with member
    "uri" (non-empty string) and OPTIONAL member "sha256" (64 lowercase hex
    characters when present), pinning the bytes behind the URI.

## Timestamp Grammar

The created_at member MUST match the grammar:

~~~
^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$
~~~

and MUST additionally denote a real calendar moment: the grammar alone accepts
impossible dates such as a month of 13, and a verifier MUST reject a created_at
that matches the grammar but fails to parse as a valid date and time. A
timestamp without a timezone designator has no place in an audit log: "14:00" in
whose timezone?

## Example

The following receipt records a governed build. It is reproduced byte-for-byte
in Appendix B, which also gives the commands to regenerate it.

~~~
{
  "action": "build-master-payload",
  "actor": "ci-runner-7",
  "created_at": "2026-08-31T18:00:00Z",
  "decision": {
    "outcome": "PASS",
    "rationale": "deterministic rebuild verified byte-identical"
  },
  "evidence": [
    {
      "uri": "https://ci.szl.example/runs/2026-08-31-001"
    }
  ],
  "policy": {
    "digest_sha256": "6b42e27fca9452605bf173cb28fd7cc6612c9951e5d18347f05b9e79a8f7f4c6",
    "id": "szl.build.v14",
    "version": "14.0.0"
  },
  "receipt_id": "27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8",
  "receipt_type": "GovernedAction/v1",
  "schema_version": "1.0",
  "subjects": [
    {
      "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
      "sha256": "435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0"
    }
  ]
}
~~~

## Canonical Form of the Example

The canonical form (Section 5) of the example receipt is the following 650 bytes
(wrapped for display; the canonical form itself contains no whitespace):

~~~
{"action":"build-master-payload","actor":"ci-runner-
7","created_at":"2026-08-
31T18:00:00Z","decision":{"outcome":"PASS","rationale":"determin
istic rebuild verified byte-identical"},"evidence":[{"uri":"http
s://ci.szl.example/runs/2026-08-31-
001"}],"policy":{"digest_sha256":"6b42e27fca9452605bf173cb28fd7c
c6612c9951e5d18347f05b9e79a8f7f4c6","id":"szl.build.v14","versio
n":"14.0.0"},"receipt_id":"27bfa6b12d88a14ba075f9f2535181172b2ac
40cab6b2ec326b8d6795cc2bba8","receipt_type":"GovernedAction/v1",
"schema_version":"1.0","subjects":[{"name":"dist/SZL_MASTER_PAYL
OAD_V14.md","sha256":"435635ff4ae235805a61b2a79299b695ddd3ad6b34
641dc02eccbfc5b34348b0"}]}
~~~

The SHA-256 of the full canonical form above is
f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059. The SHA-256 of
the canonical form of the body with "receipt_id" removed (570 bytes) is
27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8, which is the
receipt_id; see Section 4.5.

## Receipt Identity

The receipt_id of a receipt MUST be computed as follows: remove the "receipt_id"
member from the receipt object; canonicalize the remaining nine members per
Section 5; compute the SHA-256 digest of the resulting bytes; encode it as 64
lowercase hexadecimal characters.

Because canonicalization absorbs member ordering, two producers with different
serialization habits compute the same identity for the same content; that is the
whole point. A verifier MUST recompute the identity and MUST report a finding
when the declared receipt_id differs from the recomputed value. Because the
identity is a digest, a forged identifier of the form "important-receipt-
final-v2" is structurally impossible: identifiers are never human-chosen
strings.

## Reference Implementation

The reference implementation is the Python package szl-receipts 14.0.0, in which
the constructor build_receipt and the verifier verify_receipt implement exactly
the rules of this section; Appendix B reproduces the example above with it. The
verifier is deliberately non-throwing on bad data: every defect is returned as a
finding string, and an empty finding list means the receipt is well-formed and
its identity checks out. An implementation-independent description of verifier
behavior is given in Section 10.

# Canonicalization

All digest computations in this document (receipt identity, chain entry digests,
envelope payload digests) are performed over the canonical form of the relevant
JSON value. The canonical form MUST be the JSON Canonicalization Scheme (JCS)
defined by [RFC8785]. JCS removes every serialization degree of freedom so that
semantic equality becomes byte equality.

The points of [RFC8785] most consequential for implementers of this document
are:

* Object members are ordered by the UTF-16 code units of their names, not by
  Unicode code points; for astral characters the two orders differ (RFC
  8785, Section 3.2.3).
* Numbers are formatted as ECMAScript Number::toString (RFC 8785, Section
  3.2.2.3): shortest round-trip digits, fixed notation inside the standard
  exponent window, exponential notation outside it, and a sign always
  present on the exponent.
* Strings are escaped minimally and never normalized (RFC 8785, Section
  3.2.2.2): canonically equivalent but code-point-distinct strings
  canonicalize to different bytes, by design.

A receipt producer MUST NOT emit values that are not interoperable JSON
[RFC7493]: no NaN or infinities, and no integer with magnitude greater than or
equal to 2^53, because a parser may route such integers through an IEEE-754
double and silently lose precision; a canonicalizer MUST reject such values
rather than emit bytes a reader cannot hold exactly. The reference
implementation's canonicalizer raises IJsonError in these cases.

# Signing and Envelopes

A receipt proves its own integrity via its identity, but integrity is not
authenticity: anyone can construct a valid-looking receipt. Authenticity is
provided by wrapping the canonical form of the receipt in a DSSE envelope [DSSE]
and signing with Ed25519 [RFC8032], or by publishing the receipt unsigned under
the honest naming convention of Section 8. A receipt MUST NOT be presented in
any state in between: either at least one signature is present, or the artifact
is named unsigned.

## Envelope

The signed artifact is a DSSE envelope [DSSE]: a JSON object with members
"payload" (base64 of the payload bytes), "payloadType" (string), and
"signatures" (array of objects with members "keyid" and "sig", the latter base64
of the signature bytes). Base64 is the standard alphabet with strict decoding: a
verifier MUST reject non-canonical base64 at the structural stage, before any
cryptography is attempted.

The payload of a GAR envelope MUST be the canonical form (Section 5) of the
complete receipt, including receipt_id. Signing the canonical form, rather than
whatever bytes a producer happened to serialize, means the signature verifies
even if the envelope travels through JSON tooling that reserializes whitespace
or reorders members: the bytes under the signature are semantic, not incidental.

The payloadType of a GAR envelope SHOULD be "application/gar+json" (Section 12).
Producers using another payload type MUST choose a value distinct from any
payload type they use for any other signed purpose, so that the domain
separation of Section 6.2 is preserved.

## Pre-Authentication Encoding

Signatures are computed over the Pre-Authentication Encoding of the
(payloadType, payload) pair, exactly as defined by [DSSE]:

~~~
PAE = b"DSSEv1" SP len(payloadType) SP payloadType
          SP len(payload) SP payload
~~~

where SP is a single space (0x20) and the lengths are decimal ASCII byte counts.
Every field is length-prefixed before concatenation, so no pair (type, payload)
can encode to the same bytes as a different pair: the separator positions are
fixed by the lengths, and an attacker cannot smear bytes across the boundary.
This domain separation prevents a signature over a receipt from being replayed
as a signature over any other kind of object that happens to share bytes (the
classic type-confusion attack). A minimal example: PAE("a", "bc") is the byte
string "DSSEv1 1 a 2 bc". For the example receipt of Section 4.3 the encoding
begins "DSSEv1 20 application/gar+json 650 {" and runs 696 bytes in total.

## Signature Algorithm and Keys

The signature algorithm MUST be Ed25519 [RFC8032]. Ed25519 is chosen for its
small fixed-size keys and signatures, deterministic signing (no per-signature
nonce to leak), and wide deployment. One Ed25519 signature occupies 64 bytes, 88
characters base64.

The keyid of a signature SHOULD be the SHA-256 of the raw 32-byte public key, in
lowercase hex, so that keys are identified by content rather than by filename;
deployments MAY override keyid to match an external key registry. Key
distribution and trust-root selection are out of scope for this document;
Section 7.3 notes where witnessed key material can be anchored.

## in-toto Statements

Deployments that already produce in-toto attestations [INTOTO] MAY carry a
receipt as the predicate of an in-toto Statement v1 (type "https://in-
toto.io/Statement/v1"). In this mapping the Statement's subject list holds
(name, sha256) pairs for the artifacts attested, with digests in the digest map
under the "sha256" key, and the receipt appears verbatim as the predicate. The
Statement is then signed as the payload of a DSSE envelope exactly as in Section
6.1. This mapping is optional; a bare GAR envelope carries no less integrity
than a Statement-wrapped one.

## Example Envelope

The canonical bytes of Section 4.4, signed under the example key of Appendix B
(a non-secret test vector), yield the following envelope. The payload member is
wrapped for display; it is a single base64 string of the 650 canonical bytes.
The envelope verifies under the public key printed in Appendix B and is
reproducible byte-for-byte.

~~~
{
  "payload":
      "eyJhY3Rpb24iOiJidWlsZC1tYXN0ZXItcGF5bG9hZCIsImFjdG9yIjoiY2ktcnVu
      "bmVyLTciLCJjcmVhdGVkX2F0IjoiMjAyNi0wOC0zMVQxODowMDowMFoiLCJkZWNp
      "c2lvbiI6eyJvdXRjb21lIjoiUEFTUyIsInJhdGlvbmFsZSI6ImRldGVybWluaXN0
      "aWMgcmVidWlsZCB2ZXJpZmllZCBieXRlLWlkZW50aWNhbCJ9LCJldmlkZW5jZSI6
      "W3sidXJpIjoiaHR0cHM6Ly9jaS5zemwuZXhhbXBsZS9ydW5zLzIwMjYtMDgtMzEt
      "MDAxIn1dLCJwb2xpY3kiOnsiZGlnZXN0X3NoYTI1NiI6IjZiNDJlMjdmY2E5NDUy
      "NjA1YmYxNzNjYjI4ZmQ3Y2M2NjEyYzk5NTFlNWQxODM0N2YwNWI5ZTc5YThmN2Y0
      "YzYiLCJpZCI6InN6bC5idWlsZC52MTQiLCJ2ZXJzaW9uIjoiMTQuMC4wIn0sInJl
      "Y2VpcHRfaWQiOiIyN2JmYTZiMTJkODhhMTRiYTA3NWY5ZjI1MzUxODExNzJiMmFj
      "NDBjYWI2YjJlYzMyNmI4ZDY3OTVjYzJiYmE4IiwicmVjZWlwdF90eXBlIjoiR292
      "ZXJuZWRBY3Rpb24vdjEiLCJzY2hlbWFfdmVyc2lvbiI6IjEuMCIsInN1YmplY3Rz
      "IjpbeyJuYW1lIjoiZGlzdC9TWkxfTUFTVEVSX1BBWUxPQURfVjE0Lm1kIiwic2hh
      "MjU2IjoiNDM1NjM1ZmY0YWUyMzU4MDVhNjFiMmE3OTI5OWI2OTVkZGQzYWQ2YjM0
      "NjQxZGMwMmVjY2JmYzViMzQzNDhiMCJ9XX0="

  "payloadType": "application/gar+json",
  "signatures": [
    {
      "keyid": "eda5305f0821f0e27dab616e03a6f11ee73bf5cbba7096bc398e46e946dee155",
      "sig": "gm/MRQTRvxzNM+u56GMKsL4FTWCo9/N5HPW1/+8zc4L2BIFScMxy9khnNHdMQP9CTfEw0cvCsxfT/QHrFUd6Bg=="
    }
  ]
}
~~~

# Hash-Chained Logs and External Anchors

Receipts gain operational value when they are ordered. A chain binds each
receipt to a sequence number and to its predecessor, producing an append-only
log whose every entry authenticates the entire history before it.

## Chain Entry Format

A chain entry is a JSON object with exactly the members "seq" (integer, 1 for
the first entry), "receipt" (a receipt object per Section 4), "prev" (the
entry_digest of the preceding entry, or null for the genesis entry), and
"entry_digest" (64 lowercase hex characters). The binding digest is:

~~~
entry_digest = SHA-256(JCS({"seq": n,
                           "receipt": <receipt>,
                           "prev": <hex string or null>}))
~~~

computed over the canonical form of exactly those three identity-defining
members. Because the embedded receipt is itself content-addressed by receipt_id,
one digest recomputation authenticates the receipt, its position, and its
linkage. An appender MUST validate the receipt per Section 10 before it touches
the chain: a chain containing an invalid receipt is a chain that lies with
confidence.

The genesis entry of the example chain of Appendix B is:

~~~
{
  "entry_digest": "0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9",
  "prev": null,
  "receipt": {
    "action": "build-master-payload",
    "actor": "ci-runner-7",
    "created_at": "2026-08-31T18:00:00Z",
    "decision": {
      "outcome": "PASS",
      "rationale": "deterministic rebuild verified byte-identical"
    },
    "evidence": [
      {
        "uri": "https://ci.szl.example/runs/2026-08-31-001"
      }
    ],
    "policy": {
      "digest_sha256": "6b42e27fca9452605bf173cb28fd7cc6612c9951e5d18347f05b9e79a8f7f4c6",
      "id": "szl.build.v14",
      "version": "14.0.0"
    },
    "receipt_id": "27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8",
    "receipt_type": "GovernedAction/v1",
    "schema_version": "1.0",
    "subjects": [
      {
        "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
        "sha256": "435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0"
      }
    ]
  },
  "seq": 1
}
~~~

The second entry has seq 2, prev
0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9 (the digest
above), and entry_digest
ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c.

## What the Chain Detects

A chain verifier re-derives every entry_digest and cross-checks every linkage.
The following attack classes are detectable from the chain alone, and each MUST
be reported as a distinct finding (the reference implementation assigns the
stable codes shown):

digest-mismatch:
:   entry content does not hash to its declared entry_digest.
reorder:
:   seq numbers not strictly increasing along the log.
gap:
:   a forward jump in seq: middle entries are missing.
replay:
:   the same seq reappears with an identical digest.
fork:
:   the same seq reappears with two different digests.
broken-prev-link:
:   an entry's prev is not the digest of the preceding entry.
genesis-prev-not-null:
:   the first entry does not anchor at null.
malformed-entry:
:   missing members, a bad seq, or a non-canonicalizable entry.

## External Anchors and the Truncation Limitation

This section states the honest limit of any self-verifying log, because a
specification that omits it would oversell the mechanism.

A hash chain verified without external information proves integrity of the
presented history from genesis to the presented head. It cannot prove
completeness: an operator who silently drops the newest entries yields a shorter
chain that is perfectly valid. Tail truncation is undetectable from the chain
alone. No hashing scheme removes this limitation; it is a property of self-
authenticating logs, not of this design.

The mitigation is an external anchor: information about the chain obtained from
outside the chain. This document defines two anchor inputs to the verifier,
which a deployment MUST treat as untrusted-chain/trusted-anchor:

expected_entries:
:   an integer; if the chain holds fewer entries, the verifier reports
    "truncated".
expected_head:
:   a 64-hex digest; if the digest of the final entry differs, the verifier
    reports "head-mismatch".

Anchors can be published out of band (a head digest in a release announcement, a
count in a ticket) or witnessed by a transparency service. GAR chains are
deliberately compatible with the SCITT architecture [SCITT]: a signed GAR
envelope is a signed statement in SCITT terms, and a transparency service can
return an inclusion receipt for a chain head, converting the head into a
witnessed anchor. Sigstore-style transparency logs [SIGSTORE] (for example
Rekor) provide the same function for the envelope itself. Deployments that
cannot anchor MUST state in their own audit narrative that tail truncation is
outside the verified envelope.

# Honest Unsigned Naming

A file's name MUST tell the truth about its signature state. The convention:

* An envelope carrying one or more signatures is written as <base>.json, for
  example build/report.json.
* An envelope carrying zero signatures is written as <base>.unsigned.json, for
  example build/report.unsigned.json.

An empty signatures array is not a signature. The rule exists because consumers
pattern-match on extensions: an envelope with "signatures": [] written to
report.json presents as a signed-looking artifact that anyone could have
produced. Honest naming makes the trust state legible from the directory listing
alone.

Verification is bidirectional and MUST fail in both directions: a
*.unsigned.json file that contains one or more signatures is a tampered rename,
and any other .json artifact whose signatures array is empty is a tampered
rename. Both MUST be reported as verification failures (the reference
implementation raises NamingError and its CLI exits with status 2). Renaming a
file MUST NOT change what the world believes about it.

A missing signatures member is not an unsigned artifact; it is a malformed
envelope, and MUST be reported as such. Absent is different from empty, and
conflating them is how quiet forgeries pass review.

The naming convention applies to artifacts on disk and to attachments in
transit; it is orthogonal to the cryptographic checks of Section 6 and is always
applied first (Section 10).

# Outcome Vocabulary

The decision.outcome member MUST take exactly one of the following five values.
The vocabulary is closed deliberately: a free-text status field drifts ("ok",
"green", "mostly fine") until nothing can be gated on it.

PASS:
:   the governed action completed and met policy.
WARN:
:   the action completed with a recorded concern; not a pass.
FAIL:
:   the governed action failed.
BLOCKED:
:   the action was prevented from running by policy or by the environment.
UNKNOWN:
:   no verdict was recorded; the absence of a verdict is itself the record.

A verifier MUST reject a receipt whose outcome is outside this vocabulary, and a
producer MUST fail at build time rather than emit one: shipping a receipt with
an un-gateable outcome is worse than crashing the builder.

UNKNOWN MUST NOT be promoted to PASS. More precisely: absence of a verdict is
not a verdict; a promotion gate MUST admit PASS and MUST refuse FAIL, BLOCKED,
and UNKNOWN unconditionally; WARN MAY be admitted only by an explicit, recorded
override (in the reference implementation, promotion_gate(outcome,
allow_warn=True); the override is itself an auditable decision). Code that
treats "no verdict" as "passed" is how silent corruption ships; "we don't know"
is informationally worse than "it failed", because failure at least tells you
where to look.

# Verifier Behavior

This section specifies what a conforming verifier checks. Verification is fail-
closed throughout: any malformed input, any unexpected member, any mismatch
yields a negative result, never an exception that a caller might mistake for
success.

Receipt verification, given a parsed JSON value:

1. The value MUST be an object containing exactly the ten members of Section
   4.1; missing or extra members are findings.
2. receipt_type MUST be "GovernedAction/v1"; schema_version MUST be a non-
   empty string.
3. created_at MUST match the grammar of Section 4.2 and parse as a real
   calendar moment.
4. actor and action MUST be non-empty strings.
5. policy MUST have non-empty string id and version, and digest_sha256 MUST be
   64 lowercase hex characters.
6. decision.outcome MUST be within the vocabulary of Section 9;
   decision.rationale MUST be a string.
7. Every subject MUST have a non-empty name and a 64-hex sha256, and no other
   members. Where the artifact is available, the verifier SHOULD re-hash
   the artifact's bytes (in bounded chunks, so artifact size is immaterial)
   and compare.
8. Every evidence item MUST have a non-empty uri, and sha256 when present MUST
   be 64 lowercase hex characters.
9. The declared receipt_id MUST be 64 lowercase hex characters and MUST equal
   the identity recomputed per Section 4.5. Any mismatch MUST be reported:
   the body was tampered with or was produced by a non-canonical builder.

Envelope verification, given a parsed JSON value and optionally a public key,
proceeds in stages:

1. Naming: the artifact's filename MUST satisfy Section 8 for the envelope's
   actual signature state. Failure here is a verification failure, not a
   warning.
2. Structure: payloadType MUST be a non-empty string; payload MUST decode
   under strict base64; signatures MUST be an array.
3. Signature: if a public key was supplied, at least one signature entry MUST
   verify over the PAE (Section 6.2) of the embedded (payloadType, payload)
   pair under that key; malformed entries are skipped, and the result is
   boolean: authentic under this key, or not. If no key was supplied, the
   signature stage is skipped and MUST be reported as not checked, never as
   passed.
4. Payload: the decoded payload of a GAR envelope SHOULD itself be verified as
   a receipt per the first list.

Chain verification consumes a complete chain from genesis and reports each
defect of Section 7.2 as a distinct, codeable finding, then applies the external
anchors of Section 7.3 when supplied. A chain verifier MUST accept
expected_entries and expected_head inputs; a chain verified without anchors MUST
be reported with the truncation caveat stated.

The reference implementation's command-line verifier maps these outcomes onto
exit codes: 0 for success, 2 for verification failure (the artifact is reachable
but untrustworthy: tamper, dishonest naming, chain break), and 3 for usage or
I/O error. The distinction between 2 and 3 is the difference between an incident
and a retry, and integrations SHOULD preserve it.

# Security Considerations

Digest agility. SHA-256 [FIPS202] is hard-coded for this version. A future
revision that admits another hash function MUST do so by changing the
receipt_type version string, not by overloading field contents; the closed
member set and the content-addressed identity mean an algorithm change produces
a different format, and should be named like one.

Canonicalization failures are security failures. A verifier that canonicalizes
differently from the producer will either reject valid receipts (availability)
or, worse, accept a receipt under an identity the producer never computed. The
UTF-16 member ordering and ECMAScript number formatting of Section 5 are the two
places independent implementations diverge; the worked example of Appendix B is
a conformance test: an implementation that cannot reproduce its receipt_id is
not a GAR implementation.

Unsigned receipts carry no authenticity. An honest unsigned receipt (Section 8)
proves only integrity of its own bytes. Verifiers MUST NOT report an unsigned
receipt as authenticated, and pipelines SHOULD treat unsigned receipts as
inadmissible for promotion decisions.

Key custody. Ed25519 private keys are offline, operator-held artifacts. The
reference implementation writes private keys unencrypted with file mode 0600 and
refuses to overwrite an existing key, because accidental key rotation is a
silent audit gap; deliberate rotation is an operator decision. Key compromise
revokes nothing automatically: verifiers pin keys directly, and a compromised
key's receipts remain verifiable forgeries until the verifier's key set is
updated.

Log completeness requires anchors. As stated in Section 7.3, tail truncation of
a chain is undetectable without an external anchor, and deployments MUST obtain
anchors out of band or from a transparency service [SCITT] [SIGSTORE]. Forks
(two chains with a common prefix) are detectable only by comparing heads or by a
witness that refuses double-booking; the chain format makes such comparison
cheap, it does not perform it.

Timestamps are claims. created_at is supplied by the producer's clock. A receipt
authenticates that the signer asserted a time, not that the assertion was true.
Deployments requiring trustworthy time SHOULD anchor chain heads with a
timestamping or transparency service, as Section 7.3 describes.

Denial of service. Receipts are small by construction, but envelope and chain
parsing MUST bound memory: artifact hashing is streamed (the reference
implementation reads 1 MiB chunks), and verifiers SHOULD bound accepted file
sizes for chain inputs.

# IANA Considerations

This document requests registration of the following media type in the
"Application Media Types" registry. At the time of writing the type is
unregistered and provisional; this section serves as the registration template
per RFC 6838 [RFC6838]. Until registration is confirmed, the type MUST be
regarded as provisional and unregistered.

Type name:
:   application
Subtype name:
:   gar+json
Required parameters:
:   none
Optional parameters:
:   none
Encoding considerations:
:   binary (JSON text in UTF-8). The payload of a signed artifact is a DSSE
    envelope whose payload member carries base64-encoded canonical JSON.
Security considerations:
:   See Section 11 of this document. Content may be signed per Section 6;
    unsigned content follows the naming convention of Section 8. Verifiers
    MUST apply the behavior of Section 10.
Interoperability considerations:
:   All digest-bearing fields depend on RFC 8785 canonicalization; see
    Section 5.
Published specification:
:   this document
Applications that use this media type:
:   governance, build-system, and audit tooling producing or consuming
    Governed Action Receipts.
Intended usage:
:   COMMON
Change controller:
:   Stephen Lutar <stephen@szlholdings.com>

A registry for outcome values is not requested: the vocabulary of Section 9 is
closed by design and can be extended only by a revision of this document, so
that no deployment can unilaterally add an outcome that gates cannot interpret.

# Acknowledgements

The format specified here is implemented and exercised daily by the szl-receipts
library within the SZL Holdings estate; its test suite, which drives truncation,
reorder, replay, fork, broken-link, payload bit-flip, wrong-key, PAE prefix-
collision, and dishonest-rename cases, served as the executable adversarial
review for this document. The DSSE specification, the in-toto project, and the
SCITT working group's architecture draft provided the substrate this format
composes with.

--- back

# Reference Implementation Map

For reviewers cross-checking this document against code: szl-receipts 14.0.0,
package szl_receipts.

Section 4:
:   receipt.py: build_receipt, verify_receipt, compute_receipt_id
Section 5:
:   jcs.py: jcs_canon_bytes, serialize, number_to_js_str
Section 6:
:   dsse.py: pae, sign_bytes, verify_envelope, statement, keygen
Section 7:
:   chain.py: append, entry_digest_for, verify_chain
Section 8:
:   naming.py: write_envelope, verify_honest_naming, NamingError
Section 9:
:   outcome.py: Outcome, is_passing, promotion_gate
Section 10:
:   receipt.py and chain.py verifiers; cli.py exit-code contract
digests:
:   digests.py: sha256_file (1 MiB chunks), sha256_hex, sha256_bytes

# Worked Example and Reproduction

## B.1.  Inputs

Two files are created with fixed content:

~~~
mkdir -p policies dist
printf 'SZL Build Policy v14\nAll governed builds must be \
  reproducible and receipted.\n' > policies/szl.build.v14.md
printf 'SZL MASTER PAYLOAD V14\n' > dist/SZL_MASTER_PAYLOAD_V14.md
~~~

Their SHA-256 digests are
6b42e27fca9452605bf173cb28fd7cc6612c9951e5d18347f05b9e79a8f7f4c6 (policy) and
435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0 (payload
artifact). The example Ed25519 key is derived from the fixed seed
SHA-256("draft-lutar-governed-action-receipt example key") via
Ed25519PrivateKey.from_private_bytes; it is a public test vector and MUST NOT be
used operationally. Its public key is:

~~~
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAr42BDg9MLmFBYa4Dd1A2NZY2sfainY46BBByRtBYkys=
-----END PUBLIC KEY-----
~~~

## B.2.  Reproduction Script

With szl-receipts installed (pip install -e ./szl-receipts, version 14.0.0, on
Python >= 3.11 with the cryptography library >= 42), the following script
regenerates every value in Sections 4.3, 4.4, 6.5, and 7.1. Output is
deterministic: created_at is fixed and the key is fixed.

~~~
"""Reproduce the worked example of draft-lutar-governed-action-receipt-00.

Run from a directory containing the szl-receipts repository checkout:

    pip install -e ./szl-receipts          # version 14.0.0
    mkdir -p policies dist
    printf 'SZL Build Policy v14\nAll governed builds must be reproducible and receipted.\n' > policies/szl.build.v14.md
    printf 'SZL MASTER PAYLOAD V14\n' > dist/SZL_MASTER_PAYLOAD_V14.md
    python reproduce-appendix-b.py

Expected: the receipt prints with receipt_id
27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8,
canonical length 650 bytes, canonical sha256
f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059,
genesis entry_digest
0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9,
second entry_digest
ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c,
and the DSSE envelope verifies under the printed example public key.
All output is deterministic: created_at is fixed and the Ed25519
example key is derived from a fixed seed.  The example key is a
public, non-secret test vector; never use it operationally.
"""
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from szl_receipts import (
    Outcome, append, build_receipt, compute_receipt_id, jcs_canon_bytes,
    sha256_file, sha256_hex, sign_bytes, verify_chain, verify_envelope,
    verify_receipt,
)

receipt = build_receipt(
    actor="ci-runner-7",
    action="build-master-payload",
    policy={
        "id": "szl.build.v14",
        "version": "14.0.0",
        "digest_sha256": sha256_file("policies/szl.build.v14.md"),
    },
    outcome=Outcome.PASS,
    rationale="deterministic rebuild verified byte-identical",
    subjects=[{
        "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
        "sha256": sha256_file("dist/SZL_MASTER_PAYLOAD_V14.md"),
    }],
    evidence=[{"uri": "https://ci.szl.example/runs/2026-08-31-001"}],
    created_at="2026-08-31T18:00:00Z",  # fixed, so the example is reproducible
)
assert verify_receipt(receipt) == []
assert receipt["receipt_id"] == compute_receipt_id(receipt)
print(json.dumps(receipt, indent=2, sort_keys=True))

canon = jcs_canon_bytes(dict(receipt))  # the bytes a DSSE envelope carries
print("canonical bytes:", len(canon))
print("sha256(canonical):", sha256_hex(canon))
print("receipt_id:", receipt["receipt_id"])

seed = bytes.fromhex(sha256_hex(b"draft-lutar-governed-action-receipt example key"))
key = Ed25519PrivateKey.from_private_bytes(seed)  # non-secret test vector
print(key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode(), end="")

envelope = sign_bytes(canon, "application/gar+json", key)
assert verify_envelope(envelope, key.public_key())
print(json.dumps(envelope, indent=2, sort_keys=True))

chain = []
first = append(chain, receipt)
second = build_receipt(
    actor="ci-runner-7",
    action="promote-master-payload",
    policy={
        "id": "szl.build.v14",
        "version": "14.0.0",
        "digest_sha256": sha256_file("policies/szl.build.v14.md"),
    },
    outcome=Outcome.PASS,
    rationale="promotion gate passed on PASS receipt",
    subjects=[{
        "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
        "sha256": sha256_file("dist/SZL_MASTER_PAYLOAD_V14.md"),
    }],
    evidence=[{"uri": "https://ci.szl.example/runs/2026-08-31-001"}],
    created_at="2026-08-31T18:05:00Z",
)
second_entry = append(chain, second)
report = verify_chain(
    chain, expected_entries=2, expected_head=second_entry["entry_digest"]
)
assert report.ok
print("genesis entry_digest:", first["entry_digest"])
print("entry 2 digest:", second_entry["entry_digest"])
print("chain head:", report.head)
~~~

## B.3.  Expected Digests

~~~
receipt_id:           27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8
canonical bytes:      650
sha256(canonical):    f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059
keyid:                eda5305f0821f0e27dab616e03a6f11ee73bf5cbba7096bc398e46e946dee155
genesis entry_digest: 0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9
entry 2 entry_digest: ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c
chain head:           ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c
~~~

An implementation that reproduces these digests from these inputs implements
Sections 4, 5, 6, and 7 correctly. The verification chain for the signed example
also holds: verify_envelope on the envelope of Section 6.5 under the public key
of B.1 returns true; verify_chain on the two-entry chain with expected_entries=2
and expected_head equal to the chain head above reports ok.

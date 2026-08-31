---
title: "The Governed Action Receipt (GAR) Format"
abbrev: Governed Action Receipt
docname: draft-lutar-governed-action-receipt-00-latest
submissiontype: IETF
number: 0
category: info
ipr: trust200902
date: 2026-08-31
area: Security
keyword:
  - receipt
  - audit
  - DSSE
  - Ed25519
  - RFC 8785
stand_alone: true
v: 3
author:
  -
    ins: "S. Lutar"
    name: "Stephen Lutar"
    organization: "SZL Holdings"
    email: "stephen@szlholdings.com"

normative:
  DSSE:
    title: "Dead Simple Signing Envelope (DSSE)"
    author:
      -
        org: "Secure Systems Lab"
    target: https://github.com/secure-systems-lab/dsse
  FIPS180-4:
    title: "Secure Hash Standard (SHS)"
    author:
      -
        org: "National Institute of Standards and Technology"
    date: 2015-08
    seriesinfo:
      FIPS: PUB 180-4
      DOI: 10.6028/NIST.FIPS.180-4
    target: https://doi.org/10.6028/NIST.FIPS.180-4
  FIPS202:
    title: "SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions"
    author:
      -
        org: "National Institute of Standards and Technology"
    date: 2015-08
    seriesinfo:
      FIPS: PUB 202
      DOI: 10.6028/NIST.FIPS.202
    target: https://doi.org/10.6028/NIST.FIPS.202
  RFC2119:
  RFC7493:
  RFC8032:
  RFC8174:
  RFC8259:
  RFC8785:

informative:
  RFC6838:
  RFC8792:
  I-D.sharif-agent-audit-trail:
  I-D.ietf-scitt-architecture:
  INTOTO:
    title: "in-toto: Providing farm-to-table guarantees for bits and bytes"
    author:
      -
        ins: "S. Torres-Arias"
        name: "Santiago Torres-Arias"
        org: "New York University"
    date: 2019-08
    seriesinfo:
      USENIX: Security Symposium
    target: https://in-toto.io/
  SIGSTORE:
    title: "Sigstore: software signing and transparency infrastructure"
    author:
      -
        org: "The Sigstore Project"
    target: https://www.sigstore.dev/
  SZLR:
    title: "szl-receipts: cryptographic receipt core for the SZL Holdings estate (reference implementation of this document)"
    author:
      -
        org: "SZL Holdings"
    date: 2026-08
    note: Version 14.0.0. Available from the author.

--- abstract

This document specifies the Governed Action Receipt (GAR), a compact, tamper-
evident record that binds an actor, an action, a governing policy identified by
the SHA-256 digest of the policy document, a decision outcome drawn from a
closed vocabulary, the subjects of the action identified by digests of their
bytes, and references to evidence. A receipt is canonicalized with the JSON
Canonicalization Scheme {{RFC8785}} and is self-identifying: its receipt_id is
the SHA-256 digest of its canonical body with the identity field removed, so any
field-level modification is detectable by any verifier without trusting a
registry.

Receipts are carried in DSSE envelopes {{DSSE}} signed with Ed25519 {{RFC8032}},
or are published honestly unsigned under a naming convention that makes the
absence of a signature legible from the filename. Receipts may be linked into an
append-only hash-chained log in which each entry commits to its predecessor; the
limits of that construction, in particular the undetectability of tail
truncation without an external anchor, are stated explicitly. The outcome
vocabulary forbids promoting an unknown verdict to a passing one. This document
specifies the receipt format, canonicalization, signing, chaining, naming,
outcomes, and verifier behavior, and matches the reference implementation (szl-
receipts 14.0.0 {{SZLR}}) statement for statement.

--- middle

# Introduction

Automated systems increasingly perform actions with operational consequences:
building software, deploying infrastructure, admitting or rejecting artifacts,
approving changes. Each such action is justified by a policy, and each
justification evaporates when the pipeline finishes unless a record is kept. The
records that are kept are usually prose logs: greppable, mutable, and impossible
to verify independently.

This document specifies the Governed Action Receipt (GAR). A receipt is a small
JSON object {{RFC8259}} recording that a named actor performed a named action
under a named policy, with a stated outcome, over stated artifacts. The policy
is identified by identifier, version, and the SHA-256 digest of the policy
document's bytes; the artifacts (subjects) are identified by the SHA-256 digests
of their bytes, never by filename alone. The receipt's own identity, receipt_id,
is the SHA-256 digest of its canonical form with the identity field removed, so
a receipt is content-addressed: parties that agree on the bytes agree on the
identity, and any party that alters a byte produces a different identity.

Three design rules, taken from the doctrine of the estate that operates the
reference implementation, bind everything that follows:

* Bytes, not names. Every digest in a receipt covers artifact bytes, never
  path strings; a name is a claim and bytes are ground truth.
* Honest names. An empty signatures array is not a signature. An unsigned
  artifact is named *.unsigned.json, and a filename that lies about the
  signature state is a verification failure (Section 8). Renaming a file
  must never change what the world believes about it.
* UNKNOWN is never passing. The outcome vocabulary is closed (Section 9); the
  absence of a verdict is not a verdict; a promotion gate must not promote
  what it cannot characterize.

A receipt is verifiable offline with nothing but the document bytes, a SHA-256
implementation, and, for signed receipts, an Ed25519 implementation. No online
service, trusted registry, or vendor is required. Where a deployment wants
third-party witnessing, receipts compose with transparency and attestation
infrastructure (Section 7.3).

This document is an individual submission to the IETF and is published as
Informational. Every normative statement in it describes behavior that the
reference implementation, szl-receipts 14.0.0 {{SZLR}}, executes; Appendix B
contains a complete worked example whose every byte is reproducible from the
commands given there. Where this document and the implementation disagree, the
disagreement is a defect in one of them.

Related work: {{I-D.sharif-agent-audit-trail}} specifies a JSON logging format for autonomous AI agents
with hash chaining; like this document, it is an individual Internet-Draft with
no formal standing in the IETF standards process. The SCITT architecture
{{I-D.ietf-scitt-architecture}} defines transparency services for supply-chain statements; Section 7.3
describes how GAR chains obtain external anchors from such services. Sigstore
{{SIGSTORE}} provides public signing and transparency infrastructure, and in-
toto {{INTOTO}} the attestation container with which Section 6.4 composes.

# Terminology

receipt
:   A JSON object of receipt_type "GovernedAction/v1" as defined in Section 4.

GAR
:   The Governed Action Receipt format specified here.

actor
:   The entity that performed the governed action; a non-empty string whose
    semantics are deployment-defined (a CI runner name, a person, a service
    account).

action
:   A non-empty string naming the governed operation.

policy
:   The rule set under which the action was governed, identified by an
    identifier string, a version string, and the SHA-256 digest of the
    policy document's bytes.

subject
:   An artifact the action operated upon, identified by a name (a label) and
    the SHA-256 digest of its bytes.

evidence
:   A URI pointing at supporting material (build logs, attestations, run
    records), optionally pinned by a SHA-256 digest of the bytes behind the
    URI.

outcome
:   The verdict of the governed action, drawn from the closed vocabulary of
    Section 9.

receipt identity
:   The value of the receipt_id member: the SHA-256 digest, in lowercase
    hexadecimal, of the canonical form of the receipt with the receipt_id
    member removed (Section 4.5).

canonical form
:   The serialization of a JSON value under the JSON Canonicalization Scheme
    {{RFC8785}}; see Section 5.

DSSE envelope
:   The wrapping structure defined by {{DSSE}}: payload, payloadType,
    signatures; see Section 6.

PAE
:   The Pre-Authentication Encoding defined by {{DSSE}}: the domain-separated
    byte string over which signatures are computed; see Section 6.2.

chain entry
:   A record binding a receipt to a sequence number and to the digest of the
    preceding entry; see Section 7.

chain head
:   The entry_digest of the final entry of a chain.

external anchor
:   Information about a chain obtained from outside the chain: an expected
    entry count, an expected head digest, or a witnessed inclusion proof;
    see Section 7.3.

finding
:   A problem report emitted by a verifier. An empty findings list is the only
    success signal (Section 10).

# Conventions and Definitions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in BCP 14 {{RFC2119}} {{RFC8174}}
when, and only when, they appear in all capitals, as shown here.

The following notation is used throughout:

* hex64: a string of exactly 64 lowercase hexadecimal characters (matching the
  regular expression [0-9a-f]{64}), encoding a 32-byte digest.
* SHA-256(x): the SHA-256 digest {{FIPS180-4}} of byte string x, rendered as
  hex64.
* JCS(x): the canonical serialization of JSON value x per {{RFC8785}}, as
  UTF-8 bytes (Section 5).
* JSON text: text conforming to {{RFC8259}}. Input to canonicalization MUST
  also conform to I-JSON {{RFC7493}}.
* The reference implementation: szl-receipts 14.0.0 {{SZLR}}, a Python package
  whose only runtime dependency beyond the standard library is the
  "cryptography" package.

Timestamps use the ISO 8601 profile of Section 4.2. JSON member names appear in
double quotes in prose (for example, "receipt_id") and appear literally in
artwork.

# Receipt Format

## Receipt Members

A receipt is a JSON object {{RFC8259}} containing exactly the ten members
defined below. A verifier MUST report any missing member and any additional
member; the set is closed so that a producer cannot smuggle un-verified
semantics past a verifier in extension fields. Member order is insignificant:
every integrity computation operates on the canonical form (Section 5), which
absorbs ordering and whitespace.

receipt_id
:   REQUIRED. String, hex64. The receipt identity, computed as specified in
    Section 4.5.

receipt_type
:   REQUIRED. String. MUST be exactly "GovernedAction/v1".

schema_version
:   REQUIRED. Non-empty string. Receipts conforming to this document carry
    "1.0". This version's verifier checks only that the value is a non-
    empty string; the pair (receipt_type, schema_version) is the versioning
    hook for future revisions.

created_at
:   REQUIRED. String. An ISO 8601 timestamp per Section 4.2. This is a real
    wall-clock value: a receipt records that something happened at a moment
    in time, and the timestamp is data, not formatting. It is asserted by
    the producer and is not witnessed; see Section 11.

actor
:   REQUIRED. Non-empty string. The entity that performed the action.

action
:   REQUIRED. Non-empty string. The operation performed.

policy
:   REQUIRED. Object. MUST contain "id" (non-empty string), "version" (non-
    empty string), and "digest_sha256" (hex64; the SHA-256 of the policy
    document's bytes). Policy identity is content-based: a policy that
    changes while keeping its name and version is detectably a different
    policy. This version's verifier does not flag additional policy
    members, but producers SHOULD limit "policy" to these three members.

decision
:   REQUIRED. Object. MUST contain "outcome" (string from the closed vocabulary
    of Section 9) and "rationale" (string; MAY be empty).

subjects
:   REQUIRED. Array, possibly empty. Each element is an object with exactly the
    members "name" (non-empty string; a label) and "sha256" (hex64; the
    SHA-256 of the artifact's bytes). Digests cover bytes, never path
    strings; see Section 11.

evidence
:   REQUIRED. Array, possibly empty. Each element is an object with member
    "uri" (non-empty string) and OPTIONAL member "sha256" (hex64 when
    present), pinning the bytes behind the URI.

Bytes, not names: producers MUST compute subject digests over the artifact's
bytes. The reference implementation reads files in bounded 1 MiB chunks, so
multi-gigabyte artifacts hash in constant memory; its in-memory digest helper
accepts byte strings only, so passing a path string where bytes belong fails
loudly instead of hashing the name.

## Timestamp Grammar

The "created_at" member MUST match the following grammar (seconds and timezone
designator mandatory, fractional seconds optional):

~~~
YYYY-MM-DD \"T\" HH:MM:SS [.fff...] (\"Z\" | (+|-)hh:mm)

Regular expression:
\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})\Z
~~~

and MUST denote a real calendar moment: the grammar alone accepts impossible
values (a month of 13 matches it), so a verifier MUST additionally parse the
value and reject impossible dates. A timestamp without a timezone designator has
no place in an audit log. Producers MUST normalize timestamps to UTC and use the
"Z" designator; verifiers MUST accept the offset forms as well.

## Example Receipt

The following receipt records a governed build. Every byte of it, and every
digest quoted in this document, is produced by the reference implementation and
is reproduced by the commands in Appendix B. (In the plain-text rendering,
figure lines longer than the column limit are folded per {{RFC8792}}.)

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

The canonical form (Section 5) of the example receipt is the following 650
bytes, shown folded; the canonical form itself contains no whitespace:

~~~
{"action":"build-master-payload","actor":"ci-runner-7","created_at":"2026-08-31T18:00:00Z","decision":{"outcome":"PASS","rationale":"deterministic rebuild verified byte-identical"},"evidence":[{"uri":"https://ci.szl.example/runs/2026-08-31-001"}],"policy":{"digest_sha256":"6b42e27fca9452605bf173cb28fd7cc6612c9951e5d18347f05b9e79a8f7f4c6","id":"szl.build.v14","version":"14.0.0"},"receipt_id":"27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8","receipt_type":"GovernedAction/v1","schema_version":"1.0","subjects":[{"name":"dist/SZL_MASTER_PAYLOAD_V14.md","sha256":"435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0"}]}
~~~

The SHA-256 of the canonical form above is
f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059. The canonical
form of the body with "receipt_id" removed is 570 bytes, and its SHA-256 is
27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8 -- the
receipt_id of the example, per the computation of Section 4.5.

## Receipt Identity

The receipt_id of a receipt MUST be computed as follows:

~~~
receipt_id = SHA-256(JCS(body))

where body is the receipt object with the "receipt_id" member
removed.
~~~

Identity is a function of content, never a chosen string. Because
canonicalization absorbs member ordering, producers with different serialization
habits compute the same identity for the same content; that is the whole point.
Because the grammar is hex64 and the value is computed, a forged identifier of
the form "important-receipt-final-v2" is structurally impossible: receipt
identifiers are never human-chosen strings.

A verifier MUST recompute the identity from the received object and MUST report
a finding on any mismatch; a mismatch means the body was tampered with or was
produced by a non-canonical builder.

## Reference Implementation

The reference implementation is the Python package szl-receipts 14.0.0 {{SZLR}}:
its build_receipt constructor and verify_receipt verifier implement exactly the
rules of this section, and Appendix B reproduces the example above with it. The
verifier is deliberately non-throwing on bad data: every defect is returned as a
finding string, and an empty findings list means the receipt is well-formed and
its identity checks out. Raising is reserved for programmer error (arguments of
the wrong type), which is a bug in the caller, not in the receipt. Section 10
specifies verifier behavior implementation-independently.

# Canonicalization

Every digest computation in this document -- receipt identity, chain entry
digests, envelope payload digests -- is performed over the canonical form of the
relevant JSON value. The canonical form MUST be the JSON Canonicalization Scheme
(JCS) defined by {{RFC8785}}. JSON itself offers no inter-serializer byte
stability: member order, whitespace, number formatting, string escaping, and
Unicode normalization are all serializer choices. JCS removes every degree of
freedom so that equality becomes byte equality. Input to canonicalization MUST
conform to I-JSON {{RFC7493}}.

The points of {{RFC8785}} most consequential for implementers of this document:

* Object members are ordered by the UTF-16 code units of their names, not by
  Unicode code points. The orders coincide in the Basic Multilingual Plane
  but differ for astral characters: an astral character encodes as a
  surrogate pair whose first code unit sorts below U+FFFF, so ordering by
  code point is observably wrong.
* Numbers follow ECMAScript Number::toString: 1e20 serializes as
  100000000000000000000 while 1e21 serializes as 1e+21; 0.000001 stays in
  fixed notation while 0.0000001 becomes 1e-7; exponents carry an explicit
  sign and no leading zeros; negative zero canonicalizes to 0.
* Strings are escaped minimally (the two mandatory escapes, the seven single-
  character control escapes, and other C0 controls as \u00xx with lowercase
  hex) and are never normalized: canonically equivalent but code-point-
  distinct strings canonicalize to different bytes, by design.

A canonicalizer MUST reject values that are not interoperable across JSON
implementations: NaN and infinities have no JSON representation, and any integer
with magnitude greater than or equal to 2^53 MUST be rejected, because a parser
may route such a value through an IEEE-754 double and silently lose precision; a
canonicalizer must never emit bytes a reader cannot hold exactly. (The reference
implementation raises IJsonError in these cases.) The numeric content defined by
this document -- chain sequence numbers -- stays far below that bound, but the
bound MUST still be enforced: a digest is only meaningful when every
implementation agrees on the bytes.

Any {{RFC8785}}-conformant implementation produces identical bytes; the
reference implementation's canonicalizer is standard-library-only Python
{{SZLR}}. The worked example of Appendix B doubles as a conformance test: an
implementation that cannot reproduce its receipt_id from the given inputs is not
a GAR implementation.

# Signing and Envelopes

A receipt's identity proves its own integrity, but integrity is not
authenticity: anyone can construct a well-formed receipt. Authenticity is
provided by carrying the canonical form of the receipt as the payload of a DSSE
envelope {{DSSE}} signed with Ed25519 {{RFC8032}}; the honest alternative is to
publish the receipt unsigned under the naming convention of Section 8. A receipt
MUST NOT be presented in any state in between: either at least one signature is
present, or the artifact is named unsigned.

## Envelope

The signed artifact is a DSSE envelope {{DSSE}}: a JSON object with members
"payload" (base64 of the payload bytes), "payloadType" (non-empty string), and
"signatures" (array of objects with members "keyid" (string) and "sig" (base64
of the signature bytes)). Base64 uses the standard alphabet and strict decoding:
a verifier MUST reject non-canonical base64 at the structural stage, before any
cryptography is attempted. The payload is embedded verbatim, so the envelope is
self-contained: anyone can verify authenticity and read the content from one
file.

The payload of a GAR envelope MUST be the canonical form (Section 5) of the
complete receipt, including receipt_id. Signing the canonical form, rather than
whatever bytes a producer happened to serialize, means the signature verifies
even if the envelope travels through JSON tooling that reserializes whitespace
or reorders members: the bytes under the signature are semantic, not incidental.

The payloadType of a GAR envelope SHOULD be "application/gar+json" (Section 12).
The reference implementation's command-line signer defaults to
"application/json" and accepts an explicit payload-type override {{SZLR}}.
Whatever value is used, a producer MUST NOT reuse one payloadType for two
different signed meanings, so that the domain separation of Section 6.2 is
preserved.

## Pre-Authentication Encoding

The bytes being signed must carry their own type, so that a signature over "a
receipt" can never be replayed as a signature over "an authorization" that
happens to share bytes -- the classic type-confusion, or chosen-protocol,
attack. DSSE prevents it with the Pre-Authentication Encoding (PAE) {{DSSE}}.
Signatures MUST be computed over:

~~~
PAE = b"DSSEv1" SP len(payloadType) SP payloadType SP
      len(payload) SP payload

where SP is a single space (0x20) and the lengths are decimal
ASCII byte counts.
~~~

Every field is length-prefixed before concatenation, so no pair (payloadType,
payload) can encode to the same bytes as a different pair: the separator
positions are fixed by the lengths, and an attacker cannot smear bytes across
the boundary. Minimal example: PAE("a", "bc") is the byte string "DSSEv1 1 a 2
bc". For the example receipt of Section 4.3, the encoding begins "DSSEv1 20
application/gar+json 650 {"act" and runs to 685 bytes in total. Verifiers MUST
recompute the PAE from the envelope's embedded (payloadType, payload) pair after
decoding, never from values supplied alongside the envelope. The reference
implementation's test suite exercises a prefix-collision (type-confusion) attack
against this construction directly {{SZLR}}.

## Signature Algorithm and Keys

The signature algorithm for this version is Ed25519 {{RFC8032}}, chosen for its
small fixed-size keys and signatures (a signature is 64 bytes, 88 characters
base64), deterministic signing (no per-signature nonce to leak), and constant-
time verification in common backends. An envelope MAY carry multiple signatures;
verification is boolean, "authentic under this key or not", and succeeds if at
least one entry verifies (Section 10).

The keyid of a signature SHOULD default to the SHA-256, rendered as hex64, of
the raw 32-byte public key: keys are identified by content, not by filename,
because filenames move and bytes do not. Signers MAY override keyid to match an
external key registry. Key distribution and trust-root selection are out of
scope; Section 7.3 notes where witnessed key material can be anchored, and
Section 11 discusses custody.

## in-toto Statements

Deployments that already produce in-toto attestations {{INTOTO}} MAY carry a
receipt inside an in-toto Statement v1, whose "_type" member is the constant
"https://in-toto.io/Statement/v1". In this mapping the Statement's "subject"
list holds objects of the form {"name": label, "digest": {"sha256": hex64}}
pinning each subject to the digest of its bytes, and the receipt appears as the
Statement's "predicate" under a deployment-chosen "predicateType". The Statement
is then signed as the payload of a DSSE envelope exactly as in Section 6.1. The
mapping is optional; a bare GAR envelope carries no less integrity than a
Statement-wrapped one.

## Example Envelope

The canonical bytes of Section 4.4, signed under the example key of Appendix B
(a public, non-secret test vector), yield the following envelope, shown with its
payload line folded per {{RFC8792}}. Its signature entry has keyid
eda5305f0821f0e27dab616e03a6f11ee73bf5cbba7096bc398e46e946dee155. The envelope
verifies under the example public key printed in Appendix B.1 and is
reproducible byte-for-byte.

~~~
{
  "payload": "eyJhY3Rpb24iOiJidWlsZC1tYXN0ZXItcGF5bG9hZCIsImFjdG9yIjoiY2ktcnVubmVyLTciLCJjcmVhdGVkX2F0IjoiMjAyNi0wOC0zMVQxODowMDowMFoiLCJkZWNpc2lvbiI6eyJvdXRjb21lIjoiUEFTUyIsInJhdGlvbmFsZSI6ImRldGVybWluaXN0aWMgcmVidWlsZCB2ZXJpZmllZCBieXRlLWlkZW50aWNhbCJ9LCJldmlkZW5jZSI6W3sidXJpIjoiaHR0cHM6Ly9jaS5zemwuZXhhbXBsZS9ydW5zLzIwMjYtMDgtMzEtMDAxIn1dLCJwb2xpY3kiOnsiZGlnZXN0X3NoYTI1NiI6IjZiNDJlMjdmY2E5NDUyNjA1YmYxNzNjYjI4ZmQ3Y2M2NjEyYzk5NTFlNWQxODM0N2YwNWI5ZTc5YThmN2Y0YzYiLCJpZCI6InN6bC5idWlsZC52MTQiLCJ2ZXJzaW9uIjoiMTQuMC4wIn0sInJlY2VpcHRfaWQiOiIyN2JmYTZiMTJkODhhMTRiYTA3NWY5ZjI1MzUxODExNzJiMmFjNDBjYWI2YjJlYzMyNmI4ZDY3OTVjYzJiYmE4IiwicmVjZWlwdF90eXBlIjoiR292ZXJuZWRBY3Rpb24vdjEiLCJzY2hlbWFfdmVyc2lvbiI6IjEuMCIsInN1YmplY3RzIjpbeyJuYW1lIjoiZGlzdC9TWkxfTUFTVEVSX1BBWUxPQURfVjE0Lm1kIiwic2hhMjU2IjoiNDM1NjM1ZmY0YWUyMzU4MDVhNjFiMmE3OTI5OWI2OTVkZGQzYWQ2YjM0NjQxZGMwMmVjY2JmYzViMzQzNDhiMCJ9XX0=",
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
log in which each entry authenticates the entire history before it.

## Chain Entry Format

A chain entry is a JSON object with exactly the members "seq" (integer; 1 for
the genesis entry, thereafter strictly increasing by 1), "receipt" (a receipt
object per Section 4), "prev" (the entry_digest of the preceding entry, or null
for the genesis entry), and "entry_digest" (hex64). The binding digest is:

~~~
entry_digest = SHA-256(JCS({"seq": n,
                           "receipt": receipt,
                           "prev": prev}))

computed over the canonical form of exactly the three members
that define the entry's identity.
~~~

Because the embedded receipt is itself content-addressed by receipt_id, one
digest recomputation authenticates the receipt, its position, and its linkage;
the chain is only as mutable as SHA-256's collision resistance. An appender MUST
validate the receipt per Section 10 before it touches the chain: a chain
containing an invalid receipt is a chain that lies with confidence. The chain
structure is storage-agnostic -- one JSON file per entry, a JSONL stream, or
database rows; persistence is the deployment's choice.

The genesis entry of the example chain of Appendix B is shown below (digest
lines folded). Its entry_digest is
0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9.

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

The example's second entry has seq 2, prev equal to the genesis digest above,
and entry_digest
ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c; the full two-
entry chain appears in Appendix B.3.

## What the Chain Detects

A chain verifier checks a complete chain from genesis: re-deriving every
entry_digest and cross-checking every linkage. The following attack classes are
detectable from the chain alone, and each MUST be reported as a distinct finding
(the reference implementation assigns the stable codes shown, so tooling can
match attack classes without parsing prose):

malformed-entry
:   an entry is not an object with the four members, has a bad seq or non-
    string entry_digest, or cannot be canonicalized.

digest-mismatch
:   entry content does not hash to its declared entry_digest (field-level
    tamper inside an entry).

reorder
:   seq numbers are not strictly increasing along the log.

gap
:   seq jumps forward: entries are missing from the middle.

replay
:   the same seq reappears with an identical digest.

fork
:   the same seq reappears with two different digests.

broken-prev-link
:   an entry's prev is not the digest of the preceding entry (or the
    predecessor is malformed, leaving the link unverifiable).

genesis-prev-not-null
:   the first entry does not anchor at null.

The verification report is a boolean ok (true exactly when the findings list is
empty), the chain length, and the head (the final entry's entry_digest). The
reference implementation's test suite builds a five-entry chain and detects
truncation, reorder, replay, fork, and broken-prev-link attacks as separate
cases {{SZLR}}.

## External Anchors and the Truncation Limitation

This section states the honest limit of any self-verifying log, because a
specification that omits it would oversell the mechanism.

A hash chain verified without external information proves the integrity of the
presented history from genesis to the presented head. It cannot prove
completeness: an operator who silently drops the newest entries yields a shorter
chain that is perfectly valid, and no finding fires. Tail truncation is
undetectable from the chain alone. No hashing scheme removes this limitation; it
is a property of self-authenticating logs, not of this design.

The mitigation is an external anchor: information about the chain obtained from
outside the chain, which a deployment MUST treat as trusted-anchor / untrusted-
chain. This document defines two anchor inputs to the verifier:

expected_entries
:   an integer; the verifier reports "truncated" when the chain holds fewer
    entries than the anchor. (A chain longer than the anchor is not, by
    itself, a finding: the anchor pins a minimum length.)

expected_head
:   hex64; the verifier reports "head-mismatch" when the digest of the final
    entry differs from the anchor.

Anchors can be published out of band (a head digest in a release announcement,
an entry count in a change ticket) or witnessed by a transparency service. GAR
composes with the SCITT architecture {{I-D.ietf-scitt-architecture}}: a signed GAR envelope is a
signed statement in SCITT terms, and a transparency service can issue an
inclusion receipt for a chain head, converting it into a witnessed anchor.
Sigstore's public transparency log {{SIGSTORE}} (Rekor) provides the same
function for envelopes. Anchoring converts self-consistency into completeness;
deployments that cannot anchor MUST state in their own audit narrative that tail
truncation is outside the verified envelope.

# Honest Unsigned Naming

A file's name MUST tell the truth about its signature state. The convention:

* an envelope carrying one or more signatures is written as <base>.json (a
  signed artifact), for example build/report.json;
* an envelope carrying zero signatures is written as <base>.unsigned.json (an
  unsigned artifact), for example build/report.unsigned.json.

An empty signatures array is not a signature. The rule exists because consumers
pattern-match on extensions: an envelope with "signatures": [] written to
report.json presents as a signed-looking artifact that anyone could have
produced. Honest naming makes the trust state legible from the directory listing
alone.

Verification is bidirectional and MUST fail in both directions: a
*.unsigned.json file that contains one or more signatures is a tampered rename,
and any other .json artifact whose signatures array is empty is a tampered
rename. Both MUST be reported as verification failures. (The reference
implementation raises NamingError; its command-line verifier exits with status 2
{{SZLR}}.) Renaming a file MUST NOT change what the world believes about it.

A missing "signatures" member is not an unsigned artifact; it is a malformed
envelope, and MUST be reported as such. Absent is different from empty, and
conflating them is how quiet forgeries pass review.

The naming check is orthogonal to the cryptographic checks of Section 6 and is
always applied first (Section 10). Note that the on-disk serialization of an
envelope (member order, indentation) is for human review; the bytes that are
hashed and signed are always the canonical form (Section 5).

# Outcome Vocabulary

The decision.outcome member MUST take exactly one of the following five values.
The vocabulary is closed deliberately: a free-text status field drifts ("ok",
"green", "mostly fine") until nothing can be gated on it. Values serialize as
their plain text, so receipts stay plain JSON.

PASS
:   the governed action completed and met policy. This is the only passing
    outcome.

WARN
:   the action completed with a recorded concern. A recorded concern is not a
    pass.

FAIL
:   the governed action failed.

BLOCKED
:   the action was prevented from running by policy or by the environment.

UNKNOWN
:   no verdict was recorded; the absence of a verdict is itself the record.

Normative rules:

* A producer MUST reject an outcome outside this vocabulary at build time
  rather than emit an un-gateable receipt; a verifier MUST report an out-of-
  vocabulary decision.outcome as a finding.
* The predicate is_passing(outcome) is true if and only if outcome is PASS.
* A promotion gate MUST admit PASS and MUST refuse FAIL, BLOCKED, and UNKNOWN
  unconditionally. It MAY admit WARN only under an explicit, recorded
  override (in the reference implementation, promotion_gate(outcome,
  allow_warn=True); the override is itself an auditable decision).
* UNKNOWN MUST NOT be promoted to PASS, and MUST NOT be treated as passing by
  any gate, report, or dashboard. Absence of a verdict is not a verdict: "we
  don't know" is informationally worse than "it failed", because failure at
  least tells you where to look.

# Verifier Behavior

This section collects the normative verification procedure. The design
principle: a malformed or tampered receipt is an everyday operational event, not
an exception. A verifier MUST NOT crash on bad data; it reports findings, and an
empty findings list is the only success signal. A verifier SHOULD report every
defect it can determine; it MAY stop early only when required members are
absent, because type-checking absent members is meaningless.

Receipt verification, given a parsed JSON value:

1. Parse: callers parse untrusted text as JSON {{RFC8259}} themselves;
   verification operates on the parsed value, and a wrong argument type is
   programmer error, not a finding.
2. Shape: the value MUST be an object containing exactly the ten members of
   Section 4.1; report each missing and each unexpected member.
3. receipt_type MUST equal "GovernedAction/v1"; schema_version MUST be a non-
   empty string.
4. created_at MUST match the grammar of Section 4.2 and MUST denote a real
   calendar moment.
5. actor and action MUST be non-empty strings.
6. policy MUST be an object; id and version MUST be non-empty strings;
   digest_sha256 MUST be hex64.
7. decision MUST be an object; outcome MUST be inside the vocabulary of
   Section 9; rationale MUST be a string.
8. subjects MUST be an array; each element MUST be an object with a non-empty
   name and a hex64 sha256 and no other members.
9. evidence MUST be an array; each element MUST be an object with a non-empty
   uri; a sha256 member, when present, MUST be hex64.
10. Identity: the declared receipt_id MUST be hex64 and MUST equal the identity
   recomputed per Section 4.5; any mismatch MUST be reported -- the body
   was tampered with or produced by a non-canonical builder.

Envelope verification, given a parsed JSON value and optionally a trusted public
key, proceeds in stages:

1. Naming: the artifact's filename MUST satisfy Section 8 for the envelope's
   actual signature state. Failure here is a verification failure, not a
   warning.
2. Structure: payloadType MUST be a non-empty string; payload MUST decode
   under strict base64; signatures MUST be an array. An empty array passes
   this stage; honesty about it is enforced by the naming stage, and
   authenticity fails closed at the next stage.
3. Signature: when a public key is supplied, the verifier recomputes the PAE
   (Section 6.2) from the embedded (payloadType, payload) pair and returns
   authentic if and only if at least one signature entry verifies under
   that key. Malformed entries, wrong keys, and cryptographic failures MUST
   fail closed: they are skipped, never treated as errors that abort the
   scan, and never as successes. When no key is supplied, the signature
   stage is skipped and MUST be reported as not checked, never as passed.
4. Payload: when the payloadType indicates a GAR receipt, the decoded payload
   SHOULD additionally be verified as a receipt per the procedure above.

Chain verification consumes a complete chain from genesis, reports each defect
of Section 7.2 as a distinct, codeable finding, and then applies the external
anchors of Section 7.3 when supplied. A chain verifier MUST accept
expected_entries and expected_head inputs; a chain verified without anchors MUST
be reported with the truncation caveat stated. Promotion gates MUST consume
decision.outcome per Section 9.

The reference implementation's command-line verifier maps these outcomes onto
exit codes: 0 for success, 2 for verification failure (the artifact is reachable
but untrustworthy: tamper, dishonest naming, chain break), and 3 for usage or
I/O error. The distinction between 2 and 3 is the difference between an incident
and a retry; integrations SHOULD preserve it.

# Security Considerations

Field-level integrity. Any modification of any receipt member changes the
canonical bytes and therefore the recomputed receipt_id; detection requires no
trusted registry. The closed member set means an attacker cannot hide semantics
in extension members that a verifier would skip.

Type confusion. Signatures cover PAE(payloadType, payload), so a signature over
a receipt cannot be replayed as a signature over a different type that happens
to share bytes; the length-prefixing of Section 6.2 fixes the separator
positions. Producers MUST NOT reuse one payloadType for two signed meanings.

Renaming forgery. Honest naming (Section 8) makes an artifact's signature state
legible from its filename and is enforced on the verify side in both directions;
consumers MUST NOT treat a *.unsigned.json artifact as authenticated.

Log attacks. Reorder, gap, replay, fork, broken-prev-link, and genesis-anchor
violations are detectable from the chain alone (Section 7.2). Tail truncation is
not: as Section 7.3 states, without an external anchor a shortened chain is
perfectly valid. Any security claim of completeness therefore requires the
anchors of Section 7.3; self-consistency is not completeness. Forks (two valid
chains with a common prefix) are detectable only by comparing heads or by a
witness that refuses double-booking; the format makes such comparison cheap, it
does not perform it.

Time. created_at is asserted by the producer's clock and is not witnessed; a
signer can backdate a receipt. A receipt authenticates that the signer asserted
a time, not that the assertion was true. Deployments requiring trustworthy time
SHOULD anchor chain heads with a timestamping or transparency service, as
Section 7.3 describes.

Key custody. Ed25519 private keys are offline, operator-held artifacts. The
reference implementation writes private keys unencrypted with file mode 0600 and
refuses to overwrite an existing private key, because accidental key rotation is
a silent audit gap; deliberate rotation is an operator decision. This version
defines no revocation mechanism: verifiers pin keys directly, and receipts made
under a compromised key remain verifiable forgeries until the verifier's key set
is updated. Rotation and revocation are deployment matters, out of scope here.

Evidence custody. An evidence uri is a reference, not custody. When sha256 is
present the referenced bytes are pinned; when absent, the integrity and
availability of the evidence are the deployment's concern.

Digest algorithm. SHA-256 {{FIPS180-4}} is the load-bearing assumption
everywhere: receipt_id, subject digests, policy digests, entry digests, and
keyids. This version deliberately fixes one algorithm; there is no negotiation
to downgrade, and mixing digest algorithms within this version MUST NOT be done
(every hex64 position in this document is assigned to SHA-256). If SHA-256 is
ever weakened, the SHA-3 family {{FIPS202}} is the designated agility path, and
a future revision MUST introduce it by changing the (receipt_type,
schema_version) versioning hook rather than by overloading member contents: an
algorithm change produces a different format and should be named like one.

Canonicalization correctness is security-critical. A verifier that canonicalizes
differently from the producer will reject valid receipts (an availability
failure) or, worse, accept a receipt under an identity the producer never
computed. The UTF-16 member ordering and the ECMAScript number formatting of
Section 5 are where independent implementations diverge, and the I-JSON
exactness bound keeps digests meaningful across implementations.

Denial of service. Receipts are small by construction. Verifiers SHOULD bound
the size of accepted chain inputs, and artifact hashing MUST be streamed in
bounded chunks (the reference implementation reads 1 MiB per read) so that
multi-gigabyte subjects verify in constant memory.

# IANA Considerations

This document requests registration of the following media type in the "Media
Types" registry (https://www.iana.org/assignments/media-types/), following the
procedures of {{RFC6838}}:

~~~
Type name: application
Subtype name: gar+json
Required parameters: none
Optional parameters: none
Encoding considerations: binary
   (UTF-8 JSON text [RFC8259]; the canonical form used for
   digests and signatures is defined by [RFC8785])
Security considerations: see Section 11 of this document.
   Content may be signed per Section 6; unsigned content
   follows the naming convention of Section 8.  Receivers MUST
   verify per Section 10 before trusting content.
Interoperability considerations: all digest-bearing members
   depend on [RFC8785] canonicalization; member order and
   whitespace are insignificant (see Section 5 of this
   document).
Published specification: this document.
Applications that use this media type: governance, build,
   deployment, and audit tooling producing or consuming
   Governed Action Receipts; transparency logs anchoring
   receipt chains.
Fragment identifier considerations: none; JSON documents do
   not define fragment identifiers.
Additional information: none.
Person & email address to contact for further information:
   Stephen Lutar <stephen@szlholdings.com>
Intended usage: COMMON
Restrictions on usage: none.
Author: Stephen Lutar, SZL Holdings
Change controller: Stephen Lutar, SZL Holdings <stephen@szlholdings.com>
Provisional registration? (standards tree only): yes
~~~

As of this writing, the registration has NOT been made: "application/gar+json"
is provisional and unregistered. Until the type appears in the IANA registry,
implementations MUST treat it as unregistered and MUST be prepared for the
registered definition to evolve. The DSSE payloadType value
"application/gar+json" (Section 6.1) is usable immediately: payloadType is an
envelope-scoped type hint whose utility does not depend on registry completion.

No registry is requested for outcome values: the vocabulary of Section 9 is
closed by design and can be extended only by a revision of this document, so
that no deployment can unilaterally add an outcome its gates cannot interpret.

# Acknowledgements
{:numbered="false"}

The format specified here is implemented and exercised daily by the szl-receipts
package within the SZL Holdings estate; its test suite, which drives truncation,
reorder, replay, fork, and broken-link attacks against chains, payload bit-flip,
wrong-key, and PAE prefix-collision attacks against envelopes, and dishonest
renames against the naming convention, served as the executable adversarial
review for this document. The Secure Systems Lab's DSSE specification and in-
toto framework, the IETF SCITT working group's architecture draft, and the
Sigstore project provided the substrate this format composes with. Raza Sharif's
individual Internet-Draft {{I-D.sharif-agent-audit-trail}} showed that this problem space is under active
exploration at the IETF and that individual submission is the correct first
step.

--- back

# Appendix A.  Reference Implementation Map
{:numbered="false"}

For reviewers cross-checking this document against code: the reference
implementation is szl-receipts 14.0.0 {{SZLR}}, importable as the Python package
szl_receipts.

Section 4
:   receipt.py: build_receipt, verify_receipt, compute_receipt_id

Section 5
:   jcs.py: jcs_canon_bytes, serialize, number_to_js_str

Section 6
:   dsse.py: pae, sign_bytes, verify_envelope, keygen, statement

Section 7
:   chain.py: append, entry_digest_for, verify_chain

Section 8
:   naming.py: write_envelope, verify_honest_naming, NamingError

Section 9
:   outcome.py: Outcome, is_passing, promotion_gate

Section 10
:   the verifiers above; cli.py: canon, keygen, sign, verify, chain-verify and
    the exit-code contract

byte digests
:   digests.py: sha256_file (1 MiB chunks), sha256_bytes, sha256_hex

# Appendix B.  Worked Example and Reproduction
{:numbered="false"}

Reproduction requires Python 3.11 or newer, the szl-receipts package at version
14.0.0, and the "cryptography" package (version 42 or newer). The following
commands create the two input files; the digests quoted throughout this document
are the SHA-256 of their bytes:

~~~
pip install -e ./szl-receipts        # szl-receipts 14.0.0
mkdir -p policies dist
printf 'SZL Build Policy v14\nAll governed builds must be reproducible and receipted.\n' > policies/szl.build.v14.md
printf 'SZL MASTER PAYLOAD V14\n' > dist/SZL_MASTER_PAYLOAD_V14.md
~~~

The digests are 6b42e27fca9452605bf173cb28fd7cc6612c9951e5d18347f05b9e79a8f7f4c6
(policy document) and
435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0 (payload
artifact). The example Ed25519 key is derived from the fixed seed
SHA-256("draft-lutar-governed-action- receipt example key") via
Ed25519PrivateKey.from_private_bytes; it is a public, non-secret test vector and
MUST NOT be used operationally. The example public key is:

~~~
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAr42BDg9MLmFBYa4Dd1A2NZY2sfainY46BBByRtBYkys=
-----END PUBLIC KEY-----
~~~

## Reproduction Script

The following script (also distributed alongside this document as reproduce-
appendix-b.py) regenerates every value in Sections 4.3, 4.4, 6.5, and 7.1.
Output is deterministic: created_at is fixed and the key is fixed. (Long lines
are folded per {{RFC8792}} in the plain-text rendering; the distributed script
file is authoritative.)

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

## Expected Results

~~~
receipt_id:            27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8
canonical length:      650 bytes
sha256(canonical):     f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059
keyid:                 eda5305f0821f0e27dab616e03a6f11ee73bf5cbba7096bc398e46e946dee155
signature (base64):    gm/MRQTRvxzNM+u56GMKsL4FTWCo9/N5HPW1/+8zc4L2BIFScMxy9khnNHdMQP9CTfEw0cvCsxfT/QHrFUd6Bg==
genesis entry_digest:  0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9
entry 2 entry_digest:  ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c
chain head:            ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c
~~~

An implementation that reproduces these digests from these inputs implements
Sections 4, 5, 6, and 7 correctly. The verification chain also holds:
verify_envelope applied to the envelope of Section 6.5 under the public key of
B.1 returns true, and verify_chain applied to the two-entry chain with
expected_entries 2 and expected_head equal to the chain head above reports ok
with zero findings. The complete two-entry chain as produced by the script is:

~~~
[
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
  },
  {
    "entry_digest": "ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c",
    "prev": "0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9",
    "receipt": {
      "action": "promote-master-payload",
      "actor": "ci-runner-7",
      "created_at": "2026-08-31T18:05:00Z",
      "decision": {
        "outcome": "PASS",
        "rationale": "promotion gate passed on PASS receipt"
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
      "receipt_id": "bc4d37d1b456242270d31a33c81184b65a9c30b901a3251194bfe82143c90deb",
      "receipt_type": "GovernedAction/v1",
      "schema_version": "1.0",
      "subjects": [
        {
          "name": "dist/SZL_MASTER_PAYLOAD_V14.md",
          "sha256": "435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0"
        }
      ]
    },
    "seq": 2
  }
]
~~~


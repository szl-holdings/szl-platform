#!/usr/bin/env python3
"""Independent validator for draft-lutar-governed-action-receipt-00.txt.

Parses the RENDERED document (not the build script's data structures) and
checks:

  1. RFC format: every line <= 72 columns, form feed between pages,
     page headers/footers correct, page numbers sequential, ASCII only.
  2. Table of Contents: every entry's page number equals the page on
     which the heading actually appears.
  3. Worked example: the receipt JSON embedded in Section 4.3 parses and
     verifies with szl-receipts; its recomputed receipt_id matches; the
     folded canonical bytes in 4.4 re-join to bytes whose sha256 matches
     the digest quoted in the text AND equal JCS(receipt); the envelope
     in 6.5 verifies under the public key printed in Appendix B.1; the
     genesis entry in 7.1 re-hashes correctly; the full chain in
     Appendix B.3 passes verify_chain with the quoted head.
  4. Cross-format consistency: the .md source contains the same example
     values.

Run from docs/standards:  python validate_draft.py
Exits 0 and prints PASS lines, or exits 1 on the first failure list.
"""
import base64
import json
import re
import sys
from pathlib import Path

from szl_receipts import (
    compute_receipt_id, jcs_canon_bytes, sha256_hex, verify_chain,
    verify_envelope, verify_receipt,
)
from cryptography.hazmat.primitives.serialization import load_pem_public_key

HERE = Path("/home/user/workspace/szl-platform/docs/standards")
TXT = (HERE / "draft-lutar-governed-action-receipt-00.txt").read_text()
MD = (HERE / "draft-lutar-governed-action-receipt-00.md").read_text()

fails = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- format ---

lines = TXT.split("\n")
check("txt: every line <= 72 columns", all(len(l) <= 72 for l in lines),
      f"{sum(1 for l in lines if len(l) > 72)} long lines")
check("txt: ASCII only", all(ord(c) < 128 for c in TXT))

pages = TXT.split("\n\f\n")
check("txt: form feed between every page", len(pages) == TXT.count("\f") + 1)
check("txt: sensible page count", 25 <= len(pages) <= 40, f"got {len(pages)}")

hdr_re = re.compile(r"^Internet-Draft\s+Governed Action Receipt\s+August 2026$")
ftr_re = re.compile(r"^Lutar +Expires 4 March 2027 +\[Page (\d+)\]$")
ok_hdr = all(hdr_re.match(p.split("\n")[0]) for p in pages[1:])
ok_ftr = True
for i, p in enumerate(pages):
    plines = p.split("\n")
    ftr_line = plines[-1] if plines[-1] else plines[-2]
    m = ftr_re.match(ftr_line)
    if not m or int(m.group(1)) != i + 1 or len(ftr_line) != 72:
        ok_ftr = False
        break
check("txt: header line on pages 2..N", ok_hdr)
check("txt: footer with correct page number on every page", ok_ftr)

p1 = pages[0].split("\n")
check("txt: page 1 stream line", p1[3].startswith("Internet Engineering Task Force")
      and p1[3].rstrip().endswith("S. Lutar"))
check("txt: page 1 intended status", "Intended status: Informational" in p1[5])
check("txt: page 1 expiry", p1[6] == "Expires: 4 March 2027")
check("txt: page 1 title", "The Governed Action Receipt (GAR) Format" in TXT.split("\n\f")[0])
check("txt: docname centered on page 1",
      any(l.strip() == "draft-lutar-governed-action-receipt-00" for l in p1[:14]))

# every page is exactly 58 lines (page height) except possibly the last
def plen(p):
    return len(p.split("\n"))
check("txt: pages 1..N-1 are 58 lines", all(plen(p) == 58 for p in pages[:-1]),
      str([plen(p) for p in pages[:-1] if plen(p) != 58]))

# ------------------------------------------------------------------- ToC ---

toc_entries = []  # (label, page)
for pnum, page in enumerate(pages[:3], start=1):
    for line in page.split("\n"):
        m = re.match(r"^\s{3,6}(\S.*?)\s{2}\.(?: \.)*\s*(\d+)$", line)
        if m:
            toc_entries.append((m.group(1), int(m.group(2))))
check("toc: entries found", len(toc_entries) >= 30, f"got {len(toc_entries)}")

bad = []
for label, pnum in toc_entries:
    if pnum < 1 or pnum > len(pages):
        bad.append((label, pnum, "out of range"))
        continue
    body = pages[pnum - 1]
    if not any(l.rstrip() == label for l in body.split("\n")):
        bad.append((label, pnum, "heading not on that page"))
check("toc: every entry page number matches the heading's actual page", not bad,
      repr(bad[:6]))

expected_labels = [
    "Abstract", "Status of This Memo", "Copyright Notice", "Table of Contents",
    "1.  Introduction", "2.  Terminology", "3.  Conventions and Definitions",
    "4.  Receipt Format", "4.1.  Receipt Members", "4.2.  Timestamp Grammar",
    "4.3.  Example Receipt", "4.4.  Canonical Form of the Example",
    "4.5.  Receipt Identity", "4.6.  Reference Implementation",
    "5.  Canonicalization", "6.  Signing and Envelopes", "6.1.  Envelope",
    "6.2.  Pre-Authentication Encoding", "6.3.  Signature Algorithm and Keys",
    "6.4.  in-toto Statements", "6.5.  Example Envelope",
    "7.  Hash-Chained Logs and External Anchors", "7.1.  Chain Entry Format",
    "7.2.  What the Chain Detects",
    "7.3.  External Anchors and the Truncation Limitation",
    "8.  Honest Unsigned Naming", "9.  Outcome Vocabulary",
    "10.  Verifier Behavior", "11.  Security Considerations",
    "12.  IANA Considerations", "Acknowledgements", "References",
    "Appendix A.  Reference Implementation Map",
    "Appendix B.  Worked Example and Reproduction",
    "Reproduction Script", "Expected Results", "Author's Address",
]
check("toc: all expected headings listed",
      [l for l, _ in toc_entries] == expected_labels,
      repr([l for l, _ in toc_entries if l not in expected_labels]))

# ------------------------------------------------------- artwork helpers ---

FTR_RE = re.compile(r"^\S+ +Expires \d+ \w+ \d{4} +\[Page \d+\]$")
HDR_RE = re.compile(r"^Internet-Draft\s+Governed Action Receipt\s+August 2026$")


def unfold(art_lines):
    """Strip the 3-space indent; rejoin RFC 8792 single-backslash folds.
    While a fold is open (previous segment ended with '\\'), skip page
    furniture and blank padding: a page break may land between the two
    segments of a folded line, and a fold continuation never legitimately
    contains a blank line."""
    out = []
    buf = None
    for raw in art_lines:
        if buf is not None and (not raw or FTR_RE.match(raw)
                                or HDR_RE.match(raw) or raw == "\f"):
            continue
        s = raw[3:] if raw.startswith("   ") else raw
        if buf is not None:
            buf += s
        else:
            buf = s
        if buf.endswith("\\"):
            buf = buf[:-1]
            continue
        out.append(buf)
        buf = None
    return out


def artwork_after(anchor, opener, closer, start=0):
    """Find the line whose full text is `anchor` (exact-line match, so a
    ToC entry with dot leaders never matches), then the first line that is
    exactly `opener`, collect until the line that is exactly `closer`;
    return (unfolded_lines, index_after_closer)."""
    m = re.search(rf"(?m)^{re.escape(anchor)}$", TXT[start:])
    if m:
        idx = start + m.end()
    else:
        # prose anchors may be wrapped mid-paragraph: substring fallback
        idx = TXT.index(anchor, start) + len(anchor)
    sub = TXT[idx:]
    lines = sub.split("\n")
    i = next(i for i, l in enumerate(lines) if l == opener)
    j = next(j for j in range(i + 1, len(lines)) if lines[j] == closer)
    block = lines[i:j + 1]
    # figures taller than one page legitimately span a page break in RFC
    # style: strip page furniture (footer, form feed, header) from the
    # collected range; blank padding is harmless whitespace to JSON
    ftr = re.compile(r"^\S+ +Expires \d+ \w+ \d{4} +\[Page \d+\]$")
    hdr = re.compile(r"^Internet-Draft\s+Governed Action Receipt\s+August 2026$")
    block = [l for l in block
             if not (ftr.match(l) or hdr.match(l) or l == "\f")]
    return unfold(block), idx + sum(len(l) + 1 for l in lines[:j + 1])


# ------------------------------------------------- worked example checks ---

rec_lines, _ = artwork_after("4.3.  Example Receipt", "   {", "   }")
receipt = json.loads("\n".join(rec_lines))
check("example: receipt JSON parses", isinstance(receipt, dict))
check("example: receipt has exactly 10 members", len(receipt) == 10)
check("example: verify_receipt clean", verify_receipt(receipt) == [],
      repr(verify_receipt(receipt)))
check("example: receipt_id recomputes",
      compute_receipt_id(receipt) == receipt["receipt_id"])
check("example: receipt_id is the quoted value",
      receipt["receipt_id"] ==
      "27bfa6b12d88a14ba075f9f2535181172b2ac40cab6b2ec326b8d6795cc2bba8")
check("example: receipt_type string exact",
      receipt["receipt_type"] == "GovernedAction/v1")

# the canonical artwork is a single logical line folded many times:
# collect from the {"act line until the first blank line
idx = TXT.index('   {"act')
seg = []
for l in TXT[idx:].split("\n"):
    if l == "":
        break
    seg.append(l)
canon_text = unfold(seg)[0]
check("example: canonical artwork is one logical line", len(unfold(seg)) == 1)
canon_bytes = canon_text.encode()
check("example: canonical form is 650 bytes", len(canon_bytes) == 650,
      str(len(canon_bytes)))
check("example: canonical artwork == JCS(receipt)",
      canon_bytes == jcs_canon_bytes(receipt))
check("example: sha256(canonical) matches value quoted in text",
      sha256_hex(canon_bytes) ==
      "f300e474b5bf4f7cd909155b292d47143aea5a3fbd3b27d6aabaedc7a53e5059"
      and sha256_hex(canon_bytes) in TXT)

idless = {k: v for k, v in receipt.items() if k != "receipt_id"}
check("example: sha256(JCS(receipt minus receipt_id)) == receipt_id",
      sha256_hex(jcs_canon_bytes(idless)) == receipt["receipt_id"])
check("example: idless canonical length 570 quoted",
      len(jcs_canon_bytes(idless)) == 570
      and re.search(r"570\s+bytes", TXT) is not None)

# envelope (6.5)
env_lines, _ = artwork_after("6.5.  Example Envelope", "   {", "   }")
envelope = json.loads("\n".join(env_lines))
check("envelope: parses with payload/payloadType/signatures",
      set(envelope) == {"payload", "payloadType", "signatures"})
check("envelope: payloadType is application/gar+json",
      envelope["payloadType"] == "application/gar+json")
payload = base64.b64decode(envelope["payload"], validate=True)
check("envelope: payload is strict base64 of the canonical receipt",
      payload == canon_bytes)

# public key from Appendix B.1 artwork
pem_lines, _ = artwork_after("example public key is:",
                             "   -----BEGIN PUBLIC KEY-----",
                             "   -----END PUBLIC KEY-----")
pub = load_pem_public_key(("\n".join(pem_lines) + "\n").encode())
check("envelope: verifies under the Appendix B.1 public key",
      verify_envelope(envelope, pub))
check("envelope: keyid matches",
      envelope["signatures"][0]["keyid"] ==
      "eda5305f0821f0e27dab616e03a6f11ee73bf5cbba7096bc398e46e946dee155")

# PAE prefix quoted in 6.2 (prose may wrap mid-quote: flatten whitespace)
flat_ws = " ".join(TXT.split())
check("pae: quoted prefix matches recomputation",
      'DSSEv1 20 application/gar+json 650 {"act' in flat_ws)
from szl_receipts import pae as pae_fn
pae_bytes = pae_fn(b"application/gar+json", canon_bytes)
check("pae: total length 685 quoted", len(pae_bytes) == 685 and "685" in TXT)
check("pae: demo vector quoted", 'PAE("a", "bc")' in flat_ws and
      '"DSSEv1 1 a 2 bc"' in flat_ws and
      pae_fn(b"a", b"bc") == b"DSSEv1 1 a 2 bc")

# genesis entry (7.1)
gen_lines, _ = artwork_after("The genesis entry of the example chain",
                             "   {", "   }")
genesis = json.loads("\n".join(gen_lines))
check("chain: genesis entry shape", set(genesis) == {"seq", "receipt", "prev", "entry_digest"})
check("chain: genesis seq 1 / prev null",
      genesis["seq"] == 1 and genesis["prev"] is None)
check("chain: genesis embeds the example receipt", genesis["receipt"] == receipt)
check("chain: genesis entry_digest recomputes",
      sha256_hex(jcs_canon_bytes({"seq": 1, "receipt": receipt, "prev": None}))
      == genesis["entry_digest"] ==
      "0edf7eea8ebbfa8c3490d8655fce1718fe86ad9d7564c26986e3c309e6a924a9")

# full chain (Appendix B.3)
chain_lines, _ = artwork_after("The complete two-entry chain as",
                               "   [", "   ]")
chain = json.loads("\n".join(chain_lines))
check("chain: two entries", len(chain) == 2)
check("chain: entry 2 links to genesis digest",
      chain[1]["prev"] == genesis["entry_digest"])
rep = verify_chain(chain, expected_entries=2,
                   expected_head=chain[-1]["entry_digest"])
check("chain: verify_chain ok with anchors", rep.ok and not rep.findings,
      repr(rep.findings))
check("chain: head is the quoted value",
      rep.head == "ab9aefea5689350d2c357d27ed199a26ba82467e49a0a44c31616de3e8015c0c")
check("chain: head digest quoted in text", rep.head in TXT)

# policy/subject digests quoted
check("digests: policy digest quoted",
      "6b42e27fca9452605bf173cb28fd7cc6612c9951e5d18347f05b9e79a8f7f4c6" in TXT)
check("digests: subject digest quoted",
      "435635ff4ae235805a61b2a79299b695ddd3ad6b34641dc02eccbfc5b34348b0" in TXT)

# ------------------------------------------------------------- content ---

must_have = [
    "An empty signatures array is not a signature",
    "UNKNOWN MUST NOT be promoted to PASS",
    "Tail truncation is undetectable from the chain alone",
    '"truncated"', '"head-mismatch"',
    "application/gar+json",
    "provisional and unregistered",
    "BCP 14 [RFC2119] [RFC8174]",
    "malformed-entry", "digest-mismatch", "reorder", "gap", "replay",
    "fork", "broken-prev-link", "genesis-prev-not-null",
    "Individual submission; not adopted by any IETF working group",
    "https://in-toto.io/", "https://www.sigstore.dev/",
    "*.unsigned.json",
    "allow_warn=True",
    "Stephen Lutar", "SZL Holdings", "stephen@szlholdings.com",
    "[FIPS202]", "[RFC8785]", "[RFC8032]", "[DSSE]", "[AAT]", "[SCITT]",
    "[INTOTO]", "[SIGSTORE]", "[SZLR]",
]
flat = " ".join(TXT.split())
missing = [s for s in must_have if s not in flat]
check("content: all required strings present", not missing, repr(missing))

# reference URLs/ids may be broken at hyphens by 72-col wrapping; a wrap
# never removes a hyphen, so collapsing "- " back to "-" restores them
flat_nh = flat.replace("- ", "-")
for s in ["draft-sharif-agent-audit-trail-01",
          "https://github.com/secure-systems-lab/dsse",
          "https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/"]:
    check(f"content: {s[:52]}... intact across wraps", s in flat_nh)

# md cross-consistency
md_must = [
    "docname: draft-lutar-governed-action-receipt-00-latest",
    "category: info", "ipr: trust200902", "date: 2026-08-31",
    receipt["receipt_id"], rep.head, genesis["entry_digest"],
    "GovernedAction/v1", "application/gar+json",
    "{{I-D.sharif-agent-audit-trail}}", "{{I-D.ietf-scitt-architecture}}",
    "{{DSSE}}", "{{RFC8785}}", "{{RFC8032}}", "{{FIPS202}}",
    "{{INTOTO}}", "{{SIGSTORE}}", "{{SZLR}}",
]
md_missing = [s for s in md_must if s not in MD]
check("md: front matter and example values consistent", not md_missing,
      repr(md_missing))

# md citation keys all defined
cites = set(re.findall(r"\{\{([A-Za-z0-9.-]+)\}\}", MD))
fm = MD.split("---")[1]
defined = set(re.findall(r"^  ([A-Za-z0-9.-]+):", fm, re.M))
undef = [c for c in cites if not (c.startswith("RFC") or c in defined)]
check("md: every citation key resolves", not undef, repr(undef))

# md artwork fences balanced
check("md: ~~~ fences balanced", MD.count("~~~") % 2 == 0)

# appendix reproducer embedded in txt matches the distributed script:
# extract the figure, strip furniture, unfold, and compare non-blank lines
script = (HERE / "reproduce-appendix-b.py").read_text().rstrip("\n")
script_lines = [l for l in script.split("\n") if l.strip()]
m = re.search(r"(?m)^Reproduction Script$", TXT)
sub = TXT[m.end():].split("\n")
s0 = next(i for i, l in enumerate(sub)
          if l.startswith('   """Reproduce the worked example'))
s1 = next(i for i in range(s0 + 1, len(sub))
          if 'print("chain head:", report.head)' in sub[i])
fig = [l for l in sub[s0:s1 + 1]
       if not (FTR_RE.match(l) or HDR_RE.match(l) or l == "\f")]
extracted = [l for l in unfold(fig) if l.strip()]
check("appendix: embedded reproducer == reproduce-appendix-b.py "
      "(non-blank lines)",
      extracted == script_lines,
      f"{len(extracted)} vs {len(script_lines)} lines")

print()
if fails:
    print(f"{len(fails)} FAILURES:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL VALIDATION CHECKS PASSED")

# Submission Notes — draft-lutar-governed-action-receipt-00

Author: Stephen Lutar, SZL Holdings <stephen@szlholdings.com>
Date: 2026-08-31
Files: `draft-lutar-governed-action-receipt-00.md` (kramdown-rfc2629 source),
`draft-lutar-governed-action-receipt-00.txt` (rendered plain text, 33 pages,
72 columns, form feeds, ToC — passes every local format check; see
`validate_draft.py`).

## 1. Pre-flight (run before touching the datatracker)

1. Regenerate both files from the single source of truth:
   `python build_draft.py` (recomputes every worked-example byte with the
   installed `szl-receipts` 14.0.0 library — nothing in the draft is
   transcribed by hand).
2. Re-run `python validate_draft.py` — must end with
   `ALL VALIDATION CHECKS PASSED` (55 checks: pagination, ToC accuracy,
   and re-derivation of every embedded digest from the rendered `.txt`).
3. Run the official nits checker on the rendered text at
   <https://author-tools.ietf.org/idnits> and fix anything it flags. The
   I-D checklist at <https://www.ietf.org/id-info/checklist.html> is the
   authoritative pre-submission list (boilerplate, expiry date, abstract
   length, references split normative/informative — all already handled
   in the build).
4. Optional but recommended: install `kramdown-rfc2629` and `xml2rfc`, then
   produce the canonical XML from the `.md` source
   (`kramdown-rfc draft-lutar-governed-action-receipt-00.md >
   draft-lutar-governed-action-receipt-00.xml`) and diff its `xml2rfc`
   text output against the `.txt` shipped here. The `.md` front matter
   already carries `submissiontype: IETF`, `category: info`,
   `ipr: trust200902`, date `2026-08-31`, and the normative/informative
   reference split.

## 2. Posting the draft (individual submission path)

1. Create / sign in to a datatracker account at
   <https://datatracker.ietf.org/accounts/login/> (the account e-mail
   should match the draft's author address, stephen@szlholdings.com).
2. Go to **Submit an Internet-Draft**:
   <https://datatracker.ietf.org/submit/>. Individual submissions are
   accepted directly into the I-D repository; no working-group or AD
   sponsorship is needed to *post* a draft.
3. Upload the `.xml` if you produced it, otherwise the rendered `.txt`
   (the datatracker accepts plaintext uploads; the filename must be
   exactly `draft-lutar-governed-action-receipt-00` — first revisions of
   a new draft name must be `-00`).
4. Fill the metadata form (title, abstract, author list — must match the
   draft exactly) and confirm the IPR statements in §3.
5. After posting, an announcement goes to the `i-d-announce@ietf.org`
   list within minutes and the draft appears at
   `https://datatracker.ietf.org/doc/draft-lutar-governed-action-receipt/`
   with state "I-D Exists". The draft expires 185 days after posting
   (this revision: 4 March 2027); post `-01` before then to keep it
   visible, or it disappears from the active index (it is never deleted,
   just expired).

## 3. IPR statements the author must agree to at submission time

The submission form requires the submitter to certify, on behalf of all
listed authors:

1. **BCP 78 / Trust Legal Provisions grant.** The submission is made
   under the grant of rights in BCP 78 and the IETF Trust Legal
   Provisions (<https://trustee.ietf.org/license-info>): a perpetual,
   non-exclusive, royalty-free license to the IETF Trust to publish,
   reproduce, and create derivative works from the contribution. The
   draft's Copyright Notice already contains this text; the front matter
   sets `ipr: trust200902`, the correct designation for a document with
   no pre-existing-IPR carve-outs.
2. **BCP 79 IPR disclosure.** To the best of the submitter's knowledge,
   either there is no IPR (patent applications etc.) covering the
   technology, or any known IPR has been disclosed at
   <https://datatracker.ietf.org/ipr/>. For this document the expected
   answer is "no known IPR": the format is composed of public,
   royalty-free specifications (RFC 8785, RFC 8032, DSSE, FIPS 180-4) and
   is implemented by our own reference code.
3. **Note Well acknowledgement.** That the submission is subject to the
   IETF's "Note Well" terms (<https://www.ietf.org/about/note-well/>),
   including the obligation to disclose IPR you become aware of later.
4. **Code components.** Any code in the draft (Appendix B's reproduction
   script) is licensed under the Revised BSD License per section 4.e of
   the Trust Legal Provisions — already stated in the Copyright Notice.
5. **Authority to submit.** That all listed authors (here: one) have
   approved submission and the submitter is authorized to act for them.

## 4. Why individual submission comes first

Posting as an individual submission is the standard on-ramp, not a
second-class path:

- **The repository has no adoption gate for posting.** Any conformant
  draft can be posted by its author; working-group adoption is a separate,
  later step (a WG "Call for Adoption"), and most WGs will not consider
  adopting work they cannot read first. You cannot be adopted before you
  exist.
- **This is the observed pattern in this exact problem space.**
  `draft-sharif-agent-audit-trail` ("Agent Audit Trail: A Standard
  Logging Format for Autonomous AI Systems", Raza Sharif, CyberSecAI Ltd,
  revision -01 of 2026-08-19) is an **active individual Internet-Draft,
  IESG state "I-D Exists", not adopted by any working group and carrying
  no formal standing in the IETF standards process** — per its datatracker
  page <https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/>.
  Our draft cites it informatively as `[AAT]` with exactly that standing
  noted in the reference entry. Nobody owns the agent-action receipt
  format yet; two honest individual drafts in the repository is how a
  future working item gets chartered.
- **Posting starts clocks that matter more than status:** a public,
  dated, immutable artifact with a datatracker history; inclusion in
  `i-d-announce` (read by the SEC area and by the SCITT/attestation
  community our draft composes with); and a citable name for the
  compliance-mapping and standards-capture work.
- **Adoption paths after posting:** bring it to a dispatch conversation
  (SEC area) or to the Independent Submission Editor for the Independent
  Stream once external implementations exist. Until then the draft says
  what it is: Informational, individual, and exactly true of running code.

## 5. Housekeeping

- Rebuild with `python build_draft.py` before any `-01`; never hand-edit
  the `.txt` (it is generated) or the worked-example digests (they are
  computed).
- `validate_draft.py` is the regression gate: it re-derives the embedded
  receipt, envelope, and chain from the rendered document itself.
- `reproduce-appendix-b.py` must stay byte-identical to the listing in
  Appendix B.2 (the validator enforces this).

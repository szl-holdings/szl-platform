"""szl-claims-api — the live Covenant Proof Standard service.

For a company whose thesis is "prove what your model decided", stale
self-reported numbers are the first diligence attack. This package serves
every public numeric claim SZL Holdings makes, each with
{claimed, actual, last_run, drift, receipt_id} — the organization's own
marketing held to its own proof standard.

Doctrine carried over from szl-receipts / szl-estate:

1. This service REPORTS recomputations done by szl-estate; it does not
   invent them. No number is ever computed server-side from first
   principles — numbers are quoted verbatim from the claims file.
2. UNKNOWN is a first-class honest state and is never passing. A missing
   claims file degrades the store to UNAVAILABLE and every claim to
   UNKNOWN, with a note — never to fabricated numbers.
3. Every served claim carries a GovernedAction/v1 receipt whose subject is
   the sha256 of the claim's canonical bytes. A claim whose observed value
   changed gets a NEW receipt; receipts are never reused across content.
"""

from __future__ import annotations

from szl_claims_api.receipts import CLAIM_VERIFY_ACTION, ReceiptMinter
from szl_claims_api.seed import load_seed_registry, seed_claims
from szl_claims_api.store import (
    BLOCKERS_HEADER,
    STORE_STATES,
    VERDICTS,
    ClaimStore,
    StoreStats,
    default_claims_file_path,
)

__version__ = "0.1.0"

__all__ = [
    "BLOCKERS_HEADER",
    "CLAIM_VERIFY_ACTION",
    "STORE_STATES",
    "VERDICTS",
    "ClaimStore",
    "ReceiptMinter",
    "StoreStats",
    "__version__",
    "default_claims_file_path",
    "load_seed_registry",
    "seed_claims",
]

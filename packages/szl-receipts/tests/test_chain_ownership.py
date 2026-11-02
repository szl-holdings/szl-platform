"""Receipt callers cannot rewrite entries already admitted to a chain."""

import copy

import pytest
from szl_receipts.chain import append, entry_digest_for, verify_chain
from szl_receipts.jcs import jcs_canon_bytes
from szl_receipts.receipt import compute_receipt_id


@pytest.mark.parametrize("field", ["policy", "decision", "subjects", "evidence"])
def test_input_mutation_preserves_retained_bytes_and_next_link(make_receipt, field):
    receipt = make_receipt(
        subjects=[{"name": "request", "sha256": "b" * 64}],
        evidence=[{"uri": "urn:synthetic:evidence", "sha256": "c" * 64}],
    )
    chain = []
    append(chain, receipt)
    retained_bytes = jcs_canon_bytes(chain)
    anchor = chain[-1]["entry_digest"]

    if field == "policy":
        receipt["policy"]["version"] = "caller-changed"
    elif field == "decision":
        receipt["decision"]["rationale"] = "caller-changed"
    elif field == "subjects":
        receipt["subjects"][0]["name"] = "caller-changed"
    else:
        receipt["evidence"].append({"uri": "urn:caller:added"})

    assert jcs_canon_bytes(chain) == retained_bytes
    assert verify_chain(chain, expected_entries=1, expected_head=anchor).ok
    append(chain, make_receipt())
    assert chain[-1]["prev"] == anchor
    assert verify_chain(chain, expected_entries=2).ok


def test_reused_receipt_gets_a_distinct_snapshot_per_append(make_receipt):
    receipt = make_receipt()
    receipt["policy"]["context"] = {"scopes": ["synthetic:read"]}
    receipt["receipt_id"] = compute_receipt_id(receipt)
    chain = []
    append(chain, receipt)
    first = copy.deepcopy(chain[0])

    receipt["policy"]["context"]["scopes"].append("synthetic:write")
    receipt["receipt_id"] = compute_receipt_id(receipt)
    append(chain, receipt)

    assert chain[0] == first
    assert chain[1]["receipt"] == receipt
    assert chain[0]["receipt"]["receipt_id"] != chain[1]["receipt"]["receipt_id"]
    assert chain[1]["prev"] == first["entry_digest"]
    assert verify_chain(chain).ok


def test_append_keeps_existing_entry_bytes_and_return_contract(make_receipt):
    receipt = make_receipt(created_at="2026-11-01T00:00:00Z")
    expected = {"seq": 1, "receipt": copy.deepcopy(receipt), "prev": None}
    expected["entry_digest"] = entry_digest_for(1, receipt, None)
    chain = []
    entry = append(chain, receipt)

    assert entry is chain[0]
    assert jcs_canon_bytes(entry) == jcs_canon_bytes(expected)
    assert verify_chain(chain, expected_head=expected["entry_digest"]).ok


def test_rejected_receipt_does_not_change_existing_chain(make_receipt):
    chain = []
    append(chain, make_receipt())
    prior_bytes = jcs_canon_bytes(chain)
    invalid = make_receipt()
    invalid["policy"]["version"] = "stale-identity"

    with pytest.raises(ValueError, match="invalid receipt"):
        append(chain, invalid)

    assert jcs_canon_bytes(chain) == prior_bytes
    assert verify_chain(chain).ok

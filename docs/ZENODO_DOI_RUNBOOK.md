# Minting the GAR draft's DOI — one 60-second step, then I finish it

The `.zenodo.json` at this repo's root is complete and correct for the IETF draft
(draft-lutar-governed-action-receipt-00). Zenodo only mints DOIs for repos that are
toggled ON in the owner's Zenodo account — that toggle is the one action I cannot
perform for you.

## Your 60 seconds

1. Open https://zenodo.org/account/settings/github/ (log in).
2. Find **szl-holdings/szl-platform** in the repo list (hit "Sync" if it just appeared).
3. Flip its switch ON.

## Then tell me "done" — I do the rest

I will:
1. Cut release `v14.0.0-gar00` on szl-platform (tag + release notes naming the draft files).
2. Watch for the deposit (`zenodo.org/api/records?q=...`), read back the minted DOI.
3. Write the DOI into the draft's SUBMISSION_NOTES.md and this file, commit, push.
4. Hand you the datatracker submission line with the DOI included.

## Why not reuse an existing repo

szl-papers' `.zenodo.json` is pinned to Thesis v8 reference metadata by policy (a release
there would mint a record with the wrong title). a11oy's v1.1.0 deposit is still
`PENDING_ZENODO_READBACK`. A new work gets its own concept DOI from a clean repo — that
is this one, per the szl-papers deposit policy ("confirm no record exists, create exactly
one concept").

## OUTCOME (2026-09-01)

Done via the Zenodo API instead of the webhook: deposition 22217725 created, three files uploaded, metadata set, published.

- Version DOI: https://doi.org/10.5281/zenodo.22217725
- Concept DOI: https://doi.org/10.5281/zenodo.22217724
- Record: https://zenodo.org/records/22217725

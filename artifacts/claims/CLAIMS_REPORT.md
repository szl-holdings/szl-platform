# Claims verification report

Claims checked: 9

## BLOCKERS THAT OUTRANK ALL COSMETIC WORK

- **HIGH** `CLAIM_DRIFT` — `monorepo_packages`: expected '126', observed 6: counted files matching '*/pyproject.toml' under /home/user/workspace/szl-platform/packages in this run
- **HIGH** `CLAIM_DRIFT` — `hf_models`: expected '43', observed 44: computed len of JSON array at https://huggingface.co/api/models?author=SZLHOLDINGS in this run
- **HIGH** `CLAIM_DRIFT` — `hf_datasets`: expected '28', observed 30: computed len of JSON array at https://huggingface.co/api/datasets?author=SZLHOLDINGS in this run

## Claim table

| Claim | Expected (quoted) | Observed | Verdict | Evidence |
|---|---|---|---|---|
| ouroboros_tests | 218/218 | — | UNKNOWN | static_expected (not recomputed): test counts are only meaningful inside the ouroboros repo checkout |
| platform_tests | 1220/1220 across 76 packages | — | UNKNOWN | static_expected (not recomputed): requires a platform checkout and a full pytest run; not recomputed here |
| mcp_e2e | 27/27 | — | UNKNOWN | static_expected (not recomputed): no local recomputation exists for this claim |
| db_tables | 848 | — | UNKNOWN | static_expected (not recomputed): no local recomputation exists for this claim |
| api_endpoints | 5524 | — | UNKNOWN | static_expected (not recomputed): no local recomputation exists for this claim |
| monorepo_packages | 126 | 6 | DRIFT | counted files matching '*/pyproject.toml' under /home/user/workspace/szl-platform/packages in this run |
| lambda_overhead_ms_median | <= 0.59 ms | — | UNKNOWN | static_expected (not recomputed): latency medians must be measured, not scraped from a README |
| hf_models | 43 | 44 | DRIFT | computed len of JSON array at https://huggingface.co/api/models?author=SZLHOLDINGS in this run |
| hf_datasets | 28 | 30 | DRIFT | computed len of JSON array at https://huggingface.co/api/datasets?author=SZLHOLDINGS in this run |

_Observed is em-dash when the claim was not recomputed in this run; static_expected claims are UNKNOWN by construction and are never PASS._

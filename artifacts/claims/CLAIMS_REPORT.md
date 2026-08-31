# Claims verification report

Claims checked: 9

## BLOCKERS THAT OUTRANK ALL COSMETIC WORK

No CLAIM_DRIFT findings in this run.

## Claim table

| Claim | Expected (quoted) | Observed | Verdict | Evidence |
|---|---|---|---|---|
| ouroboros_tests | 218/218 | — | UNKNOWN | static_expected (not recomputed): test counts are only meaningful inside the ouroboros repo checkout |
| platform_tests | 1220/1220 across 76 packages | — | UNKNOWN | static_expected (not recomputed): requires a platform checkout and a full pytest run; not recomputed here |
| mcp_e2e | 27/27 | — | UNKNOWN | static_expected (not recomputed): no local recomputation exists for this claim |
| db_tables | 848 | — | UNKNOWN | static_expected (not recomputed): no local recomputation exists for this claim |
| api_endpoints | 5524 | — | UNKNOWN | static_expected (not recomputed): no local recomputation exists for this claim |
| monorepo_packages | 126 | — | UNKNOWN | path /home/user/workspace/packages does not exist; nothing counted |
| lambda_overhead_ms_median | <= 0.59 ms | — | UNKNOWN | static_expected (not recomputed): latency medians must be measured, not scraped from a README |
| hf_models | 44 | 44 | PASS | computed len of JSON array at https://huggingface.co/api/models?author=SZLHOLDINGS in this run |
| hf_datasets | 30 | 30 | PASS | computed len of JSON array at https://huggingface.co/api/datasets?author=SZLHOLDINGS in this run |

_Observed is em-dash when the claim was not recomputed in this run; static_expected claims are UNKNOWN by construction and are never PASS._

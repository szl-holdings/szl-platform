# Runtime working directories

`run/` holds per-service working dirs. The claims API resolves its store at
`artifacts/claims/claims.json` relative to cwd, so it is served from
`run/claims-api`-style dirs to keep the API-native schema (store.py) separate
from the szl-estate verify-claims output schema (`results` wrapper).

Regenerate after every `verify-claims` run:
  python3 scripts/adapt_claims_for_api.py   # artifacts/claims/claims.json -> run/artifacts/claims/claims.json

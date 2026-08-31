"""Enable `python -m szl_claims_api ...` to reach the CLI."""

from szl_claims_api.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

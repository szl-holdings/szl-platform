"""Enable `python -m szl_estate ...` to reach the CLI."""

from szl_estate.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

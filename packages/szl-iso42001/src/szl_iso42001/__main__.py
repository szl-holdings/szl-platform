"""Module entry point: makes `python -m szl_iso42001` work.

Kept to two lines of real code so the entire CLI contract lives in cli.main,
which tests can call in-process without a subprocess.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())

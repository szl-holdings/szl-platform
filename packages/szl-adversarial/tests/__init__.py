"""Tests for szl-adversarial.

This ``__init__.py`` is load-bearing: sibling packages (szl-receipts,
szl-iso42001) own test modules with the same basenames (``test_cli.py``,
``test_report.py``). Making this directory a package gives pytest a unique
module path (``tests.test_cli``) so multi-package runs do not collide.
"""

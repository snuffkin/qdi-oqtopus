"""Smoke test verifying the package is importable."""

import importlib


def test_package_importable() -> None:
    """The package module can be imported without error."""
    module = importlib.import_module("qdi_oqtopus")
    assert module is not None

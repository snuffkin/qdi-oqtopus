"""Layering guard: the QDI-only abstractions must not depend on OQTOPUS."""

from pathlib import Path

_SRC = Path(__file__).parent.parent / "src" / "qdi_oqtopus"
_QDI_ONLY_MODULES = ("types.py", "protocol.py")


def test_qdi_only_modules_do_not_reference_oqtopus() -> None:
    """`types.py` and `protocol.py` must stay free of OQTOPUS-specific code.

    These two modules define the QDI abstraction only; nothing OQTOPUS-shaped
    should leak into them, since the package split that used to enforce this
    boundary at import time was removed.
    """
    for name in _QDI_ONLY_MODULES:
        source = (_SRC / name).read_text(encoding="utf-8")
        assert "oqtopus_client" not in source.lower()

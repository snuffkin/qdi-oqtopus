"""Entry point registration: the client is discoverable by name."""

from importlib.metadata import entry_points

from qdi_oqtopus.client import OqtopusQdiClient

_GROUP = "qbraid.qdi_clients"


def test_oqtopus_entry_point_resolves_to_client() -> None:
    """The ``oqtopus`` entry point loads `OqtopusQdiClient`.

    Requires the package to be installed (e.g. ``pip install -e .``) so its
    metadata is visible to `importlib.metadata`.
    """
    matches = [ep for ep in entry_points(group=_GROUP) if ep.name == "oqtopus"]

    assert len(matches) == 1
    assert matches[0].value == "qdi_oqtopus.client:OqtopusQdiClient"
    assert matches[0].load() is OqtopusQdiClient

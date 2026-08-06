"""Tests for QdiClient (protocol.py) structural typing."""

from qdi_oqtopus.protocol import QdiClient


class _FakeQdiClient:
    """Minimal stand-in exposing the full QDI method surface."""

    def discover(self) -> dict:
        return {}

    def authenticate(self, credentials_dict: dict) -> None:  # ruff: ignore[unused-method-argument]
        return

    def send(
        self,
        task_payload: bytes,  # ruff: ignore[unused-method-argument]
        task_type: str,  # ruff: ignore[unused-method-argument]
        shots: int = 100,  # ruff: ignore[unused-method-argument]
    ) -> str:
        return "task-1"

    def monitor(self, task_id: str) -> tuple[int, dict]:  # ruff: ignore[unused-method-argument]
        return (0, {})

    def receive(self, task_id: str) -> tuple[str, str]:  # ruff: ignore[unused-method-argument]
        return ("{}", "openqasm3")

    def estimate_resources(
        self,
        task_payload: bytes,  # ruff: ignore[unused-method-argument]
        task_type: str,  # ruff: ignore[unused-method-argument]
        shots: int = 100,  # ruff: ignore[unused-method-argument]
    ) -> dict:
        return {}


class _IncompleteClient:
    """Stand-in missing every method except `discover`."""

    def discover(self) -> dict:
        return {}


def test_fake_client_satisfies_qdi_client_protocol() -> None:
    """A class implementing all 6 QDI methods structurally satisfies the protocol."""
    assert isinstance(_FakeQdiClient(), QdiClient)


def test_incomplete_client_does_not_satisfy_protocol() -> None:
    """A class missing required methods must not satisfy the protocol."""
    assert not isinstance(_IncompleteClient(), QdiClient)

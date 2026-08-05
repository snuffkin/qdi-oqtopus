"""Tests for QdiClientProtocol structural typing."""

from qdi_oqtopus.protocol import QdiClientProtocol


class _FakeQdiClient:
    """Minimal stand-in exposing the full QDI method surface."""

    def discover(self) -> dict:
        return {}

    def authenticate(self, credentials_dict: dict) -> None:
        del credentials_dict

    def send(self, task_payload: bytes, task_type: str, shots: int = 100) -> str:
        del task_payload, task_type, shots
        return "task-1"

    def monitor(self, task_id: str) -> tuple[int, dict]:
        del task_id
        return (0, {})

    def receive(self, task_id: str) -> tuple[str, str]:
        del task_id
        return ("{}", "openqasm3")

    def estimate_resources(
        self,
        task_payload: bytes,
        task_type: str,
        shots: int = 100,
    ) -> dict:
        del task_payload, task_type, shots
        return {}


class _IncompleteClient:
    """Stand-in missing every method except `discover`."""

    def discover(self) -> dict:
        return {}


def test_fake_client_satisfies_qdi_client_protocol() -> None:
    """A class implementing all 6 QDI methods structurally satisfies the protocol."""
    assert isinstance(_FakeQdiClient(), QdiClientProtocol)


def test_incomplete_client_does_not_satisfy_protocol() -> None:
    """A class missing required methods must not satisfy the protocol."""
    assert not isinstance(_IncompleteClient(), QdiClientProtocol)

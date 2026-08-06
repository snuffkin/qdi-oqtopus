"""QDI client protocol definition."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class QdiClient(Protocol):
    """Structural type describing the QDI client method surface.

    Named to match qdi-demo's ``QdiClient`` in ``qdi_python.py``.
    The two reference classes disagree on the signature
    of `estimate_resources`; see docs/gap-analysis.md (G010).

    This class should not really exist here: QDI's own class should be used
    directly instead. It is defined in qdi-oqtopus only because qdi-demo
    does not publish a reusable interface artifact (see
    docs/gap-analysis.md (Q5)), and should be removed from qdi-oqtopus
    once QDI provides one.

    """

    def discover(self) -> dict:
        """Discover device properties, capabilities, and configuration.

        Returns:
            Device descriptor as a JSON-compatible dict.

        """
        ...

    def authenticate(self, credentials_dict: dict) -> None:
        """Authenticate and establish trust with the device.

        Args:
            credentials_dict: Credentials payload (e.g. tokens, keys).

        """
        ...

    def send(self, task_payload: bytes, task_type: str, shots: int = 100) -> str:
        """Submit an opaque task payload to the device.

        Args:
            task_payload: Opaque bytes representing the circuit or pulse schedule.
            task_type: Format/type identifier (e.g. ``"openqasm3"``).
            shots: Execution shots limit.

        Returns:
            The generated task ID.

        """
        ...

    def monitor(self, task_id: str) -> tuple[int, dict]:
        """Query the status of a submitted task.

        Args:
            task_id: Unique task ID.

        Returns:
            A ``(status, advisory)`` pair, where ``status`` is a
            `~qdi_oqtopus.types.QdiTaskStatus` value and ``advisory`` is
            optional metadata (e.g. queue position).

        """
        ...

    def receive(self, task_id: str) -> tuple[str, str]:
        """Retrieve execution results for a completed task.

        Args:
            task_id: Unique task ID.

        Returns:
            A ``(result_payload, result_type)`` pair.

        """
        ...

    def estimate_resources(
        self,
        task_payload: bytes,
        task_type: str,
        shots: int = 100,
    ) -> dict:
        """Dry-run a task to estimate required resources or cost.

        Args:
            task_payload: Opaque bytes representing the circuit or pulse schedule.
            task_type: Format/type identifier.
            shots: Execution shots limit.

        Returns:
            Estimation result as a JSON-compatible dict.

        """
        ...

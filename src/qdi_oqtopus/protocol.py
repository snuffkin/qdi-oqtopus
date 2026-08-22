"""QDI client protocol definition."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class QdiClient(Protocol):
    """Structural type describing the QDI client method surface."""

    def discover(self) -> dict:
        """Discover available devices, their capabilities, and configuration.

        Returns:
            A mapping with a single ``"devices"`` key, holding one device
            descriptor per available device as JSON-compatible dicts.

        """
        ...

    def authenticate(self, device_id: str, credentials_dict: dict) -> None:
        """Authenticate and establish trust with the device.

        Args:
            device_id: Unique identifier of the target device.
            credentials_dict: Credentials payload (e.g. tokens, keys).

        """
        ...

    def send(
        self,
        device_id: str,
        task_payload: bytes,
        task_type: str,
        shots: int = 100,
        extensions: dict[str, Any] | None = None,
    ) -> str:
        """Submit an opaque task payload to a targeted device.

        Args:
            device_id: Unique identifier of the target device.
            task_payload: Opaque bytes representing the circuit or pulse schedule.
            task_type: Format/type identifier (e.g. ``"openqasm3"``).
            shots: Execution shots limit.
            extensions: Vendor-specific parameters declared in the device's
                `supported_extensions`.

        Returns:
            The generated task ID.

        """
        ...

    def monitor(self, device_id: str, task_id: str) -> tuple[int, dict]:
        """Query the status of a submitted task on a targeted device.

        Args:
            device_id: Unique identifier of the target device.
            task_id: Unique task ID.

        Returns:
            A ``(status, advisory)`` pair, where ``status`` is a
            `~qdi_oqtopus.types.QdiTaskStatus` value and ``advisory`` is
            optional metadata (e.g. queue position).

        """
        ...

    def receive(self, device_id: str, task_id: str) -> tuple[str, str]:
        """Retrieve execution results for a completed task on a targeted device.

        Args:
            device_id: Unique identifier of the target device.
            task_id: Unique task ID.

        Returns:
            A ``(result_payload, result_type)`` pair.

        """
        ...

    def estimate_resources(
        self,
        device_id: str,
        task_payload: bytes,
        task_type: str,
        shots: int = 100,
        extensions: dict[str, Any] | None = None,
    ) -> dict:
        """Dry-run a task on a targeted device to estimate required resources or cost.

        Args:
            device_id: Unique identifier of the target device.
            task_payload: Opaque bytes representing the circuit or pulse schedule.
            task_type: Format/type identifier.
            shots: Execution shots limit.
            extensions: Vendor-specific parameters declared in the device's
                `supported_extensions`.

        Returns:
            Estimation result as a JSON-compatible dict.

        """
        ...

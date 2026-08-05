"""QDI-side type definitions: status enums and the device descriptor."""

from dataclasses import dataclass
from enum import IntEnum


class QdiStatus(IntEnum):
    """QDI status return codes (``qdi_status`` in qdi.h)."""

    SUCCESS = 0
    ERROR_INVALID_ARGUMENT = 1
    ERROR_UNAUTHORIZED = 2
    ERROR_CONNECTION_FAILED = 3
    ERROR_TASK_NOT_FOUND = 4
    ERROR_UNSUPPORTED_FORMAT = 5
    ERROR_HARDWARE_FAULT = 6
    ERROR_ESTIMATION_FAILED = 7
    ERROR_UNKNOWN = 99


class QdiTaskStatus(IntEnum):
    """QDI task execution states (``qdi_task_status`` in qdi.h).

    This is a distinct enum from `QdiStatus`, despite both being small
    integers starting at 0. qdi-demo's ``QdiClient.monitor()`` conflates the
    two by returning ``99`` (a `QdiStatus` value) for an unrecognized task
    status; do not repeat that mistake here. See docs/gap-analysis.md#g009.
    """

    QUEUED = 0
    EXECUTING = 1
    COMPLETED = 2
    FAULTED = 3
    CANCELLED = 4


@dataclass(frozen=True, slots=True)
class QdiDeviceDescriptor:
    """Device descriptor returned by ``discover()``.

    Field set matches qdi-demo's ``mock_device_config.json``.

    Attributes:
        device_id: Unique device identifier.
        display_name: Human-readable device name.
        supported_auth_methods: Authentication methods the device accepts.
        supported_task_types: Task/circuit format identifiers the device accepts.
        is_ready: Whether the device can currently accept new tasks.
        supports_estimation: Whether ``estimate_resources()`` is meaningful for
            this device.
        num_qubits: Qubit count, or ``None`` when not published.
        max_shots: Maximum shots per task, or ``None`` when not published.

    """

    device_id: str
    display_name: str
    supported_auth_methods: list[str]
    supported_task_types: list[str]
    is_ready: bool
    supports_estimation: bool
    num_qubits: int | None
    max_shots: int | None

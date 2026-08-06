"""Pure functions mapping between QDI and OQTOPUS shapes.

No function here performs I/O; every OQTOPUS-side value is passed in already
resolved, and every QDI-side value is returned, never sent anywhere. This
keeps the module fully testable without a network connection or a mocked
transport.
"""

from collections.abc import Mapping
from typing import Any

from oqtopus_client.rest.models.jobs_job_status import JobsJobStatus
from oqtopus_client.services.device import OqtopusDevice
from oqtopus_client.services.job_spec import OqtopusJobSpec

from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiDeviceDescriptor, QdiStatus, QdiTaskStatus

_JOB_STATUS_TO_TASK_STATUS: dict[JobsJobStatus, QdiTaskStatus] = {
    JobsJobStatus.REGISTERED: QdiTaskStatus.QUEUED,
    JobsJobStatus.SUBMITTED: QdiTaskStatus.QUEUED,
    JobsJobStatus.READY: QdiTaskStatus.QUEUED,
    JobsJobStatus.RUNNING: QdiTaskStatus.EXECUTING,
    JobsJobStatus.SUCCEEDED: QdiTaskStatus.COMPLETED,
    JobsJobStatus.FAILED: QdiTaskStatus.FAULTED,
    JobsJobStatus.CANCELLED: QdiTaskStatus.CANCELLED,
}

_OQTOPUS_PROGRAM_FORMAT = "openqasm3"
_SUPPORTED_TASK_TYPE_ALIASES = frozenset({"openqasm3", "qasm3"})


def map_job_status(status: JobsJobStatus) -> tuple[QdiTaskStatus, dict[str, str]]:
    """Map an OQTOPUS job status to a QDI task status plus advisory metadata.

    Collapses OQTOPUS's 7 statuses onto QDI's 5; see
    docs/gap-analysis.md (G006).

    Args:
        status: OQTOPUS job status, as returned by ``get_job_status()``.

    Returns:
        A ``(task_status, advisory)`` pair. ``advisory`` always carries the
        original OQTOPUS status string under ``"oqtopus_status"`` so it is
        not silently dropped by the 7-to-5 collapse.

    """
    task_status = _JOB_STATUS_TO_TASK_STATUS[status]
    return task_status, {"oqtopus_status": status.value}


def map_task_type(task_type: str) -> str:
    """Map a QDI task-type identifier to the OQTOPUS program format string.

    Args:
        task_type: QDI ``task_type`` identifier (e.g. ``"openqasm3"``,
            ``"qasm3"``).

    Returns:
        The OQTOPUS program format. Always ``"openqasm3"``, since that is the
        only format OQTOPUS accepts.

    Raises:
        QdiError: With `QdiStatus.ERROR_UNSUPPORTED_FORMAT` if ``task_type``
            is not one of OQTOPUS's OPENQASM 3 aliases (e.g. ``"openqasm2"``
            or ``"qir"``).

    """
    if task_type.strip().lower() in _SUPPORTED_TASK_TYPE_ALIASES:
        return _OQTOPUS_PROGRAM_FORMAT
    msg = f"OQTOPUS only accepts OPENQASM 3 programs; got task_type={task_type!r}."
    raise QdiError(QdiStatus.ERROR_UNSUPPORTED_FORMAT, msg)


# QDI-GAP(max_shots): OQTOPUS does not publish a per-device shot limit
# anywhere in its User API. This value is *not* derived from OQTOPUS at
# all: it is qdi-demo's mock_device_config.json example value, reused here
# as a placeholder by explicit project decision. See docs/gap-analysis.md (G003).
_PLACEHOLDER_MAX_SHOTS = 10000


def build_device_descriptor(device: OqtopusDevice) -> QdiDeviceDescriptor:
    """Build a `QdiDeviceDescriptor` from an OQTOPUS device.

    Args:
        device: Device returned by ``OqtopusClient.get_device()``.

    Returns:
        The QDI-shaped device descriptor.

    """
    return QdiDeviceDescriptor(
        device_id=device.device_id,
        display_name=device.description,
        supported_auth_methods=["token"],
        supported_task_types=["openqasm3"],
        is_ready=device.status == "available",
        # QDI-GAP(supports_estimation): OQTOPUS has no dry-run resource/cost
        # estimation endpoint for any device. See docs/gap-analysis.md (G001).
        supports_estimation=False,
        num_qubits=device.n_qubits,
        max_shots=_PLACEHOLDER_MAX_SHOTS,
    )


def build_job_spec(  # ruff: ignore[too-many-arguments]
    *,
    device_id: str,
    task_payload: bytes,
    task_type: str,
    shots: int,
    name: str | None = None,
    description: str | None = None,
    transpiler_info: Mapping[str, Any] | None = None,
    simulator_info: Mapping[str, Any] | None = None,
    mitigation_info: Mapping[str, Any] | None = None,
) -> OqtopusJobSpec:
    """Build an OQTOPUS sampling job spec from a QDI `send()` call.

    ``transpiler_info``/``simulator_info``/``mitigation_info``/``name``/
    ``description`` are not reachable through QDI's `send()` signature; they
    are OQTOPUS-specific defaults supplied by `OqtopusQdiClient` at
    construction time. See docs/gap-analysis.md (G007).

    Args:
        device_id: Target OQTOPUS device id.
        task_payload: Opaque QDI task payload; must be UTF-8-encoded OPENQASM 3.
        task_type: QDI task-type identifier, validated via `map_task_type`.
        shots: Execution shots.
        name: OQTOPUS job name default.
        description: OQTOPUS job description default.
        transpiler_info: OQTOPUS transpiler settings default.
        simulator_info: OQTOPUS simulator settings default.
        mitigation_info: OQTOPUS error-mitigation settings default.

    Returns:
        The OQTOPUS sampling job specification to submit.

    Raises:
        QdiError: With `QdiStatus.ERROR_UNSUPPORTED_FORMAT` if ``task_type``
            is unsupported, or `QdiStatus.ERROR_INVALID_ARGUMENT` if
            ``task_payload`` is not valid UTF-8 text.

    """
    map_task_type(task_type)

    try:
        program = task_payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        msg = "task_payload must be UTF-8-encoded OPENQASM 3 text."
        raise QdiError(QdiStatus.ERROR_INVALID_ARGUMENT, msg) from exc

    return OqtopusJobSpec.sampling(
        device_id=device_id,
        program=program,
        shots=shots,
        name=name,
        description=description,
        transpiler_info=transpiler_info,
        simulator_info=simulator_info,
        mitigation_info=mitigation_info,
    )

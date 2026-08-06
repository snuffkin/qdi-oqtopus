"""Tests for QDI <-> OQTOPUS pure mapping functions."""

import pytest
from oqtopus_client.rest.models.jobs_job_status import JobsJobStatus
from oqtopus_client.services.job_spec import OqtopusJobSpec

from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.mapping import (
    build_device_descriptor,
    build_job_spec,
    map_job_status,
    map_task_type,
)
from qdi_oqtopus.types import QdiStatus, QdiTaskStatus

from ._factories import make_oqtopus_device as _make_device


@pytest.mark.parametrize(
    ("oqtopus_status", "expected_task_status"),
    [
        (JobsJobStatus.REGISTERED, QdiTaskStatus.QUEUED),
        (JobsJobStatus.SUBMITTED, QdiTaskStatus.QUEUED),
        (JobsJobStatus.READY, QdiTaskStatus.QUEUED),
        (JobsJobStatus.RUNNING, QdiTaskStatus.EXECUTING),
        (JobsJobStatus.SUCCEEDED, QdiTaskStatus.COMPLETED),
        (JobsJobStatus.FAILED, QdiTaskStatus.FAULTED),
        (JobsJobStatus.CANCELLED, QdiTaskStatus.CANCELLED),
    ],
)
def test_map_job_status_collapses_seven_to_five(
    oqtopus_status: JobsJobStatus,
    expected_task_status: QdiTaskStatus,
) -> None:
    """Every one of the 7 OQTOPUS statuses maps to one of the 5 QDI statuses."""
    task_status, advisory = map_job_status(oqtopus_status)
    assert task_status == expected_task_status
    assert advisory == {"oqtopus_status": oqtopus_status.value}


@pytest.mark.parametrize("task_type", ["openqasm3", "qasm3", "OPENQASM3", "  qasm3  "])
def test_map_task_type_accepts_openqasm3_aliases(task_type: str) -> None:
    """OPENQASM 3 aliases, case- and whitespace-insensitively, map to 'openqasm3'."""
    assert map_task_type(task_type) == "openqasm3"


@pytest.mark.parametrize("task_type", ["openqasm2", "qir", "llvm", "unknown"])
def test_map_task_type_rejects_unsupported_formats(task_type: str) -> None:
    """Formats OQTOPUS cannot run raise QdiError with ERROR_UNSUPPORTED_FORMAT."""
    with pytest.raises(QdiError) as exc_info:
        map_task_type(task_type)
    assert exc_info.value.status == QdiStatus.ERROR_UNSUPPORTED_FORMAT


def test_build_device_descriptor_maps_available_device() -> None:
    """An 'available' OQTOPUS device becomes a ready QdiDeviceDescriptor."""
    descriptor = build_device_descriptor(_make_device(status="available", n_qubits=16))
    assert descriptor.device_id == "dev1"
    assert descriptor.display_name == "Test device"
    assert descriptor.is_ready is True
    assert descriptor.num_qubits == 16
    assert descriptor.supported_task_types == ["openqasm3"]
    assert descriptor.supported_auth_methods == ["token"]
    assert descriptor.supports_estimation is False
    # Placeholder borrowed from qdi-demo's mock config, not real OQTOPUS
    # data; see the QDI-GAP comment on build_device_descriptor().
    assert descriptor.max_shots == 10000


def test_build_device_descriptor_maps_unavailable_device() -> None:
    """An 'unavailable' OQTOPUS device is reported as not ready."""
    descriptor = build_device_descriptor(_make_device(status="unavailable"))
    assert descriptor.is_ready is False


def test_build_device_descriptor_passes_through_missing_qubit_count() -> None:
    """A device that does not publish n_qubits reports num_qubits as None."""
    descriptor = build_device_descriptor(_make_device(n_qubits=None))
    assert descriptor.num_qubits is None


def test_build_job_spec_decodes_payload_and_maps_task_type() -> None:
    """A valid OPENQASM 3 payload becomes a sampling OqtopusJobSpec."""
    spec = build_job_spec(
        device_id="dev1",
        task_payload=b"OPENQASM 3; qubit[1] q;",
        task_type="qasm3",
        shots=1000,
    )
    assert isinstance(spec, OqtopusJobSpec)
    assert spec.device_id == "dev1"
    assert spec.program == "OPENQASM 3; qubit[1] q;"
    assert spec.shots == 1000


def test_build_job_spec_forwards_vendor_extension_defaults() -> None:
    """transpiler_info/simulator_info/mitigation_info/name/description pass through."""
    spec = build_job_spec(
        device_id="dev1",
        task_payload=b"OPENQASM 3; qubit[1] q;",
        task_type="openqasm3",
        shots=100,
        name="my-job",
        description="from qdi-oqtopus",
        transpiler_info={"transpiler_lib": "qiskit"},
        simulator_info={"n_shots": 100},
        mitigation_info={"pseudo_inverse": True},
    )
    assert spec.name == "my-job"
    assert spec.description == "from qdi-oqtopus"
    assert spec.transpiler_info == {"transpiler_lib": "qiskit"}
    assert spec.simulator_info == {"n_shots": 100}
    assert spec.mitigation_info == {"pseudo_inverse": True}


def test_build_job_spec_rejects_unsupported_task_type() -> None:
    """An unsupported task_type is rejected before any payload decoding happens."""
    with pytest.raises(QdiError) as exc_info:
        build_job_spec(
            device_id="dev1",
            task_payload=b"not used",
            task_type="qir",
            shots=100,
        )
    assert exc_info.value.status == QdiStatus.ERROR_UNSUPPORTED_FORMAT


def test_build_job_spec_rejects_non_utf8_payload() -> None:
    """A payload that is not valid UTF-8 raises QdiError with ERROR_INVALID_ARGUMENT."""
    with pytest.raises(QdiError) as exc_info:
        build_job_spec(
            device_id="dev1",
            task_payload=b"\xff\xfe\x00",
            task_type="openqasm3",
            shots=100,
        )
    assert exc_info.value.status == QdiStatus.ERROR_INVALID_ARGUMENT

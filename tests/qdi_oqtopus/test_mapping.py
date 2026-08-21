"""Tests for QDI <-> OQTOPUS pure mapping functions."""

import pytest
from oqtopus_client.rest.models.jobs_job_status import JobsJobStatus
from oqtopus_client.services.job_spec import OqtopusJobSpec

from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.mapping import (
    build_device_descriptor,
    build_device_descriptors,
    build_job_spec,
    map_job_status,
    map_task_type,
    validate_extensions,
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
    assert descriptor.supported_extensions == [
        "name",
        "description",
        "transpiler_info",
        "mitigation_info",
    ]
    assert descriptor.supports_estimation is False


def test_build_device_descriptor_maps_unavailable_device() -> None:
    """An 'unavailable' OQTOPUS device is reported as not ready."""
    descriptor = build_device_descriptor(_make_device(status="unavailable"))
    assert descriptor.is_ready is False


def test_build_device_descriptor_passes_through_missing_qubit_count() -> None:
    """A device that does not publish n_qubits reports num_qubits as None."""
    descriptor = build_device_descriptor(_make_device(n_qubits=None))
    assert descriptor.num_qubits is None


def test_build_device_descriptors_maps_each_device_in_order() -> None:
    """build_device_descriptors() maps every device, preserving order."""
    devices = [
        _make_device(device_id="dev1", status="available"),
        _make_device(device_id="dev2", status="unavailable"),
    ]

    descriptors = build_device_descriptors(devices)

    assert [descriptor.device_id for descriptor in descriptors] == ["dev1", "dev2"]
    assert descriptors[0].is_ready is True
    assert descriptors[1].is_ready is False


def test_build_device_descriptors_maps_empty_list() -> None:
    """build_device_descriptors() returns an empty list for no devices."""
    assert build_device_descriptors([]) == []


def test_build_job_spec_decodes_payload_and_maps_task_type() -> None:
    """A valid OPENQASM 3 payload becomes a sampling OqtopusJobSpec."""
    spec = build_job_spec(
        device_id="dev1",
        task_payload=b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;',
        task_type="qasm3",
        shots=1000,
    )
    assert isinstance(spec, OqtopusJobSpec)
    assert spec.device_id == "dev1"
    assert spec.program == 'OPENQASM 3; include "stdgates.inc"; qubit[1] q;'
    assert spec.shots == 1000


def test_build_job_spec_forwards_extensions() -> None:
    """name/description/transpiler_info/mitigation_info extensions pass through."""
    spec = build_job_spec(
        device_id="dev1",
        task_payload=b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;',
        task_type="openqasm3",
        shots=100,
        extensions={
            "name": "my-job",
            "description": "from qdi-oqtopus",
            "transpiler_info": {"transpiler_lib": "qiskit"},
            "mitigation_info": {"pseudo_inverse": True},
        },
    )
    assert spec.name == "my-job"
    assert spec.description == "from qdi-oqtopus"
    assert spec.transpiler_info == {"transpiler_lib": "qiskit"}
    assert spec.mitigation_info == {"pseudo_inverse": True}


def test_build_job_spec_rejects_undeclared_extension_key() -> None:
    """An undeclared extensions key is rejected before any OQTOPUS call is built."""
    with pytest.raises(QdiError) as exc_info:
        build_job_spec(
            device_id="dev1",
            task_payload=b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;',
            task_type="openqasm3",
            shots=100,
            extensions={"operator": [], "name": "my-job"},
        )
    assert exc_info.value.status == QdiStatus.ERROR_INVALID_ARGUMENT


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


@pytest.mark.parametrize(
    "extensions",
    [
        None,
        {},
        {"name": "my-job"},
        {"name": "my-job", "transpiler_info": {"transpiler_lib": "qiskit"}},
    ],
)
def test_validate_extensions_accepts_declared_keys(extensions: dict | None) -> None:
    """No error is raised when every extensions key is declared as supported."""
    validate_extensions(extensions, ["name", "description", "transpiler_info"])


@pytest.mark.parametrize(
    "extensions",
    [
        {"operator": []},
        {"name": "my-job", "operator": []},
    ],
)
def test_validate_extensions_rejects_undeclared_keys(extensions: dict) -> None:
    """An undeclared key raises QdiError with ERROR_INVALID_ARGUMENT."""
    with pytest.raises(QdiError) as exc_info:
        validate_extensions(extensions, ["name", "description", "transpiler_info"])
    assert exc_info.value.status == QdiStatus.ERROR_INVALID_ARGUMENT

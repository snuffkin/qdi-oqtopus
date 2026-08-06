"""Tests for QDI type definitions."""

from qdi_oqtopus.types import QdiDeviceDescriptor, QdiStatus, QdiTaskStatus


def test_qdi_status_values_match_qdi_h() -> None:
    """QdiStatus values must match the qdi.h `qdi_status` enum exactly."""
    assert QdiStatus.SUCCESS == 0
    assert QdiStatus.ERROR_INVALID_ARGUMENT == 1
    assert QdiStatus.ERROR_UNAUTHORIZED == 2
    assert QdiStatus.ERROR_CONNECTION_FAILED == 3
    assert QdiStatus.ERROR_TASK_NOT_FOUND == 4
    assert QdiStatus.ERROR_UNSUPPORTED_FORMAT == 5
    assert QdiStatus.ERROR_HARDWARE_FAULT == 6
    assert QdiStatus.ERROR_ESTIMATION_FAILED == 7
    assert QdiStatus.ERROR_UNKNOWN == 99


def test_qdi_task_status_values_match_qdi_h() -> None:
    """QdiTaskStatus values must match the qdi.h `qdi_task_status` enum exactly."""
    assert QdiTaskStatus.QUEUED == 0
    assert QdiTaskStatus.EXECUTING == 1
    assert QdiTaskStatus.COMPLETED == 2
    assert QdiTaskStatus.FAULTED == 3
    assert QdiTaskStatus.CANCELLED == 4


def test_qdi_status_and_qdi_task_status_are_distinct_enums() -> None:
    """The two enums must stay separate namespaces."""
    assert not issubclass(QdiTaskStatus, QdiStatus)
    assert not issubclass(QdiStatus, QdiTaskStatus)


def test_device_descriptor_holds_all_required_fields() -> None:
    """QdiDeviceDescriptor exposes all 8 fields from mock_device_config.json."""
    descriptor = QdiDeviceDescriptor(
        device_id="dev1",
        display_name="Device One",
        supported_auth_methods=["token"],
        supported_task_types=["openqasm3"],
        is_ready=True,
        supports_estimation=False,
        num_qubits=4,
        max_shots=None,
    )
    assert descriptor.device_id == "dev1"
    assert descriptor.display_name == "Device One"
    assert descriptor.supported_auth_methods == ["token"]
    assert descriptor.supported_task_types == ["openqasm3"]
    assert descriptor.is_ready is True
    assert descriptor.supports_estimation is False
    assert descriptor.num_qubits == 4
    assert descriptor.max_shots is None

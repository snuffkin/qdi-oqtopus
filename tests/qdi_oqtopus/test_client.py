"""Tests for OqtopusQdiClient, with OqtopusClient fully mocked."""

import json
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from oqtopus_client.rest.models.jobs_get_job_status_response import (
    JobsGetJobStatusResponse,
)
from oqtopus_client.rest.models.jobs_job_status import JobsJobStatus
from oqtopus_client.rest.models.jobs_register_job_response import (
    JobsRegisterJobResponse,
)
from oqtopus_client.services.client import OqtopusClient
from oqtopus_client.services.errors import ResponseValidationError, UserApiError
from oqtopus_client.services.job_results import (
    OqtopusJobResult,
    OqtopusSamplingJobResult,
)
from oqtopus_client.services.storage import OqtopusStorageError
from pytest_mock import MockerFixture

from qdi_oqtopus.client import OqtopusQdiClient
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.protocol import QdiClient
from qdi_oqtopus.types import QdiStatus, QdiTaskStatus

from ._factories import make_oqtopus_device


def _make_mock_oqtopus_client() -> MagicMock:
    return MagicMock(spec=OqtopusClient)


def _make_authenticated_client(
    mock_client: MagicMock | None = None,
) -> OqtopusQdiClient:
    return OqtopusQdiClient("dev1", client=mock_client or _make_mock_oqtopus_client())


def test_oqtopus_qdi_client_satisfies_qdi_client_protocol() -> None:
    """`OqtopusQdiClient` structurally satisfies the `QdiClient` protocol."""
    assert isinstance(OqtopusQdiClient("dev1"), QdiClient)


def test_injected_client_is_treated_as_already_authenticated(
    mocker: MockerFixture,
) -> None:
    """Supplying `client=` at construction skips the verification round-trip."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_device.return_value = make_oqtopus_device()
    oqtopus_client_class = mocker.patch("qdi_oqtopus.client.OqtopusClient")

    client = OqtopusQdiClient("dev1", client=mock_client)
    client.discover()

    oqtopus_client_class.assert_not_called()
    mock_client.get_api_token_status.assert_not_called()


@pytest.mark.parametrize(
    "call",
    [
        lambda client: client.discover(),
        lambda client: client.send(
            b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;', "openqasm3"
        ),
        lambda client: client.monitor("job-1"),
        lambda client: client.receive("job-1"),
    ],
)
def test_methods_raise_unauthorized_before_authenticate_is_called(
    call: Callable[[OqtopusQdiClient], object],
) -> None:
    """No method authenticates on the caller's behalf; each requires it first.

    This matches qdi-demo's own clients, which also require an explicit
    `authenticate()` call before anything else works. See
    docs/gap-analysis.md, gap G4.
    """
    client = OqtopusQdiClient("dev1")

    with pytest.raises(QdiError) as exc_info:
        call(client)
    assert exc_info.value.status == QdiStatus.ERROR_UNAUTHORIZED


def test_authenticate_builds_and_verifies_a_client(mocker: MockerFixture) -> None:
    """authenticate() builds an OqtopusClient from credentials_dict and verifies it."""
    mock_client = _make_mock_oqtopus_client()
    oqtopus_client_class = mocker.patch(
        "qdi_oqtopus.client.OqtopusClient", return_value=mock_client
    )
    client = OqtopusQdiClient("dev1")

    client.authenticate({"base_url": "https://example.test", "api_token": "new"})

    oqtopus_client_class.assert_called_once()
    used_config = oqtopus_client_class.call_args[0][0]
    assert used_config.base_url == "https://example.test"
    assert used_config.api_token == "new"  # ruff: ignore[hardcoded-password-string]
    mock_client.get_api_token_status.assert_called_once()


@pytest.mark.parametrize(
    "credentials_dict",
    [
        {},
        {"base_url": "https://example.test"},
        {"api_token": "some-token"},
    ],
)
def test_authenticate_rejects_incomplete_credentials(credentials_dict: dict) -> None:
    """Missing `base_url` or `api_token` surfaces as ERROR_INVALID_ARGUMENT."""
    client = OqtopusQdiClient("dev1")

    with pytest.raises(QdiError) as exc_info:
        client.authenticate(credentials_dict)
    assert exc_info.value.status == QdiStatus.ERROR_INVALID_ARGUMENT


def test_authenticate_raises_qdi_error_on_invalid_token(
    mocker: MockerFixture,
) -> None:
    """A rejected token surfaces as QdiError with ERROR_UNAUTHORIZED."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_api_token_status.side_effect = UserApiError(401, "invalid")
    mocker.patch("qdi_oqtopus.client.OqtopusClient", return_value=mock_client)
    client = OqtopusQdiClient("dev1")

    with pytest.raises(QdiError) as exc_info:
        client.authenticate({"base_url": "https://example.test", "api_token": "bad"})
    assert exc_info.value.status == QdiStatus.ERROR_UNAUTHORIZED


def test_discover_returns_device_descriptor_dict() -> None:
    """discover() returns the mapped device descriptor as a dict."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_device.return_value = make_oqtopus_device(
        status="available", n_qubits=8
    )
    client = _make_authenticated_client(mock_client)

    result = client.discover()

    mock_client.get_device.assert_called_once_with("dev1")
    assert result["device_id"] == "dev1"
    assert result["is_ready"] is True
    assert result["num_qubits"] == 8


def test_discover_translates_user_api_error() -> None:
    """A device lookup failure surfaces as QdiError."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_device.side_effect = UserApiError(404, "device not found")
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.discover()
    assert exc_info.value.status == QdiStatus.ERROR_TASK_NOT_FOUND


def test_send_submits_a_sampling_job_and_returns_job_id() -> None:
    """send() builds a sampling job spec and returns the OQTOPUS job id."""
    mock_client = _make_mock_oqtopus_client()
    register_response = MagicMock(spec=JobsRegisterJobResponse)
    register_response.job_id = "job-1"
    mock_client.submit_job.return_value = register_response
    client = _make_authenticated_client(mock_client)

    task_id = client.send(
        b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;', "openqasm3", shots=500
    )

    assert task_id == "job-1"
    submitted_spec = mock_client.submit_job.call_args[0][0]
    assert submitted_spec.device_id == "dev1"
    assert submitted_spec.shots == 500


def test_send_forwards_oqtopus_only_keyword_arguments() -> None:
    """name/description/transpiler_info/simulator_info/mitigation_info pass through.

    These have no QDI counterpart (question Q2) and are only reachable by a
    caller who steps outside QDI's `send(task_payload, task_type, shots)`
    contract.
    """
    mock_client = _make_mock_oqtopus_client()
    register_response = MagicMock(spec=JobsRegisterJobResponse)
    register_response.job_id = "job-1"
    mock_client.submit_job.return_value = register_response
    client = _make_authenticated_client(mock_client)

    client.send(
        b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;',
        "openqasm3",
        name="my-job",
        description="from qdi-oqtopus",
        transpiler_info={"transpiler_lib": "qiskit"},
        simulator_info={"n_shots": 100},
        mitigation_info={"pseudo_inverse": True},
    )

    submitted_spec = mock_client.submit_job.call_args[0][0]
    assert submitted_spec.name == "my-job"
    assert submitted_spec.description == "from qdi-oqtopus"
    assert submitted_spec.transpiler_info == {"transpiler_lib": "qiskit"}
    assert submitted_spec.simulator_info == {"n_shots": 100}
    assert submitted_spec.mitigation_info == {"pseudo_inverse": True}


def test_send_translates_user_api_error() -> None:
    """A submission HTTP failure surfaces as QdiError."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.submit_job.side_effect = UserApiError(400, "bad request")
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.send(b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;', "openqasm3")
    assert exc_info.value.status == QdiStatus.ERROR_INVALID_ARGUMENT


def test_send_translates_storage_error_as_connection_failed() -> None:
    """An S3 upload failure (no HTTP status) maps to ERROR_CONNECTION_FAILED."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.submit_job.side_effect = OqtopusStorageError("upload timed out")
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.send(b'OPENQASM 3; include "stdgates.inc"; qubit[1] q;', "openqasm3")
    assert exc_info.value.status == QdiStatus.ERROR_CONNECTION_FAILED


def test_send_rejects_unsupported_task_type_before_calling_oqtopus() -> None:
    """An unsupported task_type never reaches OqtopusClient at all."""
    mock_client = _make_mock_oqtopus_client()
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.send(b"irrelevant", "qir")
    assert exc_info.value.status == QdiStatus.ERROR_UNSUPPORTED_FORMAT
    mock_client.submit_job.assert_not_called()


def test_monitor_maps_status_and_reports_advisory() -> None:
    """monitor() maps the OQTOPUS status and carries it in the advisory dict."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_job_status.return_value = JobsGetJobStatusResponse(
        job_id="job-1", status=JobsJobStatus.RUNNING
    )
    client = _make_authenticated_client(mock_client)

    status, advisory = client.monitor("job-1")

    assert status == QdiTaskStatus.EXECUTING
    assert advisory == {"oqtopus_status": "running"}


def test_monitor_translates_user_api_error() -> None:
    """A status lookup failure surfaces as QdiError."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_job_status.side_effect = UserApiError(404, "job not found")
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.monitor("missing")
    assert exc_info.value.status == QdiStatus.ERROR_TASK_NOT_FOUND


def test_receive_returns_json_counts_and_result_type() -> None:
    """receive() returns JSON-encoded sampling counts and the 'counts' label."""
    mock_client = _make_mock_oqtopus_client()
    sampling_result = MagicMock(spec=OqtopusSamplingJobResult)
    sampling_result.get_counts.return_value = {"00": 51, "11": 49}
    mock_client.get_job.return_value = sampling_result
    client = _make_authenticated_client(mock_client)

    payload, result_type = client.receive("job-1")

    assert json.loads(payload) == {"00": 51, "11": 49}
    assert result_type == "counts"


def test_receive_rejects_non_sampling_results() -> None:
    """A non-sampling job result raises QdiError instead of misreporting counts."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_job.return_value = MagicMock(spec=OqtopusJobResult)
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.receive("job-1")
    assert exc_info.value.status == QdiStatus.ERROR_UNKNOWN


def test_receive_translates_not_ready_as_qdi_error() -> None:
    """A job with no results yet (ResponseValidationError) surfaces as QdiError."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_job.side_effect = ResponseValidationError("not ready")
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.receive("job-1")
    assert exc_info.value.status == QdiStatus.ERROR_UNKNOWN


def test_receive_translates_user_api_error() -> None:
    """A result lookup HTTP failure surfaces as QdiError."""
    mock_client = _make_mock_oqtopus_client()
    mock_client.get_job.side_effect = UserApiError(404, "job not found")
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.receive("missing")
    assert exc_info.value.status == QdiStatus.ERROR_TASK_NOT_FOUND


def test_estimate_resources_always_raises_without_touching_oqtopus() -> None:
    """estimate_resources() always fails and never calls OqtopusClient at all."""
    mock_client = _make_mock_oqtopus_client()
    client = _make_authenticated_client(mock_client)

    with pytest.raises(QdiError) as exc_info:
        client.estimate_resources(b"irrelevant", "openqasm3", shots=100)

    assert exc_info.value.status == QdiStatus.ERROR_ESTIMATION_FAILED
    mock_client.assert_not_called()

"""Tests for QdiError."""

import pytest
from oqtopus_client.services.errors import UserApiError

from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiStatus


def test_qdi_error_preserves_status_and_detail() -> None:
    """QdiError keeps both the QDI status code and the original message."""
    error = QdiError(QdiStatus.ERROR_UNAUTHORIZED, "invalid token")
    assert error.status == QdiStatus.ERROR_UNAUTHORIZED
    assert error.detail == "invalid token"
    assert "invalid token" in str(error)


def test_qdi_error_without_detail_uses_status_name() -> None:
    """When no detail is given, the message falls back to the status name."""
    error = QdiError(QdiStatus.ERROR_UNKNOWN)
    assert error.detail is None
    assert "ERROR_UNKNOWN" in str(error)


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (400, QdiStatus.ERROR_INVALID_ARGUMENT),
        (401, QdiStatus.ERROR_UNAUTHORIZED),
        (403, QdiStatus.ERROR_UNAUTHORIZED),
        (404, QdiStatus.ERROR_TASK_NOT_FOUND),
        (500, QdiStatus.ERROR_UNKNOWN),
        (418, QdiStatus.ERROR_UNKNOWN),
    ],
)
def test_from_user_api_error_maps_known_http_statuses(
    status_code: int,
    expected_status: QdiStatus,
) -> None:
    """Known HTTP statuses map to their closest QdiStatus; the rest fall back."""
    exc = UserApiError(status_code, "backend said no")
    error = QdiError.from_user_api_error(exc)
    assert error.status == expected_status
    assert error.detail == "backend said no"


def test_from_user_api_error_never_discards_the_message() -> None:
    """The original OQTOPUS error message always survives as `detail`."""
    exc = UserApiError(404, "device 'ghost' not found", payload={"code": "not_found"})
    error = QdiError.from_user_api_error(exc)
    assert error.detail == "device 'ghost' not found"

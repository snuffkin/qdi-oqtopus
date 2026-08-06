"""QDI-side error type and conversion from OQTOPUS errors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qdi_oqtopus.types import QdiStatus

if TYPE_CHECKING:
    from oqtopus_client.services.errors import UserApiError

_HTTP_STATUS_TO_QDI_STATUS: dict[int, QdiStatus] = {
    400: QdiStatus.ERROR_INVALID_ARGUMENT,
    401: QdiStatus.ERROR_UNAUTHORIZED,
    403: QdiStatus.ERROR_UNAUTHORIZED,
    404: QdiStatus.ERROR_TASK_NOT_FOUND,
}


def resolve_qdi_status(status_code: int) -> QdiStatus:
    """Map an OQTOPUS HTTP status code to the closest matching `QdiStatus`.

    # QDI-GAP(status-code-mapping): `qdi_status` has no code for "device not
    # found" distinct from `ERROR_TASK_NOT_FOUND`, and no HTTP status
    # unambiguously corresponds to `ERROR_HARDWARE_FAULT`, so an unrecognized
    # status falls back to `ERROR_UNKNOWN`. See docs/gap-analysis.md (G012).

    Args:
        status_code: HTTP status code from a `UserApiError`.

    Returns:
        The closest matching `QdiStatus`, or `QdiStatus.ERROR_UNKNOWN` if
        none is a good fit.

    """
    return _HTTP_STATUS_TO_QDI_STATUS.get(status_code, QdiStatus.ERROR_UNKNOWN)


class QdiError(Exception):
    """Exception representing a QDI status code.

    The C ABI's ``qdi_status`` return code alone cannot carry a message, but
    this Python-level exception keeps the original error message as exception
    state so nothing is discarded at the Python API layer. See
    docs/gap-analysis.md (G008).

    qdi-demo's own ``QDIError.__init__(self, code, detail=None)`` names this
    attribute ``code`` and leaves it untyped. This class keeps it as
    ``status: QdiStatus`` instead, deliberately: every call site here
    already passes a `QdiStatus` member, so a looser `int` annotation
    would describe a usage pattern that does not actually occur. See
    docs/gap-analysis.md (Q5).

    Attributes:
        status: The QDI status code this error corresponds to.
        detail: The original, non-QDI error message, when available.

    """

    def __init__(self, status: QdiStatus, detail: str | None = None) -> None:
        """Create a QDI error carrying a QDI status code and optional detail.

        Args:
            status: QDI status code.
            detail: Original error message to preserve, if any.

        """
        self.status = status
        self.detail = detail
        super().__init__(detail or f"QDI operation failed with status {status.name}")

    @classmethod
    def from_user_api_error(cls, exc: UserApiError) -> QdiError:
        """Convert an OQTOPUS `UserApiError` into a `QdiError`.

        The original message is never discarded (see docs/gap-analysis.md,
        G008): it survives as `QdiError.detail`. See `resolve_qdi_status`
        for the status-code mapping this uses.

        Args:
            exc: The OQTOPUS error being translated.

        Returns:
            A `QdiError` carrying the closest matching QDI status code and
            the original OQTOPUS error message.

        """
        return cls(resolve_qdi_status(exc.status_code), exc.message)

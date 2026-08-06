"""OQTOPUS-backed implementation of the QDI client method surface."""

from __future__ import annotations

from dataclasses import asdict
from json import dumps
from typing import TYPE_CHECKING, Any

from oqtopus_client.services.client import OqtopusClient
from oqtopus_client.services.config import OqtopusConfig
from oqtopus_client.services.errors import ResponseValidationError, UserApiError
from oqtopus_client.services.job_results import OqtopusSamplingJobResult
from oqtopus_client.services.storage import OqtopusStorageError

from qdi_oqtopus.errors import QdiError, resolve_qdi_status
from qdi_oqtopus.mapping import build_device_descriptor, build_job_spec, map_job_status
from qdi_oqtopus.types import QdiStatus

if TYPE_CHECKING:
    from collections.abc import Mapping


class OqtopusQdiClient:
    """QDI client adapter backed by OQTOPUS Cloud.

    # QDI-GAP(device-cardinality): QDI's 6 core functions never take a
    # device identifier; this adapter binds one instance to exactly one
    # device at construction time instead. See docs/gap-analysis.md (G002).

    Attributes:
        device_id: The single OQTOPUS device this instance talks to.

    """

    def __init__(
        self,
        device_id: str,
        *,
        client: OqtopusClient | None = None,
    ) -> None:
        """Bind this client to one OQTOPUS device.

        Args:
            device_id: Target OQTOPUS device id.
            client: A pre-built, already-authenticated `OqtopusClient` to
                use as-is (e.g. a mock in tests). Supplying this skips
                `authenticate()` entirely; every other method becomes
                usable immediately.

        """
        self.device_id = device_id
        self._client = client

    def _require_authenticated(self) -> OqtopusClient:
        """Return the authenticated client, or raise if never authenticated.

        Unlike an earlier revision, this does not authenticate on the
        caller's behalf: `authenticate()` must have been called explicitly
        first, matching qdi-demo's own clients.

        Returns:
            The `OqtopusClient` established by `authenticate()`.

        Raises:
            QdiError: With `QdiStatus.ERROR_UNAUTHORIZED` if `authenticate()`
                has not been called yet.

        """
        if self._client is None:
            msg = "authenticate() must be called before this operation."
            raise QdiError(QdiStatus.ERROR_UNAUTHORIZED, msg)
        return self._client

    def discover(self) -> dict:
        """Discover this device's properties, capabilities, and configuration.

        # QDI-GAP(discover-requires-auth): OQTOPUS requires `BearerAuth` on
        # every endpoint, including device lookup, so this raises unless
        # `authenticate()` was already called. qdi.h lists `qdi_discover`
        # before `qdi_authenticate`, but the only usable call order here is
        # authenticate() then discover(), the reverse. See
        # docs/gap-analysis.md (G011, Q4).

        Returns:
            The device descriptor as a JSON-compatible dict.

        Raises:
            QdiError: With `QdiStatus.ERROR_UNAUTHORIZED` if `authenticate()`
                was not called first, or if the device lookup itself fails.

        """
        client = self._require_authenticated()
        try:
            device = client.get_device(self.device_id)
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        return asdict(build_device_descriptor(device))

    def authenticate(self, credentials_dict: dict) -> None:
        """Establish the OQTOPUS client used for all other calls.

        # QDI-GAP(authenticate): OQTOPUS has no in-band credential exchange
        # endpoint at all -- even token creation itself requires an
        # existing bearer token (see spec/openapi.yaml). ``credentials_dict``
        # must therefore carry a token that was already obtained
        # out-of-band; this method can only build a client from it and
        # verify it works, not perform a real handshake. See
        # docs/gap-analysis.md (G004, Q2).

        Args:
            credentials_dict: Must contain ``base_url`` and ``api_token``.

        Raises:
            QdiError: With `QdiStatus.ERROR_INVALID_ARGUMENT` if either key
                is missing, or `QdiStatus.ERROR_UNAUTHORIZED` if the token
                does not work.

        """
        base_url = credentials_dict.get("base_url")
        api_token = credentials_dict.get("api_token")
        if not base_url or not api_token:
            msg = "credentials_dict must include both 'base_url' and 'api_token'."
            raise QdiError(QdiStatus.ERROR_INVALID_ARGUMENT, msg)

        config = OqtopusConfig(base_url=base_url, api_token=api_token)
        candidate = OqtopusClient(config)
        try:
            candidate.get_api_token_status()
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc

        self._client = candidate

    # QDI-GAP(vendor-extension-kwargs): task_payload/task_type/shots are
    # QDI's entire `send()` contract; name/description/transpiler_info/
    # simulator_info/mitigation_info below have no QDI counterpart at all
    # and are exposed only as keyword-only extras, reachable only by a
    # caller who already knows to step outside QDI. See
    # docs/gap-analysis.md (G007).
    def send(  # ruff: ignore[too-many-arguments]
        self,
        task_payload: bytes,
        task_type: str,
        shots: int = 100,
        *,
        name: str | None = None,
        description: str | None = None,
        transpiler_info: Mapping[str, Any] | None = None,
        simulator_info: Mapping[str, Any] | None = None,
        mitigation_info: Mapping[str, Any] | None = None,
    ) -> str:
        """Submit an opaque task payload to this device.

        `name`/`description`/`transpiler_info`/`simulator_info`/
        `mitigation_info` are OQTOPUS-specific `OqtopusJobSpec` fields with
        no QDI counterpart. QDI's own `send()` contract is exactly
        `(task_payload, task_type, shots)`; a caller sticking to that
        contract gets `None` for all five and plain OQTOPUS defaults. See
        docs/gap-analysis.md (G007).

        Args:
            task_payload: UTF-8-encoded OPENQASM 3 program bytes.
            task_type: QDI task-type identifier; validated via `map_task_type`.
            shots: Execution shots limit.
            name: OQTOPUS job name. Not part of QDI's `send()` contract.
            description: OQTOPUS job description. Not part of QDI's `send()`
                contract.
            transpiler_info: OQTOPUS transpiler settings. Not part of QDI's
                `send()` contract.
            simulator_info: OQTOPUS simulator settings. Not part of QDI's
                `send()` contract.
            mitigation_info: OQTOPUS error-mitigation settings. Not part of
                QDI's `send()` contract.

        Returns:
            The OQTOPUS job id, used as the QDI task id.

        Raises:
            QdiError: With `QdiStatus.ERROR_UNAUTHORIZED` if `authenticate()`
                was not called first, or if job-spec construction or
                submission fails.

        """
        client = self._require_authenticated()
        spec = build_job_spec(
            device_id=self.device_id,
            task_payload=task_payload,
            task_type=task_type,
            shots=shots,
            name=name,
            description=description,
            transpiler_info=transpiler_info,
            simulator_info=simulator_info,
            mitigation_info=mitigation_info,
        )
        try:
            response = client.submit_job(spec)
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        except OqtopusStorageError as exc:
            # QDI-GAP(send-partial-failure): submit_job()'s S3 upload step
            # can fail independently of its two HTTP calls, with no HTTP
            # status of its own to translate. See docs/gap-analysis.md (G013).
            raise QdiError(QdiStatus.ERROR_CONNECTION_FAILED, str(exc)) from exc
        return response.job_id

    def monitor(self, task_id: str) -> tuple[int, dict]:
        """Query the status of a submitted task.

        Args:
            task_id: OQTOPUS job id returned by `send()`.

        Returns:
            A ``(status, advisory)`` pair. ``advisory`` always carries the
            original OQTOPUS status string; see docs/gap-analysis.md (G006).

        Raises:
            QdiError: With `QdiStatus.ERROR_UNAUTHORIZED` if `authenticate()`
                was not called first, or if the status lookup fails.

        """
        client = self._require_authenticated()
        try:
            response = client.get_job_status(task_id)
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        task_status, advisory = map_job_status(response.status)
        return task_status, advisory

    def receive(self, task_id: str) -> tuple[str, str]:
        """Retrieve execution results for a completed task.

        # QDI-GAP(receive-not-ready): QDI has no status for "task exists but
        # results are not ready yet". OQTOPUS's own `get_job()` raises for a
        # task still in the ``registered`` state (QDI's `QUEUED`); this is
        # surfaced as `QdiStatus.ERROR_UNKNOWN` for lack of a better code.
        # See docs/gap-analysis.md (G014).

        Args:
            task_id: OQTOPUS job id returned by `send()`.

        Returns:
            A ``(result_payload, result_type)`` pair. ``result_payload`` is a
            JSON-encoded sampling counts dict; ``result_type`` is always the
            literal ``"counts"`` label (QDI does not standardize this
            string).

        Raises:
            QdiError: With `QdiStatus.ERROR_UNAUTHORIZED` if `authenticate()`
                was not called first. Also raised if the result lookup
                fails, the task is not sampling-typed, or results are not
                ready yet.

        """
        client = self._require_authenticated()
        try:
            result = client.get_job(task_id)
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        except ResponseValidationError as exc:
            msg = f"Task {task_id!r} has no results available yet."
            raise QdiError(QdiStatus.ERROR_UNKNOWN, msg) from exc
        if not isinstance(result, OqtopusSamplingJobResult):
            msg = (
                f"receive() only supports sampling jobs; "
                f"task {task_id!r} is {type(result).__name__}."
            )
            raise QdiError(QdiStatus.ERROR_UNKNOWN, msg)
        return dumps(result.get_counts()), "counts"

    # Kept as an instance method (not @staticmethod) to match
    # protocol.QdiClient's `estimate_resources(self, ...)` signature exactly.
    def estimate_resources(  # ruff: ignore[no-self-use]
        self,
        task_payload: bytes,  # ruff: ignore[unused-method-argument]
        task_type: str,  # ruff: ignore[unused-method-argument]
        shots: int = 100,  # ruff: ignore[unused-method-argument]
    ) -> dict:
        """Dry-run a task to estimate required resources or cost.

        Always fails: OQTOPUS has no such capability. See
        docs/gap-analysis.md (G001, Q3).

        Args:
            task_payload: Unused; OQTOPUS never receives this call.
            task_type: Unused; OQTOPUS never receives this call.
            shots: Unused; OQTOPUS never receives this call.

        Raises:
            QdiError: Always, with `QdiStatus.ERROR_ESTIMATION_FAILED`.

        """
        msg = "OQTOPUS has no dry-run resource/cost estimation endpoint."
        raise QdiError(QdiStatus.ERROR_ESTIMATION_FAILED, msg)

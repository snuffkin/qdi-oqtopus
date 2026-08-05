"""OQTOPUS-backed implementation of the QDI client method surface."""

from __future__ import annotations

from dataclasses import asdict, replace
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
    # device at construction time instead. See docs/gap-analysis.md#g002.

    Attributes:
        device_id: The single OQTOPUS device this instance talks to.

    """

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        device_id: str,
        config: OqtopusConfig | None = None,
        *,
        client: OqtopusClient | None = None,
        name: str | None = None,
        description: str | None = None,
        transpiler_info: Mapping[str, Any] | None = None,
        simulator_info: Mapping[str, Any] | None = None,
        mitigation_info: Mapping[str, Any] | None = None,
    ) -> None:
        """Bind this client to one OQTOPUS device.

        Args:
            device_id: Target OQTOPUS device id.
            config: Connection/credential config used to build the
                underlying `OqtopusClient` on first use, if ``client`` is not
                supplied. Defaults to `OqtopusConfig.from_file()` when both
                this and any `authenticate()` credentials are absent.
            client: A pre-built `OqtopusClient` to use as-is (e.g. a mock in
                tests, or a client whose trust is already established).
                Supplying this skips `authenticate()`'s verification
                round-trip.
            name: Default OQTOPUS job name for `send()`. Not reachable
                per-call through QDI's `send()` signature. See
                docs/gap-analysis.md#g007.
            description: Default OQTOPUS job description for `send()`. See
                docs/gap-analysis.md#g007.
            transpiler_info: Default OQTOPUS transpiler settings for
                `send()`. See docs/gap-analysis.md#g007.
            simulator_info: Default OQTOPUS simulator settings for `send()`.
                See docs/gap-analysis.md#g007.
            mitigation_info: Default OQTOPUS mitigation settings for
                `send()`. See docs/gap-analysis.md#g007.

        """
        self.device_id = device_id
        self._config = config
        self._client = client
        self._authenticated = client is not None
        self._name = name
        self._description = description
        self._transpiler_info = transpiler_info
        self._simulator_info = simulator_info
        self._mitigation_info = mitigation_info

    def authenticate(self, credentials_dict: dict) -> None:
        """Establish (or re-establish) the OQTOPUS client used for all other calls.

        # QDI-GAP(authenticate): OQTOPUS has no in-band credential exchange
        # endpoint at all -- even token creation itself requires an existing
        # bearer token (see spec/openapi.yaml). The token in
        # ``credentials_dict`` (or ``config`` supplied at construction time)
        # must therefore already have been obtained out-of-band; this method
        # can only build a client from it and verify it works, not perform a
        # real handshake. See docs/gap-analysis.md#g004 and
        # docs/qdi-spec-feedback.md#q2.

        Args:
            credentials_dict: May contain ``api_token`` to supply/replace the
                bearer token. May be empty to just (re)validate the config
                supplied at construction time.

        Raises:
            QdiError: With `QdiStatus.ERROR_UNAUTHORIZED` if the resulting
                token does not work, or `QdiStatus.ERROR_INVALID_ARGUMENT` if
                no usable config could be resolved at all.

        """
        try:
            base_config = self._config or OqtopusConfig.from_file()
            api_token = credentials_dict.get("api_token")
            config = (
                base_config
                if api_token is None
                else replace(base_config, api_token=api_token)
            )
            candidate = OqtopusClient(config)
            candidate.get_api_token_status()
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        except ValueError as exc:
            raise QdiError(QdiStatus.ERROR_INVALID_ARGUMENT, str(exc)) from exc

        self._config = config
        self._client = candidate
        self._authenticated = True

    def _ensure_authenticated(self) -> OqtopusClient:
        """Authenticate on first use if `authenticate()` was never called explicitly.

        Returns:
            The authenticated `OqtopusClient` to use for the calling method.

        Raises:
            QdiError: If authentication has not happened and cannot succeed.

        """
        if not self._authenticated:
            self.authenticate({})
        if self._client is None:
            msg = "authenticate() did not establish a usable client."
            raise QdiError(QdiStatus.ERROR_UNKNOWN, msg)
        return self._client

    def discover(self) -> dict:
        """Discover this device's properties, capabilities, and configuration.

        # QDI-GAP(discover-requires-auth): OQTOPUS requires `BearerAuth` on
        # every endpoint, including device lookup, so this transparently
        # authenticates first if needed rather than exposing an
        # unauthenticated discovery mode. See docs/gap-analysis.md#g011.

        Returns:
            The device descriptor as a JSON-compatible dict.

        Raises:
            QdiError: If authentication or the device lookup fails.

        """
        client = self._ensure_authenticated()
        try:
            device = client.get_device(self.device_id)
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        return asdict(build_device_descriptor(device))

    def send(self, task_payload: bytes, task_type: str, shots: int = 100) -> str:
        """Submit an opaque task payload to this device.

        Args:
            task_payload: UTF-8-encoded OPENQASM 3 program bytes.
            task_type: QDI task-type identifier; validated via `map_task_type`.
            shots: Execution shots limit.

        Returns:
            The OQTOPUS job id, used as the QDI task id.

        Raises:
            QdiError: If authentication, job-spec construction, or
                submission fails.

        """
        client = self._ensure_authenticated()
        spec = build_job_spec(
            device_id=self.device_id,
            task_payload=task_payload,
            task_type=task_type,
            shots=shots,
            name=self._name,
            description=self._description,
            transpiler_info=self._transpiler_info,
            simulator_info=self._simulator_info,
            mitigation_info=self._mitigation_info,
        )
        try:
            response = client.submit_job(spec)
        except UserApiError as exc:
            raise QdiError(resolve_qdi_status(exc.status_code), exc.message) from exc
        except OqtopusStorageError as exc:
            # QDI-GAP(send-partial-failure): submit_job()'s S3 upload step
            # can fail independently of its two HTTP calls, with no HTTP
            # status of its own to translate. See docs/gap-analysis.md#g013.
            raise QdiError(QdiStatus.ERROR_CONNECTION_FAILED, str(exc)) from exc
        return response.job_id

    def monitor(self, task_id: str) -> tuple[int, dict]:
        """Query the status of a submitted task.

        Args:
            task_id: OQTOPUS job id returned by `send()`.

        Returns:
            A ``(status, advisory)`` pair. ``advisory`` always carries the
            original OQTOPUS status string; see docs/gap-analysis.md#g006.

        Raises:
            QdiError: If authentication or the status lookup fails.

        """
        client = self._ensure_authenticated()
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
        # See docs/gap-analysis.md#g014.

        Args:
            task_id: OQTOPUS job id returned by `send()`.

        Returns:
            A ``(result_payload, result_type)`` pair. ``result_payload`` is a
            JSON-encoded sampling counts dict; ``result_type`` is always the
            literal ``"counts"`` label (QDI does not standardize this
            string).

        Raises:
            QdiError: If authentication or the result lookup fails, the task
                is not sampling-typed, or results are not ready yet.

        """
        client = self._ensure_authenticated()
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
    # QdiClientProtocol's `estimate_resources(self, ...)` signature exactly.
    def estimate_resources(  # ruff: ignore[no-self-use]
        self,
        task_payload: bytes,
        task_type: str,
        shots: int = 100,
    ) -> dict:
        """Dry-run a task to estimate required resources or cost.

        Always fails: OQTOPUS has no such capability. See
        docs/gap-analysis.md#g001 and docs/qdi-spec-feedback.md#q3.

        Args:
            task_payload: Unused; OQTOPUS never receives this call.
            task_type: Unused; OQTOPUS never receives this call.
            shots: Unused; OQTOPUS never receives this call.

        Raises:
            QdiError: Always, with `QdiStatus.ERROR_ESTIMATION_FAILED`.

        """
        del task_payload, task_type, shots
        msg = (
            "OQTOPUS has no dry-run resource/cost estimation endpoint; its "
            "'estimation' job type performs expectation-value estimation "
            "instead, which is a different capability."
        )
        raise QdiError(QdiStatus.ERROR_ESTIMATION_FAILED, msg)

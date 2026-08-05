# QDI ↔ OQTOPUS Gap Analysis

This document records every point where the QDI (Quantum Device Interface,
v0.1 Conceptual Draft) abstraction and the OQTOPUS Cloud User API do not map
cleanly onto each other. Recording these gaps precisely is a primary
deliverable of this project, not a secondary concern to "make it work."

Whenever code needs to paper over one of these gaps, it carries a
`# QDI-GAP(<id>): ...` marker comment pointing back to the relevant row here.

Some of these gaps trace back to an ambiguity or scope question in the QDI
spec itself, independent of OQTOPUS. Those are cross-referenced to
`docs/qdi-spec-feedback.md`, which records them as questions for the QDI
authors rather than as implementation workarounds.

## Columns

- **ID**: Stable identifier, referenced from code comments.
- **QDI element**: The QDI concept, field, or function involved.
- **OQTOPUS element**: The corresponding OQTOPUS concept, field, or endpoint
  (or "none" if there is no corresponding element).
- **Kind**: One of `missing`, `semantic-mismatch`, `cardinality`, `lossy`,
  `spec-defect`.
- **Severity**: `low` / `medium` / `high`, based on how much it constrains
  or distorts a faithful implementation.
- **Workaround**: What the adapter actually does.
- **Notes**: Supporting detail, including where this was confirmed.

## Gaps

| ID | QDI element | OQTOPUS element | Kind | Severity | Workaround | Notes |
|----|-------------|------------------|------|----------|------------|-------|
| G001 | `qdi_estimate_resources` / `estimate_resources()` | `job_type="estimation"` | semantic-mismatch | high | Always raise `QdiError(QdiStatus.ERROR_ESTIMATION_FAILED, ...)`; `supports_estimation` is reported as `False` in the device descriptor. | OQTOPUS's `estimation` job type refers to expectation-value estimation (VQE-style operator sampling), not a dry-run cost/resource estimate. The two concepts share a name but not a meaning; there is no OQTOPUS equivalent of a pre-submission resource estimate. See `docs/qdi-spec-feedback.md#q3` for the resulting spec question (no status distinguishes "not supported" from "attempted and failed"). |
| G002 | 6 core functions (`qdi_discover`, `qdi_send`, ... `qdi_estimate_resources`) | Multi-device OQTOPUS API (`list_devices`, `device_id` on every job/device call) | cardinality | high | `OqtopusQdiClient` is constructed against exactly one `device_id`; QDI has no concept of addressing multiple devices through one handle. | None of the 6 QDI functions take a device identifier — QDI assumes one handle = one device. OQTOPUS is inherently multi-device. See `docs/qdi-spec-feedback.md#q1`: device selection therefore happens entirely outside any QDI-defined function, so `discover()` can never perform zero-knowledge fleet enumeration, only introspect the one device already chosen. |
| G003 | `device_descriptor.max_shots` | none | missing | medium | Report `None` / omit the field; QDI treats it as required. | OQTOPUS's User API (`openapi.yaml`, `DevicesDeviceInfo` schema) does not publish a per-device shot limit anywhere. |
| G004 | `qdi_authenticate` (credential exchange / handshake) | `OqtopusConfig` + `POST /api-token` (every OQTOPUS operation requires `BearerAuth`, including token creation) | missing | medium | `authenticate()` builds/rebuilds the underlying `OqtopusClient` from a token that was necessarily obtained out-of-band, then verifies it with one `get_api_token_status()` round-trip. All other methods, including `discover()`, trigger this same logic on first use if `authenticate()` was never called explicitly. | This is not a general "cloud APIs can't do handshakes" problem (session-issuing APIs like AWS STS exist) — OQTOPUS specifically has no in-band bootstrap endpoint at all; even `POST /api-token` itself requires a valid bearer token. See `docs/qdi-spec-feedback.md#q2`. |
| G005 | `qdi_send` (single call) | `submit_job()` (`register_job_id` → S3 presigned upload → `submit_job`) | cardinality | high | Do not swallow partial failures; both `UserApiError` (HTTP steps) and `OqtopusStorageError` (S3 upload step; see G013) surface as `QdiError` so the caller knows submission did not fully succeed. | `OqtopusClient.submit_job()` is a 3-step process. QDI's `send()` is a single call with no idempotency key and no way to cancel a half-submitted (registered-but-not-submitted) task, so a failure between steps 1 and 3 can leave an orphaned job registration that QDI has no vocabulary to describe or clean up. |
| G006 | `qdi_task_status` (5 values: QUEUED / EXECUTING / COMPLETED / FAULTED / CANCELLED) | `JobsJobStatus` (7 values: registered / submitted / ready / running / succeeded / failed / cancelled) | cardinality | medium | Collapse `registered`/`submitted`/`ready` → `QUEUED`, `running` → `EXECUTING`, `succeeded` → `COMPLETED`, `failed` → `FAULTED`, `cancelled` → `CANCELLED`. The original OQTOPUS status string is placed in `monitor()`'s advisory dict (e.g. `{"oqtopus_status": "registered"}`) so it isn't silently dropped. | Confirmed against `oqtopus_client.rest.models.jobs_job_status.JobsJobStatus`. Note: an earlier revision of this row also mentioned surfacing a "queue position" in the advisory dict — verified against `JobsGetJobStatusResponse` (only `job_id`/`status`) and `openapi.yaml` (no "queue"/"position" field anywhere in the User API) that no such data exists in OQTOPUS at all, at the per-job level or otherwise. Removed rather than left in as an unverified example. |
| G007 | `qdi_send(payload, task_type, shots)` | `OqtopusJobSpec` (`transpiler_info`, `simulator_info`, `mitigation_info`, `name`, `description`, `operator`) | lossy | medium | Accept these as constructor-level defaults on `OqtopusQdiClient` (set once, out of band); they are not reachable per-call through the QDI `send()` signature. | QDI has no vendor-extension mechanism, so any OQTOPUS-specific job tuning is either fixed at adapter-construction time or unreachable via QDI. |
| G008 | `qdi_status` (flat 9-value enum, no message channel) | `UserApiError(status_code, message, payload)` | lossy | medium | `QdiError` carries a QDI-compliant status code for API conformance, but keeps the original message/payload as Python exception state so nothing is discarded in the Python adapter. | The information loss is real once the C ABI is involved (a `qdi_status` return code alone cannot carry a message), even though the Python-level `QdiError` itself is not lossy. |
| G009 | `qdi_status` vs `qdi_task_status` (distinct enums) | — (reference-implementation bug) | spec-defect | low | Do not imitate. Raise on unrecognized status, or map to an explicit `QDI_TASK_UNKNOWN` sentinel we define ourselves. | `qdi-demo`'s `QdiClient.monitor()` returns `99` for an unrecognized task status. `99` is `QDI_ERROR_UNKNOWN` from the *`qdi_status`* enum — it does not exist in `qdi_task_status` at all. This is a bug in the reference implementation, not a spec requirement. |
| G010 | `estimate_resources()` signature | `NativeQdiClient.estimate_resources(payload, task_type)` vs `QdiClient.estimate_resources(payload, task_type, shots=100)` | spec-defect | low | Match `QdiClient` (the HTTP-facing class we mimic) and include `shots`. | The two reference classes in `qdi_python.py` disagree on the signature of the same conceptual method. |
| G011 | `qdi_discover` (listed before `qdi_authenticate`; no documented auth precondition) | `GET /devices/{device_id}` (requires `BearerAuth`, same as every other operation) | semantic-mismatch | low | `discover()` transparently authenticates first (same on-first-use logic as G004) if not already authenticated, rather than exposing an unauthenticated discovery mode. | qdi.h's ordering and doc comments read as "capabilities can be inspected before deciding to trust the device," which does not hold for OQTOPUS. See `docs/qdi-spec-feedback.md#q4`. |

| G012 | `qdi_status` (9-value flat enum) | HTTP status codes used across `openapi.yaml`: 400 / 401 / 403 / 404 / 500 | cardinality | low | 400→`ERROR_INVALID_ARGUMENT`, 401/403→`ERROR_UNAUTHORIZED`, 404→`ERROR_TASK_NOT_FOUND`, anything else (incl. 500)→`ERROR_UNKNOWN`. | Two separate imprecisions: (1) a 404 from `get_device()` is reported as `ERROR_TASK_NOT_FOUND` even though the missing object is a device, because QDI has no distinct "device not found" code (see also G002); (2) no HTTP status unambiguously corresponds to `ERROR_HARDWARE_FAULT`, so it is never produced by this mapping — a 500 could be a genuine backend/hardware problem or an unrelated server bug, and OQTOPUS's error payload does not reliably distinguish the two. The original message is preserved as `QdiError.detail` regardless (G008). |

| G013 | `qdi_send` (single call, single failure channel implied) | `OqtopusStorage.upload()` raising `OqtopusStorageError` (no HTTP status) | lossy | low | Caught alongside `UserApiError` in `send()` and translated to `QdiError(QdiStatus.ERROR_CONNECTION_FAILED, ...)`. | `OqtopusStorageError` is a distinct exception type from `UserApiError`, with no HTTP status code to feed into the same lookup table as G012; `ERROR_CONNECTION_FAILED` was chosen as the closest fit for a failed network transfer. |
| G014 | `qdi_receive` (no "not ready yet" status) | `OqtopusClient.get_job()` raising `ResponseValidationError` for a job still in the `registered` state | missing | low | Caught in `receive()` and translated to `QdiError(QdiStatus.ERROR_UNKNOWN, ...)`, since no QDI status means "results exist eventually but are not ready yet." | Only the `registered` status is rejected this way by oqtopus-client itself; the other pre-terminal statuses (`submitted`/`ready`/`running`) return successfully from `get_job()` but with empty/absent result content. Same underlying issue as Q3 in `docs/qdi-spec-feedback.md` (no distinct "not yet" status), noted here for the receive side specifically. |

New gaps discovered during implementation should be appended below as
G015, G016, ... — do not renumber or delete earlier entries.

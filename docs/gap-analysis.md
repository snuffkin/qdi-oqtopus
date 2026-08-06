# QDI ↔ OQTOPUS Gap Analysis and QDI Specification Feedback

This document has two parts.

**Part 1, Implementation Gaps (G001-...)** records every point where the
QDI (Quantum Device Interface, v0.1 Conceptual Draft) abstraction and the
OQTOPUS Cloud User API do not map cleanly onto each other. Recording these
gaps precisely is a primary deliverable of this project, not a secondary
concern to "make it work." Whenever code needs to paper over one of these
gaps, it carries a `# QDI-GAP(<id>): ...` marker comment pointing back to
the relevant entry here.

**Part 2, QDI Specification Feedback (Q1-...)** records places where
implementing *against QDI itself*, independent of OQTOPUS, surfaced an
ambiguity, an apparent scope gap, or a design assumption in the spec that
does not hold universally. It is written as input for the QDI authors and
as discussion material for the experience paper, not as an implementation
work-around log. Each entry has two parts: the question we would put to the
QDI spec authors, and the concrete restriction this project accepted in
`OqtopusQdiClient` because the spec does not (yet) say more.

Some Part 1 gaps trace back to a Part 2 question, and vice versa; those are
cross-referenced by ID (e.g. "G002", "Q1") as plain text, not as links.
Table rows have no per-row anchor in the rendered page, so a link to one
would not actually navigate anywhere.

## Part 1: Implementation Gaps

### Columns

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

### Gaps

| ID | QDI element | OQTOPUS element | Kind | Severity | Workaround | Notes |
|----|-------------|------------------|------|----------|------------|-------|
| G001 | `qdi_estimate_resources` / `estimate_resources()` | `job_type="estimation"` | semantic-mismatch | high | Always raise `QdiError(QdiStatus.ERROR_ESTIMATION_FAILED, ...)`; `supports_estimation` is reported as `False` in the device descriptor. | OQTOPUS's `estimation` job type refers to expectation-value estimation (VQE-style operator sampling), not a dry-run cost/resource estimate. The two concepts share a name but not a meaning; there is no OQTOPUS equivalent of a pre-submission resource estimate. See Q3 (no status distinguishes "not supported" from "attempted and failed"). |
| G002 | 6 core functions (`qdi_discover`, `qdi_send`, ... `qdi_estimate_resources`) | Multi-device OQTOPUS API (`list_devices`, `device_id` on every job/device call) | cardinality | high | `OqtopusQdiClient` is constructed against exactly one `device_id`; QDI has no concept of addressing multiple devices through one handle. | None of the 6 QDI functions take a device identifier — QDI assumes one handle = one device. OQTOPUS is inherently multi-device. See Q1: device selection therefore happens entirely outside any QDI-defined function, so `discover()` can never perform zero-knowledge fleet enumeration, only introspect the one device already chosen. |
| G003 | `device_descriptor.max_shots` | none | missing | high | Report the literal `10000` from qdi-demo's `mock_device_config.json`, by explicit project decision (2026-08-06). This is **not** a value derived from OQTOPUS in any way. | OQTOPUS's User API (`openapi.yaml`, `DevicesDeviceInfo` schema) does not publish a per-device shot limit anywhere. Reporting `10000` risks a caller believing it reflects real per-device OQTOPUS data; it does not. Severity raised from `medium` to `high` relative to the previous `None` because an incorrect-looking number is more misleading than an honest absence of data. |
| G004 | `qdi_authenticate` (credential exchange / handshake) | `OqtopusConfig` + `POST /api-token` (every OQTOPUS operation requires `BearerAuth`, including token creation) | missing | medium | `authenticate(credentials_dict)` requires `base_url` and `api_token` in `credentials_dict`, builds the underlying `OqtopusClient` directly from them (no constructor-supplied config, no config-file/env-var fallback), and verifies the result with one `get_api_token_status()` round-trip. Every other method requires `authenticate()` to have been called first and raises `ERROR_UNAUTHORIZED` otherwise; none of them authenticate on the caller's behalf (matching qdi-demo's own clients; see G011). | This is not a general "cloud APIs can't do handshakes" problem (session-issuing APIs like AWS STS exist); OQTOPUS specifically has no in-band bootstrap endpoint at all, and even `POST /api-token` itself requires a valid bearer token. See Q2. |
| G005 | `qdi_send` (single call) | `submit_job()` (`register_job_id` → S3 presigned upload → `submit_job`) | cardinality | high | Do not swallow partial failures; both `UserApiError` (HTTP steps) and `OqtopusStorageError` (S3 upload step; see G013) surface as `QdiError` so the caller knows submission did not fully succeed. | `OqtopusClient.submit_job()` is a 3-step process. QDI's `send()` is a single call with no idempotency key and no way to cancel a half-submitted (registered-but-not-submitted) task, so a failure between steps 1 and 3 can leave an orphaned job registration that QDI has no vocabulary to describe or clean up. |
| G006 | `qdi_task_status` (5 values: QUEUED / EXECUTING / COMPLETED / FAULTED / CANCELLED) | `JobsJobStatus` (7 values: registered / submitted / ready / running / succeeded / failed / cancelled) | cardinality | medium | Collapse `registered`/`submitted`/`ready` → `QUEUED`, `running` → `EXECUTING`, `succeeded` → `COMPLETED`, `failed` → `FAULTED`, `cancelled` → `CANCELLED`. The original OQTOPUS status string is placed in `monitor()`'s advisory dict (e.g. `{"oqtopus_status": "registered"}`) so it isn't silently dropped. | Confirmed against `oqtopus_client.rest.models.jobs_job_status.JobsJobStatus`. Note: an earlier revision of this row also mentioned surfacing a "queue position" in the advisory dict; verified against `JobsGetJobStatusResponse` (only `job_id`/`status`) and `openapi.yaml` (no "queue"/"position" field anywhere in the User API) that no such data exists in OQTOPUS at all, at the per-job level or otherwise. Removed rather than left in as an unverified example. |
| G007 | `qdi_send(payload, task_type, shots)` | `OqtopusJobSpec` (`transpiler_info`, `simulator_info`, `mitigation_info`, `name`, `description`, `operator`) | lossy | medium | `OqtopusQdiClient.send()` accepts these as keyword-only parameters beyond QDI's 3-argument contract, defaulting to `None`/plain OQTOPUS defaults. A caller using only QDI's documented `send(task_payload, task_type, shots)` call shape never touches them. | QDI has no vendor-extension mechanism, so any OQTOPUS-specific job tuning is only reachable by a caller who already knows to step outside the QDI `send()` contract. `operator` (estimation-only) is not exposed at all, since `send()` only ever builds sampling jobs. |
| G008 | `qdi_status` (flat 9-value enum, no message channel) | `UserApiError(status_code, message, payload)` | lossy | medium | `QdiError` carries a QDI-compliant status code for API conformance, but keeps the original message/payload as Python exception state so nothing is discarded in the Python adapter. | The information loss is real once the C ABI is involved (a `qdi_status` return code alone cannot carry a message), even though the Python-level `QdiError` itself is not lossy. |
| G009 | `qdi_status` vs `qdi_task_status` (distinct enums) | none (reference-implementation bug) | spec-defect | low | Do not imitate. Raise on unrecognized status, or map to an explicit `QDI_TASK_UNKNOWN` sentinel we define ourselves. | `qdi-demo`'s `QdiClient.monitor()` returns `99` for an unrecognized task status. `99` is `QDI_ERROR_UNKNOWN` from the *`qdi_status`* enum; it does not exist in `qdi_task_status` at all. This is a bug in the reference implementation, not a spec requirement. |
| G010 | `estimate_resources()` signature | `NativeQdiClient.estimate_resources(payload, task_type)` vs `QdiClient.estimate_resources(payload, task_type, shots=100)` | spec-defect | low | Match `QdiClient` (the HTTP-facing class we mimic) and include `shots`. | The two reference classes in `qdi_python.py` disagree on the signature of the same conceptual method. |
| G011 | `qdi_discover` (listed before `qdi_authenticate`; no documented auth precondition) | `GET /devices/{device_id}` (requires `BearerAuth`, same as every other operation) | semantic-mismatch | medium | `discover()` raises `QdiError(ERROR_UNAUTHORIZED)` if `authenticate()` was not already called; it never authenticates on the caller's behalf. The only usable call order for this adapter is therefore `authenticate()` then `discover()`, the reverse of qdi.h's listed order. | qdi.h's ordering and doc comments read as "capabilities can be inspected before deciding to trust the device," which does not hold for OQTOPUS. Severity raised from `low` to `medium`: this used to be papered over by transparent auto-authentication (a design later reverted to match qdi-demo's own clients, which also require an explicit `authenticate()` call first), so the order reversal is now a real, user-visible behavior difference rather than an internal implementation detail. See Q4. |
| G012 | `qdi_status` (9-value flat enum) | HTTP status codes used across `openapi.yaml`: 400 / 401 / 403 / 404 / 500 | cardinality | low | 400 → `ERROR_INVALID_ARGUMENT`, 401/403 → `ERROR_UNAUTHORIZED`, 404 → `ERROR_TASK_NOT_FOUND`, anything else (incl. 500) → `ERROR_UNKNOWN`. | Two separate imprecisions: (1) a 404 from `get_device()` is reported as `ERROR_TASK_NOT_FOUND` even though the missing object is a device, because QDI has no distinct "device not found" code (see also G002); (2) no HTTP status unambiguously corresponds to `ERROR_HARDWARE_FAULT`, so it is never produced by this mapping; a 500 could be a genuine backend/hardware problem or an unrelated server bug, and OQTOPUS's error payload does not reliably distinguish the two. The original message is preserved as `QdiError.detail` regardless (G008). |
| G013 | `qdi_send` (single call, single failure channel implied) | `OqtopusStorage.upload()` raising `OqtopusStorageError` (no HTTP status) | lossy | low | Caught alongside `UserApiError` in `send()` and translated to `QdiError(QdiStatus.ERROR_CONNECTION_FAILED, ...)`. | `OqtopusStorageError` is a distinct exception type from `UserApiError`, with no HTTP status code to feed into the same lookup table as G012; `ERROR_CONNECTION_FAILED` was chosen as the closest fit for a failed network transfer. |
| G014 | `qdi_receive` (no "not ready yet" status) | `OqtopusClient.get_job()` raising `ResponseValidationError` for a job still in the `registered` state | missing | low | Caught in `receive()` and translated to `QdiError(QdiStatus.ERROR_UNKNOWN, ...)`, since no QDI status means "results exist eventually but are not ready yet." | Only the `registered` status is rejected this way by oqtopus-client itself; the other pre-terminal statuses (`submitted`/`ready`/`running`) return successfully from `get_job()` but with empty/absent result content. Same underlying issue as Q3 (no distinct "not yet" status), noted here for the receive side specifically. |

New gaps discovered during implementation should be appended below as
G015, G016, ... — do not renumber or delete earlier entries.

## Part 2: QDI Specification Feedback

### Q1: How is a `qdi_device_handle` obtained in the first place?

All 6 functions in `qdi.h` (`qdi_discover`, `qdi_authenticate`, `qdi_send`,
`qdi_monitor`, `qdi_receive`, `qdi_estimate_resources`) take an already-valid
`qdi_device_handle` as their first argument. The spec never defines how a
caller acquires that handle before making the first call, including before
calling `qdi_discover` itself, which is the one function whose name
suggests it might answer "what devices exist?" rather than "what can
*this* device do?".

This is a defensible scope boundary for a single, already-selected piece of
hardware (e.g. a lab controller wired to one fixed QPU), where the handle is
presumably constructed by out-of-band host code before any QDI call happens.
It becomes a real question once a "device" is actually a named resource on a
multi-device cloud service:

- Is fleet-level enumeration ("what devices can I talk to?") explicitly out
  of scope for QDI v0.1, deferred to an unspecified higher-level
  registry/discovery mechanism? If so, the draft would benefit from saying so
  directly, given the interface's name.
- If it is in scope, should one of the 6 functions (or a 7th) support calling
  `qdi_discover`-like enumeration *before* a handle exists, rather than only
  after?

**Restriction accepted here:** `OqtopusQdiClient` requires `device_id` as a
constructor argument. Device selection therefore happens entirely outside
any QDI-defined function, via our own Python API, not via `discover()`.
`discover()` itself only ever introspects the single, already-chosen device;
it can never be used for the "what's out there?" sense of discovery. OQTOPUS's
own `list_devices()` (which *does* support fleet-level enumeration) is
consequently unreachable through the QDI surface at all. See also G002.

### Q2: `qdi_authenticate` presumes a credential *exchange*; not every backend offers one

`qdi_authenticate(device, credentials_json)` reads as a live handshake: hand
over credentials, establish trust, presumably receive something (a session,
a scoped token) usable for subsequent calls. That pattern is entirely
reasonable in general; session-issuing handshakes are common in cloud APIs
(e.g. an AWS STS `AssumeRole` call returning temporary credentials used for
later requests). It is *not* a general "cloud APIs can't do this" problem, and
an earlier draft of this document wrongly implied that it was.

The concrete issue is narrower and specific to OQTOPUS: its OpenAPI spec
(`spec/openapi.yaml`) declares `security: [BearerAuth: []]` on *every single
operation*, with no exceptions, including `POST /api-token` (the endpoint
that creates a new bearer token in the first place). There is no operation
that accepts arbitrary credentials and returns a usable token; the only way
to obtain one is out-of-band (the OQTOPUS web portal), before any API call is
possible. In other words, OQTOPUS has no in-band bootstrap or handshake
endpoint at all, not because a handshake wouldn't fit a cloud API in
general, but because this particular API was not designed to offer one.

- Given that some backends (session-issuing APIs) and some backends
  (bootstrap-less, static-bearer-token APIs like OQTOPUS) are both realistic
  targets, should the spec say explicitly that `qdi_authenticate` may
  legitimately do nothing more than *validate* a credential that was
  necessarily obtained out-of-band, for backends with no in-band bootstrap?

**Restriction accepted here:** `authenticate()` on `OqtopusQdiClient` cannot
perform a real credential exchange, because OQTOPUS has none to offer. It
takes `base_url` and `api_token` directly from `credentials_dict` (which
must therefore already hold a token obtained out-of-band), builds a fresh
`OqtopusClient` from them, and performs one real round-trip
(`get_api_token_status()`) to confirm the token actually works, only then
marking the client "authenticated" for subsequent calls. Every other
method requires this to have already happened and raises otherwise; none
of them perform it on the caller's behalf (see Q4). See also G004.

### Q3: Is there a status for "not supported by this device", distinct from "attempted and failed"?

`qdi_status` defines `QDI_ERROR_ESTIMATION_FAILED`, which reads as *"an
estimation was attempted and it failed"*, e.g. a malformed circuit, or a
circuit too large for the device. It does not cleanly cover the different
case where a device has no estimation capability at all, and every call will
fail for that reason, permanently and unconditionally, regardless of the
input. The device descriptor already exposes `supports_estimation: bool`, so
a well-behaved caller could check that flag and skip the call, but nothing
in the spec says what `qdi_estimate_resources` should *itself* return when
called anyway on a device where `supports_estimation` is false.

- Would it be worth adding a distinct status (e.g. `QDI_ERROR_NOT_SUPPORTED`)
  for "this operation is not offered by this device at all", separate from
  "this operation was attempted on a supported device and failed"? The same
  ambiguity would apply to any future capability flag, not just estimation.

**Restriction accepted here:** `OqtopusQdiClient.estimate_resources()` always
raises `QdiError(QdiStatus.ERROR_ESTIMATION_FAILED, ...)`, because OQTOPUS has
no dry-run resource/cost estimation endpoint at all (see G001) and
`ERROR_ESTIMATION_FAILED` is the closest defined code, not a code documented
for this purpose. `supports_estimation` is reported as `False` in the device
descriptor so a caller can avoid the call up front, but the call itself, if
made, cannot distinguish "unsupported" from "attempted and failed" in its
return value.

### Q4: Is `qdi_discover` meant to be callable before `qdi_authenticate`?

`qdi.h` lists `qdi_discover` before `qdi_authenticate`, and `qdi_discover`'s
doc comment does not mention any authentication precondition, which reads as
"you can inspect a device's capabilities before deciding to trust it." For
OQTOPUS this ordering is not available: `GET /devices/{device_id}` requires
`BearerAuth` exactly like every other endpoint, so device capabilities cannot
be inspected before a valid credential is already in hand.

- Does the spec intend `qdi_discover` to be usable pre-authentication (e.g.
  to support "browse what's available, then decide whether to authenticate
  and use it")? If so, that assumption does not hold for backends where
  every endpoint, including capability lookup, is behind authentication.

**Restriction accepted here:** `OqtopusQdiClient.discover()` raises
`QdiError(ERROR_UNAUTHORIZED)` if `authenticate()` has not already
happened, rather than exposing a distinct "unauthenticated discovery"
mode; OQTOPUS does not have one to expose. The practical call order for
this adapter is therefore `authenticate()` then `discover()`, the reverse
of `qdi.h`'s listed order. See also G011.

### Q5: Should QDI's reference implementation publish reusable types, not just concrete clients?

qdi-demo ships two concrete client classes (`QdiClient`, HTTP-facing with
`httpx` baked in; `NativeQdiClient`, a C-ABI wrapper) and no interface or
enum definitions independent of either one. `qdi_status` and
`qdi_task_status` are real, named C enums in `qdi.h`, but `qdi_python.py`
never turns them into a Python enum either: `QdiClient._request()` and
`QdiClient.monitor()` both use raw dict literals (`{401: 2, 404: 4}`,
`{"QUEUED": 0, "EXECUTING": 1, ...}`) instead. None of this is packaged as
an importable library artifact meant for reuse by third-party adapters;
everything lives inside a demo repository whose purpose is to demonstrate
QDI, not to be a dependency.

Because of this, any downstream adapter that wants to structurally conform
to "the QDI client shape," or use `qdi_status`/`qdi_task_status` as actual
typed values instead of magic numbers, has no canonical definition to
import and must hand-derive one by reading `qdi.h`/`qdi_python.py`'s source
and re-typing it independently. That is exactly what
`qdi_oqtopus.protocol.QdiClient`, `qdi_oqtopus.types.QdiStatus`, and
`qdi_oqtopus.types.QdiTaskStatus` are: hand-derived duplicates, maintained
with no dependency relationship to qdi-demo at all. If qdi-demo's
`QdiClient` signature or either enum's values changed upstream, nothing
here would notice.

- Should a future, officially-versioned QDI release publish reusable type
  definitions (e.g. `typing.Protocol` and `enum.IntEnum` for Python, or
  equivalents for other languages) as an installable artifact, so
  downstream adapters can import and conform to the canonical definitions
  directly, instead of every adapter re-deriving its own copy?

**Restriction accepted here:** `qdi_oqtopus.protocol.QdiClient`,
`qdi_oqtopus.types.QdiStatus`, and `qdi_oqtopus.types.QdiTaskStatus` are
hand-derived stopgaps for the v0.1 Conceptual Draft phase, not something
this project expects to maintain indefinitely. Once QDI ships properly
reusable type artifacts, these should be retired in favor of
importing/aliasing the canonical definitions directly.

This is also why `qdi_oqtopus.errors.QdiError`'s constructor keeps a
`status: QdiStatus` parameter rather than matching qdi-demo's own
`QDIError.__init__(self, code, detail=None)` attribute name and (lack of)
type: `code` in qdi-demo is an untyped, bare `int`, precisely the "raw
magic number" pattern this gap is about. Naming the parameter `code` to
match qdi-demo while keeping its type as `QdiStatus` would have been a
reasonable middle ground; typing it as plain `int` to match qdi-demo
exactly was rejected, since every call site in this project already
passes a `QdiStatus` member and always will, making a looser annotation
misleading rather than more faithful.

### Q6: Should `qdi_discover`'s device descriptor have a defined schema?

`qdi.h` describes the descriptor only as "the JSON string detailing device
descriptors," with no fields specified. `QdiClient.discover()` in
`qdi_python.py` does no validation at all: it returns whatever JSON the
server sends, verbatim. The only concrete example anywhere is qdi-demo's
`mock_device_config.json`, which is a mock *server's* configuration file,
not a spec artifact, and mixes 8 fields that look portable (`device_id`,
`display_name`, `supported_auth_methods`, `supported_task_types`,
`is_ready`, `supports_estimation`, `num_qubits`, `max_shots`) with 2 that
are clearly specific to that mock server's own internals (`estimation`,
`task_type_aliases`).

- Should the spec define an actual schema for the device descriptor, even
  an informal minimum field set, so that two independent QDI
  implementations have a way to agree on what `discover()` returns? As
  written, nothing requires them to.

**Restriction accepted here:** `qdi_oqtopus.types.QdiDeviceDescriptor` is
not a duplicate of a QDI-defined structure; QDI never defined one. It is
this project's own inference of a "portable" field set, based on
`mock_device_config.json` with the 2 demo-internal fields excluded. There
is no guarantee another QDI implementation would agree with this
particular set of 8 fields.

New questions found during implementation should be appended as Q7, Q8, ...
— do not renumber or delete earlier entries.

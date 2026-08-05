# QDI Specification Feedback

`docs/gap-analysis.md` records how QDI (v0.1 Conceptual Draft) and OQTOPUS Cloud
were reconciled in this adapter. This document is different: it records places
where implementing *against QDI itself* — independent of OQTOPUS — surfaced an
ambiguity, an apparent scope gap, or a design assumption in the spec that does
not hold universally. It is written as input for the QDI authors and as
discussion material for the experience paper, not as an implementation
work-around log.

Each entry has two parts: the question we would put to the QDI spec authors,
and the concrete restriction this project accepted in `OqtopusQdiClient`
because the spec does not (yet) say more.

## Q1: How is a `qdi_device_handle` obtained in the first place?

All 6 functions in `qdi.h` (`qdi_discover`, `qdi_authenticate`, `qdi_send`,
`qdi_monitor`, `qdi_receive`, `qdi_estimate_resources`) take an already-valid
`qdi_device_handle` as their first argument. The spec never defines how a
caller acquires that handle before making the first call — including before
calling `qdi_discover` itself, which is the one function whose name suggests
it might answer "what devices exist?" rather than "what can *this* device
do?".

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
constructor argument — i.e. device selection happens entirely outside any
QDI-defined function, via our own Python API, not via `discover()`.
`discover()` itself only ever introspects the single, already-chosen device;
it can never be used for the "what's out there?" sense of discovery. OQTOPUS's
own `list_devices()` (which *does* support fleet-level enumeration) is
consequently unreachable through the QDI surface at all. See also
`docs/gap-analysis.md#g002`.

## Q2: `qdi_authenticate` presumes a credential *exchange*; not every backend offers one

`qdi_authenticate(device, credentials_json)` reads as a live handshake: hand
over credentials, establish trust, presumably receive something (a session,
a scoped token) usable for subsequent calls. That pattern is entirely
reasonable in general — session-issuing handshakes are common in cloud APIs
(e.g. an AWS STS `AssumeRole` call returning temporary credentials used for
later requests). It is *not* a general "cloud APIs can't do this" problem, and
an earlier draft of this document wrongly implied that it was.

The concrete issue is narrower and specific to OQTOPUS: its OpenAPI spec
(`spec/openapi.yaml`) declares `security: [BearerAuth: []]` on *every single
operation*, with no exceptions — including `POST /api-token` (the endpoint
that creates a new bearer token in the first place). There is no operation
that accepts arbitrary credentials and returns a usable token; the only way
to obtain one is out-of-band (the OQTOPUS web portal), before any API call is
possible. In other words, OQTOPUS has no in-band bootstrap or handshake
endpoint at all — not because a handshake wouldn't fit a cloud API in
general, but because this particular API was not designed to offer one.

- Given that some backends (session-issuing APIs) and some backends
  (bootstrap-less, static-bearer-token APIs like OQTOPUS) are both realistic
  targets, should the spec say explicitly that `qdi_authenticate` may
  legitimately do nothing more than *validate* a credential that was
  necessarily obtained out-of-band, for backends with no in-band bootstrap?

**Restriction accepted here:** `authenticate()` on `OqtopusQdiClient` cannot
perform a real credential exchange, because OQTOPUS has none to offer. It
builds (or rebuilds) the underlying `OqtopusClient` from the supplied/
constructor-time token and performs one real round-trip
(`get_api_token_status()`) to confirm the token actually works, only then
marking the client "authenticated" for subsequent calls. Every other method,
including `discover()` (see Q4), calls this same logic on first use if
`authenticate()` was never called explicitly. See also
`docs/gap-analysis.md#g004`.

## Q3: Is there a status for "not supported by this device", distinct from "attempted and failed"?

`qdi_status` defines `QDI_ERROR_ESTIMATION_FAILED`, which reads as *"an
estimation was attempted and it failed"* — e.g. a malformed circuit, or a
circuit too large for the device. It does not cleanly cover the different
case where a device has no estimation capability at all, and every call will
fail for that reason, permanently and unconditionally, regardless of the
input. The device descriptor already exposes `supports_estimation: bool`, so
a well-behaved caller could check that flag and skip the call — but nothing
in the spec says what `qdi_estimate_resources` should *itself* return when
called anyway on a device where `supports_estimation` is false.

- Would it be worth adding a distinct status (e.g. `QDI_ERROR_NOT_SUPPORTED`)
  for "this operation is not offered by this device at all", separate from
  "this operation was attempted on a supported device and failed"? The same
  ambiguity would apply to any future capability flag, not just estimation.

**Restriction accepted here:** `OqtopusQdiClient.estimate_resources()` always
raises `QdiError(QdiStatus.ERROR_ESTIMATION_FAILED, ...)`, because OQTOPUS has
no dry-run resource/cost estimation endpoint at all (see
`docs/gap-analysis.md#g001`) and `ERROR_ESTIMATION_FAILED` is the closest
defined code, not a code documented for this purpose. `supports_estimation`
is reported as `False` in the device descriptor so a caller can avoid the
call up front, but the call itself, if made, cannot distinguish
"unsupported" from "attempted and failed" in its return value.

## Q4: Is `qdi_discover` meant to be callable before `qdi_authenticate`?

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

**Restriction accepted here:** `OqtopusQdiClient.discover()` transparently
authenticates first (using the same on-first-use logic described in Q2) if
it has not already happened, rather than exposing a distinct "unauthenticated
discovery" mode — OQTOPUS does not have one to expose.

New questions found during implementation should be appended as Q5, Q6, ...
— do not renumber or delete earlier entries.

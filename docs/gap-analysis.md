# QDI ↔ OQTOPUS Gap Analysis and Questions for QDI

Target QDI spec version: 0.2 (August 2026)
Previously evaluated against: 0.1 (May 2026)

`qdi_oqtopus.protocol.QdiClient` and `qdi_oqtopus.types.QdiStatus`/
`QdiTaskStatus` are hand-derived duplicates of qdi-demo's own classes.
Once it becomes an importable package, this project will use it.

## Part 1: Implementation Gaps

### Fundamental Spec Differences

| ID | QDI element | Details |
|----|-------------|---------|
| G1 | `qdi_task_status` (5 values) | **Workaround:** QDI's 5 statuses and OQTOPUS's 7 statuses differ, so they are mapped as shown in the table below. **Notes:** v0.2 §3.3 explicitly permits advisory metadata beyond the five core states, and §4 requires any sub-codes to roll up to those five states. This project's 7-to-5 collapse is now spec-sanctioned, not merely a workaround. |

#### G1: `qdi_task_status` ↔ `JobsJobStatus` mapping

| QDI `QdiTaskStatus`  | OQTOPUS `JobsJobStatus` |
|----------------------|-------------------------|
| `QUEUED`             | `registered`            |
| `QUEUED`             | `submitted`             |
| `QUEUED`             | `ready`                 |
| `EXECUTING`          | `running`               |
| `COMPLETED`          | `succeeded`             |
| `FAULTED`            | `failed`                |
| `CANCELLED`          | `cancelled`             |

QDI should stay general-purpose rather than growing OQTOPUS-specific
statuses. For G1, formalizing this as a mapping spec seems like the right
direction, rather than adding new QDI statuses to match OQTOPUS's 7 values
one-to-one.

### OQTOPUS Limitations

G4 is not supported by OQTOPUS today; we would like to consider
supporting it in the near future.

| ID | QDI element | Details |
|----|-------------|---------|
| G2 | `qdi_estimate_resources` | **Workaround:** Always raise `QdiError(ERROR_ESTIMATION_FAILED)`. **Notes:** OQTOPUS has no dry-run resource/cost estimation capability. v0.2 §3.5 downgrades Resource Estimation to `[OPTIONAL]`; a device can now conform simply by declaring `supports_estimation: false`, which matches this project's existing behavior. See Q3 (answered in v0.2). |
| G4 | `qdi_authenticate` | **Workaround:** Call OQTOPUS's `get_api_token_status()` API to validate `base_url`/`api_token`. **Notes:** OQTOPUS has no standalone authenticate interface; it requires `BearerAuth` on every endpoint, including `discover()`, so the only usable call order is `authenticate()` then `discover()`. v0.2 §2.2 natively supports bearer tokens and allows the `Authenticate` handshake to be skipped when a valid token is provided directly, but OQTOPUS's own workaround here is unaffected, and the call-order constraint still holds. |

## Part 2: Questions for QDI

| ID | Asked against | Status |
|----|---------------|--------|
| Q1 | v0.1 | answered in v0.2 (§3) |
| Q2 | v0.1 | answered in v0.2 (§3.1, §3.2) |
| Q3 | v0.1 | answered in v0.2 (§3.1) |
| Q4 | v0.1 | answered in v0.2 (§4) |

### Q1: Is it correct that `OqtopusQdiClient` accepts `device_id` in its constructor?

qdi-demo's Python `QdiClient` does not use `device_id` at all. Since
OQTOPUS requires one, this project added it as a constructor argument on
`OqtopusQdiClient`. Is this approach correct? An alternative would be to
add `device_id` to each operation instead.

*Asked against: v0.1. Answered in v0.2 (§3).*

**Answer:** §3 states that all operations except Discover MUST explicitly
target a `device_id`, and that Discover itself MUST return a list of
devices. `OqtopusQdiClient` was updated accordingly: `discover()` returns
every available device, and `send()`/`monitor()`/`receive()`/
`estimate_resources()` each take `device_id`. The constructor no longer
accepts or defaults `device_id`.

### Q2: Is exposing OQTOPUS-specific fields as extra keyword-only parameters on `send()` the right way to bridge QDI's vendor-extension gap?

QDI's `send(payload, task_type, shots)` contract has no vendor-extension
mechanism, so a richer backend's extra parameters (e.g. `transpiler_info`)
have no defined place to go.
`OqtopusQdiClient.send()` accepts OQTOPUS's extra `OqtopusJobSpec` fields
as keyword-only parameters beyond QDI's 3-argument contract.
Is this an acceptable way to bridge the gap.

*Asked against: v0.1. Answered in v0.2 (§3.1, §3.2).*

**Answer:** §3.1 adds a `supported_extensions` descriptor field, and §3.2
adds a matching `extensions` parameter on `send()`, with undeclared keys
required to be rejected rather than silently dropped. The individual
keyword-only parameters were replaced with a single `extensions` mapping,
validated against a `_SUPPORTED_EXTENSIONS` list shared between descriptor
construction and validation.

### Q3: Should QDI add a status for "not supported by this device", distinct from "attempted and failed"?

OQTOPUS has no resource-estimation capability, so `estimate_resources()`
must fail whenever it is called. It currently returns
`QDI_ERROR_ESTIMATION_FAILED`, but that code cannot distinguish "attempted
and failed" from "not supported at all." Should `QdiStatus` add an
"operation not supported" code for this case?

*Asked against: v0.1. Answered in v0.2 (§3.1).*

**Answer:** §3.1 adds `supports_estimation` to the Discover descriptor, so
a Host can determine before ever calling `estimate_resources()` whether a
device supports it at all. Given that, this project no longer sees a need
for a dedicated status code: a spec-compliant Host checks
`supports_estimation` first and simply does not call
`estimate_resources()` on a device that reports `false`. For a Host that
calls it anyway, `ERROR_ESTIMATION_FAILED` is sufficient.

### Q4: Is it acceptable to map to the closest existing `QdiStatus` when no code corresponds exactly?

Example: OQTOPUS's `OqtopusStorageError` (an S3 upload failure during
`send()`, with no HTTP status of its own) has no exact `QdiStatus`
equivalent; `OqtopusQdiClient.send()` currently maps it to the closest
existing code, `QdiError(ERROR_CONNECTION_FAILED)`, even though it isn't a
perfect match. For now, this project proceeds with approximating using
existing codes.

*Asked against: v0.1. Answered in v0.2 (§4).*

**Answer:** §4 states: "When mapping complex driver errors to QDI,
implementations MUST map to the closest standard error code." This
confirms the approximation approach this project already took.

## Version History

### v0.2

- G3 (`max_shots`) removed: no longer a required descriptor field per
  §3.1. OQTOPUS still publishes no per-device shot limit, but QDI no
  longer asks.
- Q1 resolved.
- Q2 resolved.
- Q3 resolved.
- Q4 resolved.

### v0.1

To be back-filled with the original v0.1 evaluation: initial G1-G4, Q1-Q4.

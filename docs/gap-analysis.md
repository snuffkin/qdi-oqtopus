# QDI ↔ OQTOPUS Gap Analysis and Questions for QDI

`qdi_oqtopus.protocol.QdiClient` and `qdi_oqtopus.types.QdiStatus`/
`QdiTaskStatus` are hand-derived duplicates of qdi-demo's own classes.
Once it becomes an importable package, this project will use it.

## Part 1: Implementation Gaps

### Fundamental Spec Differences

| ID | QDI element | Details |
|----|-------------|---------|
| G1 | `qdi_task_status` (5 values) | **Workaround:** QDI's 5 statuses and OQTOPUS's 7 statuses differ, so they are mapped as shown in the table below. |

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

G3 and G4 are not supported by OQTOPUS today; we would like to consider
supporting them in the near future.

| ID | QDI element | Details |
|----|-------------|---------|
| G2 | `qdi_estimate_resources` | **Workaround:** Always raise `QdiError(ERROR_ESTIMATION_FAILED)`. **Notes:** OQTOPUS has no dry-run resource/cost estimation capability. See Q3. |
| G3 | `device_descriptor.max_shots` | **Workaround:** Report a hardcoded `10000`. **Notes:** OQTOPUS publishes no per-device shot limit; this needs to be addressed on OQTOPUS's side. |
| G4 | `qdi_authenticate` | **Workaround:** Call OQTOPUS's `get_api_token_status()` API to validate `base_url`/`api_token`. **Notes:** OQTOPUS has no standalone authenticate interface; it requires `BearerAuth` on every endpoint, including `discover()`, so the only usable call order is `authenticate()` then `discover()`. |

## Part 2: Questions for QDI

### Q1: Is it correct that `OqtopusQdiClient` accepts `device_id` in its constructor?

qdi-demo's Python `QdiClient` does not use `device_id` at all. Since
OQTOPUS requires one, this project added it as a constructor argument on
`OqtopusQdiClient`. Is this approach correct? An alternative would be to
add `device_id` to each operation instead.

### Q2: Is exposing OQTOPUS-specific fields as extra keyword-only parameters on `send()` the right way to bridge QDI's vendor-extension gap?

QDI's `send(payload, task_type, shots)` contract has no vendor-extension
mechanism, so a richer backend's extra parameters (e.g. `transpiler_info`)
have no defined place to go.
`OqtopusQdiClient.send()` accepts OQTOPUS's extra `OqtopusJobSpec` fields
as keyword-only parameters beyond QDI's 3-argument contract.
Is this an acceptable way to bridge the gap.

### Q3: Should QDI add a status for "not supported by this device", distinct from "attempted and failed"?

OQTOPUS has no resource-estimation capability, so `estimate_resources()`
must fail whenever it is called. It currently returns
`QDI_ERROR_ESTIMATION_FAILED`, but that code cannot distinguish "attempted
and failed" from "not supported at all." Should `QdiStatus` add an
"operation not supported" code for this case?

### Q4: Is it acceptable to map to the closest existing `QdiStatus` when no code corresponds exactly?

Example: OQTOPUS's `OqtopusStorageError` (an S3 upload failure during
`send()`, with no HTTP status of its own) has no exact `QdiStatus`
equivalent; `OqtopusQdiClient.send()` currently maps it to the closest
existing code, `QdiError(ERROR_CONNECTION_FAILED)`, even though it isn't a
perfect match. For now, this project proceeds with approximating using
existing codes.

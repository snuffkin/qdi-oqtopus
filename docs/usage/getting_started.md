# Getting Started

`qdi-oqtopus` implements the client-side method surface of QDI (Quantum
Device Interface, v0.1 Conceptual Draft) on top of [OQTOPUS
Cloud](https://github.com/oqtopus-team/oqtopus-client). `OqtopusQdiClient`
exposes the same 6 methods as QDI's `QdiClient` — `discover`, `authenticate`,
`send`, `monitor`, `receive`, and `estimate_resources` — while talking to
OQTOPUS underneath.

Every place where QDI and OQTOPUS do not map cleanly onto each other is
tracked in [Gap Analysis](../gap-analysis.md); this guide focuses on the
parts that do work.

## Installation

```shell
uv add qdi-oqtopus
```

## Configuration

`OqtopusQdiClient` is bound to exactly one OQTOPUS device (see
[gap G002](../gap-analysis.md)) and needs an OQTOPUS API token to do
anything. The token can come from a config file, from environment
variables, or be supplied later via `authenticate()`:

```python
from oqtopus_client.services.config import OqtopusConfig
from qdi_oqtopus.client import OqtopusQdiClient

# Option 1: load base_url/api_token from ~/.config/oqtopus/config.ini
config = OqtopusConfig.from_file()

# Option 2: load from the OQTOPUS_BASE_URL / OQTOPUS_API_TOKEN
# environment variables instead
# config = OqtopusConfig.from_env()

client = OqtopusQdiClient("your-device-id", config)
```

Replace `"your-device-id"` with a device id from your OQTOPUS account (e.g.
listed via `OqtopusClient(config).list_devices()` — QDI itself has no
multi-device listing operation; see [gap G002](../gap-analysis.md)).

## Discovering the device

```python
descriptor = client.discover()
print(descriptor["is_ready"], descriptor["num_qubits"])
```

The first call to any method (including `discover()`) transparently
authenticates the underlying OQTOPUS client if `authenticate()` was not
called explicitly first; see [gap G011](../gap-analysis.md).

## Submitting a task

QDI tasks are opaque payload bytes plus a format identifier. OQTOPUS only
accepts OPENQASM 3 programs (`"openqasm3"` / `"qasm3"`; anything else raises
`QdiError` with `ERROR_UNSUPPORTED_FORMAT`):

```python
program = b"""
OPENQASM 3;
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
"""

task_id = client.send(program, "openqasm3", shots=1000)
```

## Polling for status

```python
from qdi_oqtopus.types import QdiTaskStatus

status, advisory = client.monitor(task_id)
print(QdiTaskStatus(status).name, advisory)
```

`advisory` always carries OQTOPUS's original 7-value status string under
`"oqtopus_status"`, since QDI's 5-value `QdiTaskStatus` cannot represent it
exactly; see [gap G006](../gap-analysis.md).

## Retrieving results

Once `monitor()` reports `COMPLETED`:

```python
import json

payload, result_type = client.receive(task_id)
counts = json.loads(payload)
print(result_type, counts)
```

## What doesn't work

`estimate_resources()` always raises `QdiError` with
`ERROR_ESTIMATION_FAILED`: OQTOPUS has no dry-run resource/cost estimation
endpoint at all; see [gap G001](../gap-analysis.md).

```python
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiStatus

try:
    client.estimate_resources(program, "openqasm3", shots=1000)
except QdiError as exc:
    assert exc.status == QdiStatus.ERROR_ESTIMATION_FAILED
```

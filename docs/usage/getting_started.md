# Getting Started

`qdi-oqtopus` implements the client-side method surface of QDI (Quantum
Device Interface, v0.2) on top of OQTOPUS Cloud. It uses
[`oqtopus-client`](https://oqtopus-client.readthedocs.io/) to talk to
OQTOPUS Cloud, and exposes the same 6 methods as QDI's
[`QdiClient`](https://github.com/shassinger/qdi-demo/blob/main/qdi-core/python/qdi_python.py):
`discover`, `authenticate`, `send`, `monitor`, `receive`, and
`estimate_resources`.

Every place where QDI and OQTOPUS do not map cleanly onto each other is
tracked in [Gap Analysis](../gap-analysis.md). This guide focuses on the
parts that do work.

## Installation

`qdi-oqtopus` is not yet published to PyPI. The following is the planned
installation method once it is released:

```shell
pip install qdi-oqtopus
```

## Connecting

`OqtopusQdiClient` is scoped to one OQTOPUS connection, not one device:
QDI v0.2 requires every operation except Discover to target a device
explicitly, so the client itself takes no device id at construction time.

```python
from qdi_oqtopus.client import OqtopusQdiClient

client = OqtopusQdiClient()
```

## Authenticating

`authenticate()` must be called explicitly before any other method: no
method authenticates on the caller's behalf (see docs/gap-analysis.md, gap
G4). It requires `base_url` and `api_token` directly in
`credentials_dict`. `oqtopus-client`'s own `OqtopusConfig` is a convenient
way to resolve these values from a config file or environment variables
instead of hardcoding them; see [its getting started
guide](https://oqtopus-client.readthedocs.io/en/latest/usage/getting_started/)
for the full set of options.

```python
from oqtopus_client.services.config import OqtopusConfig

# Option 1: load base_url/api_token from ~/.config/oqtopus/config.ini
config = OqtopusConfig.from_file()

# Option 2: load from the OQTOPUS_BASE_URL / OQTOPUS_API_TOKEN
# environment variables instead
# config = OqtopusConfig.from_env()

client.authenticate({"base_url": config.base_url, "api_token": config.api_token})
```

## Discovering devices

`discover()` returns one descriptor per available device:

```python
descriptors = client.discover()
for descriptor in descriptors:
    print(descriptor["device_id"], descriptor["is_ready"], descriptor["num_qubits"])

device_id = descriptors[0]["device_id"]
```

`discover()`, like every other method, raises `QdiError` with
`ERROR_UNAUTHORIZED` if `authenticate()` was not called first. `qdi.h`
lists `discover` before `authenticate`; for this adapter the usable order
is the reverse (see docs/gap-analysis.md, gap G4).

## Submitting a task

QDI tasks are opaque payload bytes plus a format identifier. OQTOPUS only
accepts OPENQASM 3 programs (`"openqasm3"` / `"qasm3"`; anything else raises
`QdiError` with `ERROR_UNSUPPORTED_FORMAT`). Every operation past Discover
takes the target `device_id` explicitly:

```python
program = b"""
OPENQASM 3;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
"""

task_id = client.send(device_id, program, "openqasm3", shots=1000)
```

### Vendor-specific extensions

OQTOPUS-specific parameters (e.g. `transpiler_info`) are passed through the
`extensions` mapping. Only the keys a device declares in its descriptor's
`supported_extensions` are accepted; any other key is rejected with
`QdiError(ERROR_INVALID_ARGUMENT)` rather than silently dropped:

```python
task_id = client.send(
    device_id,
    program,
    "openqasm3",
    shots=1000,
    extensions={"transpiler_info": {"transpiler_lib": "qiskit"}},
)
```

## Polling for status

```python
from qdi_oqtopus.types import QdiTaskStatus

status, advisory = client.monitor(device_id, task_id)
print(QdiTaskStatus(status).name, advisory)
```

`advisory` always carries OQTOPUS's original 7-value status string under
`"oqtopus_status"`, since QDI's 5-value `QdiTaskStatus` cannot represent it
exactly (see docs/gap-analysis.md, gap G1).

## Retrieving results

Once `monitor()` reports `COMPLETED`:

```python
import json

payload, result_type = client.receive(device_id, task_id)
counts = json.loads(payload)
print(result_type, counts)
```

## What doesn't work

`estimate_resources()` always raises `QdiError` with
`ERROR_ESTIMATION_FAILED`: OQTOPUS has no dry-run resource/cost estimation
endpoint at all (see docs/gap-analysis.md, gap G2).

```python
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiStatus

try:
    client.estimate_resources(device_id, program, "openqasm3", shots=1000)
except QdiError as exc:
    assert exc.status == QdiStatus.ERROR_ESTIMATION_FAILED
```

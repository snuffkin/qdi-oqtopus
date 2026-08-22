# Getting Started

`qdi-oqtopus` implements the client-side method surface of QDI (Quantum
Device Interface, v0.2) on top of OQTOPUS Cloud. It uses
[`oqtopus-client`](https://oqtopus-client.readthedocs.io/) to talk to
OQTOPUS Cloud, and exposes the same 6 methods, with signatures following
qdi-demo's server-side
[`NativeQdiClient`](https://github.com/shassinger/qdi-demo/blob/main/qdi-core/python/qdi_python.py):
`discover`, `authenticate`, `send`, `monitor`, `receive`, and
`estimate_resources`.

## Installation

`qdi-oqtopus` is not yet published to PyPI. The following is the planned
installation method once it is released:

```shell
pip install qdi-oqtopus
```

## Connecting

`OqtopusQdiClient` is scoped to one OQTOPUS connection, not one device,
and takes no device id at construction time:

```python
from qdi_oqtopus.client import OqtopusQdiClient

client = OqtopusQdiClient()
```

Every device-scoped operation below (`authenticate`, `send`, `monitor`,
`receive`, `estimate_resources`) takes the target `device_id` explicitly
instead; only `discover()` operates across every device on the account.

## Authenticating

`authenticate()` must be called explicitly before any other method: no
method authenticates on the caller's behalf. It requires `base_url` and
`api_token` directly in `credentials_dict`. `oqtopus-client`'s own `OqtopusConfig` is a convenient
way to resolve these values from a config file or environment variables
instead of hardcoding them; see [its getting started
guide](https://oqtopus-client.readthedocs.io/en/latest/usage/getting_started/)
for the full set of options.

`authenticate()` also takes a `device_id`, to match qdi.h's
`qdi_authenticate` signature, but OQTOPUS ignores it: token validation is
platform-wide, not per device.

```python
from oqtopus_client.services.config import OqtopusConfig

# Option 1: load base_url/api_token from ~/.config/oqtopus/config.ini
config = OqtopusConfig.from_file()

# Option 2: load from the OQTOPUS_BASE_URL / OQTOPUS_API_TOKEN
# environment variables instead
# config = OqtopusConfig.from_env()

device_id = "your-device-id"  # any id from client.discover()["devices"]
client.authenticate(
    device_id, {"base_url": config.base_url, "api_token": config.api_token}
)
```

## Discovering devices

```python
devices = client.discover()["devices"]
for device in devices:
    print(device["device_id"], device["is_ready"], device["num_qubits"])
```

`discover()` returns a mapping with a single `"devices"` key, holding one
descriptor per available device. Like every other method, it raises
`QdiError` with `ERROR_UNAUTHORIZED` if `authenticate()` was not called
first.

## Submitting a task

QDI tasks are opaque payload bytes plus a format identifier. OQTOPUS only
accepts OPENQASM 3 programs (`"openqasm3"` / `"qasm3"`; anything else raises
`QdiError` with `ERROR_UNSUPPORTED_FORMAT`):

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

## Polling for status

```python
from qdi_oqtopus.types import QdiTaskStatus

status, advisory = client.monitor(device_id, task_id)
print(QdiTaskStatus(status).name, advisory)
```

`status` is one of QDI's 5 `QdiTaskStatus` values, mapped from OQTOPUS's
7-value job status as follows:

| `QdiTaskStatus` | OQTOPUS status |
|-----------------|-----------------|
| `QUEUED`        | `registered`    |
| `QUEUED`        | `submitted`     |
| `QUEUED`        | `ready`         |
| `EXECUTING`     | `running`       |
| `COMPLETED`     | `succeeded`     |
| `FAULTED`       | `failed`        |
| `CANCELLED`     | `cancelled`     |

`advisory` always carries OQTOPUS's original status string under
`"oqtopus_status"`, so it is not lost by this mapping.

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
endpoint at all.

```python
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiStatus

try:
    client.estimate_resources(device_id, program, "openqasm3", shots=1000)
except QdiError as exc:
    assert exc.status == QdiStatus.ERROR_ESTIMATION_FAILED
```

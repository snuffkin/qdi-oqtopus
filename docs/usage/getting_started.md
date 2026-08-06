# Getting Started

`qdi-oqtopus` implements the client-side method surface of QDI (Quantum
Device Interface, v0.1 Conceptual Draft) on top of OQTOPUS Cloud. It uses
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

`OqtopusQdiClient` is bound to exactly one OQTOPUS device (see
docs/gap-analysis.md, gap G002) and takes only a device id at construction
time:

```python
from qdi_oqtopus.client import OqtopusQdiClient

client = OqtopusQdiClient("your-device-id")
```

Replace `"your-device-id"` with a device id from your OQTOPUS account, e.g.
one listed via `OqtopusClient(config).list_devices()` (QDI itself has no
multi-device listing operation; see docs/gap-analysis.md, gap G002).

## Authenticating

`authenticate()` must be called explicitly before any other method: no
method authenticates on the caller's behalf (see docs/gap-analysis.md, gap
G004 and gap G011). It requires `base_url` and `api_token` directly in
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

## Discovering the device

```python
descriptor = client.discover()
print(descriptor["is_ready"], descriptor["num_qubits"])
```

`discover()`, like every other method, raises `QdiError` with
`ERROR_UNAUTHORIZED` if `authenticate()` was not called first. `qdi.h`
lists `discover` before `authenticate`; for this adapter the usable order
is the reverse (see docs/gap-analysis.md, gap G011).

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
exactly (see docs/gap-analysis.md, gap G006).

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
endpoint at all (see docs/gap-analysis.md, gap G001).

```python
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiStatus

try:
    client.estimate_resources(program, "openqasm3", shots=1000)
except QdiError as exc:
    assert exc.status == QdiStatus.ERROR_ESTIMATION_FAILED
```

"""Run a 2-qubit Bell state circuit on OQTOPUS through the QDI adapter.

Submits an OPENQASM 3 Bell state circuit with 1000 shots via `send()`,
polls `monitor()` until the task reaches a terminal state, then reads the
sampling counts back with `receive()`.

Usage:
    python examples/bell_state.py <device_id>

Requires OQTOPUS credentials resolvable via `OqtopusConfig.from_file()`;
see https://oqtopus-client.readthedocs.io/en/latest/usage/getting_started/
for how to set up ``~/.config/oqtopus/config.ini``.
"""

import json
import sys
import time

from oqtopus_client.services.config import OqtopusConfig

from qdi_oqtopus.client import OqtopusQdiClient
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiTaskStatus

TASK_PAYLOAD = b"""
OPENQASM 3;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
"""

SHOTS = 1000
POLL_INTERVAL_SECONDS = 5.0

_TERMINAL_STATUSES = {
    QdiTaskStatus.COMPLETED,
    QdiTaskStatus.FAULTED,
    QdiTaskStatus.CANCELLED,
}


def run_bell_state(device_id: str) -> None:
    """Submit the Bell state circuit to `device_id` and print the resulting counts.

    Calls `authenticate()` before `discover()`: every method other than
    `authenticate()` itself requires it to have already been called, the
    reverse of qdi.h's listed order (see docs/gap-analysis.md, gap G011).
    """
    client = OqtopusQdiClient(device_id)

    config = OqtopusConfig.from_file()
    client.authenticate({"base_url": config.base_url, "api_token": config.api_token})
    print("authenticate: ok")

    descriptor = client.discover()
    print(
        f"discover: is_ready={descriptor['is_ready']} "
        f"num_qubits={descriptor['num_qubits']}"
    )

    task_id = client.send(TASK_PAYLOAD, "openqasm3", shots=SHOTS)
    print(f"send: submitted task {task_id!r} ({SHOTS} shots)")

    status = QdiTaskStatus.QUEUED
    while status not in _TERMINAL_STATUSES:
        time.sleep(POLL_INTERVAL_SECONDS)
        raw_status, advisory = client.monitor(task_id)
        status = QdiTaskStatus(raw_status)
        print(f"status={status.name} advisory={advisory}")

    if status != QdiTaskStatus.COMPLETED:
        print(f"Task did not complete successfully: {status.name}")
        return

    payload, result_type = client.receive(task_id)
    counts = json.loads(payload)
    print(f"result_type={result_type!r}")
    print("counts:")
    for bitstring, count in sorted(counts.items()):
        print(f"  {bitstring}: {count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <device_id>", file=sys.stderr)
        sys.exit(1)
    try:
        run_bell_state(sys.argv[1])
    except QdiError as exc:
        print(f"QDI operation failed ({exc.status.name}): {exc}", file=sys.stderr)
        sys.exit(1)

"""qdi-oqtopus version of qdi-demo's full-lifecycle demo, against OQTOPUS.

See:
https://github.com/shassinger/qdi-demo/blob/main/qdi-core/python/test_qdi.py

Exercises authenticate() -> discover() -> send() -> monitor() -> receive()
against a real OQTOPUS device, then demonstrates estimate_resources()'s
documented failure (see docs/gap-analysis.md, gap G001).

``OqtopusQdiClient`` requires `authenticate()` to be called before any
other method, exactly like qdi-demo's ``NativeQdiClient``, so this script
first confirms that calling `discover()` too early fails the same way
qdi-demo's own script confirms `send()` before `authenticate()` fails.
Unlike qdi-demo, `discover()` is the method that requires authentication
first here, not `send()` (see docs/gap-analysis.md, gap G011): OQTOPUS
requires `BearerAuth` on every endpoint, including device lookup, so the
usable call order is the reverse of qdi.h's listed order.

Usage:
    python examples/test_qdi.py <device_id>

BASE_URL, API_TOKEN, and BAD_API_TOKEN below are placeholders; edit them to
match your real OQTOPUS environment before running this script for real.
"""

import sys
import time

from qdi_oqtopus.client import OqtopusQdiClient
from qdi_oqtopus.errors import QdiError
from qdi_oqtopus.types import QdiStatus, QdiTaskStatus

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
MONITOR_ATTEMPTS = 5
POLL_INTERVAL_SECONDS = 5

_TERMINAL_STATUSES = {
    QdiTaskStatus.COMPLETED,
    QdiTaskStatus.FAULTED,
    QdiTaskStatus.CANCELLED,
}

BASE_URL = "https://oqtopus.domain"
API_TOKEN = "valid-token"
BAD_API_TOKEN = "not-a-real-token"


def test_full_lifecycle(device_id: str) -> None:
    """Run authenticate, discover, send, monitor, receive, and estimate_resources."""
    print("Initializing QDI client...")
    client = OqtopusQdiClient(device_id)

    print("Attempting Discover before authenticating (should fail)...")
    try:
        client.discover()
    except QdiError as exc:
        assert exc.status == QdiStatus.ERROR_UNAUTHORIZED
        print("Successfully caught expected error (unauthorized):", exc)
    else:
        msg = "discover() should fail before authenticate() is called"
        raise AssertionError(msg)

    print("Attempting Authenticate with a bad token (should fail)...")
    try:
        client.authenticate({"base_url": BASE_URL, "api_token": BAD_API_TOKEN})
    except QdiError as exc:
        assert exc.status == QdiStatus.ERROR_UNAUTHORIZED
        print("Successfully rejected bad token:", exc)
    else:
        msg = "authenticate() should have rejected a bad token"
        raise AssertionError(msg)

    print("Running Authenticate...")
    client.authenticate({"base_url": BASE_URL, "api_token": API_TOKEN})
    print("Authenticated successfully!")

    print("Running Discover...")
    descriptor = client.discover()
    print("Descriptor:", descriptor)
    assert descriptor["device_id"] == device_id

    print("Running Send...")
    task_id = client.send(TASK_PAYLOAD, "openqasm3", shots=SHOTS)
    print("Task ID generated:", task_id)

    print("Monitoring status...")
    status = QdiTaskStatus.QUEUED
    for _ in range(MONITOR_ATTEMPTS):
        raw_status, advisory = client.monitor(task_id)
        status = QdiTaskStatus(raw_status)
        print(f"Status: {status.name}, Advisory info: {advisory}")
        if status in _TERMINAL_STATUSES:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    if status != QdiTaskStatus.COMPLETED:
        msg = f"Task did not complete successfully: {status.name}"
        raise AssertionError(msg)
    print("Task completed!")

    print("Receiving results...")
    result, result_type = client.receive(task_id)
    print(f"Result format: {result_type}")
    print(f"Result content: {result}")
    assert result_type == "counts"

    print("Running Resource Estimation (expected to fail; see gap G001)...")
    try:
        client.estimate_resources(TASK_PAYLOAD, "openqasm3", shots=SHOTS)
    except QdiError as exc:
        assert exc.status == QdiStatus.ERROR_ESTIMATION_FAILED
        print("Confirmed documented failure:", exc)
    else:
        msg = "estimate_resources() should always fail against OQTOPUS"
        raise AssertionError(msg)

    print("\n--- ALL CHECKS PASSED SUCCESSFULLY! ---")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <device_id>", file=sys.stderr)
        sys.exit(1)
    try:
        test_full_lifecycle(sys.argv[1])
    except QdiError as exc:
        print(f"QDI operation failed ({exc.status.name}): {exc}", file=sys.stderr)
        sys.exit(1)

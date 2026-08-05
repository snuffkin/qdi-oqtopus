"""Shared, offline-only test object builders for qdi_oqtopus tests."""

from oqtopus_client.rest.models.devices_device_info import DevicesDeviceInfo
from oqtopus_client.services.device import OqtopusDevice


def make_oqtopus_device(
    *, status: str = "available", n_qubits: int | None = 4
) -> OqtopusDevice:
    """Build an `OqtopusDevice` without any network access.

    Returns:
        A device wrapper with a fixed id and description, suitable for
        exercising mapping/client code offline.

    """
    raw = DevicesDeviceInfo(
        device_id="dev1",
        device_type="QPU",
        status=status,
        n_pending_jobs=0,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure"],
        description="Test device",
        n_qubits=n_qubits,
    )
    return OqtopusDevice(raw=raw)

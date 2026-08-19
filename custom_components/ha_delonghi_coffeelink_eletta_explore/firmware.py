"""Helpers for presenting manufacturer firmware identifiers."""

from __future__ import annotations

from typing import Any

from .ayla_client import AylaProperties


def appliance_software_version(
    data: AylaProperties | None,
    connectivity_fallback: Any = None,
) -> str | None:
    """Return the complete appliance software identifier for DeviceInfo.

    The Ayla device metadata ``sw_version`` describes its connectivity module.
    The appliance publishes its own, more relevant software identifier through
    the ``software_version`` property. Fall back to the module version only on
    models that do not expose the appliance property.
    """
    prop = (data or {}).get("software_version")
    value = prop.get("value") if isinstance(prop, dict) else None
    for candidate in (value, connectivity_fallback):
        if candidate is None or isinstance(candidate, bool):
            continue
        text = str(candidate).strip()
        if text:
            return text
    return None


def device_firmware_version(
    data: AylaProperties | None,
    connectivity_firmware: Any = None,
) -> str | None:
    """Return the primary firmware identifier for Home Assistant DeviceInfo.

    Home Assistant already presents ``sw_version`` with its localized Firmware
    label. Prefer the appliance identifier and use the connectivity-module value
    only as a compatibility fallback for models without that property.
    """
    return appliance_software_version(data, connectivity_firmware)

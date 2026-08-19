"""Privacy-safe diagnostics for De'Longhi Coffee Link – Eletta Explore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .firmware import appliance_software_version

if TYPE_CHECKING:
    from . import DelonghiConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DelonghiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without credentials, identifiers, values or raw frames."""
    integration = await async_get_integration(hass, DOMAIN)
    devices: list[dict[str, Any]] = []
    for coordinator in entry.runtime_data.coordinators:
        monitor = coordinator.monitor or {}
        devices.append(
            {
                "model": coordinator.device.model,
                "oem_model": coordinator.device.oem_model,
                "appliance_software_version": appliance_software_version(
                    coordinator.data, coordinator.device.sw_version
                ),
                "connectivity_firmware_version": coordinator.device.sw_version,
                "profile": coordinator.profile.key,
                "connection_status": coordinator.device.connection_status,
                "detected_properties": {
                    "command": coordinator.command_property,
                    "response": coordinator.response_property,
                    "connected": coordinator.connected_property,
                },
                "property_names": sorted((coordinator.data or {}).keys()),
                "coordinator": {
                    "last_update_success": coordinator.last_update_success,
                    "last_command_result": coordinator.last_command_result,
                    "active_beverage_known": coordinator.active_beverage_id is not None,
                    "monitor": {
                        "source_property": monitor.get("source_property"),
                        "status": monitor.get("status_name"),
                        "status_code": monitor.get("status"),
                        "step_code": monitor.get("step", monitor.get("action")),
                        "progress_percentage": monitor.get(
                            "progress_percentage", monitor.get("progress")
                        ),
                        "accessory_code": monitor.get("accessory"),
                        "switches": (
                            f"0x{monitor['switches']:04X}"
                            if isinstance(monitor.get("switches"), int)
                            else None
                        ),
                        "alarms": (
                            f"0x{monitor['alarms']:08X}"
                            if isinstance(monitor.get("alarms"), int)
                            else None
                        ),
                        "error": monitor.get("error"),
                    },
                    "learned_recipe_ids": sorted(coordinator.learned_start_frames),
                    "learned_stop_recipe_ids": sorted(coordinator.learned_stop_frames),
                    "wake_frame_learned": coordinator.learned_wake_frame is not None,
                },
            }
        )
    return {
        "integration": {
            "domain": DOMAIN,
            "version": integration.version,
            "config_entry_version": entry.version,
        },
        "devices": devices,
    }


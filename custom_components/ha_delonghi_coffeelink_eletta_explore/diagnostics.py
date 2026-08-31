"""Privacy-safe diagnostics for De'Longhi Coffee Link – Eletta Explore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .firmware import appliance_software_version

if TYPE_CHECKING:
    from . import DelonghiConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: DelonghiConfigEntry) -> dict[str, Any]:
    """Return diagnostics without credentials, identifiers, values or raw frames."""
    integration = await async_get_integration(hass, DOMAIN)
    devices: list[dict[str, Any]] = []
    for coordinator in entry.runtime_data.coordinators:
        monitor = coordinator.monitor or {}
        devices.append(
            {
                "model": coordinator.device.model,
                "oem_model": coordinator.device.oem_model,
                "appliance_software_version": appliance_software_version(coordinator.data, coordinator.device.sw_version),
                "connectivity_firmware_version": coordinator.device.sw_version,
                "profile": coordinator.profile.key,
                "connection_status": coordinator.device.connection_status,
                "connection_info": {
                    "supported": coordinator._connection_info_supported,
                    "connectivity_type": coordinator.connection_info.get("connectivity_type"),
                    "wifi_signal_dbm": coordinator.connection_info.get("rssi"),
                },
                "detected_properties": {
                    "command": coordinator.command_property,
                    "command_ack_enabled": coordinator.command_ack_enabled,
                    "response": coordinator.response_property,
                    "connected": coordinator.connected_property,
                },
                "property_names": sorted((coordinator.data or {}).keys()),
                "coordinator": {
                    "last_update_success": coordinator.last_update_success,
                    "cloud_update_mode": coordinator.dss_state,
                    "dss_events_received": coordinator.dss_events_received,
                    "cloud_snapshot_refresh": {
                        "attempts": coordinator.statistics_sync_attempts,
                        "successes": coordinator.statistics_sync_successes,
                        "last_attempt_at": coordinator.last_statistics_sync_attempt_at,
                        "last_success_at": coordinator.last_statistics_sync_success_at,
                        "last_result": coordinator.last_statistics_sync_result,
                        "last_trigger": coordinator.last_statistics_sync_trigger,
                        "snapshot_changed": coordinator.last_statistics_sync_snapshot_changed,
                        "ack_status": coordinator.last_statistics_sync_ack_status,
                    },
                    "last_command_result": coordinator.last_command_result,
                    "active_beverage_known": coordinator.active_beverage_id is not None,
                    "monitor": {
                        "source_property": monitor.get("source_property"),
                        "status": monitor.get("status_name"),
                        "status_code": monitor.get("status"),
                        "step_code": monitor.get("step", monitor.get("action")),
                        "progress_percentage": monitor.get("progress_percentage", monitor.get("progress")),
                        "accessory_code": monitor.get("accessory"),
                        "switches": (f"0x{monitor['switches']:04X}" if isinstance(monitor.get("switches"), int) else None),
                        "alarms": (f"0x{monitor['alarms']:08X}" if isinstance(monitor.get("alarms"), int) else None),
                        "error": monitor.get("error"),
                    },
                    "learned_recipe_ids": sorted(coordinator.learned_start_frames),
                    "learned_stop_recipe_ids": sorted(coordinator.learned_stop_frames),
                    "wake_frame_learned": coordinator.learned_wake_frame is not None,
                },
            }
        )
    dss_manager = getattr(entry.runtime_data, "dss_manager", None)
    return {
        "integration": {
            "domain": DOMAIN,
            "version": integration.version,
            "config_entry_version": entry.version,
        },
        "cloud_stream": (
            {
                "state": dss_manager.state,
                "events_received": dss_manager.events_received,
                "event_type_counts": dict(dss_manager.event_type_counts),
                "reconnect_count": dss_manager.reconnect_count,
                "last_event_at": dss_manager.last_event_at,
                "last_error_type": dss_manager.last_error_type,
            }
            if dss_manager is not None
            else {"state": "disabled"}
        ),
        "devices": devices,
    }

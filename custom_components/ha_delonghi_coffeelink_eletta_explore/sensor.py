"""Sensor platform for De'Longhi Coffee Link – Eletta Explore."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ayla_client import AylaProperties, normalize_signed_app_id
from .const import (
    APP_ID_PROPERTY,
    BREAKDOWN_COUNTER_SENSORS,
    COUNTER_SENSORS,
    COUNTER_TRANSLATION_KEY_OVERRIDES,
    MACHINE_STATUS_OPTIONS,
)
from .coordinator import DelonghiCoordinator
from .counters import (
    counter_breakdown_sum,
    parse_counter_value,
    parse_percentage_value,
    parse_remaining_percentage,
    parse_water_hardness_level,
    parse_water_volume_liters,
)
from .entity import DelonghiCoordinatorEntity

if TYPE_CHECKING:
    from . import DelonghiConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

CLOUD_SESSION_HOLDER_OPTIONS = ("unknown", "free", "ha", "foreign")
LAST_COMMAND_RESULT_OPTIONS = (
    "pending",
    "sent",
    "acknowledged",
    "timed_out",
    "rejected",
)


def _resolve_property(data: AylaProperties | None, candidates: list[str]) -> str | None:
    """Return the first candidate property name present on the device, else None.

    Property names differ across DeLonghi models (e.g. d700_tot_bev_b on Soul vs
    d701_tot_bev_b on Eletta Explore), so each sensor declares a candidate list.
    """
    data = data or {}
    for candidate in candidates:
        if candidate in data:
            return candidate
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DelonghiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators = entry.runtime_data.coordinators
    entities: list[SensorEntity] = []
    for coord in coordinators:
        for candidates, key, _friendly, icon in COUNTER_SENSORS:
            prop_name = _resolve_property(coord.data, candidates)
            if prop_name is None:
                _LOGGER.debug(
                    "Skipping counter '%s': none of %s present",
                    key,
                    candidates,
                )
                continue
            entities.append(
                DelonghiCounterSensor(
                    coord,
                    prop_name,
                    key,
                    icon,
                    COUNTER_TRANSLATION_KEY_OVERRIDES.get((key, prop_name)),
                )
            )
        for candidates, key, _friendly, icon, breakdown_keys in BREAKDOWN_COUNTER_SENSORS:
            prop_name = _resolve_property(coord.data, candidates)
            prop = (coord.data or {}).get(prop_name) if prop_name else None
            value = prop.get("value") if prop else None
            if prop_name is None or counter_breakdown_sum(value, breakdown_keys) is None:
                _LOGGER.debug(
                    "Skipping breakdown counter '%s': selected "
                    "fields are absent from %s",
                    key,
                    candidates,
                )
                continue
            entities.append(
                DelonghiBreakdownCounterSensor(
                    coord, prop_name, key, icon, breakdown_keys
                )
            )
        entities.append(DelonghiMachineStatusSensor(coord))
        entities.append(DelonghiLastCommandSensor(coord))
        if coord.connection_info.get("rssi") is not None:
            entities.append(DelonghiWifiSignalSensor(coord))
        if coord.profile.uses_cloud_session and APP_ID_PROPERTY in (coord.data or {}):
            entities.append(DelonghiCloudSessionAppIdSensor(coord))
    async_add_entities(entities)


class _Base(DelonghiCoordinatorEntity, SensorEntity):

    def __init__(
        self,
        coord: DelonghiCoordinator,
        unique_suffix: str,
        translation_key: str | None = None,
    ) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.device.dsn}_{unique_suffix}"
        self._attr_translation_key = translation_key or unique_suffix


class DelonghiCounterSensor(_Base):
    """Numeric counter, volume or percentage sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coord: DelonghiCoordinator,
        prop_name: str,
        key: str,
        icon: str,
        translation_key: str | None = None,
    ) -> None:
        super().__init__(coord, key, translation_key)
        self._prop_name = prop_name
        self._key = key
        self._logged_unparseable = False
        if key in {
            "total_descales",
            "water_total_quantity",
            "total_filters_used",
            "water_filter_quantity",
            "water_hardness",
            "beverages_since_descale_warning",
            "descale_alert_count",
        }:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key in {"beverages_since_descale_warning", "descale_alert_count"}:
            self._attr_entity_registry_enabled_default = False
        if key in {"water_total_quantity", "water_filter_quantity"}:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            self._attr_suggested_display_precision = 3
            self._attr_state_class = (
                SensorStateClass.TOTAL
                if key == "water_total_quantity"
                else SensorStateClass.TOTAL_INCREASING
            )
        elif key in {"grounds_container_fill", "filter_usage", "descale_limit_usage"}:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_suggested_display_precision = 0
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key in {"water_hardness", "descale_status"}:
            # Hardness and descale status are settings/states, not monotonically
            # increasing totals.
            self._attr_state_class = None

    @property
    def native_value(self) -> int | float | None:
        prop = (self.coordinator.data or {}).get(self._prop_name)
        if not prop:
            return None
        val = prop.get("value")
        if val is None:
            return None
        # Soul exposes counters as plain integers; newer models (Eletta) publish
        # some as a JSON object of per-recipe sub-counts. parse_counter_value
        # handles both; an unparseable scalar yields None and is logged once so
        # the format can be reported and the parser extended.
        if self._key in {"water_total_quantity", "water_filter_quantity"}:
            result = parse_water_volume_liters(val)
        elif self._key == "water_hardness":
            result = parse_water_hardness_level(val)
        elif self._key == "descale_limit_usage":
            result = parse_remaining_percentage(val)
        elif self._key in {"grounds_container_fill", "filter_usage"}:
            result = parse_percentage_value(val)
        else:
            result = parse_counter_value(val)
        if result is None and not self._logged_unparseable:
            self._logged_unparseable = True
            _LOGGER.warning(
                "Numeric property '%s' (%s): value is invalid for this sensor "
                "(base_type=%s, value_type=%s). Sensor left unknown; use a "
                "privacy-sanitized diagnostic when reporting the problem.",
                self._prop_name,
                self.name,
                prop.get("base_type"),
                type(val).__name__,
            )
        return result

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        # Large JSON breakdowns change often and unnecessarily grow Recorder.
        # Selected useful totals are exposed as their own sensors instead.
        return None


class DelonghiBreakdownCounterSensor(_Base):
    """Counter derived from selected fields of a JSON aggregate property."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coord: DelonghiCoordinator,
        prop_name: str,
        key: str,
        icon: str,
        breakdown_keys: tuple[str, ...],
    ) -> None:
        super().__init__(coord, key)
        self._prop_name = prop_name
        self._breakdown_keys = breakdown_keys

    @property
    def native_value(self) -> int | None:
        prop = (self.coordinator.data or {}).get(self._prop_name)
        if not prop:
            return None
        return counter_breakdown_sum(prop.get("value"), self._breakdown_keys)


class DelonghiMachineStatusSensor(_Base):
    """Machine operational state decoded from ``d302_monitor_machine``
    (standby, ready, rinsing, ...). Contributed via PR #5 (@TischenkoArseny,
    based on the DlghIoT client). ``None``/unknown if the blob doesn't parse
    on this model - the parse error is surfaced as an attribute.
    """

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord, "machine_status")
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(MACHINE_STATUS_OPTIONS)

    @property
    def native_value(self) -> str | None:
        monitor = self.coordinator.monitor or {}
        if "error" in monitor:
            return "unknown"
        return monitor.get("status_name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        monitor = self.coordinator.monitor or {}
        attributes = {
            key: monitor[key]
            for key in ("source_property", "error")
            if key in monitor
        }
        if "error" not in monitor:
            attributes.update(
                {
                    "status_code": monitor.get("status"),
                    "step_code": monitor.get("step", monitor.get("action")),
                    "progress_percentage": monitor.get(
                        "progress_percentage", monitor.get("progress")
                    ),
                    "accessory_code": monitor.get("accessory"),
                }
            )
            if isinstance(monitor.get("switches"), int):
                attributes["switches"] = f"0x{monitor['switches']:04X}"
            if isinstance(monitor.get("alarms"), int):
                attributes["alarms"] = f"0x{monitor['alarms']:08X}"
        return attributes


def _parse_cloud_session_app_id(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return normalize_signed_app_id(int(str(raw).strip()))
    except (TypeError, ValueError):
        return None


class DelonghiCloudSessionAppIdSensor(_Base):
    """Privacy-safe diagnostic for the current cloud-session holder."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(
            coord, "cloud_session_app_id"
        )
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(CLOUD_SESSION_HOLDER_OPTIONS)

    @property
    def native_value(self) -> str:
        prop = (self.coordinator.data or {}).get(APP_ID_PROPERTY)
        if not isinstance(prop, dict):
            return "unknown"
        return self.coordinator.cloud_session_holder(
            _parse_cloud_session_app_id(prop.get("value"))
        )


class DelonghiLastCommandSensor(_Base):
    """Privacy-safe status of the latest command issued by Home Assistant."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(
            coord,
            "last_captured_command",
            "last_command_status",
        )
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(LAST_COMMAND_RESULT_OPTIONS)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.last_command_result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # This sensor deliberately exposes only the HA-issued command. Frames
        # sniffed from the official Coffee Link app are unrelated diagnostics.
        return dict(self.coordinator.last_command or {})


class DelonghiWifiSignalSensor(_Base):
    """Optional Ayla Wi-Fi RSSI diagnostic, disabled by default."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord, "wifi_signal_strength")

    @property
    def native_value(self) -> int | None:
        value = self.coordinator.connection_info.get("rssi")
        return value if isinstance(value, int) else None


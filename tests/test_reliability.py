"""Regression tests for truthful and serialized command execution."""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "ha_delonghi_coffeelink_eletta_explore"
PKG_NAME = "delonghi_reliability_tests"


class HomeAssistantError(Exception):
    """Test double for Home Assistant's user-visible error."""

    def __init__(self, message="", **kwargs):
        super().__init__(message)
        self.translation_domain = kwargs.get("translation_domain")
        self.translation_key = kwargs.get("translation_key")


class ServiceValidationError(HomeAssistantError):
    """Test double for a translated action-validation error."""


class ConfigEntryAuthFailed(Exception):
    """Test double for Home Assistant's reauth signal."""

    def __init__(self, message="", **kwargs):
        super().__init__(message)
        self.translation_domain = kwargs.get("translation_domain")
        self.translation_key = kwargs.get("translation_key")


class DataUpdateCoordinator:
    """Small test double sufficient for constructing the coordinator."""

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval, config_entry):
        self.hass = hass
        self.config_entry = config_entry
        self.data = {}
        self.last_update_success = True
        self.update_interval = update_interval
        self._test_listeners = []

    async def async_shutdown(self):
        return None

    async def async_request_refresh(self):
        return None

    def async_update_listeners(self):
        for listener in tuple(self._test_listeners):
            listener()

    def async_add_listener(self, listener):
        self._test_listeners.append(listener)

        def unsubscribe():
            self._test_listeners.remove(listener)

        return unsubscribe


class Store:
    def __init__(self, hass, version, key):
        pass

    def async_delay_save(self, callback, delay):
        pass


def _install_homeassistant_stubs() -> None:
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda value: value
    voluptuous.Required = lambda value: value
    voluptuous.Optional = lambda value: value
    voluptuous.All = lambda *values: values[-1]
    voluptuous.In = lambda values: values
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    sensor_component = types.ModuleType("homeassistant.components.sensor")
    binary_sensor_component = types.ModuleType("homeassistant.components.binary_sensor")
    button_component = types.ModuleType("homeassistant.components.button")
    core = types.ModuleType("homeassistant.core")
    config_entries = types.ModuleType("homeassistant.config_entries")
    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    exceptions = types.ModuleType("homeassistant.exceptions")
    constants = types.ModuleType("homeassistant.const")
    helpers = types.ModuleType("homeassistant.helpers")
    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    issue_registry = types.ModuleType("homeassistant.helpers.issue_registry")
    service = types.ModuleType("homeassistant.helpers.service")
    typing_module = types.ModuleType("homeassistant.helpers.typing")
    storage = types.ModuleType("homeassistant.helpers.storage")
    update = types.ModuleType("homeassistant.helpers.update_coordinator")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    loader = types.ModuleType("homeassistant.loader")

    class ConfigEntry:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

    class ConfigEntryState:
        LOADED = "loaded"

    class Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        BUTTON = "button"

    class EntityCategory:
        DIAGNOSTIC = "diagnostic"

    class UnitOfVolume:
        LITERS = "L"

    class SensorDeviceClass:
        ENUM = "enum"
        SIGNAL_STRENGTH = "signal_strength"
        WATER = "water"

    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"

    class BinarySensorDeviceClass:
        CONNECTIVITY = "connectivity"
        PROBLEM = "problem"

    class Entity:
        @property
        def name(self):
            return getattr(self, "_attr_translation_key", None)

    class SensorEntity(Entity):
        pass

    class BinarySensorEntity(Entity):
        pass

    class ButtonEntity(Entity):
        pass

    class CoordinatorEntity(Entity):
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return self.coordinator.last_update_success

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    class IssueSeverity:
        ERROR = "error"

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

        def __init__(self):
            self.hass = object()
            self._reauth_entry = None
            self._reconfigure_entry = None
            self.unique_id = None
            self.abort_configured_called = False

        def _get_reauth_entry(self):
            return self._reauth_entry

        def _get_reconfigure_entry(self):
            return self._reconfigure_entry

        async def async_set_unique_id(self, unique_id):
            self.unique_id = unique_id

        def _abort_if_unique_id_mismatch(self):
            return None

        def _abort_if_unique_id_configured(self):
            self.abort_configured_called = True

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_update_reload_and_abort(self, entry, *, data_updates, reason="reauth_successful"):
            return {
                "type": "abort",
                "reason": reason,
                "entry": entry,
                "data_updates": data_updates,
            }

    async def async_get_integration(hass, domain):
        return types.SimpleNamespace(version="0.3.16")

    core.HomeAssistant = object
    core.ServiceCall = object
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigEntryState = ConfigEntryState
    config_entries.ConfigFlow = ConfigFlow
    config_entries.ConfigFlowResult = dict
    constants.ATTR_DEVICE_ID = "device_id"
    constants.PERCENTAGE = "%"
    constants.SIGNAL_STRENGTH_DECIBELS_MILLIWATT = "dBm"
    constants.EntityCategory = EntityCategory
    constants.Platform = Platform
    constants.UnitOfVolume = UnitOfVolume
    exceptions.HomeAssistantError = HomeAssistantError
    exceptions.ServiceValidationError = ServiceValidationError
    exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    exceptions.ConfigEntryNotReady = RuntimeError
    config_validation.config_entry_only_config_schema = lambda domain: {domain: {}}
    config_validation.ensure_list = lambda value: value if isinstance(value, list) else [value]
    config_validation.string = str
    device_registry.async_get = lambda hass: hass.device_registry
    device_registry.async_entries_for_config_entry = lambda registry, entry_id: [
        item for item in registry.entries if item.config_entry_id == entry_id
    ]
    device_registry.DeviceInfo = DeviceInfo
    entity_registry.async_get = lambda hass: hass.entity_registry
    entity_registry.async_entries_for_config_entry = lambda registry, entry_id: [
        item for item in registry.entries if item.config_entry_id == entry_id
    ]
    issue_registry.IssueSeverity = IssueSeverity
    issue_registry.async_create_issue = lambda *args, **kwargs: None
    issue_registry.async_delete_issue = lambda *args, **kwargs: None
    service.async_register_admin_service = lambda *args, **kwargs: None
    typing_module.ConfigType = dict
    helpers.config_validation = config_validation
    helpers.device_registry = device_registry
    helpers.entity_registry = entity_registry
    helpers.issue_registry = issue_registry
    storage.Store = Store
    update.CoordinatorEntity = CoordinatorEntity
    update.DataUpdateCoordinator = DataUpdateCoordinator

    class UpdateFailed(RuntimeError):
        def __init__(self, message: str, *, retry_after: float | None = None) -> None:
            super().__init__(message)
            self.retry_after = retry_after

    update.UpdateFailed = UpdateFailed
    loader.async_get_integration = async_get_integration
    aiohttp_client.async_get_clientsession = lambda hass: object()
    homeassistant.config_entries = config_entries
    sensor_component.SensorDeviceClass = SensorDeviceClass
    sensor_component.SensorEntity = SensorEntity
    sensor_component.SensorStateClass = SensorStateClass
    binary_sensor_component.BinarySensorDeviceClass = BinarySensorDeviceClass
    binary_sensor_component.BinarySensorEntity = BinarySensorEntity
    button_component.ButtonEntity = ButtonEntity
    entity_platform.AddEntitiesCallback = object
    sys.modules.update(
        {
            "voluptuous": voluptuous,
            "homeassistant": homeassistant,
            "homeassistant.components": components,
            "homeassistant.components.sensor": sensor_component,
            "homeassistant.components.binary_sensor": binary_sensor_component,
            "homeassistant.components.button": button_component,
            "homeassistant.core": core,
            "homeassistant.const": constants,
            "homeassistant.config_entries": config_entries,
            "homeassistant.data_entry_flow": data_entry_flow,
            "homeassistant.exceptions": exceptions,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.config_validation": config_validation,
            "homeassistant.helpers.device_registry": device_registry,
            "homeassistant.helpers.entity_registry": entity_registry,
            "homeassistant.helpers.entity_platform": entity_platform,
            "homeassistant.helpers.issue_registry": issue_registry,
            "homeassistant.helpers.service": service,
            "homeassistant.helpers.typing": typing_module,
            "homeassistant.helpers.storage": storage,
            "homeassistant.helpers.update_coordinator": update,
            "homeassistant.helpers.aiohttp_client": aiohttp_client,
            "homeassistant.loader": loader,
        }
    )


_install_homeassistant_stubs()
package = types.ModuleType(PKG_NAME)
package.__path__ = [str(PKG_DIR)]
package.DelonghiRuntimeData = type("DelonghiRuntimeData", (), {})
sys.modules[PKG_NAME] = package


def _load(name: str):
    full_name = f"{PKG_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, PKG_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
command_builder = _load("command_builder")
ayla_client = _load("ayla_client")
model_profiles = _load("model_profiles")
_load("monitor")
coordinator_module = _load("coordinator")
errors_module = sys.modules[f"{PKG_NAME}.errors"]
diagnostics_module = _load("diagnostics")
config_flow_module = _load("config_flow")
sensor_module = _load("sensor")
binary_sensor_module = _load("binary_sensor")
button_module = _load("button")


def _load_integration_init():
    full_name = f"{PKG_NAME}.integration_init"
    spec = importlib.util.spec_from_file_location(full_name, PKG_DIR / "__init__.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


integration_module = _load_integration_init()


def test_retired_cloud_entities_are_removed_from_registry():
    config_entry_id = "coffee-link-entry"
    entries = [
        types.SimpleNamespace(
            entity_id="sensor.machine_last_connected",
            unique_id="dsn_last_connected",
            domain="sensor",
            config_entry_id=config_entry_id,
        ),
        types.SimpleNamespace(
            entity_id="sensor.machine_data_updated",
            unique_id="dsn_data_updated",
            domain="sensor",
            config_entry_id=config_entry_id,
        ),
        types.SimpleNamespace(
            entity_id="sensor.machine_statistics_synchronized",
            unique_id="dsn_statistics_synchronized",
            domain="sensor",
            config_entry_id=config_entry_id,
        ),
        types.SimpleNamespace(
            entity_id="sensor.machine_connection_status",
            unique_id="dsn_connection_status",
            domain="sensor",
            config_entry_id=config_entry_id,
        ),
        types.SimpleNamespace(
            entity_id="sensor.machine_cloud_session",
            unique_id="dsn_cloud_session_app_id",
            domain="sensor",
            config_entry_id=config_entry_id,
        ),
    ]

    class Registry:
        def __init__(self):
            self.entries = entries
            self.removed: list[str] = []

        def async_remove(self, entity_id):
            self.removed.append(entity_id)

    registry = Registry()
    hass = types.SimpleNamespace(entity_registry=registry)
    entry = types.SimpleNamespace(entry_id=config_entry_id)

    integration_module._async_remove_retired_sensor_entities(hass, entry)

    assert registry.removed == [
        "sensor.machine_last_connected",
        "sensor.machine_data_updated",
        "sensor.machine_statistics_synchronized",
        "sensor.machine_connection_status",
    ]


class FakeClient:
    def __init__(self):
        self.writes: list[tuple[str, str, str]] = []
        self.connect_posts = 0

    async def async_set_property_value(self, dsn, prop, value):
        self.writes.append((dsn, prop, value))

    async def async_post_cloud_session(self, dsn, prop, app_id):
        self.connect_posts += 1

    async def async_get_connection_info(self, dsn):
        return {}


class FakeConfigEntry:
    """Test double that owns coordinator background tasks like Home Assistant."""

    def async_create_background_task(self, hass, target, name):
        return asyncio.create_task(target, name=name)


def _coordinator(oem_model: str = "DL-millcore"):
    client = FakeClient()
    device = ayla_client.AylaDevice(
        dsn="private-device-id",
        name="Machine",
        oem_model=oem_model,
        model="model",
        sw_version="1",
        connection_status="online",
    )
    coordinator = coordinator_module.DelonghiCoordinator(object(), client, device, FakeConfigEntry(), lambda _devices: None)
    coordinator.command_property = "data_request"
    return coordinator, client


def test_sensor_platform_reports_counters_machine_and_command_state():
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.data = {
        "counter": {"value": "12"},
        const.APP_ID_PROPERTY: {"value": str(coordinator._integration_app_id)},
    }
    coordinator.monitor = {
        "status": 7,
        "status_name": "ready",
        "step": 0,
        "progress_percentage": 0,
        "accessory": 0,
        "switches": 0,
        "alarms": 0,
    }

    counter = sensor_module.DelonghiCounterSensor(coordinator, "counter", "total_beverages", "mdi:counter")
    machine = sensor_module.DelonghiMachineStatusSensor(coordinator)
    session = sensor_module.DelonghiCloudSessionAppIdSensor(coordinator)
    command = sensor_module.DelonghiLastCommandSensor(coordinator)

    assert counter.native_value == 12
    assert counter.extra_state_attributes is None
    assert machine.native_value == "ready"
    assert machine.extra_state_attributes["status_code"] == 7
    assert session.native_value == "ha"
    assert command.native_value is None
    assert command.extra_state_attributes == {}
    assert counter.device_info["sw_version"] == "1"


def test_optional_wifi_signal_sensor_is_diagnostic_and_disabled_by_default():
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.connection_info = {"rssi": -58}
    signal = sensor_module.DelonghiWifiSignalSensor(coordinator)
    assert signal.native_value == -58
    assert signal._attr_native_unit_of_measurement == "dBm"
    assert signal._attr_entity_registry_enabled_default is False
    coordinator.connection_info = {"rssi": "invalid"}
    assert signal.native_value is None

    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[coordinator]))
    coordinator.connection_info = {"rssi": -60}
    coordinator.data = {}
    added = []
    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))
    assert any(isinstance(entity, sensor_module.DelonghiWifiSignalSensor) for entity in added)


def test_binary_sensor_platform_uses_stable_maintenance_snapshot():
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.stable_maintenance_monitor = {
        "alarms": (1 << 1) | (1 << 3),
        "switches": 1 << 4,
    }
    coordinator.data = {"d512_percentage_to_deca": {"value": "95"}}

    connection = binary_sensor_module.DelonghiCloudConnectionBinarySensor(coordinator)
    water = binary_sensor_module.DelonghiWaterTankBinarySensor(coordinator)
    waste = binary_sensor_module.DelonghiWasteContainerBinarySensor(coordinator)
    descale = binary_sensor_module.DelonghiDecalcificationBinarySensor(coordinator)
    filter_sensor = binary_sensor_module.DelonghiFilterBinarySensor(coordinator)

    assert connection.available is True
    assert connection.is_on is True
    assert water.available is True
    assert water.is_on is True
    assert water.extra_state_attributes["water_tank_present"] is False
    assert waste.is_on is True
    assert descale.is_on is True
    assert filter_sensor.is_on is True


def test_button_platform_exposes_only_safe_learned_actions():
    coordinator, _client = _coordinator("DL-striker-cb")
    start = button_module.DelonghiStartBeverageButton(coordinator, 1, "espresso", "Espresso", "mdi:coffee")
    stop = button_module.DelonghiStopButton(coordinator)

    assert start.available is False
    assert stop.available is False

    coordinator.learned_start_frames[1] = "learned-start"
    coordinator.learned_stop_frames[1] = "learned-stop"
    coordinator.active_beverage_id = 1

    assert start.available is True
    assert stop.available is True
    assert start._attr_unique_id == "private-device-id_start_beverage_1"


def test_cloud_connection_sensor_preserves_unknown_and_offline_states():
    coordinator, _client = _coordinator("DL-striker-cb")
    sensor = binary_sensor_module.DelonghiCloudConnectionBinarySensor(coordinator)

    coordinator.device.connection_status = "mystery"
    assert sensor.is_on is None
    coordinator.device.connection_status = "offline"
    assert sensor.is_on is False
    coordinator.last_update_success = False
    assert sensor.available is False


def test_sensor_setup_entry_covers_supported_and_absent_properties(monkeypatch):
    eletta, _client = _coordinator("DL-striker-cb")
    soul, _client = _coordinator("DL-millcore")
    eletta.data = {
        "present": {"value": "7"},
        "break_invalid": {"value": "{}"},
        "break_valid": {"value": '{"selected": 3}'},
        const.APP_ID_PROPERTY: {"value": "0"},
    }
    soul.data = {"present": {"value": "2"}}
    monkeypatch.setattr(
        sensor_module,
        "COUNTER_SENSORS",
        [
            (["missing"], "skipped_counter", "Skipped", "mdi:counter"),
            (["alias", "present"], "kept_counter", "Kept", "mdi:counter"),
        ],
    )
    monkeypatch.setattr(
        sensor_module,
        "BREAKDOWN_COUNTER_SENSORS",
        [
            (["missing"], "missing_breakdown", "Missing", "mdi:counter", ("selected",)),
            (["break_invalid"], "invalid_breakdown", "Invalid", "mdi:counter", ("selected",)),
            (["break_valid"], "valid_breakdown", "Valid", "mdi:counter", ("selected",)),
        ],
    )
    added = []
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[eletta, soul]))

    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))

    assert sum(isinstance(item, sensor_module.DelonghiCounterSensor) for item in added) == 2
    assert sum(isinstance(item, sensor_module.DelonghiBreakdownCounterSensor) for item in added) == 1
    assert sum(isinstance(item, sensor_module.DelonghiMachineStatusSensor) for item in added) == 2
    assert sum(isinstance(item, sensor_module.DelonghiLastCommandSensor) for item in added) == 2
    assert sum(isinstance(item, sensor_module.DelonghiCloudSessionAppIdSensor) for item in added) == 1
    assert any(getattr(item, "_attr_translation_key", None) == "kept_counter" for item in added)

    empty = []
    empty_entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[]))
    asyncio.run(sensor_module.async_setup_entry(object(), empty_entry, empty.extend))
    assert empty == []
    assert sensor_module._resolve_property(None, []) is None


def test_sensor_setup_entry_builds_coffee_link_official_aggregates(monkeypatch):
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.data = {
        "d701_tot_bev_b": {"value": 616},
        "d702_tot_bev_other": {"value": '{"tot_bev_bw":300,"tot_bev_w":8}'},
        "d733_tot_bev_counters": {"value": ('{"tot_bev_b_iced":23,"tot_bev_bw_iced":7,"tot_bev_w_iced":3}')},
        "d731_tot_mug_hot": {"value": 16},
        "d732_tot_mug_cold": {"value": 0},
        "d736_mug_bev": {"value": 16},
    }
    monkeypatch.setattr(
        sensor_module,
        "COUNTER_SENSORS",
        [
            (["d701_tot_bev_b"], "total_beverages", "Black", "mdi:counter"),
            (["d702_tot_bev_other"], "total_milk_drinks", "Milk", "mdi:cup"),
            (["d736_mug_bev"], "total_mug_bev", "Mug", "mdi:coffee-to-go"),
        ],
    )
    monkeypatch.setattr(sensor_module, "BREAKDOWN_COUNTER_SENSORS", [])
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[coordinator]))
    added = []

    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))

    aggregates = [entity for entity in added if isinstance(entity, sensor_module.DelonghiCoffeeLinkAggregateSensor)]
    assert {entity._key: entity.native_value for entity in aggregates} == {
        "total_beverages": 639,
        "total_milk_drinks": 308,
        "total_cold_milk_drinks": 10,
        "total_mug_bev": 16,
    }
    assert not any(isinstance(entity, sensor_module.DelonghiCounterSensor) for entity in added)
    assert (
        next(entity for entity in aggregates if entity._key == "total_beverages")._attr_translation_key
        == "total_black_coffee_beverages"
    )


def test_sensor_setup_entry_builds_legacy_official_aggregates(monkeypatch):
    coordinator, _client = _coordinator("DL-millcore")
    coordinator.data = {
        "d700_tot_bev_b": {"value": 314},
        "d701_tot_bev_bw": {"value": 250},
        "d703_tot_bev_w": {"value": 17},
    }
    monkeypatch.setattr(sensor_module, "COUNTER_SENSORS", [])
    monkeypatch.setattr(sensor_module, "BREAKDOWN_COUNTER_SENSORS", [])
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[coordinator]))
    added = []

    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))

    aggregates = [entity for entity in added if isinstance(entity, sensor_module.DelonghiCoffeeLinkAggregateSensor)]
    assert {entity._key: entity.native_value for entity in aggregates} == {
        "total_beverages": 314,
        "total_milk_drinks": 267,
    }
    assert all(entity._attr_translation_key in {"total_black_coffee_beverages", "total_milk_drinks"} for entity in aggregates)


def test_non_cold_brew_striker_uses_its_official_hot_milk_formula(monkeypatch):
    coordinator, _client = _coordinator("DL-striker-base")
    coordinator.data = {
        "d702_tot_bev_other": {"value": '{"tot_bev_bw":40,"tot_bev_w":5}'},
    }
    monkeypatch.setattr(sensor_module, "COUNTER_SENSORS", [])
    monkeypatch.setattr(sensor_module, "BREAKDOWN_COUNTER_SENSORS", [])
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[coordinator]))
    added = []

    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))

    aggregates = [entity for entity in added if isinstance(entity, sensor_module.DelonghiCoffeeLinkAggregateSensor)]
    assert {entity._key: entity.native_value for entity in aggregates} == {
        "total_milk_drinks": 40,
    }


def test_unknown_model_does_not_guess_legacy_counter_semantics(monkeypatch):
    coordinator, _client = _coordinator("DL-future-xyz")
    coordinator.profile = model_profiles.profile_for("DL-future-xyz", command_property="data_request")
    coordinator.data = {
        "d700_tot_bev_b": {"value": 314},
        "d701_tot_bev_bw": {"value": 250},
        "d703_tot_bev_w": {"value": 17},
    }
    monkeypatch.setattr(sensor_module, "COUNTER_SENSORS", [])
    monkeypatch.setattr(sensor_module, "BREAKDOWN_COUNTER_SENSORS", [])
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[coordinator]))
    added = []

    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))

    assert not any(isinstance(entity, sensor_module.DelonghiCoffeeLinkAggregateSensor) for entity in added)


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("water_total_quantity", "1234", 0.617),
        ("water_filter_quantity", "2500", 2.5),
        ("water_hardness", "2", 3),
        ("descale_limit_usage", "21", 79),
        ("grounds_container_fill", "42", 42),
        ("filter_usage", "31", 31),
        ("total_beverages", '{"a": 2, "b": 3}', 5),
    ],
)
def test_counter_sensor_uses_parser_selected_by_entity_key(key, raw, expected):
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.data = {"property": {"value": raw}}
    sensor = sensor_module.DelonghiCounterSensor(coordinator, "property", key, "mdi:counter")
    assert sensor.native_value == expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("total_beverages", 639),
        ("total_milk_drinks", 308),
        ("total_cold_milk_drinks", 10),
        ("total_mug_bev", 16),
        ("unsupported", None),
    ],
)
def test_coffee_link_aggregate_sensor_matches_official_statistics(key, expected):
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.data = {
        "d701_tot_bev_b": {"value": 616},
        "d702_tot_bev_other": {"value": '{"tot_bev_bw":300,"tot_bev_w":8}'},
        "d733_tot_bev_counters": {"value": ('{"tot_bev_b_iced":23,"tot_bev_bw_iced":7,"tot_bev_w_iced":3}')},
        "d731_tot_mug_hot": {"value": 16},
        "d732_tot_mug_cold": {"value": 0},
    }
    aggregate = sensor_module.DelonghiCoffeeLinkAggregateSensor(coordinator, key)
    assert aggregate.native_value == expected


def test_counter_sensor_metadata_missing_values_and_single_warning(caplog):
    coordinator, _client = _coordinator("DL-striker-cb")

    diagnostic = sensor_module.DelonghiCounterSensor(coordinator, "missing", "total_descales", "mdi:counter")
    disabled = sensor_module.DelonghiCounterSensor(coordinator, "missing", "descale_alert_count", "mdi:counter")
    detailed = sensor_module.DelonghiCounterSensor(coordinator, "missing", "total_espresso", "mdi:coffee")
    filter_volume = sensor_module.DelonghiCounterSensor(coordinator, "missing", "water_filter_quantity", "mdi:water")
    percentage = sensor_module.DelonghiCounterSensor(coordinator, "missing", "grounds_container_fill", "mdi:percent")
    status = sensor_module.DelonghiCounterSensor(coordinator, "missing", "descale_status", "mdi:state")

    assert diagnostic._attr_entity_category == "diagnostic"
    assert disabled._attr_entity_registry_enabled_default is False
    assert detailed._attr_entity_registry_enabled_default is False
    assert filter_volume._attr_native_unit_of_measurement == "L"
    assert filter_volume._attr_state_class == "total_increasing"
    assert percentage._attr_native_unit_of_measurement == "%"
    assert percentage._attr_state_class == "measurement"
    assert status._attr_state_class is None
    assert diagnostic.native_value is None

    coordinator.data = {"missing": {"value": None}}
    assert diagnostic.native_value is None
    coordinator.data = {"missing": {"value": "invalid", "base_type": "string"}}
    with caplog.at_level("WARNING"):
        assert diagnostic.native_value is None
        assert diagnostic.native_value is None
    assert caplog.text.count("value is invalid for this sensor") == 1


def test_breakdown_machine_and_cloud_session_sensor_edge_states():
    coordinator, _client = _coordinator("DL-striker-cb")
    breakdown = sensor_module.DelonghiBreakdownCounterSensor(
        coordinator,
        "breakdown",
        "total_cold_brew",
        "mdi:snowflake",
        ("a", "b"),
    )
    assert breakdown._attr_entity_registry_enabled_default is False
    assert breakdown.native_value is None
    coordinator.data = {"breakdown": {"value": '{"a": 2, "b": 4}'}}
    assert breakdown.native_value == 6

    machine = sensor_module.DelonghiMachineStatusSensor(coordinator)
    coordinator.monitor = {"source_property": "monitor", "error": "bad frame"}
    assert machine.native_value == "unknown"
    assert machine.extra_state_attributes == {
        "source_property": "monitor",
        "error": "bad frame",
    }
    coordinator.monitor = {
        "status": 7,
        "status_name": "ready",
        "action": 0,
        "progress": 10,
        "accessory": 2,
        "switches": "not-an-int",
        "alarms": None,
    }
    assert machine.extra_state_attributes == {
        "status_code": 7,
        "step_code": 0,
        "progress_percentage": 10,
        "accessory_code": 2,
    }
    coordinator.monitor = {
        **coordinator.monitor,
        "switches": 0x12,
        "alarms": 0x34,
    }
    assert machine.extra_state_attributes["switches"] == "0x0012"
    assert machine.extra_state_attributes["alarms"] == "0x00000034"

    session = sensor_module.DelonghiCloudSessionAppIdSensor(coordinator)
    coordinator.data = {const.APP_ID_PROPERTY: "not-a-property"}
    assert session.native_value == "unknown"
    assert sensor_module._parse_cloud_session_app_id(None) is None
    assert sensor_module._parse_cloud_session_app_id("invalid") is None
    assert sensor_module._parse_cloud_session_app_id("-1") == -1


def test_platform_device_info_fallbacks_are_privacy_safe_and_cloud_only():
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator.device.name = ""
    coordinator.device.oem_model = ""
    coordinator.device.model = "fallback-model"
    coordinator.data = {"software_version": {"value": "Appliance 2.0"}}

    infos = [
        sensor_module.DelonghiMachineStatusSensor(coordinator).device_info,
        binary_sensor_module.DelonghiCloudConnectionBinarySensor(coordinator).device_info,
        button_module.DelonghiWakeButton(coordinator).device_info,
    ]
    for info in infos:
        assert info["name"] == "De'Longhi coffee maker"
        assert info["model"] == "fallback-model"
        assert info["sw_version"] == "Appliance 2.0"
        assert "configuration_url" not in info


def test_binary_sensor_setup_property_parser_and_unavailable_states():
    soul, _client = _coordinator("DL-millcore")
    eletta, _client = _coordinator("DL-striker-cb")
    added = []
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[soul, eletta]))
    asyncio.run(binary_sensor_module.async_setup_entry(object(), entry, added.extend))
    assert sum(isinstance(item, binary_sensor_module.DelonghiCloudConnectionBinarySensor) for item in added) == 2
    assert len(added) == 6

    assert binary_sensor_module._prop_int(None, "x") is None
    assert binary_sensor_module._prop_int({"x": "raw"}, "x") is None
    assert binary_sensor_module._prop_int({"x": {"value": None}}, "x") is None
    assert binary_sensor_module._prop_int({"x": {"value": " 7 "}}, "x") == 7
    assert binary_sensor_module._prop_int({"x": {"value": "bad"}}, "x") is None

    water = binary_sensor_module.DelonghiWaterTankBinarySensor(eletta)
    waste = binary_sensor_module.DelonghiWasteContainerBinarySensor(eletta)
    descale = binary_sensor_module.DelonghiDecalcificationBinarySensor(eletta)
    filter_sensor = binary_sensor_module.DelonghiFilterBinarySensor(eletta)
    for entity in (water, waste, descale, filter_sensor):
        assert entity.available is False
        assert entity.is_on is None
        assert entity.extra_state_attributes == {}

    eletta.stable_maintenance_monitor = {"alarms": 0, "error": "transient"}
    assert water.available is False
    eletta.last_update_success = False
    eletta.stable_maintenance_monitor = {"alarms": 0}
    assert water.available is False


def test_binary_sensor_normal_and_alarm_variants():
    coordinator, _client = _coordinator("DL-striker-cb")
    water = binary_sensor_module.DelonghiWaterTankBinarySensor(coordinator)
    waste = binary_sensor_module.DelonghiWasteContainerBinarySensor(coordinator)
    descale = binary_sensor_module.DelonghiDecalcificationBinarySensor(coordinator)
    filter_sensor = binary_sensor_module.DelonghiFilterBinarySensor(coordinator)

    coordinator.stable_maintenance_monitor = {
        "alarms": 0,
        "switches": 1 << 6,
    }
    coordinator.data = {}
    assert water.available is True
    assert water.is_on is False
    assert water.extra_state_attributes == {
        "water_tank_present": True,
        "water_level_low": True,
        "water_empty_alarm": False,
    }
    assert waste.is_on is False
    assert waste.extra_state_attributes == {
        "waste_container_present": True,
        "waste_full_alarm": False,
    }
    assert descale.is_on is False
    assert descale.extra_state_attributes == {"descale_alarm": False}
    assert filter_sensor.is_on is False
    assert filter_sensor.extra_state_attributes == {"filter_alarm": False}

    coordinator.data = {"d512_percentage_to_deca": {"value": "89"}}
    assert descale.is_on is False
    assert descale.extra_state_attributes["decalc_percentage"] == 89
    coordinator.data = {"d512_percentage_to_deca": {"value": "90"}}
    assert descale.is_on is True
    coordinator.stable_maintenance_monitor = {"alarms": 1 << 2}
    coordinator.data = {"d512_percentage_to_deca": {"value": "invalid"}}
    assert descale.is_on is True
    assert descale.extra_state_attributes == {"descale_alarm": True}


class _ButtonRegistry:
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.removed = []
        self.updated = []

    def async_remove(self, entity_id):
        self.removed.append(entity_id)

    def async_update_entity(self, entity_id, *, new_unique_id):
        self.updated.append((entity_id, new_unique_id))


def _registry_entry(entity_id, unique_id, *, platform=const.DOMAIN, entry_id="entry"):
    return types.SimpleNamespace(
        entity_id=entity_id,
        unique_id=unique_id,
        platform=platform,
        config_entry_id=entry_id,
    )


def test_button_migration_filters_merges_and_canonicalizes_entities():
    dsn = "private-device-id"
    registry = _ButtonRegistry(
        [
            _registry_entry("button.other", f"{dsn}_start_espresso", platform="other"),
            _registry_entry("sensor.not_button", f"{dsn}_start_espresso"),
            _registry_entry("button.unknown", f"{dsn}_start_unknown"),
            _registry_entry("button.espresso", f"{dsn}_start_beverage_1"),
            _registry_entry("button.cold_brew", f"{dsn}_start_cold_brew"),
            _registry_entry("button.mug", f"{dsn}_start_cold_brew_mug_to_go"),
            _registry_entry("button.mug_2", f"{dsn}_start_recipe_140"),
            _registry_entry("button.latte", f"{dsn}_start_beverage_141"),
            _registry_entry("button.latte_2", f"{dsn}_start_cold_brew_latte_mug_to_go"),
        ]
    )
    hass = types.SimpleNamespace(entity_registry=registry)

    button_module._migrate_start_button_entities(hass, "entry", dsn)

    assert "button.mug_2" in registry.removed
    assert "button.latte_2" in registry.removed
    assert ("button.cold_brew", f"{dsn}_start_beverage_120") in registry.updated
    assert ("button.mug", f"{dsn}_start_beverage_140") in registry.updated
    assert not any(entity_id == "button.espresso" for entity_id, _uid in registry.updated)
    assert not any(entity_id == "button.latte" for entity_id, _uid in registry.updated)


class _PlatformEntry:
    def __init__(self, coordinators, entry_id="entry"):
        self.entry_id = entry_id
        self.runtime_data = types.SimpleNamespace(coordinators=coordinators)
        self.unload_callbacks = []

    def async_on_unload(self, callback):
        self.unload_callbacks.append(callback)


def test_button_setup_adds_catalog_learned_and_dynamic_recipes(monkeypatch):
    monkeypatch.setattr(
        button_module,
        "BEVERAGES",
        [(1, "espresso", "Espresso", "mdi:coffee")],
    )
    soul, _client = _coordinator("DL-millcore")
    eletta, _client = _coordinator("DL-striker-cb")
    eletta.learned_start_frames.update({1: "one", 120: "cold", 999: "custom"})
    registry = _ButtonRegistry()
    hass = types.SimpleNamespace(entity_registry=registry)
    batches = []
    entry = _PlatformEntry([soul, eletta])

    asyncio.run(button_module.async_setup_entry(hass, entry, lambda items: batches.append(list(items))))

    initial = batches[0]
    starts = [item for item in initial if isinstance(item, button_module.DelonghiStartBeverageButton)]
    assert {item._bev_id for item in starts} == {1, 120, 999}
    custom = next(item for item in starts if item._bev_id == 999)
    assert custom._attr_translation_key == "start_recipe"
    assert custom._attr_translation_placeholders == {"recipe_id": "999"}
    assert len(entry.unload_callbacks) == 2

    eletta.learned_start_frames[140] = "mug"
    eletta.async_update_listeners()
    assert any(isinstance(item, button_module.DelonghiStartBeverageButton) and item._bev_id == 140 for item in batches[-1])
    batch_count = len(batches)
    eletta.async_update_listeners()
    assert len(batches) == batch_count

    empty_batches = []
    asyncio.run(
        button_module.async_setup_entry(
            hass,
            _PlatformEntry([]),
            lambda items: empty_batches.append(list(items)),
        )
    )
    assert empty_batches == [[]]


def test_button_actions_availability_and_metadata():
    async def scenario():
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator.async_send_beverage = AsyncMock()
        coordinator.async_send_wake = AsyncMock()
        coordinator.async_send_standby = AsyncMock()
        coordinator.async_stop_active_beverage = AsyncMock()
        coordinator.async_synchronize_statistics = AsyncMock()
        coordinator.log_recipe_datapoints = lambda: calls.append("dump")
        coordinator.has_device_signature = lambda: signature_available[0]

        translated = button_module.DelonghiStartBeverageButton(coordinator, 1, "espresso", "Espresso", "mdi:coffee")
        custom = button_module.DelonghiStartBeverageButton(
            coordinator, 999, "recipe_999", "Recipe 999", "mdi:coffee", translated=False
        )
        wake = button_module.DelonghiWakeButton(coordinator)
        standby = button_module.DelonghiStandbyButton(coordinator)
        stop = button_module.DelonghiStopButton(coordinator)
        synchronize = button_module.DelonghiSynchronizeButton(coordinator)
        dump = button_module.DelonghiDumpRecipesButton(coordinator)

        assert translated._attr_translation_key == "start_espresso"
        assert custom._attr_translation_placeholders == {"recipe_id": "999"}
        assert synchronize._attr_translation_key == "synchronize"
        assert synchronize._attr_entity_category == "diagnostic"
        assert synchronize._attr_entity_registry_enabled_default is False
        assert dump._attr_translation_key == "dump_recipes"
        assert dump._attr_entity_category == "diagnostic"
        assert dump._attr_entity_registry_enabled_default is False
        assert wake.available is False
        assert standby.available is False
        assert synchronize.available is False
        signature_available[0] = True
        assert wake.available is True
        assert standby.available is True
        assert synchronize.available is True

        assert translated.available is False
        coordinator.learned_start_frames[1] = "learned"
        assert translated.available is True
        coordinator.last_update_success = False
        assert translated.available is False
        assert wake.available is False
        coordinator.last_update_success = True

        coordinator.active_beverage_id = 1
        assert stop.available is False
        coordinator.learned_stop_frames[1] = "learned-stop"
        assert stop.available is True

        await translated.async_press()
        await wake.async_press()
        await standby.async_press()
        await stop.async_press()
        await synchronize.async_press()
        await dump.async_press()

        coordinator.async_send_beverage.assert_awaited_once_with(1, const.ACTION_START)
        coordinator.async_send_wake.assert_awaited_once()
        coordinator.async_send_standby.assert_awaited_once()
        coordinator.async_stop_active_beverage.assert_awaited_once()
        coordinator.async_synchronize_statistics.assert_awaited_once()
        assert calls == ["dump"]

    calls = []
    signature_available = [False]
    asyncio.run(scenario())


def test_last_command_is_unknown_until_ha_issues_a_command():
    coordinator, _client = _coordinator()

    assert coordinator.last_command_result is None
    assert coordinator.last_command is None


def test_localized_error_factories_preserve_translation_metadata():
    runtime_error = errors_module.translated_error("not_ready")
    service_error = errors_module.translated_service_error("water_tank_empty")
    auth_error = errors_module.translated_auth_error()

    assert str(runtime_error) == errors_module.ERROR_MESSAGES["not_ready"]
    assert runtime_error.translation_domain == const.DOMAIN
    assert runtime_error.translation_key == "not_ready"
    assert isinstance(service_error, ServiceValidationError)
    assert service_error.translation_key == "water_tank_empty"
    assert isinstance(auth_error, ConfigEntryAuthFailed)
    assert auth_error.translation_key == "credentials_invalid"


def test_last_command_metadata_describes_only_the_ha_transaction():
    async def scenario():
        coordinator, _client = _coordinator()

        await coordinator.async_send_beverage(0x01, const.ACTION_START)

        assert coordinator.last_command_result == "sent"
        assert coordinator.last_command is not None
        assert coordinator.last_command["source"] == "home_assistant"
        assert coordinator.last_command["command_type"] == "beverage"
        assert coordinator.last_command["action"] == "start"
        assert coordinator.last_command["beverage_id"] == "0x01"
        assert coordinator.last_command["beverage_name"] == "Espresso"
        assert coordinator.last_command["started_at"].endswith("+00:00")
        assert coordinator.last_command["completed_at"].endswith("+00:00")

        assert coordinator.last_command["beverage_name"] == "Espresso"

    asyncio.run(scenario())


def test_monitor_falls_back_to_second_property_when_preferred_is_invalid(monkeypatch):
    coordinator, _client = _coordinator()

    def parse(value):
        return (
            {"error": "bad"}
            if value == "bad"
            else {
                "status": 7,
                "status_name": "ready",
                "step": 0,
                "progress_percentage": 0,
                "accessory": 0,
            }
        )

    monkeypatch.setattr(coordinator_module, "parse_monitor_b64", parse)
    coordinator._update_monitor(
        {
            "d302_monitor_machine": {"value": "bad"},
            "d302_monitor": {"value": "good"},
        }
    )
    assert coordinator.monitor["source_property"] == "d302_monitor"
    assert coordinator.monitor["status_name"] == "ready"


def test_only_ready_idle_monitor_becomes_maintenance_snapshot(monkeypatch):
    coordinator, _client = _coordinator()
    parsed = {
        "status": 7,
        "status_name": "preparing_beverage",
        "step": 11,
        "progress_percentage": 20,
        "accessory": 0,
        "switches": 0,
        "alarms": 1,
    }
    monkeypatch.setattr(coordinator_module, "parse_monitor_b64", lambda _value: parsed)
    coordinator._update_monitor({"d302_monitor_machine": {"value": "frame"}})
    assert coordinator.stable_maintenance_monitor == {}

    parsed = {**parsed, "status_name": "ready", "step": 0, "alarms": 0}
    coordinator._update_monitor({"d302_monitor_machine": {"value": "frame2"}})
    assert coordinator.stable_maintenance_monitor["alarms"] == 0


def test_completed_standby_requires_two_identical_frames_for_maintenance(monkeypatch):
    coordinator, _client = _coordinator()
    parsed = {
        "status": 0,
        "status_name": "standby",
        "step": 2,
        "progress_percentage": 100,
        "accessory": 0,
        "switches": 0x84,
        "alarms": 0,
    }
    monkeypatch.setattr(coordinator_module, "parse_monitor_b64", lambda _value: parsed)
    props = {"d302_monitor_machine": {"value": "frame"}}
    coordinator._update_monitor(props)
    assert coordinator.stable_maintenance_monitor == {}
    coordinator._update_monitor(props)
    assert coordinator.stable_maintenance_monitor["status_name"] == "standby"


@pytest.mark.parametrize(
    ("monitor", "message"),
    [
        ({"status": 0, "step": 0}, "not ready"),
        ({"status": 7, "step": 1}, "already preparing"),
        ({"status": 7, "step": 4}, "already preparing"),
        ({"status": 7, "step": 255}, "already preparing"),
        ({"status": 7, "step": 0, "alarms": 1}, "water tank is empty"),
        ({"status": 7, "step": 0, "switches": 1 << 3}, "grounds container is missing"),
    ],
)
def test_start_safety_rejects_known_blocking_state(monitor, message):
    coordinator, _client = _coordinator()
    coordinator.monitor = monitor
    with pytest.raises(HomeAssistantError, match=message):
        coordinator._validate_beverage_start()


def test_start_safety_does_not_guess_water_tank_state_from_alarm_13():
    coordinator, _client = _coordinator()
    coordinator.monitor = {
        "status": 7,
        "step": 0,
        "alarms": 1 << 13,
        "switches": 0,
    }
    coordinator._validate_beverage_start()


def test_start_safety_rejects_unknown_monitor_for_learned_models():
    coordinator, _client = _coordinator()
    coordinator.profile = types.SimpleNamespace(learns_from_app=True)
    coordinator.monitor = {"error": "unknown format"}
    with pytest.raises(HomeAssistantError, match="could not be verified"):
        coordinator._validate_beverage_start()


def test_start_safety_rejects_offline_device():
    coordinator, _client = _coordinator()
    coordinator.device.connection_status = "Offline"
    with pytest.raises(HomeAssistantError, match="not connected"):
        coordinator._validate_beverage_start()


def test_authentication_http_5xx_is_cloud_error_not_bad_credentials(monkeypatch):
    class Response:
        status = 503

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def text(self):
            return "temporary outage"

    class Session:
        def __init__(self):
            self.calls = 0

        def post(self, *args, **kwargs):
            self.calls += 1
            return Response()

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(ayla_client.asyncio, "sleep", no_sleep)
    session = Session()
    client = ayla_client.DelonghiAylaClient(session, "user@example.com", "password")

    async def scenario():
        with pytest.raises(ayla_client.CloudError) as raised:
            await client._authentication_request(
                "https://example.invalid/login",
                data={},
                operation="Login",
            )
        assert raised.value.http_status == 503

    asyncio.run(scenario())
    assert session.calls == const.CLOUD_HTTP_RETRY_COUNT + 1


def test_authentication_http_401_is_credential_error():
    class Response:
        status = 401

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def text(self):
            return "rejected"

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    client = ayla_client.DelonghiAylaClient(Session(), "user@example.com", "wrong-password")

    async def scenario():
        with pytest.raises(ayla_client.AuthError):
            await client._authentication_request(
                "https://example.invalid/login",
                data={},
                operation="Login",
            )

    asyncio.run(scenario())


def test_eletta_action_02_is_learned_as_start_when_machine_was_idle():
    coordinator, _client = _coordinator("DL-striker-cb")
    frame = "DRGD8AECAQAoAgQIABsBCn5oaiRo7xEiM0Q="
    decoded = command_builder.decode_command(frame)

    coordinator.monitor = {"status": 7, "step": 0}
    coordinator._maybe_learn_frame(decoded)

    assert coordinator.learned_start_frames[0x01] == frame
    assert 0x01 not in coordinator.learned_stop_frames


def test_eletta_action_02_is_learned_as_stop_when_same_beverage_is_active():
    coordinator, _client = _coordinator("DL-striker-cb")
    frame = "DRGD8AECAQAoAgQIABsBCn5oaiRo7xEiM0Q="
    decoded = command_builder.decode_command(frame)

    coordinator.active_beverage_id = 0x01
    coordinator.monitor = {"status": 7, "step": 4}
    coordinator._maybe_learn_frame(decoded)

    assert coordinator.learned_stop_frames[0x01] == frame
    assert 0x01 not in coordinator.learned_start_frames


def test_invalid_crc_is_never_learned_or_sent():
    coordinator, _client = _coordinator("DL-striker-cb")
    valid = "DRGD8AECAQAoAgQIABsBCn5oaiRo7xEiM0Q="
    raw = bytearray(base64.b64decode(valid))
    raw[6] ^= 0x01
    invalid = base64.b64encode(raw).decode()

    coordinator._maybe_learn_frame(command_builder.decode_command(invalid))

    assert coordinator.learned_start_frames == {}
    assert coordinator.learned_stop_frames == {}
    assert not command_builder.validate_replayed_beverage_frame(
        invalid,
        0x01,
        const.ACTION_START,
        require_eletta=True,
    )


def test_duplicate_command_is_rejected_not_queued():
    async def scenario():
        coordinator, _client = _coordinator()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def first_send():
            entered.set()
            await release.wait()

        first = asyncio.create_task(coordinator._run_command_transaction(first_send))
        await entered.wait()

        with pytest.raises(HomeAssistantError, match="still in progress"):
            await coordinator._run_command_transaction(lambda: asyncio.sleep(0))

        release.set()
        await first
        assert coordinator.last_command_result == "sent"

    asyncio.run(scenario())


def test_missing_learned_frame_is_rejected_without_write():
    async def scenario():
        coordinator, client = _coordinator()

        class LearnOnlyProfile:
            learns_from_app = True
            uses_cloud_session = False

            @staticmethod
            def beverage_value(beverage_id, action, learned_frame):
                return learned_frame

        coordinator.profile = LearnOnlyProfile()
        coordinator.monitor = {"status": 7, "action": 0, "alarms": 0, "switches": 0}
        with pytest.raises(HomeAssistantError, match="until its frame has been learned"):
            await coordinator.async_send_beverage(0x02, const.ACTION_START)

        assert client.writes == []
        assert coordinator.last_command_result == "rejected"

    asyncio.run(scenario())


def test_stop_uses_active_beverage_id():
    async def scenario():
        coordinator, client = _coordinator()
        coordinator.active_beverage_id = 0x07

        await coordinator.async_stop_active_beverage()

        sent = command_builder.decode_command(client.writes[0][2])
        assert sent["beverage_id"] == "0x07"
        assert sent["action"] == const.ACTION_STOP
        assert coordinator.active_beverage_id is None

    asyncio.run(scenario())


def test_cold_connect_is_awaited_before_property_write(monkeypatch):
    async def scenario():
        coordinator, client = _coordinator("DL-striker-cb")
        coordinator.connected_property = "app_device_connected"
        coordinator.data = {const.APP_ID_PROPERTY: {"value": 0}}
        coordinator.monitor = {"status": 7, "action": 0, "alarms": 0, "switches": 0}
        coordinator.learned_start_frames[0x01] = "DRGD8AECAQAoAgQIABsBCn5oaiRo7xEiM0Q="
        monkeypatch.setattr(coordinator_module, "CONNECT_SETTLE_DELAY", 0)

        async def confirmed():
            return True

        async def confirmation_unavailable(_before):
            return None

        coordinator._wait_for_session_confirmed = confirmed
        coordinator._wait_for_command_confirmation = confirmation_unavailable
        await coordinator.async_send_beverage(0x01, const.ACTION_START)

        assert client.connect_posts == 1
        assert len(client.writes) == 1
        assert coordinator.last_command_result == "sent"

    asyncio.run(scenario())


def test_cold_connect_timeout_is_visible_and_does_not_write(monkeypatch):
    async def scenario():
        coordinator, client = _coordinator("DL-striker-cb")
        coordinator.connected_property = "app_device_connected"
        coordinator.data = {const.APP_ID_PROPERTY: {"value": 0}}
        coordinator.monitor = {"status": 7, "action": 0, "alarms": 0, "switches": 0}
        coordinator.learned_start_frames[0x01] = "DRGD8AECAQAoAgQIABsBCn5oaiRo7xEiM0Q="
        monkeypatch.setattr(coordinator_module, "CONNECT_SETTLE_DELAY", 0)

        async def timed_out():
            return False

        coordinator._wait_for_session_confirmed = timed_out
        with pytest.raises(HomeAssistantError, match="Timed out"):
            await coordinator.async_send_beverage(0x01, const.ACTION_START)

        assert client.writes == []
        assert coordinator.last_command_result == "timed_out"
        assert coordinator.active_beverage_id is None

    asyncio.run(scenario())


def test_late_start_acknowledgement_retains_beverage_for_safe_stop():
    async def scenario():
        coordinator, client = _coordinator()

        async def timed_out_after_write(_before):
            return False

        coordinator._wait_for_command_confirmation = timed_out_after_write
        with pytest.raises(HomeAssistantError, match="did not acknowledge"):
            await coordinator.async_send_beverage(0x01, const.ACTION_START)

        assert len(client.writes) == 1
        assert coordinator.last_command_result == "timed_out"
        assert coordinator.active_beverage_id == 0x01

    asyncio.run(scenario())


def test_statistics_sync_refreshes_without_persisting_a_timestamp(monkeypatch):
    async def scenario():
        coordinator, _client = _coordinator()
        refreshes = 0

        async def with_session(send_fn):
            await send_fn()

        async def no_sleep(_delay):
            return None

        async def refresh():
            nonlocal refreshes
            refreshes += 1

        coordinator._with_cloud_session = with_session
        coordinator.async_request_refresh = refresh
        monkeypatch.setattr(coordinator_module.asyncio, "sleep", no_sleep)

        await coordinator.async_synchronize_statistics()

        assert refreshes == 1
        assert coordinator._learned_storage_data() == {"start": {}, "stop": {}}

    asyncio.run(scenario())


@pytest.mark.parametrize("method_name", ["async_send_wake", "async_send_standby"])
def test_power_commands_use_extended_confirmation_timeout(method_name):
    async def scenario():
        coordinator, _client = _coordinator("DL-striker-cb")
        observed: list[float | None] = []

        async def with_session(send_fn):
            await send_fn()

        async def no_session_refresh():
            return None

        async def capture_send(
            _value,
            _label,
            *,
            confirm=True,
            confirmation_timeout=None,
        ):
            assert confirm is True
            observed.append(confirmation_timeout)

        coordinator._with_cloud_session = with_session
        coordinator._maybe_send_session_refresh = no_session_refresh
        coordinator._send_property_command = capture_send
        await getattr(coordinator, method_name)()

        assert observed == [const.POWER_COMMAND_CONFIRM_TIMEOUT]

    asyncio.run(scenario())


def test_foreign_cloud_session_is_not_adopted():
    async def scenario():
        coordinator, client = _coordinator("DL-striker-cb")
        coordinator.connected_property = "app_device_connected"
        coordinator.data = {const.APP_ID_PROPERTY: {"value": 123456}}
        coordinator.monitor = {"status": 7, "action": 0, "alarms": 0, "switches": 0}
        coordinator.learned_start_frames[0x01] = "DRGD8AECAQAoAgQIABsBCn5oaiRo7xEiM0Q="

        with pytest.raises(HomeAssistantError, match="Another application"):
            await coordinator.async_send_beverage(0x01, const.ACTION_START)

        assert client.connect_posts == 0
        assert client.writes == []
        assert coordinator._integration_app_id == coordinator._default_app_id

    asyncio.run(scenario())


def test_known_eletta_signature_restores_device_specific_app_id():
    coordinator, _client = _coordinator("DL-striker-cb")
    captured = "DQ+D8AIDAQBuAgMnAQa/qWp4qtoRIjNE"
    coordinator.learned_start_frames[0x02] = captured

    coordinator._restore_device_app_id()

    signature = command_builder.device_signature_from_frame(captured)
    assert signature == bytes.fromhex("11 22 33 44")
    assert coordinator._integration_app_id == 287_454_020
    assert base64.b64decode(captured)[-4:] == signature


def test_downloaded_diagnostics_redact_credentials_and_identifiers():
    async def scenario():
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator.data = {
            "app_id": {"value": 12_944_929},
            "data_request": {
                "value": "raw-secret-frame",
                "ack_enabled": True,
            },
        }
        coordinator.command_property = "data_request"
        entry = types.SimpleNamespace(
            runtime_data=types.SimpleNamespace(coordinators=[coordinator]),
            version=1,
            data={"email": "private@example.com", "password": "secret-password"},
        )

        diagnostics = await diagnostics_module.async_get_config_entry_diagnostics(object(), entry)
        rendered = json.dumps(diagnostics)

        for secret in (
            "private@example.com",
            "secret-password",
            "private-device-id",
            "raw-secret-frame",
            "12944929",
        ):
            assert secret not in rendered
        assert diagnostics["devices"][0]["property_names"] == [
            "app_id",
            "data_request",
        ]
        assert diagnostics["devices"][0]["detected_properties"]["command_ack_enabled"] is True

        coordinator.data["data_request"] = "unexpected"
        diagnostics = await diagnostics_module.async_get_config_entry_diagnostics(object(), entry)
        assert diagnostics["devices"][0]["detected_properties"]["command_ack_enabled"] is None

        coordinator.data["data_request"] = {"ackEnabled": "unexpected"}
        diagnostics = await diagnostics_module.async_get_config_entry_diagnostics(object(), entry)
        assert diagnostics["devices"][0]["detected_properties"]["command_ack_enabled"] is None

    asyncio.run(scenario())


def test_config_flow_account_validation_maps_all_outcomes(monkeypatch):
    class FakeValidationClient:
        mode = "success"

        def __init__(self, session, email, password):
            self.email = email

        async def async_authenticate(self):
            if self.mode == "auth":
                raise ayla_client.AuthError("bad credentials")
            if self.mode == "cloud":
                raise ayla_client.CloudError("offline")
            if self.mode == "unexpected":
                raise RuntimeError("unexpected")

        async def async_get_devices(self):
            if self.mode == "empty":
                return []
            return [types.SimpleNamespace(name="Machine")]

    monkeypatch.setattr(config_flow_module, "DelonghiAylaClient", FakeValidationClient)
    flow = config_flow_module.DelonghiConfigFlow()

    expected = {
        "auth": ("invalid_auth", None),
        "cloud": ("cannot_connect", None),
        "unexpected": ("unknown", None),
        "empty": ("no_devices", None),
    }
    for mode, result in expected.items():
        FakeValidationClient.mode = mode
        assert asyncio.run(flow._async_validate_account(" user@example.com ", "pw")) == result

    FakeValidationClient.mode = "success"
    error, devices = asyncio.run(flow._async_validate_account(" user@example.com ", "pw"))
    assert error is None
    assert len(devices) == 1


def test_config_flow_user_step_form_error_and_success():
    flow = config_flow_module.DelonghiConfigFlow()
    initial = asyncio.run(flow.async_step_user())
    assert initial["type"] == "form"
    assert initial["step_id"] == "user"

    flow._async_validate_account = AsyncMock(return_value=("cannot_connect", None))
    failed = asyncio.run(flow.async_step_user({const.CONF_EMAIL: " user@example.com ", const.CONF_PASSWORD: "pw"}))
    assert failed["errors"] == {"base": "cannot_connect"}

    flow._async_validate_account = AsyncMock(return_value=(None, [types.SimpleNamespace(name="Machine")]))
    created = asyncio.run(flow.async_step_user({const.CONF_EMAIL: " User@Example.COM ", const.CONF_PASSWORD: "pw"}))
    assert created == {
        "type": "create_entry",
        "title": "De'Longhi Coffee Link – Eletta Explore",
        "data": {const.CONF_EMAIL: "User@Example.COM", const.CONF_PASSWORD: "pw"},
    }
    assert flow.unique_id == "user@example.com"
    assert flow.abort_configured_called is True


def test_config_flow_reauth_and_reconfigure_forms_and_errors():
    flow = config_flow_module.DelonghiConfigFlow()
    entry = types.SimpleNamespace(data={const.CONF_EMAIL: "old@example.com", const.CONF_PASSWORD: "old"})
    flow._reauth_entry = entry
    reauth = asyncio.run(flow.async_step_reauth(entry.data))
    assert reauth["step_id"] == "reauth_confirm"
    assert reauth["description_placeholders"] == {"email": "old@example.com"}

    flow._reconfigure_entry = entry
    initial = asyncio.run(flow.async_step_reconfigure())
    assert initial["step_id"] == "reconfigure"
    flow._async_validate_account = AsyncMock(return_value=("no_devices", None))
    failed = asyncio.run(flow.async_step_reconfigure({const.CONF_PASSWORD: "new"}))
    assert failed["errors"] == {"base": "no_devices"}


def test_coordinator_collection_and_target_resolution_failures():
    coordinator, _client = _coordinator()
    loaded = types.SimpleNamespace(
        state=integration_module.ConfigEntryState.LOADED,
        runtime_data=integration_module.DelonghiRuntimeData(client=object(), coordinators=[coordinator]),
    )
    unloaded = types.SimpleNamespace(
        state="not_loaded",
        runtime_data=integration_module.DelonghiRuntimeData(client=object(), coordinators=[coordinator]),
    )
    invalid_runtime = types.SimpleNamespace(
        state=integration_module.ConfigEntryState.LOADED,
        runtime_data=object(),
    )
    hass = types.SimpleNamespace(
        config_entries=types.SimpleNamespace(async_entries=lambda domain: [unloaded, invalid_runtime, loaded])
    )
    assert integration_module._coordinators(hass) == [coordinator]

    call = types.SimpleNamespace(data={"device_id": ["missing"]})
    hass.device_registry = types.SimpleNamespace(async_get=lambda device_id: None)
    with pytest.raises(ServiceValidationError) as missing:
        integration_module._target_coordinator(hass, call)
    assert missing.value.translation_key == "target_missing"

    hass.device_registry = types.SimpleNamespace(
        async_get=lambda device_id: types.SimpleNamespace(identifiers={(const.DOMAIN, "different-dsn")})
    )
    with pytest.raises(ServiceValidationError) as not_loaded:
        integration_module._target_coordinator(hass, call)
    assert not_loaded.value.translation_key == "target_not_loaded"


def test_async_setup_registers_and_executes_all_services(monkeypatch):
    class Services:
        def __init__(self):
            self.registered = {}

        def async_register(self, domain, service, handler, *, schema):
            self.registered[service] = (handler, schema)

    coordinator = types.SimpleNamespace(
        async_send_beverage=AsyncMock(),
        async_stop_active_beverage=AsyncMock(),
        async_send_raw=AsyncMock(),
    )
    services = Services()
    hass = types.SimpleNamespace(services=services)
    admin = {}

    def register_admin(hass_arg, domain, service, handler, *, schema):
        admin[service] = (handler, schema)

    monkeypatch.setattr(integration_module, "async_register_admin_service", register_admin)
    monkeypatch.setattr(integration_module, "_target_coordinator", lambda hass_arg, call: coordinator)

    assert asyncio.run(integration_module.async_setup(hass, {})) is True
    assert set(services.registered) == {
        const.SERVICE_START_BEVERAGE,
        const.SERVICE_STOP_BEVERAGE,
    }
    assert set(admin) == {const.SERVICE_SEND_RAW_COMMAND}

    start = services.registered[const.SERVICE_START_BEVERAGE][0]
    stop = services.registered[const.SERVICE_STOP_BEVERAGE][0]
    raw = admin[const.SERVICE_SEND_RAW_COMMAND][0]
    asyncio.run(start(types.SimpleNamespace(data={"device_id": ["one"], "beverage": "espresso"})))
    asyncio.run(stop(types.SimpleNamespace(data={"device_id": ["one"], "beverage": "espresso"})))
    asyncio.run(stop(types.SimpleNamespace(data={"device_id": ["one"]})))
    asyncio.run(raw(types.SimpleNamespace(data={"device_id": ["one"], "value_base64": "frame"})))

    coordinator.async_send_beverage.assert_any_await(integration_module.BEVERAGE_IDS["espresso"], const.ACTION_START)
    coordinator.async_send_beverage.assert_any_await(integration_module.BEVERAGE_IDS["espresso"], const.ACTION_STOP)
    coordinator.async_stop_active_beverage.assert_awaited_once()
    coordinator.async_send_raw.assert_awaited_once_with("frame")


class _LifecycleRegistry:
    def __init__(self):
        self.entries = []
        self.removed = []

    def async_remove(self, entity_id):
        self.removed.append(entity_id)


class _LifecycleDeviceRegistry:
    def __init__(self):
        self.entries = []
        self.removed = []

    def async_remove_device(self, device_id):
        self.removed.append(device_id)


class _LifecycleConfigEntries:
    def __init__(self, *, unload_ok=True):
        self.forwarded = []
        self.unloaded = []
        self.reloaded = []
        self.unload_ok = unload_ok

    async def async_forward_entry_setups(self, entry, platforms):
        self.forwarded.append((entry, list(platforms)))
        await asyncio.sleep(0)

    async def async_unload_platforms(self, entry, platforms):
        self.unloaded.append((entry, list(platforms)))
        return self.unload_ok

    async def async_reload(self, entry_id):
        self.reloaded.append(entry_id)
        return True


def _lifecycle_hass(*, unload_ok=True):
    return types.SimpleNamespace(
        entity_registry=_LifecycleRegistry(),
        device_registry=_LifecycleDeviceRegistry(),
        config_entries=_LifecycleConfigEntries(unload_ok=unload_ok),
    )


def _lifecycle_entry():
    return types.SimpleNamespace(
        entry_id="entry",
        data={const.CONF_EMAIL: "user@example.com", const.CONF_PASSWORD: "pw"},
        async_create_background_task=lambda hass, target, name: asyncio.create_task(target, name=name),
    )


def test_stale_devices_and_their_entities_are_removed_from_registries():
    hass = _lifecycle_hass()
    entry = _lifecycle_entry()
    hass.device_registry.entries = [
        types.SimpleNamespace(
            id="active-device",
            identifiers={(const.DOMAIN, "active")},
            config_entry_id=entry.entry_id,
        ),
        types.SimpleNamespace(
            id="stale-device",
            identifiers={(const.DOMAIN, "stale")},
            config_entry_id=entry.entry_id,
        ),
        types.SimpleNamespace(
            id="other-device",
            identifiers={("other_domain", "stale")},
            config_entry_id=entry.entry_id,
        ),
    ]
    hass.entity_registry.entries = [
        types.SimpleNamespace(
            entity_id="sensor.active",
            device_id="active-device",
            config_entry_id=entry.entry_id,
        ),
        types.SimpleNamespace(
            entity_id="sensor.stale",
            device_id="stale-device",
            config_entry_id=entry.entry_id,
        ),
    ]

    integration_module._async_remove_stale_devices(hass, entry, frozenset({"active"}))

    assert hass.entity_registry.removed == ["sensor.stale"]
    assert hass.device_registry.removed == ["stale-device"]


def test_setup_entry_auth_cloud_and_empty_account_failures(monkeypatch):
    class FailingClient:
        mode = "auth"

        def __init__(self, session, email, password):
            pass

        async def async_authenticate(self):
            if self.mode == "auth":
                raise integration_module.AuthError("bad")
            if self.mode == "cloud":
                raise integration_module.CloudError("offline")

        async def async_get_devices(self):
            return []

    monkeypatch.setattr(integration_module, "DelonghiAylaClient", FailingClient)
    for mode, exception in (
        ("auth", ConfigEntryAuthFailed),
        ("cloud", RuntimeError),
        ("empty", RuntimeError),
    ):
        FailingClient.mode = mode
        with pytest.raises(exception):
            asyncio.run(integration_module.async_setup_entry(_lifecycle_hass(), _lifecycle_entry()))


def test_setup_entry_success_and_partial_initialization_cleanup(monkeypatch):
    devices = [types.SimpleNamespace(dsn="first"), types.SimpleNamespace(dsn="second")]

    class Client:
        def __init__(self, session, email, password):
            pass

        async def async_authenticate(self):
            return None

        async def async_get_devices(self):
            return devices

    class Coordinator:
        instances = []
        fail_second = False
        reported_devices = devices

        def __init__(self, hass, client, device, config_entry, device_list_callback):
            self.device = device
            self.config_entry = config_entry
            self.device_list_callback = device_list_callback
            self.loaded = False
            self.refreshed = False
            self.maintenance_confirmed = False
            self.shutdown = False
            self.__class__.instances.append(self)

        async def async_load_learned(self):
            self.loaded = True

        async def async_config_entry_first_refresh(self):
            await self.async_load_learned()
            if self.fail_second and self.device.dsn == "second":
                raise RuntimeError("second failed")
            self.device_list_callback(self.reported_devices)
            self.refreshed = True

        async def async_confirm_initial_maintenance_snapshot(self):
            self.maintenance_confirmed = True

        async def async_shutdown(self):
            self.shutdown = True

    class DssManager:
        instances = []

        def __init__(self, hass, entry, client, coordinators):
            self.started = False
            self.stopped = False
            self.__class__.instances.append(self)

        def start(self):
            self.started = True

        async def async_stop(self):
            self.stopped = True

    monkeypatch.setattr(integration_module, "DelonghiAylaClient", Client)
    monkeypatch.setattr(integration_module, "DelonghiCoordinator", Coordinator)
    monkeypatch.setattr(integration_module, "AylaDssManager", DssManager)

    hass = _lifecycle_hass()
    entry = _lifecycle_entry()
    assert asyncio.run(integration_module.async_setup_entry(hass, entry)) is True
    assert len(entry.runtime_data.coordinators) == 2
    assert all(item.loaded and item.refreshed and item.maintenance_confirmed for item in entry.runtime_data.coordinators)
    assert entry.runtime_data.dss_manager.started is True
    assert hass.config_entries.forwarded == [(entry, integration_module.PLATFORMS)]

    Coordinator.instances = []
    Coordinator.reported_devices = [
        types.SimpleNamespace(dsn="third"),
    ]
    changed_hass = _lifecycle_hass()
    assert asyncio.run(integration_module.async_setup_entry(changed_hass, _lifecycle_entry())) is True
    assert changed_hass.config_entries.reloaded == ["entry"]

    Coordinator.instances = []
    Coordinator.reported_devices = devices
    Coordinator.fail_second = True
    with pytest.raises(RuntimeError, match="second failed"):
        asyncio.run(integration_module.async_setup_entry(_lifecycle_hass(), _lifecycle_entry()))
    first, second = Coordinator.instances
    assert first.shutdown is True
    assert second.shutdown is True

    Coordinator.instances = []
    Coordinator.fail_second = False
    failing_hass = _lifecycle_hass()
    failing_hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=RuntimeError("forward failed"))
    with pytest.raises(RuntimeError, match="forward failed"):
        asyncio.run(integration_module.async_setup_entry(failing_hass, _lifecycle_entry()))
    assert DssManager.instances[-1].stopped is True
    assert all(item.shutdown for item in Coordinator.instances)


def test_unload_entry_stops_dss_only_after_platform_success():
    first = types.SimpleNamespace(async_shutdown=AsyncMock())
    second = types.SimpleNamespace(async_shutdown=AsyncMock())
    dss_manager = types.SimpleNamespace(async_stop=AsyncMock())
    entry = types.SimpleNamespace(
        runtime_data=integration_module.DelonghiRuntimeData(
            client=object(), coordinators=[first, second], dss_manager=dss_manager
        )
    )

    assert asyncio.run(integration_module.async_unload_entry(_lifecycle_hass(unload_ok=True), entry)) is True
    first.async_shutdown.assert_not_awaited()
    second.async_shutdown.assert_not_awaited()
    dss_manager.async_stop.assert_awaited_once()

    first.async_shutdown.reset_mock()
    second.async_shutdown.reset_mock()
    dss_manager.async_stop.reset_mock()
    assert asyncio.run(integration_module.async_unload_entry(_lifecycle_hass(unload_ok=False), entry)) is False
    first.async_shutdown.assert_not_awaited()
    second.async_shutdown.assert_not_awaited()
    dss_manager.async_stop.assert_not_awaited()

    no_dss_entry = types.SimpleNamespace(
        runtime_data=integration_module.DelonghiRuntimeData(client=object(), coordinators=[first, second], dss_manager=None)
    )
    assert asyncio.run(integration_module.async_unload_entry(_lifecycle_hass(unload_ok=True), no_dss_entry)) is True


def test_reauth_rejects_bad_password_then_updates_existing_entry(monkeypatch):
    class FakeAuthClient:
        def __init__(self, session, email, password):
            self.password = password

        async def async_authenticate(self):
            if self.password == "wrong":
                raise ayla_client.AuthError("rejected")

        async def async_get_devices(self):
            return [types.SimpleNamespace(name="Machine")]

    monkeypatch.setattr(config_flow_module, "DelonghiAylaClient", FakeAuthClient)
    flow = config_flow_module.DelonghiConfigFlow()
    entry = types.SimpleNamespace(data={const.CONF_EMAIL: "private@example.com", const.CONF_PASSWORD: "old"})
    flow._reauth_entry = entry

    bad = asyncio.run(flow.async_step_reauth_confirm({const.CONF_PASSWORD: "wrong"}))
    assert bad["type"] == "form"
    assert bad["errors"] == {"base": "invalid_auth"}

    good = asyncio.run(flow.async_step_reauth_confirm({const.CONF_PASSWORD: "replacement"}))
    assert good["type"] == "abort"
    assert good["reason"] == "reauth_successful"
    assert good["entry"] is entry
    assert good["data_updates"] == {const.CONF_PASSWORD: "replacement"}
    assert flow.unique_id == "private@example.com"


def test_reconfigure_validates_and_updates_existing_account(monkeypatch):
    validated_emails = []

    class FakeAuthClient:
        def __init__(self, session, email, password):
            self.email = email
            validated_emails.append(email)

        async def async_authenticate(self):
            return None

        async def async_get_devices(self):
            return [types.SimpleNamespace(name="Machine")]

    monkeypatch.setattr(config_flow_module, "DelonghiAylaClient", FakeAuthClient)
    flow = config_flow_module.DelonghiConfigFlow()
    entry = types.SimpleNamespace(data={const.CONF_EMAIL: "old@example.com", const.CONF_PASSWORD: "old"})
    flow._reconfigure_entry = entry

    result = asyncio.run(flow.async_step_reconfigure({const.CONF_PASSWORD: "new-password"}))

    assert result["reason"] == "reconfigure_successful"
    assert result["data_updates"] == {const.CONF_PASSWORD: "new-password"}
    assert validated_emails == ["old@example.com"]
    assert flow.unique_id == "old@example.com"


def test_device_target_resolves_exactly_one_coordinator():
    coordinator_a, _client_a = _coordinator()
    coordinator_b, _client_b = _coordinator()
    coordinator_a.device.dsn = "device-a"
    coordinator_b.device.dsn = "device-b"
    runtime = integration_module.DelonghiRuntimeData(client=object(), coordinators=[coordinator_a, coordinator_b])
    entry = types.SimpleNamespace(
        state="loaded",
        runtime_data=runtime,
    )
    device = types.SimpleNamespace(
        identifiers={(const.DOMAIN, "device-a")},
    )

    class Registry:
        @staticmethod
        def async_get(device_id):
            return device if device_id == "ha-device-a" else None

    hass = types.SimpleNamespace(
        config_entries=types.SimpleNamespace(
            async_entries=lambda domain: [entry],
        ),
        device_registry=Registry(),
    )
    call = types.SimpleNamespace(data={"device_id": ["ha-device-a"]})

    assert integration_module._target_coordinator(hass, call) is coordinator_a

    ambiguous = types.SimpleNamespace(data={"device_id": ["one", "two"]})
    with pytest.raises(HomeAssistantError, match="exactly one"):
        integration_module._target_coordinator(hass, ambiguous)

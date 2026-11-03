"""Conservative issue #15 handling and replay-safe filter scale regression tests."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import types
from unittest.mock import AsyncMock, Mock

import pytest
from test_reliability import (
    _coordinator,
    _lifecycle_entry,
    _lifecycle_hass,
    _load,
    const,
    coordinator_module,
    integration_module,
    model_profiles,
    sensor_module,
)

migration = _load("statistics_migration")
counters = sys.modules[f"{sensor_module.__package__}.counters"]


@pytest.mark.parametrize(
    "oem,divisor", [("DL-striker-cb", 2000), ("DL-striker-base", 1000), ("DL-millcore", 1000), ("unknown", 1000)]
)
def test_filter_scale_is_model_specific(oem, divisor):
    assert model_profiles.profile_for(oem).filter_water_volume_divisor == divisor
    coordinator, _ = _coordinator(oem)
    coordinator.data = {"d555_water_filter_qty": {"value": 80303}}
    sensor = sensor_module.DelonghiCounterSensor(coordinator, "d555_water_filter_qty", "water_filter_quantity", "mdi:water")
    assert sensor.native_value == round(80303 / divisor, 3)
    assert sensor._attr_unique_id.endswith("_water_filter_quantity")


@pytest.mark.parametrize(
    "value,expected",
    [
        ('{"last_4_water_calc_qty":25,"last_4_calc_threshold":100}', 25),
        ({"last_4_water_calc_qty": "200", "last_4_calc_threshold": "100"}, 100),
        ('{"last_4_water_calc_qty":0,"last_4_calc_threshold":100}', 0),
        ('{"last_4_water_calc_qty":25,"last_4_calc_threshold":0}', None),
        ('{"last_4_water_calc_qty":25}', None),
        ('{"last_4_water_calc_qty":true,"last_4_calc_threshold":100}', None),
        ('{"last_4_water_calc_qty":1.5,"last_4_calc_threshold":100}', None),
        ('{"last_4_water_calc_qty":-1,"last_4_calc_threshold":100}', None),
        ('{"last_4_water_calc_qty":"bad","last_4_calc_threshold":100}', None),
        ('{"last_4_water_calc_qty":1,"last_4_calc_threshold":null}', None),
        ('{"broken":}', None),
        (1, None),
        (None, None),
    ],
)
def test_optional_service_ratio_never_invents_zero_or_units(value, expected):
    assert counters.service_descale_progress(value) == expected


def test_service_sensors_are_validated_opt_in_diagnostics():
    coordinator, _ = _coordinator("DL-striker-cb")
    coordinator.data = {
        "d580_service_parameters": {
            "value": json.dumps(
                {
                    "last_4_water_calc_qty": 25,
                    "last_4_calc_threshold": 100,
                    "descale_status": 7,
                }
            )
        }
    }
    entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(coordinators=[coordinator]))
    added = []
    asyncio.run(sensor_module.async_setup_entry(object(), entry, added.extend))
    service = {item._key: item for item in added if isinstance(item, sensor_module.DelonghiServiceParameterSensor)}
    assert {key: item.native_value for key, item in service.items()} == {
        "service_descale_progress": 25,
        "service_descale_status": 7,
    }
    assert all(
        item._attr_entity_category == "diagnostic" and item._attr_entity_registry_enabled_default is False
        for item in service.values()
    )
    assert service["service_descale_status"]._attr_state_class is None
    assert service["service_descale_progress"]._attr_native_unit_of_measurement == "%"
    coordinator.data = {}
    assert all(item.native_value is None for item in service.values())


def test_missing_signature_repair_is_actionable_and_clears(monkeypatch):
    coordinator, _ = _coordinator("DL-striker-cb")
    coordinator.connected_property = "app_device_connected"
    create = Mock()
    delete = Mock()
    monkeypatch.setattr(coordinator_module.ir, "async_create_issue", create)
    monkeypatch.setattr(coordinator_module.ir, "async_delete_issue", delete)
    coordinator._sync_statistics_learning_issue()
    assert create.call_args.kwargs["translation_key"] == "statistics_learning_required"
    assert create.call_args.kwargs["is_fixable"] is False
    monkeypatch.setattr(coordinator, "has_device_signature", lambda: True)
    coordinator._sync_statistics_learning_issue()
    delete.assert_called_with(coordinator.hass, const.DOMAIN, coordinator._statistics_learning_issue_id)


def _migration_environment(monkeypatch, *, entity=True, metadata=True):
    statistic_id = "sensor.synthetic_filter_water"
    meta = {
        "statistic_id": statistic_id,
        "source": "recorder",
        "unit_class": "volume",
        "unit_of_measurement": "L",
        "mean_type": 0,
        "has_sum": True,
        "name": None,
    }
    state = {"journal": None, "saves": [], "ignore_imports": False, "stats": {statistic_id: meta} if metadata else {}}

    class FakeStore:
        async def async_load(self):
            return copy.deepcopy(state["journal"])

        async def async_save(self, value):
            state["journal"] = copy.deepcopy(value)
            state["saves"].append(copy.deepcopy(value))

    class Recorder:
        async def async_add_executor_job(self, function):
            return function()

        async def async_block_till_done(self):
            return None

    recorder = Recorder()
    modules = {
        "homeassistant.helpers.recorder": types.SimpleNamespace(get_instance=lambda hass: recorder),
        "homeassistant.components.recorder.statistics": types.SimpleNamespace(
            get_metadata=lambda *args, statistic_ids, **kwargs: {
                key: (1, value) for key, value in state["stats"].items() if key in statistic_ids
            }
        ),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(migration, "Store", lambda *args: FakeStore())
    coordinator, _ = _coordinator("DL-striker-cb")
    unique_id = f"{coordinator.device.dsn}_water_filter_quantity"

    class Registry:
        def __init__(self):
            self.entries = (
                {
                    unique_id: types.SimpleNamespace(
                        entity_id=statistic_id,
                        name="Custom name",
                        icon=None,
                        area_id="kitchen",
                        disabled_by="user",
                        hidden_by=None,
                        labels={"coffee"},
                        aliases=["Filter"],
                        options={"sensor": {"display_precision": 2}},
                        device_id="synthetic-device",
                        config_subentry_id=None,
                    )
                }
                if entity
                else {}
            )

        @property
        def entities(self):
            return {item.entity_id: item for item in self.entries.values()}

        def async_get_entity_id(self, domain, platform, unique):
            return self.entries[unique].entity_id if unique in self.entries else None

        def async_update_entity(self, entity_id, **updates):
            key, item = next((key, item) for key, item in self.entries.items() if item.entity_id == entity_id)
            if "new_entity_id" in updates:
                new = updates.pop("new_entity_id")
                if not state["ignore_imports"] and entity_id in state["stats"]:
                    state["stats"][new] = state["stats"].pop(entity_id)
                item.entity_id = new
            if "new_unique_id" in updates:
                self.entries[updates.pop("new_unique_id")] = self.entries.pop(key)
            for name, value in updates.items():
                setattr(item, name, value)
            return item

        def async_get_or_create(self, domain, platform, unique, **kwargs):
            if unique not in self.entries:
                self.entries[unique] = types.SimpleNamespace(entity_id=f"sensor.{kwargs['suggested_object_id']}")
            return self.entries[unique]

        def async_update_entity_options(self, entity_id, domain, options):
            self.entities[entity_id].options = {domain: options}

    monkeypatch.setattr(migration.er, "RegistryEntryDisabler", types.SimpleNamespace(INTEGRATION="integration"), raising=False)
    monkeypatch.setattr(migration.er, "RegistryEntryHider", types.SimpleNamespace(INTEGRATION="integration"), raising=False)
    registry = Registry()
    hass = types.SimpleNamespace(
        state="running",
        config=types.SimpleNamespace(components={"recorder"}),
        entity_registry=registry,
        states=types.SimpleNamespace(async_remove=Mock()),
    )
    return hass, coordinator, state, registry, meta, recorder


def test_statistics_migration_archives_once_and_is_replay_safe(monkeypatch):
    hass, coordinator, state, registry, meta, recorder = _migration_environment(monkeypatch)
    recorder.async_block_till_done = AsyncMock(side_effect=RuntimeError("interrupted"))
    with pytest.raises(RuntimeError, match="interrupted"):
        asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert state["journal"]["complete"] is False
    assert len(registry.entries) == 1
    assert "sensor.synthetic_filter_water" not in state["stats"]
    recorder.async_block_till_done = AsyncMock()
    asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert state["journal"]["complete"] is True
    assert len(registry.entries) == 2
    active = registry.entities["sensor.synthetic_filter_water"]
    assert active.name == "Custom name" and active.disabled_by == "user" and active.labels == {"coffee"}
    assert active.options == {"sensor": {"display_precision": 2}}
    archive = registry.entities[state["journal"]["archive_id"]]
    assert archive.disabled_by == "integration" and archive.hidden_by == "integration"
    previous_saves = len(state["saves"])
    asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert len(state["saves"]) == previous_saves


def test_new_filter_sensor_has_no_old_history_to_archive(monkeypatch):
    hass, coordinator, state, *_ = _migration_environment(monkeypatch, entity=False, metadata=False)
    asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert state["journal"] == {"complete": True, "reason": "new_entity"}


def test_first_migration_defers_before_start_without_touching_registry(monkeypatch):
    hass, coordinator, state, registry, *_ = _migration_environment(monkeypatch)
    hass.state = "not_running"
    before = set(registry.entities)
    with pytest.raises(RuntimeError, match="Waiting for Home Assistant startup"):
        asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert state["journal"] is None and set(registry.entities) == before
    # A completed marker must not delay subsequent HA restarts.
    state["journal"] = {"complete": True}
    asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))


def test_statistics_migration_is_fail_closed_and_optional(monkeypatch):
    hass, coordinator, state, registry, meta, _ = _migration_environment(monkeypatch)
    import hashlib

    archive_id = (
        "sensor.synthetic_filter_water_legacy_scale_v1_" + hashlib.sha256(coordinator.device.dsn.encode()).hexdigest()[:12]
    )
    state["stats"][archive_id] = meta
    with pytest.raises(ValueError, match="already in use"):
        asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    state["stats"].pop(archive_id)
    state["ignore_imports"] = True
    with pytest.raises(ValueError, match="did not finish"):
        asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert state["journal"]["complete"] is False
    state["journal"] = None
    coordinator.profile = model_profiles.profile_for("DL-millcore")
    asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))
    assert state["journal"] is None
    hass.config.components.clear()
    asyncio.run(migration.async_migrate_filter_statistics(hass, _lifecycle_entry(), [coordinator]))


def test_setup_does_not_publish_corrected_states_after_failed_migration(monkeypatch):
    client = types.SimpleNamespace(
        async_authenticate=AsyncMock(), async_get_devices=AsyncMock(return_value=[types.SimpleNamespace(dsn="synthetic")])
    )
    coordinator = types.SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(),
        async_confirm_initial_maintenance_snapshot=AsyncMock(),
        async_shutdown=AsyncMock(),
    )
    monkeypatch.setattr(integration_module, "DelonghiAylaClient", lambda *args: client)
    monkeypatch.setattr(integration_module, "DelonghiCoordinator", lambda *args: coordinator)
    monkeypatch.setattr(integration_module, "AylaDssManager", lambda *args: object())
    monkeypatch.setattr(integration_module, "async_migrate_filter_statistics", AsyncMock(side_effect=ValueError("unsafe")))
    hass = _lifecycle_hass()
    with pytest.raises(RuntimeError, match="could not be completed safely"):
        asyncio.run(integration_module.async_setup_entry(hass, _lifecycle_entry()))
    coordinator.async_shutdown.assert_awaited_once()
    assert hass.config_entries.forwarded == []

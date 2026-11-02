"""Verify the scale transition with real registries and an in-memory Recorder."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import partial
from types import SimpleNamespace

import pytest
from homeassistant.components.recorder import migration as recorder_schema_migration
from homeassistant.components.recorder.core import Recorder
from homeassistant.components.recorder.db_schema import Statistics, StatisticsShortTerm
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_delonghi_coffeelink_eletta_explore.const import DOMAIN
from custom_components.ha_delonghi_coffeelink_eletta_explore.statistics_migration import async_migrate_filter_statistics


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prepare the in-memory database before the HA fixture is constructed."""
    # The upstream fixture autospecs _find_schema_errors. Python 3.14 evaluates
    # its deferred annotation although HA imports Recorder only for TYPE_CHECKING.
    # Supply the genuine class for introspection; do not mock database behavior.
    monkeypatch.setattr(recorder_schema_migration, "Recorder", Recorder, raising=False)


async def test_filter_scale_archive_keeps_ids_preferences_and_unmodified_history(hass: HomeAssistant, recorder_mock) -> None:
    """Do not recycle old-scale statistics into the corrected active entity."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Synthetic Coffee Link")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    unique = "synthetic-filter-device_water_filter_quantity"
    old = registry.async_get_or_create("sensor", DOMAIN, unique, config_entry=entry, suggested_object_id="test_filter_water")
    registry.async_update_entity(old.entity_id, name="My filter", disabled_by=er.RegistryEntryDisabler.USER)
    recorder_mock.async_import_statistics(
        {
            "statistic_id": old.entity_id,
            "source": "recorder",
            "unit_class": "volume",
            "unit_of_measurement": "L",
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "name": None,
        },
        [{"start": datetime(2026, 11, 2, tzinfo=UTC), "state": 80.303, "sum": 80.303}],
        Statistics,
    )
    recorder_mock.async_import_statistics(
        {
            "statistic_id": old.entity_id,
            "source": "recorder",
            "unit_class": "volume",
            "unit_of_measurement": "L",
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "name": None,
        },
        [{"start": datetime(2026, 11, 2, tzinfo=UTC), "state": 80.303, "sum": 80.303}],
        StatisticsShortTerm,
    )
    await recorder_mock.async_block_till_done()
    coordinator = SimpleNamespace(
        device=SimpleNamespace(dsn="synthetic-filter-device"), profile=SimpleNamespace(filter_water_volume_divisor=2000)
    )
    await async_migrate_filter_statistics(hass, entry, [coordinator])
    await hass.async_block_till_done()
    await recorder_mock.async_block_till_done()
    active = registry.async_get(old.entity_id)
    assert active is not None and active.unique_id == unique
    assert active.name == "My filter" and active.disabled_by is er.RegistryEntryDisabler.USER
    archive_id = registry.async_get_entity_id("sensor", DOMAIN, unique + "_legacy_scale_v1")
    assert archive_id is not None
    archive = registry.async_get(archive_id)
    assert archive.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert archive.hidden_by is er.RegistryEntryHider.INTEGRATION
    metadata = await recorder_mock.async_add_executor_job(partial(get_metadata, hass, statistic_ids={old.entity_id, archive_id}))
    assert set(metadata) == {archive_id}
    for period in ("hour", "5minute"):
        rows = await recorder_mock.async_add_executor_job(
            partial(
                statistics_during_period,
                hass,
                datetime(2026, 11, 1, tzinfo=UTC),
                datetime(2026, 11, 3, tzinfo=UTC) + timedelta(days=1),
                {archive_id},
                period,
                None,
                {"state", "sum"},
            )
        )
        assert rows[archive_id][0]["state"] == 80.303
        assert rows[archive_id][0]["sum"] == 80.303
    # Repeating setup must neither archive the corrected series nor add entries.
    before = set(registry.entities)
    await async_migrate_filter_statistics(hass, entry, [coordinator])
    assert set(registry.entities) == before

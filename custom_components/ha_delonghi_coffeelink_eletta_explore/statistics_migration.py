"""Archive the old filter scale through HA's supported registry rename hooks.

Do not mix old-scale raw state history with corrected statistics. Recorder moves
both state history and statistics when the old registry entity is renamed. A
replacement retains the active entity ID, unique ID and user preferences, but
starts a clean, correctly scaled history. The disabled archive is never polled.
"""

from __future__ import annotations

import asyncio
import hashlib
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.const import EntityCategory
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from . import DelonghiConfigEntry
    from .coordinator import DelonghiCoordinator


async def async_migrate_filter_statistics(
    hass: HomeAssistant, entry: DelonghiConfigEntry, coordinators: list[DelonghiCoordinator]
) -> None:
    """Archive existing history once, before exposing corrected sensor states."""
    if "recorder" not in hass.config.components:
        return
    from homeassistant.components.recorder.statistics import get_metadata
    from homeassistant.helpers.recorder import get_instance

    recorder = get_instance(hass)
    registry = er.async_get(hass)
    for coordinator in coordinators:
        if coordinator.profile.filter_water_volume_divisor != 2000:
            continue
        unique_id = f"{coordinator.device.dsn}_water_filter_quantity"
        device_hash = hashlib.sha256(coordinator.device.dsn.encode()).hexdigest()[:12]
        store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}_filter_scale_v2_{device_hash}")
        journal = await store.async_load()
        if journal is not None and journal.get("complete"):
            continue
        entity_id = journal["entity_id"] if journal is not None else registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is None:
            await store.async_save({"complete": True, "reason": "new_entity"})
            continue
        # Recorder's worker can wait for HA startup before consuming queued jobs.
        # ConfigEntryNotReady releases the bootstrap wait and lets HA retry after
        # reaching RUNNING. A new/already-migrated entity never needs this wait.
        if hass.state is not CoreState.running:
            raise ConfigEntryNotReady("Waiting for Home Assistant startup before archiving legacy filter history")
        if journal is None:
            old = registry.entities[entity_id]
            archive_id = f"{entity_id}_legacy_scale_v1_{device_hash}"
            archive_statistics = await recorder.async_add_executor_job(partial(get_metadata, hass, statistic_ids={archive_id}))
            if archive_id in registry.entities or archive_statistics:
                raise ValueError("Filter-volume archive ID is already in use; refusing to overwrite history")
            journal = {
                "complete": False,
                "entity_id": entity_id,
                "archive_id": archive_id,
                "preferences": {
                    "name": old.name,
                    "icon": old.icon,
                    "area_id": old.area_id,
                    "disabled_by": old.disabled_by,
                    "hidden_by": old.hidden_by,
                    "labels": sorted(old.labels),
                    "aliases": [alias for alias in old.aliases if isinstance(alias, str)],
                },
                "options": dict(old.options),
                "device_id": old.device_id,
                "config_subentry_id": old.config_subentry_id,
            }
            await store.async_save(journal)
        entity_id, archive_id = journal["entity_id"], journal["archive_id"]
        archive_unique_id = f"{unique_id}_legacy_scale_v1"
        if registry.async_get_entity_id("sensor", DOMAIN, archive_unique_id) is None:
            registry.async_update_entity(
                entity_id,
                new_entity_id=archive_id,
                new_unique_id=archive_unique_id,
                disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                hidden_by=er.RegistryEntryHider.INTEGRATION,
                entity_category=EntityCategory.DIAGNOSTIC,
                name=None,
                translation_key="water_filter_quantity_legacy",
                original_name="Filter water volume (legacy scale archive)",
            )
        # Registry events invoke Recorder's public rename handlers, which enqueue
        # both metadata moves. Wait before reusing the original active ID.
        await asyncio.sleep(0)
        await recorder.async_block_till_done()
        remaining = await recorder.async_add_executor_job(partial(get_metadata, hass, statistic_ids={entity_id}))
        if remaining:
            raise ValueError("Filter-volume history rename did not finish; preserving migration journal")
        hass.states.async_remove(entity_id)
        active = registry.async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            config_entry=entry,
            config_subentry_id=journal["config_subentry_id"],
            device_id=journal["device_id"],
            suggested_object_id=entity_id.split(".", 1)[1],
            has_entity_name=True,
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="water_filter_quantity",
            unit_of_measurement="L",
        )
        preferences = dict(journal["preferences"])
        preferences["labels"] = set(preferences["labels"])
        registry.async_update_entity(active.entity_id, new_entity_id=entity_id, **preferences)
        for domain, options in journal["options"].items():
            registry.async_update_entity_options(entity_id, domain, options)
        await store.async_save({"complete": True, "entity_id": entity_id, "archive_id": archive_id, "version": "1.3.2-beta.3"})

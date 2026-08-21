"""Button platform for De'Longhi Coffee Link – Eletta Explore - one button per beverage."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .button_migration import (
    canonical_start_unique_id,
    preferred_entity_index,
    start_button_beverage_id,
)
from .const import ACTION_START, BEVERAGES, DOMAIN, ELETTA_LEARNED_BEVERAGES
from .coordinator import DelonghiCoordinator
from .entity import DelonghiCoordinatorEntity

if TYPE_CHECKING:
    from . import DelonghiConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _migrate_start_button_entities(
    hass: HomeAssistant,
    config_entry_id: str,
    dsn: str,
) -> None:
    """Merge legacy aliases and migrate beverage buttons to stable unique IDs."""
    registry = er.async_get(hass)
    key_to_id = {key: beverage_id for beverage_id, key, _name, _icon in BEVERAGES}
    key_to_id.update({key: beverage_id for beverage_id, (key, _name, _icon) in ELETTA_LEARNED_BEVERAGES.items()})
    grouped: dict[int, list[er.RegistryEntry]] = {}
    for registry_entry in er.async_entries_for_config_entry(registry, config_entry_id):
        if registry_entry.platform != DOMAIN or not registry_entry.entity_id.startswith("button."):
            continue
        beverage_id = start_button_beverage_id(registry_entry.unique_id, dsn, key_to_id)
        if beverage_id is not None:
            grouped.setdefault(beverage_id, []).append(registry_entry)

    for beverage_id, candidates in grouped.items():
        canonical = canonical_start_unique_id(dsn, beverage_id)
        if len(candidates) == 1 and candidates[0].unique_id == canonical:
            continue
        keep_index = preferred_entity_index([item.entity_id for item in candidates])
        keeper = candidates[keep_index]
        for index, duplicate in enumerate(candidates):
            if index != keep_index:
                registry.async_remove(duplicate.entity_id)
                _LOGGER.info(
                    "Removed duplicate beverage button %s in favour of %s",
                    duplicate.entity_id,
                    keeper.entity_id,
                )
        if keeper.unique_id != canonical:
            registry.async_update_entity(keeper.entity_id, new_unique_id=canonical)
            _LOGGER.info(
                "Migrated beverage button %s to stable beverage ID %s",
                keeper.entity_id,
                beverage_id,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DelonghiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators = entry.runtime_data.coordinators
    entities: list[ButtonEntity] = []
    for coord in coordinators:
        _migrate_start_button_entities(hass, entry.entry_id, coord.device.dsn)
        entities.append(DelonghiWakeButton(coord))
        entities.append(DelonghiStandbyButton(coord))
        beverage_catalog = {bev_id: (key, friendly, icon) for bev_id, key, friendly, icon in BEVERAGES}
        created_beverage_ids: set[int] = set()

        def _new_recipe_buttons(
            coordinator: DelonghiCoordinator = coord,
            created: set[int] = created_beverage_ids,
            catalog: dict[int, tuple[str, str, str]] = beverage_catalog,
        ) -> list[ButtonEntity]:
            supported = set(coordinator.learned_start_frames) if coordinator.profile.learns_from_app else set(catalog)
            added: list[ButtonEntity] = []
            for beverage_id in sorted(supported - created):
                if beverage_id in catalog:
                    key, friendly, icon = catalog[beverage_id]
                    translated = True
                elif beverage_id in ELETTA_LEARNED_BEVERAGES:
                    key, friendly, icon = ELETTA_LEARNED_BEVERAGES[beverage_id]
                    translated = True
                else:
                    friendly, icon = f"Recipe {beverage_id}", "mdi:coffee"
                    key = f"recipe_{beverage_id}"
                    translated = False
                added.append(
                    DelonghiStartBeverageButton(
                        coordinator,
                        beverage_id,
                        key,
                        friendly,
                        icon,
                        translated=translated,
                    )
                )
                created.add(beverage_id)
            return added

        entities.extend(_new_recipe_buttons())

        def _discover_learned_buttons(
            callback: Callable[[], list[ButtonEntity]] = _new_recipe_buttons,
        ) -> None:
            if added := callback():
                async_add_entities(added)

        entry.async_on_unload(coord.async_add_listener(_discover_learned_buttons))
        entities.append(DelonghiStopButton(coord))
        entities.append(DelonghiSynchronizeButton(coord))
        entities.append(DelonghiDumpRecipesButton(coord))
    async_add_entities(entities)


class _Base(DelonghiCoordinatorEntity, ButtonEntity):
    """Base for coffee-machine button entities."""


class DelonghiStartBeverageButton(_Base):
    """Press to START a specific beverage."""

    def __init__(
        self,
        coord: DelonghiCoordinator,
        bev_id: int,
        key: str,
        friendly: str,
        icon: str,
        *,
        translated: bool = True,
    ) -> None:
        super().__init__(coord)
        self._bev_id = bev_id
        self._attr_unique_id = canonical_start_unique_id(coord.device.dsn, bev_id)
        if translated:
            self._attr_translation_key = f"start_{key}"
        else:
            self._attr_translation_key = "start_recipe"
            self._attr_translation_placeholders = {"recipe_id": str(bev_id)}

    async def async_press(self) -> None:
        _LOGGER.info("Start beverage 0x%02x (%s)", self._bev_id, self.name)
        await self.coordinator.async_send_beverage(self._bev_id, ACTION_START)

    @property
    def available(self) -> bool:
        """Do not offer a known-incompatible synthesized command."""
        return super().available and (
            not self.coordinator.profile.learns_from_app or self._bev_id in self.coordinator.learned_start_frames
        )


class DelonghiWakeButton(_Base):
    """Wake the machine from standby (captured cmd family 0x84 0x0f)."""

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.device.dsn}_wake"
        self._attr_translation_key = "wake"

    async def async_press(self) -> None:
        _LOGGER.info("Sending WAKE to machine")
        await self.coordinator.async_send_wake()

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.has_device_signature()


class DelonghiStandbyButton(_Base):
    """Put the machine in standby / power it off (cmd family 0x84 0x0f, params 01 01).

    Same effect as pressing the physical power button. Validated live on the
    PrimaDonna Soul; on Eletta-style models the learned device signature is
    appended (see coordinator.async_send_standby).
    """

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.device.dsn}_standby"
        self._attr_translation_key = "standby"

    async def async_press(self) -> None:
        _LOGGER.info("Sending STANDBY to machine")
        await self.coordinator.async_send_standby()

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.has_device_signature()


class DelonghiStopButton(_Base):
    """Stop the beverage tracked by the coordinator."""

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.device.dsn}_stop"
        self._attr_translation_key = "stop"

    async def async_press(self) -> None:
        await self.coordinator.async_stop_active_beverage()

    @property
    def available(self) -> bool:
        """Stop is safe only while the active beverage is known."""
        beverage_id = self.coordinator.active_beverage_id
        return (
            super().available
            and beverage_id is not None
            and (not self.coordinator.profile.learns_from_app or beverage_id in self.coordinator.learned_stop_frames)
        )


class DelonghiSynchronizeButton(_Base):
    """Acquire a safe cloud session and request fresh counters/state."""

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.device.dsn}_synchronize"
        self._attr_translation_key = "synchronize"

    async def async_press(self) -> None:
        await self.coordinator.async_synchronize_statistics()

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.has_device_signature()


class DelonghiDumpRecipesButton(_Base):
    """Diagnostic: log the machine's stored recipe datapoints (read-only).

    Sends nothing to the machine - only dumps the recipe definitions it already
    reports, so the recipe->command mapping can be confirmed (zero-touch work).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coord: DelonghiCoordinator) -> None:
        super().__init__(coord)
        self._attr_unique_id = f"{coord.device.dsn}_dump_recipes"
        self._attr_translation_key = "dump_recipes"

    async def async_press(self) -> None:
        self.coordinator.log_recipe_datapoints()

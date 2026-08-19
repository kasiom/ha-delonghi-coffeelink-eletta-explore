"""Shared entity helpers for De'Longhi Coffee Link – Eletta Explore."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import DelonghiCoordinator
from .firmware import device_firmware_version


class DelonghiCoordinatorEntity(CoordinatorEntity[DelonghiCoordinator]):
    """Base for entities belonging to one discovered coffee machine."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return stable device-registry metadata shared by every platform."""
        device = self.coordinator.device
        return DeviceInfo(
            identifiers={(DOMAIN, device.dsn)},
            name=device.name or f"DeLonghi {device.dsn}",
            manufacturer=MANUFACTURER,
            model=device.oem_model or device.model,
            sw_version=device_firmware_version(
                self.coordinator.data, device.sw_version
            ),
            configuration_url=(
                f"http://{device.lan_ip}" if device.lan_ip else None
            ),
        )

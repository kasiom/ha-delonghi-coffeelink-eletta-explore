"""Smoke tests against Home Assistant's real config-entry and registry APIs."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_delonghi_coffeelink_eletta_explore.ayla_client import (
    AylaDevice,
    DelonghiAylaClient,
)
from custom_components.ha_delonghi_coffeelink_eletta_explore.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
)
from custom_components.ha_delonghi_coffeelink_eletta_explore.diagnostics import (
    async_get_config_entry_diagnostics,
)

TEST_EMAIL = "owner@example.test"
TEST_PASSWORD = "not-a-real-password"
TEST_DSN = "synthetic-device-id"

if sys.platform == "win32":
    # Windows' ProactorEventLoop implements its internal wakeup pipe with a
    # loopback socket.  Linux CI keeps the Home Assistant socket ban enabled.
    pytestmark = pytest.mark.enable_socket


def _device() -> AylaDevice:
    """Return a synthetic device that cannot identify a real coffee maker."""
    return AylaDevice(
        dsn=TEST_DSN,
        name="Test coffee maker",
        oem_model="DL-millcore",
        model="Synthetic model",
        sw_version="test-version",
        lan_ip="",
        connection_status="online",
    )


async def test_user_config_flow_uses_real_home_assistant(hass: HomeAssistant) -> None:
    """Create an entry through Home Assistant's actual data-entry flow."""
    with (
        patch.object(DelonghiAylaClient, "async_authenticate", AsyncMock()),
        patch.object(
            DelonghiAylaClient,
            "async_get_devices",
            AsyncMock(return_value=[_device()]),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: f" {TEST_EMAIL} ", CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_setup_diagnostics_and_unload_use_real_registries(
    hass: HomeAssistant,
) -> None:
    """Exercise setup, platforms, diagnostics and unload through real HA APIs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="De'Longhi Coffee Link – Eletta Explore",
        unique_id=TEST_EMAIL,
        data={CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    device = _device()
    properties = {"data_request": {"value": ""}}

    with (
        patch.object(DelonghiAylaClient, "async_authenticate", AsyncMock()),
        patch.object(
            DelonghiAylaClient,
            "async_get_devices",
            AsyncMock(return_value=[device]),
        ),
        patch.object(
            DelonghiAylaClient,
            "async_get_properties",
            AsyncMock(return_value=properties),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert len(entry.runtime_data.coordinators) == 1

        device_entry = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, TEST_DSN), entry.entry_id
        )
        assert device_entry is not None
        assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        rendered = repr(diagnostics)
        assert TEST_EMAIL not in rendered
        assert TEST_PASSWORD not in rendered
        assert TEST_DSN not in rendered

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED

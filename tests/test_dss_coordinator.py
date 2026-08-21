"""Coordinator coverage for hybrid DSS updates and diagnostics."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from test_reliability import (
    HomeAssistantError,
    _coordinator,
    ayla_client,
    const,
    coordinator_module,
)

cm = coordinator_module


def run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


def _dss_event(**changes: Any) -> Any:
    values = {
        "sequence": "1",
        "event_type": "datapoint",
        "dsn": "private-device-id",
        "property_name": "counter",
        "datapoint_id": "dp-1",
        "value": 2,
        "updated_at": "2026-08-20T12:00:00Z",
        "acked_at": None,
        "ack_status": None,
        "ack_message": None,
    }
    values.update(changes)
    return cm.DssEvent(**values)


def test_poll_merge_and_connection_info_are_privacy_safe() -> None:
    coordinator, client = _coordinator()
    coordinator.data = {
        "newer": {"value": 2, "data_updated_at": "2026-08-20T12:00:02Z"},
        "older": {"value": 1, "dataUpdatedAt": "2026-08-20T12:00:00Z"},
        "invalid": "value",
    }
    props = {
        "newer": {"value": 1, "data_updated_at": "2026-08-20T12:00:01Z"},
        "older": {"value": 2, "data_updated_at": "2026-08-20T12:00:01Z"},
        "invalid": {"value": 3},
        "missing": "value",
    }
    merged = coordinator._merge_poll_with_push(props)
    assert merged["newer"]["value"] == 2
    assert merged["older"]["value"] == 2

    async def scenario() -> None:
        client.async_get_connection_info = AsyncMock(
            return_value={
                "connectivityType": "Wifi",
                "rssi": "-57",
                "networkName": "secret",
            }
        )
        await coordinator._async_refresh_connection_info(4000)
        assert coordinator.connection_info == {
            "connectivity_type": "Wifi",
            "rssi": -57,
        }
        assert "secret" not in str(coordinator.connection_info)
        await coordinator._async_refresh_connection_info(4001)
        assert client.async_get_connection_info.await_count == 1

        coordinator._last_connection_info_refresh = 0
        client.async_get_connection_info = AsyncMock(
            return_value={"connectivity_type": 3, "rssi": "invalid"}
        )
        await coordinator._async_refresh_connection_info(8000)
        assert coordinator.connection_info == {
            "connectivity_type": None,
            "rssi": None,
        }

        coordinator._last_connection_info_refresh = 0
        client.async_get_connection_info = AsyncMock(
            side_effect=ayla_client.CloudError("missing", http_status=404)
        )
        await coordinator._async_refresh_connection_info(12000)
        assert coordinator._connection_info_supported is False
        await coordinator._async_refresh_connection_info(16000)

        coordinator._connection_info_supported = None
        coordinator._last_connection_info_refresh = 0
        client.async_get_connection_info = AsyncMock(
            side_effect=ayla_client.CloudError("temporary", http_status=503)
        )
        await coordinator._async_refresh_connection_info(20000)
        assert coordinator._connection_info_supported is None

    run(scenario())


def test_monitor_rejects_older_official_ordering_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, _client = _coordinator()
    parsed = {
        "status": 7,
        "status_name": "ready",
        "step": 0,
        "progress_percentage": 0,
        "accessory": 0,
    }
    monkeypatch.setattr(cm, "parse_monitor_b64", lambda _value: dict(parsed))
    monkeypatch.setattr(cm, "monitor_ordering_token", Mock(side_effect=[20, 10]))
    coordinator._update_monitor({"d302_monitor_machine": {"value": "new"}})
    newest = dict(coordinator.monitor)
    coordinator._update_monitor({"d302_monitor_machine": {"value": "old"}})
    assert coordinator.monitor == newest
    assert coordinator._monitor_ordering_token == 20


def test_dss_state_switches_polling_interval_and_refreshes_on_loss() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        coordinator._dss_sequences[("datapoint", "counter")] = 5
        coordinator.async_request_refresh = AsyncMock()
        coordinator.set_dss_state("streaming")
        assert (
            coordinator.update_interval.total_seconds()
            == const.DSS_FALLBACK_SCAN_INTERVAL
        )
        assert coordinator._dss_sequences == {}
        coordinator.set_dss_state("polling", request_refresh=True)
        task = coordinator._dss_fallback_refresh_task
        coordinator.set_dss_state("polling", request_refresh=True)
        assert coordinator._dss_fallback_refresh_task is task
        await task
        coordinator.async_request_refresh.assert_awaited_once()
        assert coordinator.update_interval.total_seconds() == const.DEFAULT_SCAN_INTERVAL

    run(scenario())


def test_dss_sequence_ack_cache_and_event_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    assert coordinator._normalized_dss_sequence(None) is None
    assert coordinator._normalized_dss_sequence("5") == 5
    assert coordinator._normalized_dss_sequence("x") == "x"
    assert coordinator._accept_dss_sequence(_dss_event(sequence=None)) is True
    assert coordinator._accept_dss_sequence(_dss_event(sequence="2")) is True
    assert coordinator._accept_dss_sequence(_dss_event(sequence="1")) is False
    assert coordinator._accept_dss_sequence(_dss_event(sequence="3")) is True
    assert coordinator._accept_dss_sequence(_dss_event(sequence="x")) is True
    assert coordinator._accept_dss_sequence(_dss_event(sequence="x")) is False

    coordinator._dss_sequences.clear()
    assert coordinator.handle_dss_event(_dss_event(sequence="1")) is True
    assert coordinator.data["counter"]["value"] == 2
    assert coordinator.handle_dss_event(_dss_event(sequence="1")) is False
    assert (
        coordinator.handle_dss_event(
            _dss_event(
                sequence="2",
                event_type="connectivity",
                property_name=None,
                datapoint_id=None,
            )
        )
        is False
    )

    coordinator._dss_sequences.clear()
    assert (
        coordinator.handle_dss_event(
            _dss_event(
                event_type="datapointack",
                property_name=None,
                ack_status=200,
            )
        )
        is True
    )
    assert coordinator._recent_dss_acks["dp-1"] == 200

    assert coordinator.handle_dss_event(
        _dss_event(
            sequence="2",
            event_type="datapointack",
            value=None,
            updated_at=None,
            acked_at="2026-08-20T12:00:01Z",
            ack_status=202,
            ack_message="accepted",
        )
    ) is True
    assert coordinator.data["counter"]["acked_at"] == "2026-08-20T12:00:01Z"
    assert coordinator.data["counter"]["ack_status"] == 202
    assert coordinator.data["counter"]["ack_message"] == "accepted"

    coordinator.data["counter"]["data_updated_at"] = "2026-08-20T12:00:05Z"
    coordinator._dss_sequences.clear()
    assert (
        coordinator.handle_dss_event(
            _dss_event(updated_at="2026-08-20T12:00:04Z")
        )
        is False
    )

    monitor = Mock()
    sniff = Mock()
    session = Mock()
    monkeypatch.setattr(coordinator, "_update_monitor", monitor)
    monkeypatch.setattr(coordinator, "_sniff_app_traffic", sniff)
    monkeypatch.setattr(coordinator, "_update_session_from_props", session)
    coordinator.command_property = "command"
    coordinator.response_property = "response"
    coordinator._dss_sequences.clear()
    coordinator.handle_dss_event(
        _dss_event(
            sequence="3", property_name="d302_monitor_machine", value="frame"
        )
    )
    coordinator.handle_dss_event(
        _dss_event(sequence="4", property_name="command", value="frame")
    )
    coordinator.handle_dss_event(
        _dss_event(sequence="5", property_name=const.APP_ID_PROPERTY, value=0)
    )
    monitor.assert_called_once()
    sniff.assert_called_once()
    session.assert_called_once()

    async def waiter_scenario() -> None:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        coordinator._dss_ack_waiters["live"] = future
        coordinator._remember_dss_ack("live", 201)
        assert await future == 201
        coordinator._remember_dss_ack("live", 202)
        assert coordinator._recent_dss_acks["live"] == 202
        for index in range(40):
            coordinator._remember_dss_ack(f"cached-{index}", 200)
        assert len(coordinator._recent_dss_acks) <= 32

    run(waiter_scenario())


def test_exact_dss_ack_wait_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        assert await coordinator._async_wait_for_dss_ack("one") == (False, None)
        coordinator.dss_state = "streaming"
        coordinator._recent_dss_acks["cached"] = 200
        assert await coordinator._async_wait_for_dss_ack("cached") == (True, 200)

        task = asyncio.create_task(coordinator._async_wait_for_dss_ack("live"))
        await asyncio.sleep(0)
        coordinator._remember_dss_ack("live", None)
        assert await task == (True, None)

        class AckArrivesBetweenChecks(dict[str, int]):
            checks = 0

            def __contains__(self, key: object) -> bool:
                self.checks += 1
                return self.checks > 1

        coordinator._recent_dss_acks = AckArrivesBetweenChecks(race=204)
        assert await coordinator._async_wait_for_dss_ack("race") == (True, 204)
        coordinator._recent_dss_acks = {}

        monkeypatch.setattr(cm, "DSS_ACK_GRACE_PERIOD", 0)
        assert await coordinator._async_wait_for_dss_ack("timeout") == (False, None)

    run(scenario())


def test_send_property_command_prefers_exact_ack_and_handles_rejection() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()
        client.async_set_property_value = AsyncMock(
            return_value={"datapoint": {"id": "exact"}}
        )
        coordinator._begin_command({"command_type": "test"})
        coordinator._async_wait_for_dss_ack = AsyncMock(return_value=(True, 200))
        await coordinator._send_property_command("frame", "test")
        assert coordinator.last_command_result == "acknowledged"
        assert coordinator.last_command["confirmation_source"] == "dss_ack"
        assert coordinator.last_command["ack_status"] == 200

        coordinator._begin_command({"command_type": "test"})
        coordinator._async_wait_for_dss_ack = AsyncMock(return_value=(True, 400))
        with pytest.raises(HomeAssistantError, match="explicitly rejected"):
            await coordinator._send_property_command("frame", "test")
        assert coordinator.last_command_result == "rejected"
        assert coordinator.last_command["ack_status"] == 400

        coordinator._begin_command({"command_type": "test"})
        coordinator._async_wait_for_dss_ack = AsyncMock(return_value=(True, 0))
        coordinator._wait_for_command_confirmation = AsyncMock(return_value=True)
        await coordinator._send_property_command(
            "frame", "test", confirmation_timeout=1
        )
        assert coordinator.last_command["confirmation_source"] == "cloud_state"

        coordinator._begin_command({"command_type": "test"})
        coordinator._async_wait_for_dss_ack = AsyncMock(return_value=(True, None))
        coordinator._wait_for_command_confirmation = AsyncMock(return_value=True)
        await coordinator._send_property_command("frame", "test")

        coordinator.last_command = None
        coordinator._async_wait_for_dss_ack = AsyncMock(return_value=(True, 200))
        await coordinator._send_property_command("frame", "test")
        assert coordinator.last_command_result == "acknowledged"

        coordinator.last_command = None
        coordinator._async_wait_for_dss_ack = AsyncMock(return_value=(True, 400))
        with pytest.raises(HomeAssistantError, match="explicitly rejected"):
            await coordinator._send_property_command("frame", "test")

    run(scenario())


def test_confirmation_checks_push_state_before_poll() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        coordinator.response_property = "response"
        coordinator._last_resp_marker = "new"
        coordinator.async_request_refresh = AsyncMock()
        assert await coordinator._wait_for_command_confirmation(("old", {})) is True
        coordinator.async_request_refresh.assert_not_awaited()

        coordinator.response_property = None
        coordinator.monitor = {"status": 7}
        assert (
            await coordinator._wait_for_command_confirmation((None, {"status": 0}))
            is True
        )

    run(scenario())


def test_shutdown_cancels_dss_refresh_and_ack_waiters() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        refresh = asyncio.create_task(asyncio.sleep(30))
        waiter = asyncio.get_running_loop().create_future()
        coordinator._dss_fallback_refresh_task = refresh
        coordinator._dss_ack_waiters["id"] = waiter
        await coordinator.async_shutdown()
        await asyncio.sleep(0)
        assert refresh.cancelled()
        assert waiter.cancelled()
        assert coordinator._dss_ack_waiters == {}

    run(scenario())

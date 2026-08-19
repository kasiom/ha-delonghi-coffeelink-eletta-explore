"""Additional branch coverage for the coordinator's state machine.

The Home Assistant and cloud doubles are defined in ``test_reliability``.  All
tests remain local and deterministic; no real Ayla request is made.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import types
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from test_reliability import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    _coordinator,
    ayla_client,
    command_builder,
    const,
    coordinator_module,
)

cm = coordinator_module


def run(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run a coordinator coroutine in an isolated event loop."""
    return asyncio.run(coro)


def replacement_device(dsn: str = "private-device-id") -> Any:
    return ayla_client.AylaDevice(
        dsn=dsn,
        name="Updated",
        oem_model="DL-striker-cb",
        model="Eletta",
        sw_version="2",
        lan_ip="192.0.2.20",
        connection_status="online",
    )


def test_shutdown_resets_session_cancels_task_and_calls_base(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    task = Mock()
    coordinator._post_command_refresh_task = task
    coordinator._last_connect_at = 10
    coordinator._integration_app_id = 123
    shutdown = AsyncMock()
    monkeypatch.setattr(cm.DataUpdateCoordinator, "async_shutdown", shutdown)

    run(coordinator.async_shutdown())

    assert coordinator._last_connect_at == 0
    assert coordinator._integration_app_id == coordinator._default_app_id
    task.cancel.assert_called_once()
    assert coordinator._post_command_refresh_task is None
    shutdown.assert_awaited_once()

    coordinator, _client = _coordinator()
    run(coordinator.async_shutdown())


def test_update_data_detects_channels_refreshes_metadata_and_reuses_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, client = _coordinator("DL-striker-cb")
    coordinator.command_property = None
    props = {
        const.COMMAND_PROPERTY_CANDIDATES[0]: {"value": "command"},
        const.RESPONSE_PROPERTY_CANDIDATES[0]: {"value": "response"},
        const.CONNECTED_PROPERTY_CANDIDATES[0]: {"value": "connected"},
    }
    client.async_get_properties = AsyncMock(return_value=props)
    replacement = replacement_device()
    client.async_get_devices = AsyncMock(
        side_effect=[[replacement_device("other"), replacement], [replacement]]
    )
    sniff = Mock()
    monitor = Mock()
    session = Mock()
    device_list_callback = Mock()
    coordinator._device_list_callback = device_list_callback
    monkeypatch.setattr(coordinator, "_sniff_app_traffic", sniff)
    monkeypatch.setattr(coordinator, "_update_monitor", monitor)
    monkeypatch.setattr(coordinator, "_update_session_from_props", session)
    coordinator._last_device_metadata_refresh = -1e20

    assert run(coordinator._async_update_data()) == props
    assert coordinator.command_property == const.COMMAND_PROPERTY_CANDIDATES[0]
    assert coordinator.response_property == const.RESPONSE_PROPERTY_CANDIDATES[0]
    assert coordinator.connected_property == const.CONNECTED_PROPERTY_CANDIDATES[0]
    assert coordinator.device is replacement
    device_list_callback.assert_called_once_with(
        [replacement_device("other"), replacement]
    )
    sniff.assert_called_once_with(props)
    monitor.assert_called_once_with(props)
    session.assert_called_once_with(props)

    assert run(coordinator._async_update_data()) == props
    assert client.async_get_devices.await_count == 1


@pytest.mark.parametrize(
    ("error", "expected_type", "message"),
    [
        (ayla_client.AuthError("bad"), ConfigEntryAuthFailed, "credentials"),
        (ayla_client.CloudError("offline"), RuntimeError, "Ayla cloud error"),
        (ValueError("broken"), RuntimeError, "Error fetching Delonghi data"),
    ],
)
def test_update_data_maps_failures(
    error: Exception,
    expected_type: type[Exception],
    message: str,
) -> None:
    coordinator, client = _coordinator()
    client.async_get_properties = AsyncMock(side_effect=error)
    with pytest.raises(expected_type, match=message):
        run(coordinator._async_update_data())


def test_detect_property_required_optional_and_found() -> None:
    coordinator, _client = _coordinator()
    assert coordinator._detect_property({"second": {}}, ["first", "second"], "test") == "second"
    assert coordinator._detect_property({}, ["missing"], "test", required=False) is None
    with pytest.raises(ayla_client.CloudError, match="No known test property"):
        coordinator._detect_property({}, ["missing"], "test")


def test_monitor_empty_first_error_and_nonfatal_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _client = _coordinator()
    coordinator._update_monitor({})
    assert coordinator.monitor == {}

    monkeypatch.setattr(cm, "parse_monitor_b64", lambda value: {"error": value})
    coordinator._update_monitor(
        {
            const.MONITOR_PROPERTY_CANDIDATES[0]: {"value": " first "},
            const.MONITOR_PROPERTY_CANDIDATES[1]: {"value": "second"},
        }
    )
    assert coordinator.monitor == {
        "error": " first ",
        "source_property": const.MONITOR_PROPERTY_CANDIDATES[0],
    }

    monkeypatch.setattr(cm, "parse_monitor_b64", Mock(side_effect=ValueError("bad monitor")))
    coordinator._update_monitor({const.MONITOR_PROPERTY_CANDIDATES[0]: {"value": "frame"}})
    assert coordinator.monitor == {}


def test_monitor_maintenance_requires_complete_stable_state(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _client = _coordinator()
    parsed = {
        "status": 7,
        "status_name": "ready",
        "action": 0,
        "progress": 0,
        "accessory": 1,
        "switches": "unknown",
        "alarms": 0,
    }
    monkeypatch.setattr(cm, "parse_monitor_b64", lambda _value: dict(parsed))
    props = {const.MONITOR_PROPERTY_CANDIDATES[0]: {"value": "frame"}}
    coordinator._update_monitor(props)
    assert coordinator.stable_maintenance_monitor == {}

    parsed["switches"] = 2
    coordinator._update_monitor(props)
    assert coordinator.stable_maintenance_monitor["status_name"] == "ready"
    parsed["accessory"] = 2
    coordinator._update_monitor(props)
    assert coordinator._maintenance_candidate_count == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, None), (" 123 ", 123), ("bad", None), (object(), None)],
)
def test_parse_app_id_value(raw: Any, expected: int | None) -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    assert coordinator._parse_app_id_value(raw) == expected


def test_app_id_from_props_and_cached_or_live_read() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        assert coordinator._app_id_from_props({}) is None
        assert coordinator._app_id_from_props({const.APP_ID_PROPERTY: "wrong"}) is None
        coordinator.data = {const.APP_ID_PROPERTY: {"value": "55"}}
        coordinator._fetch_app_id_live = AsyncMock(return_value=(66, True))
        assert await coordinator._read_app_id() == 55
        assert await coordinator._read_app_id(live=True) == 66
        coordinator.data = {const.APP_ID_PROPERTY: {"value": "bad"}}
        assert await coordinator._read_app_id() == 66

    run(scenario())


def test_fetch_app_id_live_success_and_cloud_failure() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator("DL-striker-cb")
        client.async_get_property_resilient = AsyncMock(
            side_effect=[{"value": "77"}, ayla_client.CloudError("offline", http_status=503)]
        )
        assert await coordinator._fetch_app_id_live() == (77, True)
        assert await coordinator._fetch_app_id_live() == (None, False)

    run(scenario())


def test_wait_for_session_confirmation_success_progress_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def success() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._fetch_app_id_live = AsyncMock(
            side_effect=[(None, False), (coordinator._integration_app_id, True)]
        )
        times = iter([0.0, 0.0, 16.0, 16.0, 17.0])
        monkeypatch.setattr(cm.time, "time", lambda: next(times))
        monkeypatch.setattr(cm.asyncio, "sleep", AsyncMock())
        assert await coordinator._wait_for_session_confirmed() is True
        assert coordinator._session_confirmed is True

    run(success())

    async def timeout() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._fetch_app_id_live = AsyncMock(return_value=(999, True))
        monkeypatch.setattr(cm, "CONNECT_CONFIRM_TIMEOUT", 0)
        monkeypatch.setattr(cm.time, "time", lambda: 100.0)
        assert await coordinator._wait_for_session_confirmed() is False
        assert coordinator._session_confirmed is False
        coordinator._fetch_app_id_live.assert_awaited_once()

    run(timeout())


def test_session_state_update_holders_reversion_and_nonfatal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    own = coordinator._integration_app_id
    for value, confirmed in ((None, False), (0, False), (own, True), (999, False)):
        coordinator._update_session_from_props({const.APP_ID_PROPERTY: {"value": value}})
        assert coordinator._session_confirmed is confirmed

    coordinator._integration_app_id = 999
    coordinator._last_connect_at = 20
    coordinator._update_session_from_props({const.APP_ID_PROPERTY: {"value": 0}})
    assert coordinator._integration_app_id == coordinator._default_app_id
    assert coordinator._last_connect_at == 0

    monkeypatch.setattr(coordinator, "_app_id_from_props", Mock(side_effect=ValueError("bad")))
    coordinator._update_session_from_props({})


def test_cloud_session_holder_and_revert_foreign_id() -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    own = coordinator._integration_app_id
    assert coordinator.cloud_session_holder(None) == "unknown"
    assert coordinator.cloud_session_holder(0) == "free"
    assert coordinator.cloud_session_holder(own) == "ha"
    assert coordinator.cloud_session_holder(999) == "foreign"

    coordinator._integration_app_id = 999
    coordinator._last_connect_at = 10
    coordinator._revert_foreign_app_id_if_session_clear(None)
    assert coordinator._integration_app_id == coordinator._default_app_id
    assert coordinator._last_connect_at == 0
    coordinator._integration_app_id = 999
    coordinator._revert_foreign_app_id_if_session_clear(123)
    assert coordinator._integration_app_id == 999


def test_start_validation_remaining_paths_and_signature() -> None:
    coordinator, _client = _coordinator()
    coordinator.monitor = {}
    coordinator._validate_beverage_start()
    coordinator.monitor = {"status": 7, "step": 0, "alarms": "?", "switches": "?"}
    coordinator._validate_beverage_start()

    coordinator.monitor = {"status": 7, "step": 0, "alarms": 1 << 1, "switches": 0}
    with pytest.raises(HomeAssistantError, match="grounds container is full"):
        coordinator._validate_beverage_start()
    coordinator.monitor = {"status": 7, "step": 0, "alarms": 0, "switches": 1 << 4}
    with pytest.raises(HomeAssistantError, match="water tank is missing"):
        coordinator._validate_beverage_start()

    assert coordinator.has_device_signature() is True
    eletta, _client = _coordinator("DL-striker-cb")
    assert eletta.has_device_signature() is False
    eletta.learned_start_frames[1] = "DQ+D8AIDAQBuAgMnAQa/qWp4qtoRIjNE"
    assert eletta.has_device_signature() is True


def test_command_metadata_default_unknown_beverage_and_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, _client = _coordinator()
    monkeypatch.setattr(coordinator, "_command_timestamp", lambda: "now")
    coordinator._begin_command(None)
    assert coordinator.last_command == {
        "source": "home_assistant",
        "command_type": "unknown",
        "started_at": "now",
    }
    coordinator._set_last_command_result("sent", completed=True)
    assert coordinator.last_command["completed_at"] == "now"
    context = coordinator._beverage_command_context(0xFE, const.ACTION_STOP)
    assert context["beverage_name"] == "0xfe"
    assert context["action"] == "stop"


def test_post_command_refresh_cancels_previous_uses_ha_task_and_handles_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        previous = Mock()
        coordinator._post_command_refresh_task = previous
        refresh = AsyncMock()
        coordinator.async_request_refresh = refresh
        monkeypatch.setattr(cm, "POST_COMMAND_REFRESH_DELAY", 0)
        created: list[str] = []

        def create_task(
            hass: Any, coro: Coroutine[Any, Any, Any], name: str
        ) -> asyncio.Task[Any]:
            created.append(name)
            return asyncio.create_task(coro, name=name)

        coordinator._config_entry = types.SimpleNamespace(
            async_create_background_task=create_task
        )
        coordinator._schedule_post_command_refresh()
        await coordinator._post_command_refresh_task
        previous.cancel.assert_called_once()
        refresh.assert_awaited_once()
        assert created == [
            f"{const.DOMAIN}_post_command_refresh_{coordinator._device_log_id}"
        ]

        coordinator._post_command_refresh_task = None
        coordinator.async_request_refresh = AsyncMock(side_effect=RuntimeError("refresh failed"))
        coordinator._schedule_post_command_refresh()
        await coordinator._post_command_refresh_task

    run(scenario())


def test_wait_for_command_confirmation_response_monitor_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        monkeypatch.setattr(cm.asyncio, "sleep", AsyncMock())

        coordinator.response_property = "response"
        coordinator._last_resp_marker = "old"

        async def change_response() -> None:
            coordinator._last_resp_marker = "new"

        coordinator.async_request_refresh = change_response
        assert await coordinator._wait_for_command_confirmation(("old", {}), timeout=1) is True

        coordinator.response_property = None
        coordinator.monitor = {"status": 7}

        async def change_monitor() -> None:
            coordinator.monitor = {"status": 5}

        coordinator.async_request_refresh = change_monitor
        assert await coordinator._wait_for_command_confirmation((None, {"status": 7}), timeout=1) is True

        coordinator.async_request_refresh = AsyncMock()
        assert await coordinator._wait_for_command_confirmation((None, coordinator.monitor), timeout=0) is False

    run(scenario())


def test_send_property_command_confirmation_modes() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()
        coordinator._wait_for_command_confirmation = AsyncMock(side_effect=[True, None])
        await coordinator._send_property_command("one", "first")
        assert coordinator.last_command_result == "acknowledged"
        await coordinator._send_property_command("two", "second", confirm=False)
        await coordinator._send_property_command("three", "third", confirmation_timeout=9)
        assert client.writes == [
            (coordinator.device.dsn, "data_request", "one"),
            (coordinator.device.dsn, "data_request", "two"),
            (coordinator.device.dsn, "data_request", "three"),
        ]
        assert coordinator._wait_for_command_confirmation.await_args_list[-1].kwargs == {
            "timeout": 9
        }

    run(scenario())


def test_session_refresh_power_values_and_freshness(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        send = AsyncMock()
        coordinator._send_property_command = send
        coordinator.monitor = {"status": 7}
        await coordinator._maybe_send_session_refresh()
        send.assert_not_awaited()
        coordinator.monitor = {"status": 0}
        await coordinator._maybe_send_session_refresh()
        send.assert_awaited_once()
        assert send.await_args.kwargs == {"confirm": False}
        assert coordinator._wake_command_value()
        assert coordinator._standby_command_value()

        monkeypatch.setattr(cm.time, "time", lambda: 100.0)
        coordinator._last_connect_at = 99.0
        assert coordinator._session_is_fresh(999) is True
        coordinator._last_connect_at = 100.0 - cm.CONNECT_SETTLE_DELAY - 1
        assert coordinator._session_is_fresh(None) is True
        assert coordinator._session_is_fresh(coordinator._integration_app_id) is True
        assert coordinator._session_is_fresh(999) is False
        coordinator._last_connect_at = -1000
        assert coordinator._session_is_fresh(coordinator._integration_app_id) is False

    run(scenario())


def test_post_cloud_session_optional_and_present() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator("DL-striker-cb")
        await coordinator._post_cloud_session()
        assert client.connect_posts == 0
        coordinator.connected_property = "connected"
        await coordinator._post_cloud_session()
        assert client.connect_posts == 1

    run(scenario())


def test_with_cloud_session_cached_verification_and_confirmed_send() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator.connected_property = "connected"
        coordinator._read_app_id = AsyncMock(return_value=coordinator._integration_app_id)
        coordinator._session_is_fresh = Mock(return_value=True)
        coordinator._session_confirmed = False
        coordinator._fetch_app_id_live = AsyncMock(side_effect=[(None, False), (999, True)])
        send = AsyncMock()

        with pytest.raises(HomeAssistantError, match="could not be verified"):
            await coordinator._with_cloud_session(send)
        with pytest.raises(HomeAssistantError, match="could not be verified"):
            await coordinator._with_cloud_session(send)

        coordinator._fetch_app_id_live = AsyncMock(
            return_value=(coordinator._integration_app_id, True)
        )
        await coordinator._with_cloud_session(send)
        send.assert_awaited_once()

        coordinator._session_confirmed = True
        await coordinator._with_cloud_session(send)
        assert send.await_count == 2

    run(scenario())


def test_sniffer_guards_channels_and_nonfatal_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _client = _coordinator()
    capture = Mock()
    monkeypatch.setattr(coordinator, "_capture_channel", capture)
    coordinator.response_property = "response"
    coordinator._sniff_app_traffic({})
    assert capture.call_count == 2

    capture.side_effect = ValueError("bad capture")
    coordinator._sniff_app_traffic({})


def test_capture_channel_all_origins_and_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _client = _coordinator()
    learn = Mock()
    monkeypatch.setattr(coordinator, "_maybe_learn_frame", learn)
    monkeypatch.setattr(cm, "decode_command", lambda value: {"type": value})

    coordinator._capture_channel({}, "command", "command")
    coordinator._capture_channel({"command": "wrong"}, "command", "command")
    coordinator._capture_channel({"command": {"value": "  "}}, "command", "command")

    coordinator._capture_channel(
        {"command": {"value": " first ", "data_updated_at": "m1"}},
        "command",
        "command",
    )
    coordinator._capture_channel(
        {"command": {"value": "first", "data_updated_at": "m1"}},
        "command",
        "command",
    )
    learn.assert_not_called()

    coordinator._capture_channel(
        {"command": {"value": "app-value", "data_updated_at": "m2"}},
        "command",
        "command",
    )
    learn.assert_called_once_with({"type": "app-value"})

    coordinator._record_sent("own-value")
    coordinator._capture_channel(
        {"command": {"value": "own-value", "data_updated_at": "m3"}},
        "command",
        "command",
    )
    assert learn.call_count == 1

    coordinator._capture_channel(
        {"response": {"value": "reply", "data_updated_at": "r1"}},
        "response",
        "response",
    )
    coordinator._capture_channel(
        {"response": {"value": "reply-2", "data_updated_at": "r2"}},
        "response",
        "response",
    )
    assert coordinator._last_resp_marker == "r2"


def test_load_learned_handles_store_failure_and_empty() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._store.async_load = AsyncMock(side_effect=RuntimeError("disk"))
        await coordinator.async_load_learned()
        coordinator._store.async_load = AsyncMock(return_value=None)
        await coordinator.async_load_learned()

    run(scenario())


def test_load_learned_filters_frames_and_invalid_wake(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._store.async_load = AsyncMock(return_value={"stored": True})
        start = {1: "start-good", 2: "start-bad"}
        stop = {1: "stop-wrong-signature", 3: "stop-good"}
        monkeypatch.setattr(cm, "deserialize_learned_frames", lambda _data: (start, stop, "wake"))

        def validate(frame: str, *_args: Any, expected_signature=None, **_kwargs: Any) -> bool:
            if frame == "start-bad":
                return False
            if frame == "stop-wrong-signature":
                return expected_signature is None
            return True

        signatures = {
            "start-good": b"same",
            "stop-wrong-signature": b"diff",
            "stop-good": b"same",
            "wake": b"diff",
        }
        monkeypatch.setattr(cm, "validate_replayed_beverage_frame", validate)
        monkeypatch.setattr(cm, "device_signature_from_frame", signatures.get)
        monkeypatch.setattr(cm, "replay_with_timestamp", lambda frame: frame)
        monkeypatch.setattr(cm, "validate_replayed_wake_frame", lambda _frame: True)
        restore = Mock()
        create_issue = Mock()
        monkeypatch.setattr(coordinator, "_restore_device_app_id", restore)
        monkeypatch.setattr(cm.ir, "async_create_issue", create_issue)

        await coordinator.async_load_learned()
        assert coordinator.learned_start_frames == {1: "start-good"}
        assert coordinator.learned_stop_frames == {3: "stop-good"}
        assert coordinator.learned_wake_frame is None
        assert coordinator._discarded_learning_keys == {
            "start_02",
            "stop_01",
            "wake",
        }
        assert create_issue.call_args.kwargs["translation_placeholders"]["count"] == "3"
        restore.assert_called_once()

    run(scenario())


def test_load_learned_accepts_matching_wake_and_sanitizes_soul(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def eletta() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._store.async_load = AsyncMock(return_value={"stored": True})
        monkeypatch.setattr(
            cm,
            "deserialize_learned_frames",
            lambda _data: ({}, {}, "wake-good"),
        )
        monkeypatch.setattr(cm, "replay_with_timestamp", lambda frame: frame)
        monkeypatch.setattr(cm, "validate_replayed_wake_frame", lambda _frame: True)
        monkeypatch.setattr(cm, "device_signature_from_frame", lambda _frame: b"same")
        await coordinator.async_load_learned()
        assert coordinator.learned_wake_frame == "wake-good"

    run(eletta())

    async def soul() -> None:
        coordinator, _client = _coordinator()
        coordinator._store.async_load = AsyncMock(return_value={"stored": True})
        monkeypatch.setattr(
            cm,
            "deserialize_learned_frames",
            lambda _data: ({}, {}, "not-wake"),
        )
        monkeypatch.setattr(cm, "decode_command", lambda _frame: {"type": "power"})
        monkeypatch.setattr(cm, "is_wake_power_frame", lambda _decoded: False)
        await coordinator.async_load_learned()
        assert coordinator.learned_wake_frame is None

    run(soul())


def test_log_recipe_datapoints_empty_none_and_lines(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    coordinator, _client = _coordinator()
    with caplog.at_level(logging.WARNING, logger=cm.__name__):
        coordinator.log_recipe_datapoints()
        coordinator.data = {"other": {}}
        monkeypatch.setattr(cm, "recipe_dump_lines", lambda _data: [])
        coordinator.log_recipe_datapoints()
        monkeypatch.setattr(cm, "recipe_dump_lines", lambda _data: ["one", "two"])
        coordinator.log_recipe_datapoints()
    assert "no data fetched" in caplog.text
    assert "No recipe datapoints" in caplog.text
    assert "Recipe datapoint: one" in caplog.text
    assert "Recipe datapoint: two" in caplog.text


def test_maybe_learn_frame_guard_and_power_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    soul, _client = _coordinator()
    soul._maybe_learn_frame({"raw_b64": "x"})

    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator._maybe_learn_frame({})
    coordinator._maybe_learn_frame({"raw_b64": "x", "type": "other"})
    coordinator._maybe_learn_frame({"raw_b64": "x", "type": "beverage"})
    coordinator._maybe_learn_frame(
        {"raw_b64": "x", "type": "beverage", "beverage_id": "bad", "action": 1}
    )

    monkeypatch.setattr(coordinator, "_learned_device_signature", lambda: b"same")
    monkeypatch.setattr(cm, "device_signature_from_frame", lambda _frame: b"different")
    coordinator._maybe_learn_frame(
        {"raw_b64": "bad-power", "type": "power", "crc_valid": True, "params": "01 01"}
    )
    assert coordinator.learned_wake_frame is None

    monkeypatch.setattr(cm, "device_signature_from_frame", lambda _frame: b"same")
    monkeypatch.setattr(cm, "is_wake_power_frame", lambda _decoded: True)
    restore = Mock()
    delete_issue = Mock()
    monkeypatch.setattr(coordinator, "_restore_device_app_id", restore)
    monkeypatch.setattr(cm.ir, "async_delete_issue", delete_issue)
    coordinator._discarded_learning_keys.add("wake")
    coordinator._maybe_learn_frame(
        {"raw_b64": "good-power", "type": "power", "crc_valid": True, "params": "01 01"}
    )
    assert coordinator.learned_wake_frame == "good-power"
    assert coordinator._discarded_learning_keys == set()
    delete_issue.assert_called_once()
    restore.assert_called_once()
    coordinator._maybe_learn_frame(
        {"raw_b64": "good-power", "type": "power", "crc_valid": True, "params": "01 01"}
    )
    assert restore.call_count == 1


def test_maybe_learn_frame_invalid_action_and_unchanged_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    monkeypatch.setattr(cm, "validate_replayed_beverage_frame", lambda *_args, **_kwargs: True)
    decoded = {
        "raw_b64": "frame",
        "type": "beverage",
        "beverage_id": "0x01",
        "beverage_name": "Espresso",
        "action": 9,
    }
    coordinator._maybe_learn_frame(decoded)
    assert coordinator.learned_start_frames == {}

    decoded["action"] = const.ACTION_START
    coordinator.learned_start_frames[1] = "frame"
    coordinator._discarded_learning_keys.add("start_01")
    coordinator._maybe_learn_frame(decoded)
    assert coordinator.active_beverage_id == 1
    assert coordinator._discarded_learning_keys == set()


def test_update_data_metadata_refresh_without_matching_device() -> None:
    coordinator, client = _coordinator()
    props = {"data_request": {"value": "frame"}}
    client.async_get_properties = AsyncMock(return_value=props)
    client.async_get_devices = AsyncMock(return_value=[replacement_device("other")])
    coordinator._last_device_metadata_refresh = -1e20
    original = coordinator.device
    assert run(coordinator._async_update_data()) == props
    assert coordinator.device is original


def test_wait_for_session_confirmation_foreign_without_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._fetch_app_id_live = AsyncMock(
            side_effect=[(999, True), (coordinator._integration_app_id, True)]
        )
        times = iter([0.0, 0.0, 1.0, 1.0, 2.0])
        monkeypatch.setattr(cm.time, "time", lambda: next(times))
        monkeypatch.setattr(cm.asyncio, "sleep", AsyncMock())
        assert await coordinator._wait_for_session_confirmed() is True

    run(scenario())


def test_command_confirmation_polls_unchanged_state_before_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        coordinator.monitor = {"status": 7}
        coordinator.async_request_refresh = AsyncMock()
        monkeypatch.setattr(cm.asyncio, "sleep", AsyncMock())
        assert (
            await coordinator._wait_for_command_confirmation(
                (None, dict(coordinator.monitor)), timeout=0.0001
            )
            is False
        )
        assert coordinator.async_request_refresh.await_count >= 1

    run(scenario())


def test_sniffer_independent_optional_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator, _client = _coordinator()
    capture = Mock()
    monkeypatch.setattr(coordinator, "_capture_channel", capture)
    coordinator.command_property = None
    coordinator.response_property = "response"
    coordinator._sniff_app_traffic({})
    capture.assert_called_once_with({}, "response", channel="response")

    capture.reset_mock()
    coordinator.command_property = "command"
    coordinator.response_property = None
    coordinator._sniff_app_traffic({})
    capture.assert_called_once_with({}, "command", channel="command")


def test_load_learned_no_wake_and_valid_soul_wake(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_wake() -> None:
        coordinator, _client = _coordinator("DL-striker-cb")
        coordinator._store.async_load = AsyncMock(return_value={"stored": True})
        monkeypatch.setattr(cm, "deserialize_learned_frames", lambda _data: ({}, {}, None))
        await coordinator.async_load_learned()
        assert coordinator.learned_wake_frame is None

    run(no_wake())

    async def valid_soul_wake() -> None:
        coordinator, _client = _coordinator()
        coordinator._store.async_load = AsyncMock(return_value={"stored": True})
        monkeypatch.setattr(
            cm,
            "deserialize_learned_frames",
            lambda _data: ({}, {}, "valid-wake"),
        )
        monkeypatch.setattr(cm, "decode_command", lambda _frame: {"type": "power"})
        monkeypatch.setattr(cm, "is_wake_power_frame", lambda _decoded: True)
        await coordinator.async_load_learned()
        assert coordinator.learned_wake_frame == "valid-wake"

    run(valid_soul_wake())


def test_maybe_learn_frame_type_error_beverage_id() -> None:
    coordinator, _client = _coordinator("DL-striker-cb")
    coordinator._maybe_learn_frame(
        {
            "raw_b64": "frame",
            "type": "beverage",
            "beverage_id": object(),
            "action": const.ACTION_START,
        }
    )
    assert coordinator.learned_start_frames == {}


def test_send_beverage_discards_invalid_learned_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator("DL-striker-cb")
        coordinator.connected_property = None
        coordinator.monitor = {"status": 7, "step": 0, "alarms": 0, "switches": 0}
        coordinator.learned_start_frames[1] = "invalid"
        monkeypatch.setattr(cm, "validate_replayed_beverage_frame", lambda *_a, **_k: False)
        with pytest.raises(HomeAssistantError, match="integrity check"):
            await coordinator.async_send_beverage(1, const.ACTION_START)
        assert coordinator.learned_start_frames == {}
        assert coordinator._discarded_learning_keys == {"start_01"}
        assert client.writes == []

    run(scenario())


def test_send_beverage_builds_when_nonlearning_profile_returns_none() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()

        class BuildFallbackProfile:
            learns_from_app = False
            uses_cloud_session = False

            @staticmethod
            def beverage_value(_beverage_id: int, _action: int, _learned: str | None) -> None:
                return None

        coordinator.profile = BuildFallbackProfile()
        await coordinator.async_send_beverage(1, const.ACTION_START)
        assert len(client.writes) == 1

    run(scenario())


def test_send_stop_for_different_tracked_beverage_keeps_other_active() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        coordinator.active_beverage_id = 7
        await coordinator.async_send_beverage(1, const.ACTION_STOP)
        assert coordinator.active_beverage_id == 7

    run(scenario())


def test_stop_active_beverage_rejects_unknown() -> None:
    coordinator, _client = _coordinator()
    with pytest.raises(HomeAssistantError, match="active beverage is unknown"):
        run(coordinator.async_stop_active_beverage())
    assert coordinator.last_command_result == "rejected"
    assert coordinator.last_command["action"] == "stop"


@pytest.mark.parametrize(
    ("error", "expected_type", "result", "message"),
    [
        (ConfigEntryAuthFailed("reauth"), ConfigEntryAuthFailed, "rejected", "reauth"),
        (ayla_client.AuthError("bad"), ConfigEntryAuthFailed, "rejected", "credentials"),
        (HomeAssistantError("blocked"), HomeAssistantError, "rejected", "blocked"),
        (TimeoutError("slow"), HomeAssistantError, "timed_out", "could not be completed"),
        (ayla_client.CloudError("offline"), HomeAssistantError, "timed_out", "could not be completed"),
        (ValueError("broken"), HomeAssistantError, "rejected", "failed"),
    ],
)
def test_command_transaction_maps_all_failures(
    error: Exception,
    expected_type: type[Exception],
    result: str,
    message: str,
) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        coordinator._with_cloud_session = AsyncMock(side_effect=error)
        with pytest.raises(expected_type, match=message):
            await coordinator._run_command_transaction(AsyncMock())
        assert coordinator.last_command_result == result

    run(scenario())


def test_command_transaction_preserves_timeout_and_acknowledgement() -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()

        async def timed_out(_send: Any) -> None:
            coordinator._set_last_command_result("timed_out", completed=True)
            raise HomeAssistantError("late")

        coordinator._with_cloud_session = timed_out
        with pytest.raises(HomeAssistantError, match="late"):
            await coordinator._run_command_transaction(AsyncMock())
        assert coordinator.last_command_result == "timed_out"

        async def acknowledged(_send: Any) -> None:
            coordinator._set_last_command_result("acknowledged", completed=True)

        coordinator._with_cloud_session = acknowledged
        await coordinator._run_command_transaction(AsyncMock())
        assert coordinator.last_command_result == "acknowledged"

        async def sent(_send: Any) -> None:
            coordinator._set_last_command_result("sent")

        coordinator._with_cloud_session = sent
        await coordinator._run_command_transaction(AsyncMock())
        assert coordinator.last_command_result == "sent"
        assert "completed_at" in coordinator.last_command

    run(scenario())


def test_soul_wake_and_standby_commands() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()
        await coordinator.async_send_wake()
        await coordinator.async_send_standby()
        assert len(client.writes) == 2
        assert command_builder.decode_command(client.writes[0][2])["type"] == "power"
        assert command_builder.decode_command(client.writes[1][2])["type"] == "power"

    run(scenario())


@pytest.mark.parametrize(
    ("method_name", "message"),
    [
        ("async_send_wake", "Wake is unavailable"),
        ("async_send_standby", "Standby is unavailable"),
    ],
)
def test_future_learned_non_session_profile_requires_power_frame(
    method_name: str,
    message: str,
) -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()

        class LearnedWithoutSessionProfile:
            learns_from_app = True
            uses_cloud_session = False

            @staticmethod
            def wake_value(_frame: str | None) -> None:
                return None

            @staticmethod
            def standby_value(_signature: bytes | None) -> None:
                return None

        coordinator.profile = LearnedWithoutSessionProfile()
        with pytest.raises(HomeAssistantError, match=message):
            await getattr(coordinator, method_name)()
        assert client.writes == []
        assert coordinator.last_command_result == "rejected"

    run(scenario())


@pytest.mark.parametrize("method_name", ["async_send_wake", "async_send_standby"])
def test_nonlearning_profile_falls_back_to_built_power_frame(method_name: str) -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()

        class BuildFallbackProfile:
            learns_from_app = False
            uses_cloud_session = False

            @staticmethod
            def wake_value(_frame: str | None) -> None:
                return None

            @staticmethod
            def standby_value(_signature: bytes | None) -> None:
                return None

        coordinator.profile = BuildFallbackProfile()
        await getattr(coordinator, method_name)()
        assert len(client.writes) == 1
        assert command_builder.decode_command(client.writes[0][2])["type"] == "power"

    run(scenario())


def test_restore_device_app_id_guards() -> None:
    soul, _client = _coordinator()
    before = soul._integration_app_id
    soul._restore_device_app_id()
    assert soul._integration_app_id == before

    eletta, _client = _coordinator("DL-striker-cb")
    before = eletta._integration_app_id
    eletta._restore_device_app_id()
    assert eletta._integration_app_id == before


def test_raw_command_rejects_invalid_and_sends_valid_with_context() -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator()
        with pytest.raises(HomeAssistantError, match="protocol, device-signature, or safety"):
            await coordinator.async_send_raw("not-base64")
        assert coordinator.last_command_result == "rejected"

        beverage = command_builder.build_and_encode(1, const.ACTION_START)
        await coordinator.async_send_raw(beverage)
        assert client.writes[-1][2] == beverage
        assert coordinator.last_command["command_type"] == "beverage"
        assert coordinator.last_command["beverage_id"] == "0x01"

        power = command_builder.build_wake_encoded()
        await coordinator.async_send_raw(power)
        assert coordinator.last_command["command_type"] == "power"
        assert "beverage_id" not in coordinator.last_command

        standby = command_builder.build_standby_encoded()
        await coordinator.async_send_raw(standby)
        assert coordinator.last_command["action"] == "standby"

        stop = command_builder.build_and_encode(1, const.ACTION_STOP)
        await coordinator.async_send_raw(stop)
        assert coordinator.last_command["action"] == "stop"

    run(scenario())


def test_raw_command_rejects_incomplete_identity_and_unknown_soul_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, _client = _coordinator()
        monkeypatch.setattr(
            cm,
            "decode_command",
            Mock(return_value={"type": "beverage", "crc_valid": True}),
        )
        with pytest.raises(HomeAssistantError, match="protocol"):
            await coordinator.async_send_raw("frame")

        cm.decode_command.return_value = {
            "type": "beverage",
            "crc_valid": True,
            "beverage_id": "0x01",
            "action": 9,
        }
        with pytest.raises(HomeAssistantError, match="protocol"):
            await coordinator.async_send_raw("frame")

    run(scenario())


def test_raw_command_enforces_eletta_signature_readiness_and_power_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        coordinator, client = _coordinator("DL-striker-cb")
        monkeypatch.setattr(
            coordinator,
            "_wait_for_command_confirmation",
            AsyncMock(return_value=True),
        )
        coordinator.monitor = {"status": 7, "step": 0, "alarms": 0, "switches": 0}
        signature = bytes.fromhex("11 22 33 44")
        beverage = command_builder.build_and_encode(1, const.ACTION_START)
        signed_beverage = base64.b64encode(
            base64.b64decode(beverage) + signature
        ).decode()

        wake = command_builder.build_wake_encoded()
        signed_wake = base64.b64encode(base64.b64decode(wake) + signature).decode()
        with pytest.raises(HomeAssistantError, match="device-signature"):
            await coordinator.async_send_raw(signed_wake)

        coordinator.learned_start_frames[1] = signed_beverage

        await coordinator.async_send_raw(signed_beverage)
        assert client.writes[-1][2] == signed_beverage
        assert coordinator.last_command["action"] == "start"

        wrong_signature = base64.b64encode(
            base64.b64decode(beverage) + bytes.fromhex("55 66 77 88")
        ).decode()
        with pytest.raises(HomeAssistantError, match="device-signature"):
            await coordinator.async_send_raw(wrong_signature)

        coordinator.monitor["alarms"] = 1
        with pytest.raises(HomeAssistantError, match="water tank is empty"):
            await coordinator.async_send_raw(signed_beverage)
        assert coordinator.last_command_result == "rejected"

        session_refresh = command_builder.build_session_refresh_encoded(0x11223344)
        with pytest.raises(HomeAssistantError, match="protocol"):
            await coordinator.async_send_raw(session_refresh)

        coordinator.monitor["alarms"] = 0
        await coordinator.async_send_raw(signed_wake)
        assert coordinator.last_command["action"] == "wake"

        wrong_wake = base64.b64encode(
            base64.b64decode(wake) + bytes.fromhex("55 66 77 88")
        ).decode()
        with pytest.raises(HomeAssistantError, match="device-signature"):
            await coordinator.async_send_raw(wrong_wake)

    run(scenario())

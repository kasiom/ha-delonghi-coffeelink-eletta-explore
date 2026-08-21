"""Deterministic tests for the Ayla cloud push transport."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import aiohttp
import pytest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "ha_delonghi_coffeelink_eletta_explore"
PKG_NAME = "delonghi_dss_tests"


def _load(name: str):
    full_name = f"{PKG_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(full_name, PKG_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType(PKG_NAME)
package.__path__ = [str(PKG_DIR)]
sys.modules[PKG_NAME] = package
const = _load("const")
_load("ayla_client")
dss = _load("dss")


def run(coro):
    return asyncio.run(coro)


def _frame(*, event_type="datapoint", dsn="dsn", metadata=None, datapoint=None, seq="9"):
    meta = {
        "event_type": event_type,
        "dsn": dsn,
        "property_name": "status",
        **(metadata or {}),
    }
    document = {
        "seq": seq,
        "metadata": meta,
        "datapoint": datapoint
        or {
            "id": 12,
            "value": "ready",
            "updated_at": "2026-08-20T12:00:00Z",
            "acked_at": "2026-08-20T12:00:01Z",
            "ack_status": "200",
            "ack_message": 0,
        },
    }
    return f"8|{json.dumps(document)}"


def test_optional_int_and_parser_reject_malformed_frames():
    assert dss._optional_int(None) is None
    assert dss._optional_int("bad") is None
    assert dss._optional_int("2") == 2
    for value in (
        None,
        "1|Z",
        "1|X",
        "missing separator",
        "1|",
        "1|not-json",
        "1|[]",
        '1|{"metadata": null}',
        _frame(event_type="unsupported"),
        _frame(dsn=""),
    ):
        assert dss.parse_dss_message(value) is None


def test_parser_normalizes_snake_and_camel_case_events():
    event = dss.parse_dss_message(_frame())
    assert event == dss.DssEvent(
        sequence="9",
        event_type="datapoint",
        dsn="dsn",
        property_name="status",
        datapoint_id="12",
        value="ready",
        updated_at="2026-08-20T12:00:00Z",
        acked_at="2026-08-20T12:00:01Z",
        ack_status=200,
        ack_message=0,
    )

    camel = dss.parse_dss_message(
        _frame(
            event_type="datapointack",
            metadata={"event_type": None, "eventType": "datapointack", "property_name": 3, "propertyName": "cmd"},
            datapoint={
                "id": "abc",
                "value": None,
                "updatedAt": "updated",
                "ackedAt": "acked",
                "ackStatus": "bad",
                "ackMessage": "message",
            },
            seq=None,
        )
    )
    assert camel is not None
    assert camel.sequence == "8"
    assert camel.property_name == "cmd"
    assert camel.ack_status is None
    assert camel.ack_message == "message"

    no_datapoint = json.dumps({"metadata": {"event_type": "connectivity", "dsn": "dsn"}, "datapoint": []})
    event = dss.parse_dss_message(f"2|{no_datapoint}")
    assert event is not None
    assert event.property_name is None
    assert event.datapoint_id is None


class FakeCoordinator:
    def __init__(self, dsn="dsn", *, handled=True):
        self.device = types.SimpleNamespace(dsn=dsn)
        self.handled = handled
        self.states = []
        self.events = []

    def set_dss_state(self, state, *, request_refresh=False):
        self.states.append((state, request_refresh))

    def handle_dss_event(self, event):
        self.events.append(event)
        return self.handled


class FakeEntry:
    def async_create_background_task(self, hass, target, name):
        return asyncio.create_task(target, name=name)


class FakeWebSocket:
    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.closed = False
        self.sent = []

    async def receive(self, *, timeout):
        return self.messages.pop(0)

    async def send_str(self, value):
        self.sent.append(value)

    async def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, websocket=None, subscription=None):
        self.websocket = websocket
        self.subscription = subscription or {"stream_key": "secret"}

    async def async_create_dss_subscription(self):
        return self.subscription

    @staticmethod
    def dss_subscription_stream_key(subscription):
        return subscription.get("stream_key")

    async def async_open_dss_websocket(self, stream_key):
        return self.websocket


def _message(message_type, data=None):
    return types.SimpleNamespace(type=message_type, data=data)


def test_manager_state_start_and_stop_lifecycle():
    async def scenario():
        coordinator = FakeCoordinator()
        manager = dss.AylaDssManager(object(), FakeEntry(), FakeClient(), [coordinator])
        manager._async_run = AsyncMock()
        manager.start()
        first = manager._task
        manager.start()
        assert manager._task is first
        websocket = FakeWebSocket()
        manager._websocket = websocket
        await manager.async_stop()
        assert websocket.closed is True
        assert manager._task is None
        await manager.async_stop()

        manager._set_state("polling")
        manager._set_state("streaming")
        manager._set_state("polling")
        assert coordinator.states == [
            ("streaming", False),
            ("polling", True),
        ]

    run(scenario())


def test_receive_routes_events_and_handles_heartbeat_and_close():
    async def scenario():
        coordinator = FakeCoordinator()
        ignored = FakeCoordinator("ignored", handled=False)
        messages = [
            _message(aiohttp.WSMsgType.TEXT, "1|Z"),
            _message(aiohttp.WSMsgType.TEXT, "bad"),
            _message(aiohttp.WSMsgType.TEXT, _frame(dsn="other")),
            _message(aiohttp.WSMsgType.TEXT, _frame(dsn="ignored")),
            _message(aiohttp.WSMsgType.TEXT, _frame(dsn="dsn")),
            _message(aiohttp.WSMsgType.BINARY, b"ignored"),
            _message(aiohttp.WSMsgType.CLOSE),
        ]
        websocket = FakeWebSocket(messages)
        manager = dss.AylaDssManager(object(), FakeEntry(), FakeClient(websocket), [coordinator, ignored])
        manager._websocket = websocket
        with pytest.raises(dss.CloudError, match="ended"):
            await manager._async_receive()
        assert websocket.sent == ["1|Z"]
        assert manager.events_received == 1
        assert manager.event_type_counts == {
            "datapoint": 1,
            "datapointack": 0,
            "connectivity": 0,
        }
        assert manager.last_event_at is not None
        assert len(coordinator.events) == 1
        assert len(ignored.events) == 1

        manager._websocket = None
        with pytest.raises(dss.CloudError, match="not opened"):
            await manager._async_receive()

        manager._websocket = websocket
        manager._stopping = True
        await manager._async_receive()

    run(scenario())


@pytest.mark.parametrize("second_attempt", [False, True])
def test_supervisor_uses_polling_fallback_for_cloud_failures(monkeypatch, second_attempt):
    async def scenario():
        coordinator = FakeCoordinator()
        client = FakeClient(subscription={})
        manager = dss.AylaDssManager(object(), FakeEntry(), client, [coordinator])
        manager.reconnect_count = 1 if second_attempt else 0

        async def stop_after_delay(_delay):
            manager._stopping = True

        monkeypatch.setattr(dss.asyncio, "sleep", stop_after_delay)
        monkeypatch.setattr(dss.random, "uniform", lambda _start, _end: 0)
        await manager._async_run()
        assert manager.state == "polling"
        assert manager.last_error_type == "CloudError"
        assert manager.reconnect_count == (2 if second_attempt else 1)

    run(scenario())


def test_supervisor_closes_stream_and_contains_unexpected_failure(monkeypatch):
    async def scenario():
        coordinator = FakeCoordinator()
        websocket = FakeWebSocket()
        manager = dss.AylaDssManager(object(), FakeEntry(), FakeClient(websocket), [coordinator])

        async def stop_receive():
            manager._stopping = True

        manager._async_receive = stop_receive
        await manager._async_run()
        assert websocket.closed is True
        assert manager.state == "streaming"

        manager = dss.AylaDssManager(object(), FakeEntry(), FakeClient(), [coordinator])
        manager._client.async_create_dss_subscription = AsyncMock(side_effect=ValueError("unexpected"))

        async def stop_after_delay(_delay):
            manager._stopping = True

        monkeypatch.setattr(dss.asyncio, "sleep", stop_after_delay)
        await manager._async_run()
        assert manager.last_error_type == "ValueError"

        manager = dss.AylaDssManager(object(), FakeEntry(), FakeClient(), [coordinator])
        manager._client.async_create_dss_subscription = AsyncMock(side_effect=asyncio.CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await manager._async_run()

        missing_key_client = FakeClient()
        missing_key_client.subscription = {}
        manager = dss.AylaDssManager(object(), FakeEntry(), missing_key_client, [coordinator])

        async def stop_missing_key_retry(_delay):
            manager._stopping = True

        monkeypatch.setattr(dss.asyncio, "sleep", stop_missing_key_retry)
        await manager._async_run()
        assert manager.last_error_type == "CloudError"

        websocket = FakeWebSocket()
        manager = dss.AylaDssManager(object(), FakeEntry(), FakeClient(websocket), [coordinator])
        manager._async_receive = AsyncMock(return_value=None)

        async def stop_closed_stream_retry(_delay):
            manager._stopping = True

        monkeypatch.setattr(dss.asyncio, "sleep", stop_closed_stream_retry)
        await manager._async_run()
        assert manager.last_error_type == "CloudError"

    run(scenario())


def test_supervisor_creates_fresh_subscription_after_stream_loss(monkeypatch):
    async def scenario():
        coordinator = FakeCoordinator()
        client = FakeClient(FakeWebSocket())
        client.async_create_dss_subscription = AsyncMock(side_effect=[{"stream_key": "first"}, {"stream_key": "second"}])
        client.async_open_dss_websocket = AsyncMock(side_effect=[FakeWebSocket(), FakeWebSocket()])
        manager = dss.AylaDssManager(object(), FakeEntry(), client, [coordinator])
        receive_count = 0

        async def receive_then_stop():
            nonlocal receive_count
            receive_count += 1
            if receive_count == 1:
                raise dss.CloudError("first stream ended")
            manager._stopping = True

        manager._async_receive = receive_then_stop
        monkeypatch.setattr(dss.asyncio, "sleep", AsyncMock())
        monkeypatch.setattr(dss.random, "uniform", lambda _start, _end: 0)

        await manager._async_run()

        assert client.async_create_dss_subscription.await_count == 2
        assert [call.args[0] for call in client.async_open_dss_websocket.await_args_list] == [
            "first",
            "second",
        ]

    run(scenario())

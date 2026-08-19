"""Deterministic tests for the Gigya/Ayla cloud client.

No request in this module leaves the process.  The fake transport models the
small part of aiohttp's async context-manager API used by the integration.
"""
from __future__ import annotations

import asyncio
import base64
import functools
import importlib.util
import json
import logging
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

PKG_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_delonghi_coffeelink_eletta_explore"
)


def _load(modname: str, filename: str):
    full = f"ha_delonghi_coffeelink_eletta_explore.{modname}"
    spec = importlib.util.spec_from_file_location(full, PKG_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


if "ha_delonghi_coffeelink_eletta_explore" not in sys.modules:
    package = types.ModuleType("ha_delonghi_coffeelink_eletta_explore")
    package.__path__ = [str(PKG_DIR)]
    sys.modules["ha_delonghi_coffeelink_eletta_explore"] = package

const = _load("const", "const.py")
ac = _load("ayla_client", "ayla_client.py")


def async_test(func):
    """Run one async test without requiring a pytest event-loop plugin."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


class FakeResponse:
    """Minimal aiohttp response with an optional failure while reading text."""

    def __init__(
        self,
        status: int = 200,
        body: Any = None,
        *,
        raw_text: str | None = None,
        headers: dict[str, str] | None = None,
        content_type: str = "application/json",
        text_error: Exception | None = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self.content_type = content_type
        self._text = raw_text if raw_text is not None else json.dumps(body)
        self._text_error = text_error

    async def text(self) -> str:
        if self._text_error is not None:
            raise self._text_error
        return self._text


class FakeRequestContext:
    """Async request context returning a response or raising a queued error."""

    def __init__(
        self,
        outcome: FakeResponse | Exception,
        on_enter: Callable[[], None] | None = None,
    ) -> None:
        self._outcome = outcome
        self._on_enter = on_enter

    async def __aenter__(self) -> FakeResponse:
        if self._on_enter:
            self._on_enter()
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    async def __aexit__(self, *_args: Any) -> None:
        return None


class FakeSession:
    """Queue-backed fake for ClientSession.post and ClientSession.request."""

    def __init__(
        self,
        *,
        posts: list[FakeResponse | Exception | FakeRequestContext] | None = None,
        requests: list[FakeResponse | Exception | FakeRequestContext] | None = None,
    ) -> None:
        self.posts = list(posts or [])
        self.requests = list(requests or [])
        self.post_calls: list[tuple[str, dict[str, Any]]] = []
        self.request_calls: list[tuple[str, str, dict[str, Any]]] = []

    @staticmethod
    def _context(outcome: FakeResponse | Exception | FakeRequestContext) -> FakeRequestContext:
        if isinstance(outcome, FakeRequestContext):
            return outcome
        return FakeRequestContext(outcome)

    def post(self, url: str, **kwargs: Any) -> FakeRequestContext:
        self.post_calls.append((url, kwargs))
        return self._context(self.posts.pop(0))

    def request(self, method: str, url: str, **kwargs: Any) -> FakeRequestContext:
        self.request_calls.append((method, url, kwargs))
        return self._context(self.requests.pop(0))


@pytest.fixture
def no_delays(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    sleep = AsyncMock()
    monkeypatch.setattr(ac.asyncio, "sleep", sleep)
    monkeypatch.setattr(ac.random, "uniform", lambda _start, _end: 0.0)
    return sleep


def make_client(session: FakeSession | None = None) -> Any:
    return ac.DelonghiAylaClient(session or FakeSession(), "owner@example.test", "secret")


def authenticated(client: Any) -> None:
    client._access_token = "access"
    client._expires_at = 10_000


def test_cloud_error_device_and_small_helpers(caplog: pytest.LogCaptureFixture) -> None:
    error = ac.CloudError("offline", http_status=503)
    assert str(error) == "offline"
    assert error.http_status == 503

    device = ac.AylaDevice("dsn", "name", "oem", "model", "sw", "ip", "Online")
    assert device.properties == {}

    client = make_client()
    assert client.ads_url == const.AYLA_EU_ADS_URL
    client._access_token = "abc"
    assert client._auth_headers() == {"Authorization": "auth_token abc"}
    assert client._value_hint("coffee") == "len=6"
    assert client._value_hint(3) == "int"

    with caplog.at_level(logging.DEBUG, logger=ac.__name__):
        client._log_http("GET", "https://example.test/good", 200, 12.3)
    assert "HTTP 200" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=ac.__name__):
        client._log_http("POST", "write property", 500, 5, detail=" [write]")
    assert "HTTP 500" in caplog.text
    assert "[write]" in caplog.text
    assert "example.test" not in caplog.text


@async_test
async def test_authenticate_and_locked_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    locked = AsyncMock()
    monkeypatch.setattr(client, "_async_authenticate_locked", locked)
    await client.async_authenticate()
    locked.assert_awaited_once()

    login = AsyncMock(return_value="jwt")
    sso = AsyncMock()
    monkeypatch.setattr(client, "_gigya_login_and_jwt", login)
    monkeypatch.setattr(client, "_ayla_sso_sign_in", sso)
    await ac.DelonghiAylaClient._async_authenticate_locked(client)
    login.assert_awaited_once()
    sso.assert_awaited_once_with("jwt")


@async_test
async def test_ensure_auth_fresh_expired_and_refreshed_by_waiter(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    authenticate = AsyncMock()
    monkeypatch.setattr(client, "_async_authenticate_locked", authenticate)
    monkeypatch.setattr(ac.time, "time", lambda: 100.0)

    client._access_token = "fresh"
    client._expires_at = 131
    await client.async_ensure_auth()
    authenticate.assert_not_awaited()

    client._expires_at = 129
    await client.async_ensure_auth()
    authenticate.assert_awaited_once()

    authenticate.reset_mock()
    client._access_token = None

    class RefreshingLock:
        async def __aenter__(self) -> None:
            client._access_token = "from-other-waiter"
            client._expires_at = 131

        async def __aexit__(self, *_args: Any) -> None:
            return None

    client._auth_lock = RefreshingLock()
    await client.async_ensure_auth()
    authenticate.assert_not_awaited()


@async_test
async def test_authentication_request_success_and_rejections() -> None:
    session = FakeSession(
        posts=[
            FakeResponse(body={"ok": True}),
            FakeResponse(status=401, body={"error": "bad"}),
            FakeResponse(status=418, body={"error": "tea"}),
        ]
    )
    client = make_client(session)
    result = await client._authentication_request(
        "https://auth.test/login", data={"x": "y"}, operation="Login"
    )
    assert result == {"ok": True}
    assert session.post_calls[0][1]["data"] == {"x": "y"}
    assert isinstance(session.post_calls[0][1]["timeout"], aiohttp.ClientTimeout)

    with pytest.raises(ac.AuthError, match="HTTP 401"):
        await client._authentication_request(
            "https://auth.test/login", data={}, operation="Login"
        )
    with pytest.raises(ac.CloudError, match="HTTP 418") as err:
        await client._authentication_request(
            "https://auth.test/login", data={}, operation="Login"
        )
    assert err.value.http_status == 418


@async_test
async def test_authentication_request_response_validation() -> None:
    client = make_client(
        FakeSession(
            posts=[
                FakeResponse(raw_text="not-json"),
                FakeResponse(body=["unexpected"]),
            ]
        )
    )
    with pytest.raises(ac.CloudError, match="invalid response") as invalid:
        await client._authentication_request("https://auth.test", data={}, operation="Auth")
    assert invalid.value.http_status == 200
    with pytest.raises(ac.CloudError, match="unexpected response"):
        await client._authentication_request("https://auth.test", data={}, operation="Auth")


@async_test
async def test_authentication_request_retries_http_cloud_and_network(
    no_delays: AsyncMock,
) -> None:
    transient_from_text = ac.CloudError("upstream", http_status=503)
    session = FakeSession(
        posts=[
            FakeResponse(status=503, body={}),
            FakeResponse(body={"after_http": True}),
            FakeResponse(text_error=transient_from_text),
            FakeResponse(body={"after_cloud_error": True}),
            TimeoutError("slow"),
            FakeResponse(body={"after_timeout": True}),
            aiohttp.ClientConnectionError("down-1"),
            aiohttp.ClientConnectionError("down-2"),
            aiohttp.ClientConnectionError("down-3"),
        ]
    )
    client = make_client(session)
    assert await client._authentication_request("https://a", data={}, operation="A") == {
        "after_http": True
    }
    assert await client._authentication_request("https://b", data={}, operation="B") == {
        "after_cloud_error": True
    }
    assert await client._authentication_request("https://c", data={}, operation="C") == {
        "after_timeout": True
    }
    with pytest.raises(ac.CloudError, match="network error.*ClientConnectionError"):
        await client._authentication_request("https://d", data={}, operation="D")
    assert no_delays.await_count == 5


@async_test
async def test_authentication_request_transient_exhaustion(no_delays: AsyncMock) -> None:
    client = make_client(
        FakeSession(posts=[FakeResponse(status=503, body={}) for _ in range(3)])
    )
    with pytest.raises(ac.CloudError, match="HTTP 503") as err:
        await client._authentication_request("https://auth.test", data={}, operation="Auth")
    assert err.value.http_status == 503
    assert no_delays.await_count == 2


@async_test
async def test_authentication_request_defensive_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(ac, "CLOUD_HTTP_RETRY_COUNT", -1)
    with pytest.raises(ac.CloudError, match="failed after retries"):
        await client._authentication_request("https://auth.test", data={}, operation="Auth")

    client = make_client()

    def increase_retry_count() -> None:
        ac.CLOUD_HTTP_RETRY_COUNT = 1

    client._session.posts = [
        FakeRequestContext(TimeoutError("late"), on_enter=increase_retry_count)
    ]
    monkeypatch.setattr(ac, "CLOUD_HTTP_RETRY_COUNT", 0)
    monkeypatch.setattr(ac.asyncio, "sleep", AsyncMock())
    with pytest.raises(ac.CloudError, match="network error.*TimeoutError"):
        await client._authentication_request("https://auth.test", data={}, operation="Auth")


@async_test
async def test_request_json_success_blank_and_datapoint_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        requests=[
            FakeResponse(body={"ok": True}),
            FakeResponse(raw_text="   ", content_type="text/plain"),
            FakeResponse(status=201, body={"written": True}),
            FakeResponse(status=204, raw_text=""),
        ]
    )
    client = make_client(session)
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())
    captured: list[tuple[Any, ...]] = []
    monkeypatch.setattr(client, "_log_http", lambda *args, **kwargs: captured.append((*args, kwargs)))

    assert await client._request_json("GET", "https://api.test/value") == {"ok": True}
    assert await client._request_json("DELETE", "https://api.test/value", op="delete") is None
    assert await client._request_json(
        "POST",
        "https://api.test/value",
        json_body={"datapoint": {"value": "secret-payload"}},
        data={"form": "value"},
        op="write",
    ) == {"written": True}
    assert "[write] value=len=14" in captured[-1][-1]["detail"]
    assert await client._request_json(
        "DELETE",
        "https://api.test/value",
        ok_status=frozenset({204}),
    ) is None
    request_kwargs = session.request_calls[-2][2]
    assert request_kwargs["headers"] == {"Authorization": "auth_token None"}
    assert request_kwargs["data"] == {"form": "value"}


@async_test
async def test_request_json_auth_and_non_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        requests=[
            FakeResponse(status=403, body={}),
            FakeResponse(status=409, raw_text="conflict"),
        ]
    )
    client = make_client(session)
    authenticated(client)
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())
    with pytest.raises(ac.AuthError, match="write rejected.*HTTP 403"):
        await client._request_json("POST", "https://api.test", op="write")
    assert client._access_token is None
    assert client._expires_at == 0
    with pytest.raises(ac.CloudError, match=r"write failed \(HTTP 409\)") as err:
        await client._request_json("POST", "https://api.test", op="write")
    assert err.value.http_status == 409


@async_test
async def test_request_json_retries_retry_after_and_invalid_header(
    monkeypatch: pytest.MonkeyPatch,
    no_delays: AsyncMock,
) -> None:
    session = FakeSession(
        requests=[
            FakeResponse(status=429, body={}, headers={"Retry-After": "2.5"}),
            FakeResponse(body={"first": True}),
            FakeResponse(status=503, body={}, headers={"Retry-After": "later"}),
            FakeResponse(body={"second": True}),
        ]
    )
    client = make_client(session)
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())
    assert await client._request_json("GET", "https://api.test/one", op="one") == {
        "first": True
    }
    assert await client._request_json("GET", "https://api.test/two") == {"second": True}
    assert no_delays.await_args_list[0].args == (2.5,)
    assert no_delays.await_args_list[1].args == (ac.CLOUD_HTTP_RETRY_BACKOFF,)


@async_test
async def test_request_json_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(
        FakeSession(requests=[FakeResponse(raw_text="<html>", content_type="text/html")])
    )
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())
    with pytest.raises(ac.CloudError, match="expected JSON.*text/html") as err:
        await client._request_json("GET", "https://api.test", op="read")
    assert err.value.http_status == 200


@async_test
async def test_request_json_network_retry_and_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
    no_delays: AsyncMock,
) -> None:
    session = FakeSession(
        requests=[
            TimeoutError("slow"),
            FakeResponse(body={"recovered": True}),
            aiohttp.ClientConnectionError("down-1"),
            aiohttp.ClientConnectionError("down-2"),
            aiohttp.ClientConnectionError("down-3"),
        ]
    )
    client = make_client(session)
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())
    assert await client._request_json("GET", "https://api.test/one", op="read") == {
        "recovered": True
    }
    with pytest.raises(ac.CloudError, match="network error.*ClientConnectionError") as error:
        await client._request_json(
            "GET", "https://api.test/two", op="read properties dsn=private-device"
        )
    assert "private-device" not in str(error.value)
    assert no_delays.await_count == 3


@async_test
async def test_request_json_defensive_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())
    monkeypatch.setattr(ac, "CLOUD_HTTP_RETRY_COUNT", -1)
    with pytest.raises(ac.CloudError, match="failed after retries"):
        await client._request_json("GET", "https://api.test", op="read")

    client = make_client()
    monkeypatch.setattr(client, "async_ensure_auth", AsyncMock())

    def increase_retry_count() -> None:
        ac.CLOUD_HTTP_RETRY_COUNT = 1

    client._session.requests = [
        FakeRequestContext(TimeoutError("late"), on_enter=increase_retry_count)
    ]
    monkeypatch.setattr(ac, "CLOUD_HTTP_RETRY_COUNT", 0)
    monkeypatch.setattr(ac.asyncio, "sleep", AsyncMock())
    with pytest.raises(ac.CloudError, match="network error.*TimeoutError"):
        await client._request_json("GET", "https://api.test")


@async_test
async def test_gigya_login_jwt_success(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = base64.b64encode(b"signing-secret").decode()
    request = AsyncMock(
        side_effect=[
            {
                "errorCode": 0,
                "sessionInfo": {"sessionToken": "token", "sessionSecret": secret},
            },
            {"errorCode": 0, "id_token": "jwt-value"},
        ]
    )
    client = make_client()
    monkeypatch.setattr(client, "_authentication_request", request)
    monkeypatch.setattr(ac.time, "time", lambda: 1_700_000_000)
    assert await client._gigya_login_and_jwt() == "jwt-value"
    login_call, jwt_call = request.await_args_list
    assert login_call.kwargs["data"]["loginID"] == "owner@example.test"
    assert login_call.kwargs["data"]["password"] == "secret"
    assert jwt_call.kwargs["data"]["timestamp"] == "1700000000"
    assert jwt_call.kwargs["data"]["nonce"] == "1700000000_1"
    assert jwt_call.kwargs["data"]["sig"]


@async_test
@pytest.mark.parametrize(
    ("body", "error_type"),
    [
        ({"errorCode": 403042, "errorMessage": "invalid"}, ac.AuthError),
        ({"errorCode": 500, "errorMessage": "failure"}, ac.CloudError),
    ],
)
async def test_gigya_login_errors(
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, Any],
    error_type: type[Exception],
) -> None:
    client = make_client()
    monkeypatch.setattr(client, "_authentication_request", AsyncMock(return_value=body))
    with pytest.raises(error_type, match="Gigya login failed"):
        await client._gigya_login_and_jwt()


@async_test
async def test_gigya_jwt_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client,
        "_authentication_request",
        AsyncMock(
            side_effect=[
                {
                    "errorCode": 0,
                    "sessionInfo": {
                        "sessionToken": "token",
                        "sessionSecret": base64.b64encode(b"secret").decode(),
                    },
                },
                {"errorCode": 1, "errorMessage": "jwt denied"},
            ]
        ),
    )
    with pytest.raises(ac.CloudError, match=r"getJWT failed \(code 1\)"):
        await client._gigya_login_and_jwt()


@async_test
async def test_ayla_sso_success_and_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    request = AsyncMock(
        side_effect=[
            {"access_token": "access", "refresh_token": "refresh", "expires_in": 90},
            {"access_token": "default-expiry"},
            {"refresh_token": "missing"},
        ]
    )
    monkeypatch.setattr(client, "_authentication_request", request)
    monkeypatch.setattr(ac.time, "time", lambda: 1000)
    await client._ayla_sso_sign_in("jwt")
    assert (client._access_token, client._refresh_token, client._expires_at) == (
        "access",
        "refresh",
        1090,
    )
    await client._ayla_sso_sign_in("jwt-2")
    assert client._expires_at == 4600
    assert client._refresh_token is None
    with pytest.raises(ac.AuthError, match="did not contain an access token"):
        await client._ayla_sso_sign_in("jwt-3")


@async_test
async def test_get_devices_maps_wrapped_direct_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    request = AsyncMock(
        side_effect=[
            [
                {
                    "device": {
                        "dsn": "dsn-1",
                        "product_name": "Kitchen",
                        "oem_model": "OEM",
                        "model": "Eletta",
                        "sw_version": "1.0",
                        "lan_ip": "192.0.2.1",
                        "connection_status": "Online",
                    }
                },
                {"dsn": "dsn-2"},
            ],
            {"not": "a list"},
        ]
    )
    monkeypatch.setattr(client, "_request_json", request)
    devices = await client.async_get_devices()
    assert devices[0].name == "Kitchen"
    assert devices[0].connection_status == "Online"
    assert devices[1] == ac.AylaDevice("dsn-2", "dsn-2", "", "", "", "", "Unknown")
    with pytest.raises(ac.CloudError, match="expected a JSON list"):
        await client.async_get_devices()


@async_test
async def test_get_properties_filters_unnamed_and_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    monkeypatch.setattr(
        client,
        "_request_json",
        AsyncMock(
            side_effect=[
                [
                    {"property": {"name": "status", "value": "Ready"}},
                    {"property": {"value": 1}},
                    {},
                ],
                None,
            ]
        ),
    )
    assert await client.async_get_properties("dsn") == {
        "status": {"name": "status", "value": "Ready"}
    }
    with pytest.raises(ac.CloudError, match="expected a JSON list"):
        await client.async_get_properties("dsn")


@async_test
async def test_set_property_result_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    request = AsyncMock(side_effect=[{"datapoint": {"id": 1}}, None])
    monkeypatch.setattr(client, "_request_json", request)
    assert await client.async_set_property_value("dsn", "request", "value") == {
        "datapoint": {"id": 1}
    }
    assert await client.async_set_property_value("dsn", "request", 2) == {}
    assert request.await_args_list[0].kwargs["json_body"] == {
        "datapoint": {"value": "value"}
    }


@async_test
@pytest.mark.parametrize("method_name", ["async_get_property", "async_get_property_resilient"])
async def test_get_property_methods_valid_and_invalid(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
) -> None:
    client = make_client()
    request = AsyncMock(
        side_effect=[
            {"property": {"name": "status", "value": "Ready"}},
            {"property": "wrong"},
        ]
    )
    monkeypatch.setattr(client, "_request_json", request)
    method = getattr(client, method_name)
    assert await method("dsn", "status") == {"name": "status", "value": "Ready"}
    with pytest.raises(ac.CloudError, match="unexpected response"):
        await method("dsn", "status")


@async_test
async def test_cloud_session_payload_and_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    request = AsyncMock(side_effect=[{"datapoint": {"id": 1}}, None])
    monkeypatch.setattr(client, "_request_json", request)
    monkeypatch.setattr(ac.time, "time", lambda: 0x01020304)

    result = await client.async_post_cloud_session("dsn", "connected", 0x89ABCDEF)
    assert result == {"datapoint": {"id": 1}}
    payload = request.await_args_list[0].kwargs["json_body"]["datapoint"]["value"]
    assert base64.b64decode(payload) == bytes.fromhex("0102030489abcdef")
    assert await client.async_post_cloud_session("dsn", "connected", 1) == {}

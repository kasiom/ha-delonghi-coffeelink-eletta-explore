"""Authentication and API client for De'Longhi Coffee Link – Eletta Explore via Ayla cloud.

Auth chain: Gigya email/password login -> Gigya JWT (HMAC-SHA1 signed request)
 -> Ayla SSO sign-in -> Ayla access and refresh tokens. Rejected short-lived
 access tokens are renewed in memory before a full login is attempted.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import random
import time
import urllib.parse
from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Any

import aiohttp

from .const import (
    APP_ID,
    APP_SECRET,
    AYLA_EU_ADS_URL,
    AYLA_EU_MDSS_URL,
    AYLA_EU_MSTREAM_URL,
    AYLA_EU_USER_URL,
    CLOUD_HTTP_RETRY_BACKOFF,
    CLOUD_HTTP_RETRY_COUNT,
    CLOUD_HTTP_TIMEOUT,
    CLOUD_RETRY_AFTER_DEFAULT,
    CLOUD_RETRY_AFTER_MAX,
    CLOUD_TRANSIENT_HTTP_CODES,
    DSS_SUBSCRIPTION_DESCRIPTION,
    DSS_SUBSCRIPTION_NAME,
    DSS_SUBSCRIPTION_TYPES,
    GIGYA_API_KEY,
    GIGYA_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

type AylaProperty = dict[str, Any]
type AylaProperties = dict[str, AylaProperty]


class AuthError(Exception):
    """Raised when authentication fails."""


class CloudError(Exception):
    """Raised for Ayla API errors."""

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class _AccessTokenRejected(Exception):
    """Internal signal that an authenticated Ayla request rejected its token."""

    def __init__(self, status: int, token: str | None) -> None:
        super().__init__(f"Ayla access token rejected (HTTP {status})")
        self.status = status
        self.token = token


class RateLimitError(CloudError):
    """Raised when Ayla asks the client to defer further requests."""

    def __init__(self, message: str, *, retry_after: float) -> None:
        super().__init__(message, http_status=429)
        self.retry_after = retry_after


@dataclass(slots=True)
class AylaDevice:
    """Minimal device info."""

    dsn: str
    name: str
    oem_model: str
    model: str
    sw_version: str
    connection_status: str


class DelonghiAylaClient:
    """Client for Gigya + Ayla flow."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0
        self._auth_lock = asyncio.Lock()
        self._devices_lock = asyncio.Lock()
        self._devices_cache: tuple[float, tuple[AylaDevice, ...]] | None = None

    @property
    def ads_url(self) -> str:
        return AYLA_EU_ADS_URL

    async def async_authenticate(self) -> None:
        """Perform full auth chain: Gigya -> JWT -> Ayla SSO."""
        async with self._auth_lock:
            await self._async_authenticate_locked()

    async def _async_authenticate_locked(self) -> None:
        """Perform authentication while the caller holds ``_auth_lock``."""
        jwt = await self._gigya_login_and_jwt()
        await self._ayla_sso_sign_in(jwt)

    async def async_ensure_auth(self) -> None:
        """Refresh access_token if expired."""
        if self._access_token and monotonic() <= self._expires_at - 30:
            return
        async with self._auth_lock:
            if self._access_token and monotonic() <= self._expires_at - 30:
                return
            if await self._async_refresh_access_token_locked():
                return
            await self._async_authenticate_locked()

    async def _async_reauthenticate_after_rejection(self, rejected_token: str | None) -> None:
        """Replace a server-rejected token once without duplicate concurrent logins."""
        async with self._auth_lock:
            if self._access_token and self._access_token != rejected_token:
                return
            self._access_token = None
            self._expires_at = 0
            if await self._async_refresh_access_token_locked():
                return
            await self._async_authenticate_locked()

    async def _authentication_request(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        ok_status: frozenset[int] = frozenset({200}),
        operation: str,
        credential_rejection: bool = False,
    ) -> dict[str, Any]:
        """POST an authentication request with transient-error classification.

        Only the direct Gigya password login may classify HTTP 400/401/403 as
        invalid credentials.  Rejected refresh, JWT and Ayla exchange requests
        are cloud/session failures and must never trigger Home Assistant reauth.
        """
        if (data is None) == (json_body is None):
            raise ValueError("authentication request requires exactly one request body")
        last_error: CloudError | None = None
        for attempt in range(CLOUD_HTTP_RETRY_COUNT + 1):
            try:
                request_kwargs: dict[str, Any] = {
                    "timeout": aiohttp.ClientTimeout(total=CLOUD_HTTP_TIMEOUT),
                }
                if data is not None:
                    request_kwargs["data"] = data
                else:
                    request_kwargs["json"] = json_body
                async with self._session.post(
                    url,
                    **request_kwargs,
                ) as resp:
                    text = await resp.text()
                    if resp.status == 429:
                        raise RateLimitError(
                            f"{operation} was rate limited",
                            retry_after=self._sanitized_retry_after(resp.headers.get("Retry-After")),
                        )
                    if resp.status in {400, 401, 403}:
                        if credential_rejection:
                            raise AuthError(f"{operation} rejected the credentials (HTTP {resp.status})")
                        raise CloudError(
                            f"{operation} rejected the request (HTTP {resp.status})",
                            http_status=resp.status,
                        )
                    if resp.status in CLOUD_TRANSIENT_HTTP_CODES and attempt < CLOUD_HTTP_RETRY_COUNT:
                        await asyncio.sleep(CLOUD_HTTP_RETRY_BACKOFF * (2**attempt))
                        continue
                    if resp.status not in ok_status:
                        raise CloudError(
                            f"{operation} failed (HTTP {resp.status})",
                            http_status=resp.status,
                        )
                    try:
                        body = json.loads(text)
                    except json.JSONDecodeError as err:
                        raise CloudError(
                            f"{operation} returned an invalid response",
                            http_status=resp.status,
                        ) from err
                    if not isinstance(body, dict):
                        raise CloudError(
                            f"{operation} returned an unexpected response",
                            http_status=resp.status,
                        )
                    return body
            except AuthError:
                raise
            except RateLimitError:
                raise
            except CloudError as err:
                last_error = err
                if err.http_status in CLOUD_TRANSIENT_HTTP_CODES and attempt < CLOUD_HTTP_RETRY_COUNT:
                    await asyncio.sleep(CLOUD_HTTP_RETRY_BACKOFF * (2**attempt))
                    continue
                raise
            except (TimeoutError, aiohttp.ClientError) as err:
                last_error = CloudError(f"{operation} network error ({type(err).__name__})")
                if attempt < CLOUD_HTTP_RETRY_COUNT:
                    await asyncio.sleep(CLOUD_HTTP_RETRY_BACKOFF * (2**attempt))
                    continue
                raise last_error from err
        raise last_error or CloudError(f"{operation} failed after retries")

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"auth_token {self._access_token}"}

    @staticmethod
    def _sanitized_retry_after(raw: str | None) -> float:
        """Return a bounded delay for an untrusted Retry-After header."""
        try:
            delay = float(raw) if raw is not None else CLOUD_RETRY_AFTER_DEFAULT
        except TypeError, ValueError:
            delay = CLOUD_RETRY_AFTER_DEFAULT
        if not isfinite(delay):
            delay = CLOUD_RETRY_AFTER_DEFAULT
        return min(max(delay, 0.0), CLOUD_RETRY_AFTER_MAX)

    @staticmethod
    def _value_hint(value: Any) -> str:
        if isinstance(value, str):
            return f"len={len(value)}"
        return type(value).__name__

    def _log_http(
        self,
        method: str,
        operation: str,
        status: int,
        elapsed_ms: float,
        *,
        detail: str = "",
    ) -> None:
        msg = "%s %s -> HTTP %d (%.0fms)%s"
        args: tuple[Any, ...] = (method, operation, status, elapsed_ms, detail)
        # The coordinator owns the one unavailable/available warning cycle.
        # Per-request details stay at debug level to avoid log floods, and the
        # caller supplies a privacy-safe operation without a device DSN or URL.
        _LOGGER.debug(msg, *args)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        ok_status: frozenset[int] | set[int] | None = None,
        op: str = "",
        _retry_auth: bool = True,
    ) -> Any:
        """Perform an authenticated Ayla request with bounded retries."""
        await self.async_ensure_auth()
        safe_operation = op.split(" dsn=", 1)[0] if op else method
        if ok_status is None:
            ok_status = frozenset({200, 201})
        last_error: CloudError | None = None
        for attempt in range(CLOUD_HTTP_RETRY_COUNT + 1):
            started = time.monotonic()
            try:
                request_token = self._access_token
                async with self._session.request(
                    method,
                    url,
                    headers={**self._auth_headers(), **(extra_headers or {})},
                    json=json_body,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=CLOUD_HTTP_TIMEOUT),
                ) as resp:
                    elapsed_ms = (time.monotonic() - started) * 1000
                    text = await resp.text()
                    detail = f" [{safe_operation}]" if op else ""
                    if json_body and "datapoint" in json_body:
                        prop_val = json_body["datapoint"].get("value")
                        detail += f" value={self._value_hint(prop_val)}"
                    self._log_http(
                        method,
                        safe_operation,
                        resp.status,
                        elapsed_ms,
                        detail=detail,
                    )

                    if resp.status in (401, 403):
                        raise _AccessTokenRejected(resp.status, request_token)

                    if resp.status == 429:
                        raise RateLimitError(
                            f"{safe_operation} was rate limited",
                            retry_after=self._sanitized_retry_after(resp.headers.get("Retry-After")),
                        )

                    if resp.status in CLOUD_TRANSIENT_HTTP_CODES and attempt < CLOUD_HTTP_RETRY_COUNT:
                        retry_after = resp.headers.get("Retry-After")
                        try:
                            retry_hint = float(retry_after) if retry_after is not None else 0.0
                        except TypeError, ValueError:
                            retry_hint = 0.0
                        if not isfinite(retry_hint):
                            retry_hint = 0.0
                        retry_delay = max(
                            min(max(retry_hint, 0.0), CLOUD_RETRY_AFTER_MAX),
                            CLOUD_HTTP_RETRY_BACKOFF * (2**attempt) + random.uniform(0, 0.4),
                        )
                        _LOGGER.debug(
                            "Ayla transient HTTP %d on %s %s; retry %d/%d in %.1fs",
                            resp.status,
                            method,
                            safe_operation,
                            attempt + 1,
                            CLOUD_HTTP_RETRY_COUNT,
                            retry_delay,
                        )
                        await asyncio.sleep(retry_delay)
                        continue

                    if resp.status not in ok_status:
                        raise CloudError(
                            f"{safe_operation} failed (HTTP {resp.status})",
                            http_status=resp.status,
                        )

                    if not text.strip():
                        return None
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError as err:
                        raise CloudError(
                            f"{safe_operation}: expected JSON, got {resp.content_type!r} ({len(text)} bytes)",
                            http_status=resp.status,
                        ) from err
            except _AccessTokenRejected as err:
                if _retry_auth:
                    await self._async_reauthenticate_after_rejection(err.token)
                    return await self._request_json(
                        method,
                        url,
                        json_body=json_body,
                        data=data,
                        extra_headers=extra_headers,
                        ok_status=ok_status,
                        op=op,
                        _retry_auth=False,
                    )
                raise CloudError(
                    f"{safe_operation} remained unauthorized after automatic token renewal (HTTP {err.status})",
                    http_status=err.status,
                ) from err
            except (TimeoutError, aiohttp.ClientError) as err:
                elapsed_ms = (time.monotonic() - started) * 1000
                last_error = CloudError(f"{safe_operation} network error after {elapsed_ms:.0f}ms ({type(err).__name__})")
                if attempt < CLOUD_HTTP_RETRY_COUNT:
                    _LOGGER.debug(
                        "Ayla network error on %s %s; retry %d/%d (error_type=%s)",
                        method,
                        safe_operation,
                        attempt + 1,
                        CLOUD_HTTP_RETRY_COUNT,
                        type(err).__name__,
                    )
                    await asyncio.sleep(CLOUD_HTTP_RETRY_BACKOFF * (2**attempt) + random.uniform(0, 0.4))
                    continue
                raise last_error from err

        if last_error:
            raise last_error
        raise CloudError(f"{safe_operation} failed after retries")

    async def _gigya_login_and_jwt(self) -> str:
        """Login to Gigya + get JWT via signed request (HMAC-SHA1 with sessionSecret)."""
        login_url = f"{GIGYA_BASE_URL}/accounts.login"
        body = await self._authentication_request(
            login_url,
            data={
                "apiKey": GIGYA_API_KEY,
                "loginID": self._email,
                "password": self._password,
                "format": "json",
                "targetEnv": "mobile",
            },
            operation="Gigya login",
            credential_rejection=True,
        )
        if body.get("errorCode") != 0:
            error_code = body.get("errorCode")
            message = f"Gigya login failed (code {error_code})"
            if error_code == 403042:
                raise AuthError(message)
            raise CloudError(message)

        session_token = body["sessionInfo"]["sessionToken"]
        session_secret = body["sessionInfo"]["sessionSecret"]

        timestamp = str(int(time.time()))
        nonce = f"{timestamp}_1"
        url = f"{GIGYA_BASE_URL}/accounts.getJWT"
        params = {
            "apiKey": GIGYA_API_KEY,
            "oauth_token": session_token,
            "format": "json",
            "timestamp": timestamp,
            "nonce": nonce,
        }
        sorted_params = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted(params.items()))
        base_str = f"POST&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(sorted_params, safe='')}"
        sig = base64.b64encode(hmac.new(base64.b64decode(session_secret), base_str.encode(), hashlib.sha1).digest()).decode()
        params["sig"] = sig
        jwt_body = await self._authentication_request(
            url,
            data=params,
            operation="Gigya JWT request",
        )
        if jwt_body.get("errorCode") != 0:
            raise CloudError(f"Gigya getJWT failed (code {jwt_body.get('errorCode', 'unknown')})")
        if not isinstance(id_token := jwt_body.get("id_token"), str):
            raise CloudError("Gigya getJWT response did not contain an ID token")
        return id_token

    async def _ayla_sso_sign_in(self, jwt_token: str) -> None:
        """Exchange JWT for Ayla access_token (form-urlencoded)."""
        url = f"{AYLA_EU_USER_URL}/api/v1/token_sign_in"
        data = {"token": jwt_token, "app_id": APP_ID, "app_secret": APP_SECRET}
        body = await self._authentication_request(
            url,
            data=data,
            ok_status=frozenset({200, 201}),
            operation="Ayla SSO",
        )
        self._store_ayla_tokens(body, operation="Ayla SSO")

    @staticmethod
    def _token_ttl(value: Any) -> float:
        """Return a usable relative token lifetime from an untrusted response."""
        try:
            ttl = float(value)
        except TypeError, ValueError:
            return 3600.0
        return ttl if isfinite(ttl) and ttl > 0 else 3600.0

    def _store_ayla_tokens(
        self,
        body: dict[str, Any],
        *,
        operation: str,
        keep_refresh_token: bool = False,
    ) -> None:
        """Validate and store an Ayla token response without exposing secrets."""
        access_token = body.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise CloudError(f"{operation} response did not contain an access token")
        refresh_token = body.get("refresh_token")
        self._access_token = access_token
        if isinstance(refresh_token, str) and refresh_token:
            self._refresh_token = refresh_token
        elif not keep_refresh_token:
            self._refresh_token = None
        self._expires_at = monotonic() + self._token_ttl(body.get("expires_in", 3600))

    async def _async_refresh_access_token_locked(self) -> bool:
        """Use Ayla's refresh token while the caller owns the authentication lock."""
        if not self._refresh_token:
            return False
        refresh_token = self._refresh_token
        try:
            body = await self._authentication_request(
                f"{AYLA_EU_USER_URL}/users/refresh_token.json",
                json_body={"user": {"refresh_token": refresh_token}},
                ok_status=frozenset({200, 201}),
                operation="Ayla token refresh",
            )
        except CloudError as err:
            if err.http_status not in {400, 401, 403}:
                raise
            self._refresh_token = None
            return False
        self._store_ayla_tokens(
            body,
            operation="Ayla token refresh",
            keep_refresh_token=True,
        )
        return True

    async def async_get_devices(self, *, max_age: float = 0) -> list[AylaDevice]:
        """List account devices, optionally sharing a bounded account-wide cache."""
        now = time.monotonic()
        cached = self._devices_cache
        if cached is not None and max_age > 0 and now - cached[0] < max_age:
            return list(cached[1])

        async with self._devices_lock:
            now = time.monotonic()
            cached = self._devices_cache
            if cached is not None and max_age > 0 and now - cached[0] < max_age:
                return list(cached[1])

            url = f"{AYLA_EU_ADS_URL}/apiv1/devices.json"
            data = await self._request_json("GET", url, ok_status=frozenset({200}), op="list devices")
            if not isinstance(data, list):
                raise CloudError("list devices: expected a JSON list")
            devices: list[AylaDevice] = []
            for wrap in data:
                d = wrap.get("device", wrap)
                devices.append(
                    AylaDevice(
                        dsn=d.get("dsn", ""),
                        name=d.get("product_name") or d.get("dsn", ""),
                        oem_model=d.get("oem_model", ""),
                        model=d.get("model", ""),
                        sw_version=d.get("sw_version", ""),
                        connection_status=d.get("connection_status", "Unknown"),
                    )
                )
            self._devices_cache = (now, tuple(devices))
            return list(devices)

    async def async_get_properties(self, dsn: str) -> AylaProperties:
        """Fetch all properties of a device, keyed by property name."""
        url = f"{AYLA_EU_ADS_URL}/apiv1/dsns/{dsn}/properties.json"
        data = await self._request_json("GET", url, ok_status=frozenset({200}), op=f"list properties dsn={dsn}")
        if not isinstance(data, list):
            raise CloudError("list properties: expected a JSON list")
        props: AylaProperties = {}
        for item in data:
            p = item.get("property", {})
            name = p.get("name")
            if name:
                props[name] = p
        return props

    async def async_get_connection_info(self, dsn: str) -> dict[str, Any]:
        """Return optional Ayla connectivity diagnostics for one device.

        The caller is responsible for retaining only privacy-safe fields.  In
        particular, ``network_name`` must never be exposed by diagnostics or
        logs because it can contain the user's Wi-Fi SSID.
        """
        url = f"{AYLA_EU_ADS_URL}/apiv1/dsns/{dsn}/connection_info.json"
        data = await self._request_json("GET", url, ok_status=frozenset({200}), op=f"connection info dsn={dsn}")
        if not isinstance(data, dict):
            raise CloudError("connection info: expected a JSON object")
        info = data.get("connection_info", data.get("connectionInfo", data))
        if not isinstance(info, dict):
            raise CloudError("connection info: unexpected response")
        return info

    @staticmethod
    def _unwrap_dss_subscription(value: Any) -> dict[str, Any] | None:
        """Normalize the wrapper used by the Ayla subscription API."""
        if not isinstance(value, dict):
            return None
        subscription = value.get("subscription", value)
        return subscription if isinstance(subscription, dict) else None

    @staticmethod
    def dss_subscription_stream_key(subscription: dict[str, Any]) -> str | None:
        """Return a stream key without ever logging or persisting it."""
        value = subscription.get("stream_key", subscription.get("streamKey"))
        return value if isinstance(value, str) and value else None

    async def async_create_dss_subscription(self) -> dict[str, Any]:
        """Create one fresh, account-wide DSS stream subscription.

        Coffee Link creates a new subscription whenever it needs a new stream
        and discards the saved stream key as soon as the WebSocket opens.  A
        key therefore remains an in-memory, single-connection credential; it
        is never recovered from the subscription list or persisted by this
        integration.  The integration uses its own name and never inspects,
        modifies or deletes Coffee Link's ``ANDROID_DSS`` subscription.
        """
        url = f"{AYLA_EU_MDSS_URL}/api/v1/subscriptions"
        body = {
            "name": DSS_SUBSCRIPTION_NAME,
            "description": DSS_SUBSCRIPTION_DESCRIPTION,
            "dsn": None,
            "property_name": "*",
            "client_type": "mobile",
            "batch_size": "1",
            "subscription_type": DSS_SUBSCRIPTION_TYPES,
        }
        created = await self._request_json(
            "POST",
            url,
            json_body=body,
            ok_status=frozenset({200, 201}),
            op="create DSS subscription",
        )
        subscription = self._unwrap_dss_subscription(created)
        if not subscription or not self.dss_subscription_stream_key(subscription):
            raise CloudError("create DSS subscription: stream key missing")
        return subscription

    async def async_open_dss_websocket(self, stream_key: str) -> aiohttp.ClientWebSocketResponse:
        """Open the Ayla DSS stream for a short-lived in-memory stream key."""
        await self.async_ensure_auth()
        query = urllib.parse.urlencode({"stream_key": stream_key})
        url = f"{AYLA_EU_MSTREAM_URL.replace('https://', 'wss://')}/stream?{query}"
        return await self._session.ws_connect(
            url,
            heartbeat=None,
            autoclose=True,
            autoping=True,
            timeout=aiohttp.ClientWSTimeout(ws_receive=CLOUD_HTTP_TIMEOUT),
        )

    async def async_set_property_value(self, dsn: str, property_name: str, value: Any) -> dict[str, Any]:
        """Write a value to a device property (e.g. data_request)."""
        url = f"{AYLA_EU_ADS_URL}/apiv1/dsns/{dsn}/properties/{property_name}/datapoints.json"
        result = await self._request_json(
            "POST",
            url,
            json_body={"datapoint": {"value": value}},
            extra_headers={"x-ayla-source": "Mobile"},
            ok_status=frozenset({200, 201}),
            op=f"set {property_name} dsn={dsn}",
        )
        return result or {}

    async def async_get_property(self, dsn: str, property_name: str) -> AylaProperty:
        """Fetch a single device property (fallback when coordinator.data is empty)."""
        url = f"{AYLA_EU_ADS_URL}/apiv1/dsns/{dsn}/properties/{property_name}.json"
        data = await self._request_json("GET", url, ok_status=frozenset({200}), op=f"get {property_name} dsn={dsn}")
        prop = data.get("property")
        if not isinstance(prop, dict):
            raise CloudError(f"get_property {property_name}: unexpected response type")
        return prop

    async def async_get_property_resilient(self, dsn: str, property_name: str) -> AylaProperty:
        """Eletta-only: GET with retry (confirm loop live app_id polling)."""
        url = f"{AYLA_EU_ADS_URL}/apiv1/dsns/{dsn}/properties/{property_name}.json"
        data = await self._request_json(
            "GET",
            url,
            ok_status=frozenset({200}),
            op=f"get {property_name} dsn={dsn}",
        )
        prop = data.get("property")
        if not isinstance(prop, dict):
            raise CloudError(f"get_property {property_name}: unexpected response {data!r}")
        raw = prop.get("value")
        _LOGGER.debug(
            "Property %s value_hint=%s",
            property_name,
            self._value_hint(raw),
        )
        return prop

    async def async_post_cloud_session(self, dsn: str, connected_property: str, integration_app_id: int) -> dict[str, Any]:
        """Register a cloud app session (app_device_connected / device_connected).

        Payload: base64(timestamp_4bytes + signed_app_id_4bytes), per DlghIoT.
        """
        now_s = int(time.time())
        payload = base64.b64encode(
            now_s.to_bytes(4, "big", signed=False) + integration_app_id_to_bytes(integration_app_id)
        ).decode("utf-8")
        _LOGGER.debug(
            "POST cloud session connect property=%s payload_len=%d",
            connected_property,
            len(payload),
        )
        url = f"{AYLA_EU_ADS_URL}/apiv1/dsns/{dsn}/properties/{connected_property}/datapoints.json"
        result = await self._request_json(
            "POST",
            url,
            json_body={"datapoint": {"value": payload}},
            extra_headers={"x-ayla-source": "Mobile"},
            ok_status=frozenset({200, 201}),
            op=f"set {connected_property} dsn={dsn}",
        )
        return result or {}


def normalize_signed_app_id(app_id: int) -> int:
    """Convert an app id to signed int32 (matches machine property decimal form)."""
    return ((app_id & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000


def integration_app_id_to_bytes(app_id: int) -> bytes:
    """Encode app id as signed int32 big-endian (DlghIoT convention)."""
    return normalize_signed_app_id(app_id).to_bytes(4, "big", signed=True)

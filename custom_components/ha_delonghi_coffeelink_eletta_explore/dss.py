"""Ayla Data Stream Service (DSS) with a polling safety fallback.

Coffee Link 4.9.6 creates a fresh account-wide subscription for each stream
connection and discards the returned stream key after the WebSocket opens.
Frames contain one changed datapoint or one datapoint acknowledgement.  This
module mirrors only that cloud mechanism; it has no LAN code and never persists
or logs the stream key.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from .ayla_client import AuthError, CloudError, DelonghiAylaClient
from .const import (
    DOMAIN,
    DSS_RECONNECT_MAX_DELAY,
    DSS_RECONNECT_MIN_DELAY,
    DSS_STREAM_IDLE_TIMEOUT,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import DelonghiCoordinator

_LOGGER = logging.getLogger(__name__)

_DSS_HEARTBEAT = "1|Z"
_DSS_KEEP_ALIVE = "1|X"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except TypeError, ValueError:
        return None


@dataclass(frozen=True, slots=True)
class DssEvent:
    """Privacy-safe normalized subset of one Ayla stream event."""

    sequence: str | None
    event_type: str
    dsn: str
    property_name: str | None
    datapoint_id: str | None
    value: Any
    updated_at: str | None
    acked_at: str | None
    ack_status: int | None
    ack_message: int | str | None


def parse_dss_message(message: str) -> DssEvent | None:
    """Parse a DSS WebSocket text frame; return ``None`` for keep-alives.

    Ayla prefixes JSON with a sequence and ``|``.  Invalid or unrelated frames
    are ignored so malformed cloud data can never take the integration down.
    """
    if not isinstance(message, str) or message in {_DSS_HEARTBEAT, _DSS_KEEP_ALIVE}:
        return None
    prefix, separator, payload = message.partition("|")
    if not separator or not payload:
        return None
    try:
        document = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return None
    event_type = metadata.get("event_type") or metadata.get("eventType")
    dsn = metadata.get("dsn")
    if event_type not in {"datapoint", "datapointack", "connectivity"}:
        return None
    if not isinstance(dsn, str) or not dsn:
        return None

    datapoint = document.get("datapoint")
    if not isinstance(datapoint, dict):
        datapoint = {}
    property_name = metadata.get("property_name")
    if not isinstance(property_name, str):
        property_name = metadata.get("propertyName")
    if not isinstance(property_name, str):
        property_name = None
    datapoint_id = datapoint.get("id")
    if datapoint_id is not None:
        datapoint_id = str(datapoint_id)
    updated_at = datapoint.get("updated_at", datapoint.get("updatedAt"))
    acked_at = datapoint.get("acked_at", datapoint.get("ackedAt"))
    sequence = document.get("seq")
    if sequence is None:
        sequence = prefix
    return DssEvent(
        sequence=str(sequence) if sequence is not None else None,
        event_type=event_type,
        dsn=dsn,
        property_name=property_name,
        datapoint_id=datapoint_id,
        value=datapoint.get("value"),
        updated_at=updated_at if isinstance(updated_at, str) else None,
        acked_at=acked_at if isinstance(acked_at, str) else None,
        ack_status=_optional_int(datapoint.get("ack_status", datapoint.get("ackStatus"))),
        ack_message=datapoint.get("ack_message", datapoint.get("ackMessage")),
    )


class AylaDssManager:
    """Own one resilient account-wide DSS stream."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DelonghiAylaClient,
        coordinators: list[DelonghiCoordinator],
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._client = client
        self._coordinators = {coordinator.device.dsn: coordinator for coordinator in coordinators}
        self._task: asyncio.Task[None] | None = None
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._stopping = False
        self.state = "polling"
        self.events_received = 0
        self.event_type_counts = {
            "datapoint": 0,
            "datapointack": 0,
            "connectivity": 0,
        }
        self.reconnect_count = 0
        self.last_event_at: str | None = None
        self.last_error_type: str | None = None

    def start(self) -> None:
        """Start stream supervision in the config entry's task scope."""
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = self._entry.async_create_background_task(
            self._hass,
            self._async_run(),
            f"{DOMAIN}_dss_stream",
        )

    async def async_stop(self) -> None:
        """Stop the stream and discard its short-lived in-memory credential."""
        self._stopping = True
        if self._websocket is not None and not self._websocket.closed:
            await self._websocket.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        self._websocket = None

    def _set_state(self, state: str) -> None:
        if state == self.state:
            return
        previous = self.state
        self.state = state
        for coordinator in self._coordinators.values():
            coordinator.set_dss_state(state, request_refresh=previous == "streaming")

    async def _async_run(self) -> None:
        delay = float(DSS_RECONNECT_MIN_DELAY)
        while not self._stopping:
            try:
                self._set_state("connecting")
                subscription = await self._client.async_create_dss_subscription()
                stream_key = self._client.dss_subscription_stream_key(subscription)
                if not stream_key:
                    raise CloudError("DSS subscription did not contain a stream key")
                self._websocket = await self._client.async_open_dss_websocket(stream_key)
                self.last_error_type = None
                self._set_state("streaming")
                delay = float(DSS_RECONNECT_MIN_DELAY)
                await self._async_receive()
                if not self._stopping:
                    raise CloudError("DSS stream closed")
            except asyncio.CancelledError:
                raise
            except (AuthError, CloudError, TimeoutError, aiohttp.ClientError) as err:
                self.last_error_type = type(err).__name__
                self.reconnect_count += 1
                self._set_state("polling")
                if self.reconnect_count == 1:
                    _LOGGER.warning(
                        "Ayla DSS stream unavailable; using polling fallback (error_type=%s)",
                        self.last_error_type,
                    )
                else:
                    _LOGGER.debug(
                        "Ayla DSS reconnect scheduled (error_type=%s, attempt=%d)",
                        self.last_error_type,
                        self.reconnect_count,
                    )
            except Exception as err:  # noqa: BLE001 - push must never break polling
                self.last_error_type = type(err).__name__
                self.reconnect_count += 1
                self._set_state("polling")
                _LOGGER.warning(
                    "Unexpected Ayla DSS failure; using polling fallback (error_type=%s)",
                    self.last_error_type,
                )
            finally:
                websocket = self._websocket
                self._websocket = None
                if websocket is not None and not websocket.closed:
                    await websocket.close()

            if self._stopping:
                break
            await asyncio.sleep(delay + random.uniform(0, min(1.0, delay / 4)))
            delay = min(float(DSS_RECONNECT_MAX_DELAY), delay * 2)

    async def _async_receive(self) -> None:
        websocket = self._websocket
        if websocket is None:
            raise CloudError("DSS WebSocket was not opened")
        while not self._stopping:
            message = await websocket.receive(timeout=DSS_STREAM_IDLE_TIMEOUT)
            if message.type is aiohttp.WSMsgType.TEXT:
                if message.data == _DSS_HEARTBEAT:
                    await websocket.send_str(_DSS_HEARTBEAT)
                    continue
                event = parse_dss_message(message.data)
                if event is None:
                    continue
                coordinator = self._coordinators.get(event.dsn)
                if coordinator is None:
                    continue
                if coordinator.handle_dss_event(event):
                    self.events_received += 1
                    self.event_type_counts[event.event_type] += 1
                    self.last_event_at = datetime.now(UTC).isoformat()
            elif message.type in {
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            }:
                raise CloudError("DSS WebSocket ended")

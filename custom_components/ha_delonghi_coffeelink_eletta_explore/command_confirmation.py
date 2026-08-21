"""Event-driven command confirmation with a bounded polling fallback."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic


class CommandConfirmationTracker:
    """Coordinate DSS state notifications with command confirmation waits."""

    def __init__(self) -> None:
        self._waiters: set[asyncio.Future[None]] = set()

    @property
    def has_waiters(self) -> bool:
        """Return whether a command is currently waiting for a DSS transition."""
        return bool(self._waiters)

    def notify(self) -> None:
        """Wake every confirmation waiting for a relevant state transition."""
        for waiter in tuple(self._waiters):
            if not waiter.done():
                waiter.set_result(None)

    def cancel(self) -> None:
        """Cancel in-flight confirmations during integration unload."""
        for waiter in self._waiters:
            waiter.cancel()
        self._waiters.clear()

    async def async_wait(
        self,
        *,
        changed: Callable[[], bool],
        streaming: Callable[[], bool],
        refresh: Callable[[], Awaitable[None]],
        timeout: float,
        poll_interval: float,
    ) -> bool:
        """Wait for state change and reconcile once if a stream misses an event."""
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if changed():
                return True

            if streaming():
                waiter = asyncio.get_running_loop().create_future()
                self._waiters.add(waiter)
                try:
                    # Close the race between the state check and registration.
                    if changed():
                        return True
                    remaining = max(0.0, deadline - monotonic())
                    try:
                        await asyncio.wait_for(waiter, remaining)
                    except TimeoutError:
                        break
                finally:
                    self._waiters.discard(waiter)
                continue

            await refresh()
            if changed():
                return True
            remaining = deadline - monotonic()
            if remaining > 0:
                await asyncio.sleep(min(poll_interval, remaining))

        # A push stream can miss an event while reconnecting. One authoritative
        # reconciliation keeps the timeout path fail-safe without full polling.
        if streaming():
            await refresh()
        return changed()

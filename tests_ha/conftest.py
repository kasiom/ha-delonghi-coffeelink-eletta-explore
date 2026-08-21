"""Fixtures for tests running against the real Home Assistant package."""

from __future__ import annotations

import sys

import pytest
import pytest_socket


def _keep_windows_socket_enabled(allow_unix_socket: bool = False) -> None:
    """Keep sockets available for Windows' internal asyncio loopback pair."""
    pytest_socket.enable_socket()


@pytest.hookimpl(tryfirst=True)
def pytest_configure() -> None:
    """Preserve Home Assistant's socket guard except on Windows."""
    if sys.platform == "win32":
        pytest_socket.disable_socket = _keep_windows_socket_enabled


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant's loader to load this repository's integration."""

"""Fixtures for tests running against the real Home Assistant package."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant's loader to load this repository's integration."""

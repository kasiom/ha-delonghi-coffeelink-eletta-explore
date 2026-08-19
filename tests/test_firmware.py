"""Tests for concise manufacturer firmware presentation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PKG_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_delonghi_coffeelink_eletta_explore"
)


def _load_firmware():
    name = "ha_delonghi_coffeelink_eletta_explore.firmware"
    spec = importlib.util.spec_from_file_location(name, PKG_DIR / "firmware.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


firmware = _load_firmware()
appliance_software_version = firmware.appliance_software_version
device_firmware_version = firmware.device_firmware_version


@pytest.mark.parametrize(
    ("data", "fallback", "expected"),
    [
        (
            {"software_version": {"value": "Striker_cb_demo 1.1.0 Oct 18 2022 10:44:21"}},
            "ADA 1.6 esp-idf-v3.3.1",
            "Striker_cb_demo 1.1.0 Oct 18 2022 10:44:21",
        ),
        ({"software_version": {"value": "  "}}, "ADA 1.6", "ADA 1.6"),
        ({}, "ADA 1.6", "ADA 1.6"),
        (None, None, None),
    ],
)
def test_appliance_software_version(data, fallback, expected):
    assert appliance_software_version(data, fallback) == expected


@pytest.mark.parametrize(
    ("data", "connectivity", "expected"),
    [
        (
            {"software_version": {"value": "Striker_cb_demo 1.1.0 Oct 18 2022 10:44:21"}},
            "ADA 1.6 esp-idf-v3.3.1",
            "Striker_cb_demo 1.1.0 Oct 18 2022 10:44:21",
        ),
        ({"software_version": {"value": "Striker 2.0"}}, None, "Striker 2.0"),
        ({}, "ADA 1.6", "ADA 1.6"),
        ({}, None, None),
    ],
)
def test_device_firmware_version(data, connectivity, expected):
    assert device_firmware_version(data, connectivity) == expected

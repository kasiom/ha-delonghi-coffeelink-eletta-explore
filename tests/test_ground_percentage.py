"""Tests for the De'Longhi grounds-container percentage parser."""
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


def _load_counters():
    name = "ha_delonghi_coffeelink_eletta_explore.counters"
    spec = importlib.util.spec_from_file_location(name, PKG_DIR / "counters.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parse_percentage_value = _load_counters().parse_percentage_value
parse_remaining_percentage = _load_counters().parse_remaining_percentage


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (45, 45),
        (100, 100),
        (" 72 ", 72),
        (-1, None),
        (101, None),
        (True, None),
        (None, None),
        ("not-a-percentage", None),
    ],
)
def test_parse_percentage_value(value, expected):
    assert parse_percentage_value(value) == expected


@pytest.mark.parametrize(
    ("consumed", "remaining"),
    [
        (0, 100),
        (21, 79),
        (90, 10),
        (100, 0),
        (-1, None),
        (101, None),
        (True, None),
    ],
)
def test_parse_remaining_percentage(consumed, remaining):
    assert parse_remaining_percentage(consumed) == remaining


def test_undocumented_raw_ground_counter_is_not_exposed() -> None:
    """The raw d551 value must create neither an entity nor a state attribute."""
    const_source = (PKG_DIR / "const.py").read_text(encoding="utf-8")
    binary_sensor_source = (PKG_DIR / "binary_sensor.py").read_text(
        encoding="utf-8"
    )

    assert "d551_cnt_coffee_fondi" not in const_source
    assert "grounds_counter" not in binary_sensor_source


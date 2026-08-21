"""Unit tests for the pure counter-value parsing (counters.py).

Loads only the dependency-free ``counters`` module (no Home Assistant import),
matching the approach in test_command_builder.py. Covers both value shapes seen
in the field: plain integers (PrimaDonna Soul) and JSON-object aggregated
counters (Eletta Explore, #7).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "ha_delonghi_coffeelink_eletta_explore"


def _load(modname: str, filename: str):
    full = f"ha_delonghi_coffeelink_eletta_explore.{modname}"
    spec = importlib.util.spec_from_file_location(full, PKG_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


counters = _load("counters", "counters.py")
parse_counter_value = counters.parse_counter_value
counter_breakdown = counters.counter_breakdown
counter_breakdown_sum = counters.counter_breakdown_sum
coffee_link_black_coffee_total = counters.coffee_link_black_coffee_total
coffee_link_cold_milk_total = counters.coffee_link_cold_milk_total
coffee_link_hot_milk_total = counters.coffee_link_hot_milk_total
coffee_link_mug_total = counters.coffee_link_mug_total
parse_total_water_volume_liters = counters.parse_total_water_volume_liters
parse_water_volume_liters = counters.parse_water_volume_liters
parse_water_hardness_level = counters.parse_water_hardness_level
coffee_link_legacy_black_coffee_total = counters.coffee_link_legacy_black_coffee_total
coffee_link_legacy_hot_milk_total = counters.coffee_link_legacy_hot_milk_total


# --- parse_counter_value -------------------------------------------------- #


@pytest.mark.parametrize(
    "value,expected",
    [
        # Soul: plain integers / numeric strings
        (314, 314),
        (0, 0),
        ("314", 314),
        ("  42 ", 42),
        # Eletta: JSON object of per-recipe sub-counts -> sum
        ('{"espresso": 12, "coffee": 3}', 15),
        ('{"a": 1, "b": 2, "c": 3}', 6),
        ('{"only": 7}', 7),
        ("{}", 0),
        # JSON where some sub-values are not integers -> ignored, rest summed
        ('{"good": 5, "bad": "x", "also": 2}', 7),
        # Unparseable / unexpected -> None (sensor stays unknown)
        (None, None),
        (True, None),
        (False, None),
        ("", None),
        ("not-a-number", None),
        ('{"broken": ', None),  # malformed non-object-looking string
        ('{"broken":}', None),  # malformed object-looking JSON
        ("[1, 2, 3]", None),  # JSON array, not an object
    ],
)
def test_parse_counter_value(value, expected):
    assert parse_counter_value(value) == expected


def test_parse_counter_value_bool_is_not_int():
    # bool is a subtype of int in Python; ensure we never treat it as a count.
    assert parse_counter_value(True) is None
    assert parse_counter_value(False) is None


@pytest.mark.parametrize(
    ("raw_milliliters", "liters"),
    [
        (0, 0.0),
        (1, 0.001),
        (1234, 1.234),
        ("2500", 2.5),
        (None, None),
        ("invalid", None),
    ],
)
def test_parse_water_volume_liters(raw_milliliters, liters):
    assert parse_water_volume_liters(raw_milliliters) == liters


@pytest.mark.parametrize(
    ("raw_half_milliliter_ticks", "liters"),
    [
        (0, 0.0),
        (1, 0.001),
        (2000, 1.0),
        (419850, 209.925),
        (None, None),
        ("invalid", None),
    ],
)
def test_parse_total_water_volume_liters(raw_half_milliliter_ticks, liters):
    assert parse_total_water_volume_liters(raw_half_milliliter_ticks) == liters


@pytest.mark.parametrize(
    ("black", "expected"),
    [("314", 314), (None, None), ("invalid", None)],
)
def test_coffee_link_legacy_black_coffee_total(black, expected):
    assert coffee_link_legacy_black_coffee_total(black) == expected


@pytest.mark.parametrize(
    ("coffee_and_milk", "milk_only", "expected"),
    [("250", "17", 267), ("250", None, 250), (None, "17", None)],
)
def test_coffee_link_legacy_hot_milk_total(coffee_and_milk, milk_only, expected):
    assert coffee_link_legacy_hot_milk_total(coffee_and_milk, milk_only) == expected


def test_coffee_link_striker_without_cold_brew_excludes_milk_only_field():
    value = '{"tot_bev_bw":40,"tot_bev_w":5}'
    assert counters.coffee_link_hot_milk_total(value, include_milk_only=False) == 40


@pytest.mark.parametrize(
    ("cloud_value", "display_level"),
    [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (" 2 ", 3),
        (-1, None),
        (4, None),
        (True, None),
        (None, None),
    ],
)
def test_parse_water_hardness_level(cloud_value, display_level):
    assert parse_water_hardness_level(cloud_value) == display_level


# --- counter_breakdown ---------------------------------------------------- #


def test_counter_breakdown_returns_json_object():
    assert counter_breakdown('{"espresso": 12, "coffee": 3}') == {
        "espresso": 12,
        "coffee": 3,
    }


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        314,
        True,
        "",
        "314",
        "not-json",
        "[1,2]",
        '{"broken": ',
        '{"broken":}',
    ],
)
def test_counter_breakdown_none_for_non_objects(value):
    assert counter_breakdown(value) is None


# --- counter_breakdown_sum ------------------------------------------------ #


def test_counter_breakdown_sum_selects_only_requested_fields():
    value = '{"over_ice": 3, "cold_brew": 11, "cold_brew_latte": "2"}'
    assert counter_breakdown_sum(value, ("over_ice",)) == 3
    assert counter_breakdown_sum(value, ("cold_brew", "cold_brew_latte")) == 13


def test_counter_breakdown_sum_requires_at_least_one_selected_field():
    assert counter_breakdown_sum('{"another_recipe": 4}', ("espresso",)) is None
    assert counter_breakdown_sum("not-json", ("espresso",)) is None


def test_counter_breakdown_sum_ignores_invalid_selected_values():
    value = '{"good": 5, "bad": "x", "boolean": true}'
    assert counter_breakdown_sum(value, ("good", "bad", "boolean")) == 5
    assert counter_breakdown_sum(value, ("bad", "boolean")) is None


def test_coffee_link_official_eletta_aggregates():
    iced = '{"tot_bev_b_iced":23,"tot_bev_bw_iced":7,"tot_bev_w_iced":3,"unrelated":99}'
    other = '{"tot_bev_bw":300,"tot_bev_w":8,"unrelated":99}'

    assert coffee_link_black_coffee_total(616, iced) == 639
    assert coffee_link_hot_milk_total(other) == 308
    assert coffee_link_cold_milk_total(iced) == 10
    assert coffee_link_mug_total(16, 0) == 16


def test_coffee_link_aggregates_require_official_primary_fields():
    assert coffee_link_black_coffee_total(None, '{"tot_bev_b_iced":23}') is None
    assert coffee_link_black_coffee_total(616, None) == 616
    assert coffee_link_hot_milk_total('{"tot_bev_w":8}') is None
    assert coffee_link_cold_milk_total('{"tot_bev_w_iced":3}') is None
    assert coffee_link_mug_total(None, 2) is None
    assert coffee_link_mug_total(16, None) == 16


@pytest.mark.parametrize(
    ("parser", "invalid"),
    [
        (coffee_link_hot_milk_total, '{"tot_bev_bw":true,"tot_bev_w":8}'),
        (coffee_link_hot_milk_total, '{"tot_bev_bw":"bad","tot_bev_w":8}'),
        (
            coffee_link_cold_milk_total,
            '{"tot_bev_bw_iced":true,"tot_bev_w_iced":3}',
        ),
    ],
)
def test_coffee_link_aggregates_reject_invalid_required_fields(parser, invalid):
    assert parser(invalid) is None


def test_eletta_cold_group_keeps_over_ice_separate_from_cold_brew():
    value = (
        '{"tot_id57_over_ice_espresso":3,'
        '"tot_id120_cold_brew_coffee":11,'
        '"tot_id121_cold_brew_coffee_ess":2,'
        '"tot_id122_cold_brew_coffee_pot":0,'
        '"tot_id123_cold_brew_latte":1,'
        '"tot_id124_cold_brew_cappuccino":3,'
        '"tot_id140_cold_brew_mug":0,'
        '"tot_id141_cold_brew_latte_mug":0,'
        '"tot_id142_cold_brew_cappuccino_mug":0}'
    )
    cold_brew_keys = (
        "tot_id120_cold_brew_coffee",
        "tot_id121_cold_brew_coffee_ess",
        "tot_id122_cold_brew_coffee_pot",
        "tot_id123_cold_brew_latte",
        "tot_id124_cold_brew_cappuccino",
        "tot_id140_cold_brew_mug",
        "tot_id141_cold_brew_latte_mug",
        "tot_id142_cold_brew_cappuccino_mug",
    )

    assert parse_counter_value(value) == 20
    assert counter_breakdown_sum(value, ("tot_id57_over_ice_espresso",)) == 3
    assert counter_breakdown_sum(value, cold_brew_keys) == 17

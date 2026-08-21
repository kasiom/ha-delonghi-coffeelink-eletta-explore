"""Tests for stable beverage-button identity and legacy migration helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "ha_delonghi_coffeelink_eletta_explore" / "button_migration.py"
SPEC = importlib.util.spec_from_file_location("button_migration", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_canonical_id_uses_immutable_numeric_beverage_id() -> None:
    assert MODULE.canonical_start_unique_id("SERIAL", 120) == "SERIAL_start_beverage_120"


def test_resolves_semantic_technical_and_canonical_legacy_ids() -> None:
    keys = {"espresso": 1, "cold_brew": 120}
    assert MODULE.start_button_beverage_id("SERIAL_start_espresso", "SERIAL", keys) == 1
    assert MODULE.start_button_beverage_id("SERIAL_start_cold_brew", "SERIAL", keys) == 120
    assert MODULE.start_button_beverage_id("SERIAL_start_recipe_120", "SERIAL", keys) == 120
    assert MODULE.start_button_beverage_id("SERIAL_start_beverage_120", "SERIAL", keys) == 120


def test_rejects_unrelated_or_malformed_unique_ids() -> None:
    keys = {"espresso": 1}
    assert MODULE.start_button_beverage_id("OTHER_start_espresso", "SERIAL", keys) is None
    assert MODULE.start_button_beverage_id("SERIAL_stop", "SERIAL", keys) is None
    assert MODULE.start_button_beverage_id("SERIAL_start_recipe_x", "SERIAL", keys) is None


def test_prefers_established_entity_id_without_duplicate_suffix() -> None:
    entity_ids = [
        "button.kuchyne_cold_brew_2",
        "button.kuchyne_cold_brew",
        "button.kuchyne_cold_brew_3",
    ]
    assert MODULE.preferred_entity_index(entity_ids) == 1


def test_preferred_entity_uses_stable_order_for_equal_candidates() -> None:
    assert MODULE.preferred_entity_index(["button.first", "button.second"]) == 0


def test_preferred_entity_rejects_empty_candidate_list() -> None:
    with pytest.raises(ValueError, match="At least one entity ID"):
        MODULE.preferred_entity_index([])

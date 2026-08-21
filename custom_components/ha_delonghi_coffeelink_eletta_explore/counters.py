"""Pure counter-value parsing for DeLonghi datapoints.

Kept free of Home Assistant imports so the parsing logic is unit-testable on its
own (see tests/test_counters.py). Two value shapes exist across models:

- PrimaDonna Soul (DL-millcore): counters are plain integers (e.g. ``314``).
- Eletta Explore (DL-striker-cb): some counters are published as a JSON object
  of per-recipe sub-counts (e.g. ``{"espresso": 12, "coffee": 3}``), which left
  the sensor ``unknown`` before #7. For those, the sensor state is the sum of
  the integer sub-values and the raw object is exposed as attributes.
"""
from __future__ import annotations

import json
from collections.abc import Collection
from contextlib import suppress
from typing import Any


def _looks_like_json_object(val_str: str) -> bool:
    return val_str.startswith("{") and val_str.endswith("}")


def parse_counter_value(val: Any) -> int | None:
    """Return the integer state for a counter datapoint value, or ``None``.

    Plain integers pass through. A JSON object is summed over its integer
    sub-values. Anything else (booleans, unparseable strings, malformed JSON)
    yields ``None`` so the sensor stays unknown rather than guessing.
    """
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    val_str = str(val).strip()
    if _looks_like_json_object(val_str):
        try:
            data = json.loads(val_str)
        except json.JSONDecodeError:
            return None
        total = 0
        for sub in data.values():
            with suppress(ValueError, TypeError):
                total += int(sub)
        return total
    try:
        return int(val_str)
    except (TypeError, ValueError):
        return None


def parse_water_volume_liters(val: Any) -> float | None:
    """Convert a legacy/filter water-volume counter from millilitres to litres.

    This conversion is intentionally kept separate from
    :func:`parse_total_water_volume_liters`.  Coffee Link 4.9.6 proves the
    half-millilitre scale only for ``d553_water_tot_qty``; applying it to the
    filter counter without equivalent evidence would silently change an
    unrelated sensor.
    """
    milliliters = parse_counter_value(val)
    if milliliters is None:
        return None
    return round(milliliters / 1000, 3)


def parse_total_water_volume_liters(val: Any) -> float | None:
    """Convert ``d553_water_tot_qty`` half-millilitre ticks to litres.

    The Eletta Coffee Link statistics screen calculates this property as
    ``raw / 2000`` (the app truncates the displayed number to whole litres).
    Home Assistant retains the available three-decimal precision.
    """
    half_milliliter_ticks = parse_counter_value(val)
    if half_milliliter_ticks is None:
        return None
    return round(half_milliliter_ticks / 2000, 3)


def parse_percentage_value(val: Any) -> int | None:
    """Return an integer percentage in the inclusive 0-100 range."""
    percentage = parse_counter_value(val)
    if percentage is None or not 0 <= percentage <= 100:
        return None
    return percentage


def parse_remaining_percentage(val: Any) -> int | None:
    """Convert a consumed 0-100 percentage to the remaining percentage."""
    consumed = parse_percentage_value(val)
    if consumed is None:
        return None
    return 100 - consumed


def parse_water_hardness_level(val: Any) -> int | None:
    """Convert Eletta's zero-based cloud value to De'Longhi level 1-4.

    The ``d556_water_hardness`` property uses the internal range 0-3, while
    the machine display, Coffee Link and De'Longhi documentation present the
    setting as levels 1-4. Values outside the documented cloud range are not
    guessed and leave the entity unknown.
    """
    cloud_level = parse_counter_value(val)
    if cloud_level is None or not 0 <= cloud_level <= 3:
        return None
    return cloud_level + 1


def counter_breakdown(val: Any) -> dict | None:
    """Return the per-recipe JSON breakdown of a counter value, else ``None``.

    Only JSON-object values (Eletta aggregated counters) have a breakdown; plain
    integers and unparseable values return ``None``.
    """
    if not val or isinstance(val, int | bool):
        return None
    val_str = str(val).strip()
    if _looks_like_json_object(val_str):
        try:
            data = json.loads(val_str)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return None


def counter_breakdown_sum(val: Any, keys: Collection[str]) -> int | None:
    """Return the sum of selected integer fields from a JSON counter.

    The function is deliberately strict about the requested fields: it returns
    ``None`` when the value is not a JSON object or none of the requested keys
    is present. This prevents a derived entity from silently reporting zero on
    a model that publishes a different counter layout.
    """
    data = counter_breakdown(val)
    if data is None:
        return None

    found = False
    total = 0
    for key in keys:
        if key not in data:
            continue
        sub_value = data[key]
        if isinstance(sub_value, bool):
            continue
        try:
            total += int(sub_value)
        except (TypeError, ValueError):
            continue
        found = True
    return total if found else None


def _required_breakdown_sum(
    val: Any, required_key: str, keys: Collection[str]
) -> int | None:
    """Sum JSON fields only when Coffee Link's required discriminator exists."""
    data = counter_breakdown(val)
    if data is None or required_key not in data:
        return None
    required_value = data[required_key]
    if isinstance(required_value, bool):
        return None
    try:
        int(required_value)
    except (TypeError, ValueError):
        return None
    return counter_breakdown_sum(val, keys)


def coffee_link_black_coffee_total(black: Any, iced_counters: Any) -> int | None:
    """Return Coffee Link's black-coffee total for Eletta Explore.

    Coffee Link adds the scalar ``d701_tot_bev_b`` and the optional
    ``tot_bev_b_iced`` field from ``d733_tot_bev_counters``.
    """
    hot_black = parse_counter_value(black)
    if hot_black is None:
        return None
    iced_black = counter_breakdown_sum(iced_counters, ("tot_bev_b_iced",))
    return hot_black + (iced_black or 0)


def coffee_link_hot_milk_total(other_counters: Any) -> int | None:
    """Return Coffee Link's aggregate hot-milk beverage count."""
    return _required_breakdown_sum(
        other_counters,
        "tot_bev_bw",
        ("tot_bev_bw", "tot_bev_w"),
    )


def coffee_link_cold_milk_total(iced_counters: Any) -> int | None:
    """Return Coffee Link's aggregate cold-milk beverage count."""
    return _required_breakdown_sum(
        iced_counters,
        "tot_bev_bw_iced",
        ("tot_bev_bw_iced", "tot_bev_w_iced"),
    )


def coffee_link_mug_total(hot_mug: Any, cold_mug: Any) -> int | None:
    """Return Coffee Link's Mug to Go total (hot plus optional cold)."""
    hot = parse_counter_value(hot_mug)
    if hot is None:
        return None
    cold = parse_counter_value(cold_mug)
    return hot + (cold or 0)


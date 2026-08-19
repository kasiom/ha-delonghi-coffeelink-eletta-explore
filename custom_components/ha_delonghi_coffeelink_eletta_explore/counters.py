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
    """Convert a De'Longhi water-volume counter from millilitres to litres."""
    milliliters = parse_counter_value(val)
    if milliliters is None:
        return None
    return round(milliliters / 1000, 3)


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


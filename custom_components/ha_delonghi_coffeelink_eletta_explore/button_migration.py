"""Stable identity helpers for beverage start buttons."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


def canonical_start_unique_id(dsn: str, beverage_id: int) -> str:
    """Return an immutable unique ID derived from the protocol beverage ID."""
    return f"{dsn}_start_beverage_{beverage_id}"


def start_button_beverage_id(
    unique_id: str,
    dsn: str,
    key_to_id: Mapping[str, int],
) -> int | None:
    """Resolve current and legacy start-button unique IDs to a beverage ID."""
    prefix = f"{dsn}_start_"
    if not unique_id.startswith(prefix):
        return None

    suffix = unique_id.removeprefix(prefix)
    for numeric_prefix in ("beverage_", "recipe_"):
        if suffix.startswith(numeric_prefix):
            value = suffix.removeprefix(numeric_prefix)
            return int(value) if value.isdecimal() else None
    return key_to_id.get(suffix)


def preferred_entity_index(entity_ids: Sequence[str]) -> int:
    """Prefer the established entity ID without HA's duplicate numeric suffix."""
    if not entity_ids:
        raise ValueError("At least one entity ID is required")
    return min(
        range(len(entity_ids)),
        key=lambda index: (bool(re.search(r"_\d+$", entity_ids[index])), index),
    )

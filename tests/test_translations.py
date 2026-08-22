"""Translation consistency tests."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "ha_delonghi_coffeelink_eletta_explore"
PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")
CZECH_DIACRITICS = re.compile(r"[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(value: dict[str, Any], prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, child in value.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(child, str):
            result[full_key] = child
        else:
            result.update(_flatten(child, full_key))
    return result


def _literal_assignment(name: str) -> tuple[str, ...]:
    tree = ast.parse((COMPONENT / "sensor.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    return tuple(value)
    raise AssertionError(f"Assignment {name} was not found")


def _literal_dict_assignment(name: str) -> dict[Any, Any]:
    tree = ast.parse((COMPONENT / "const.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    return dict(value)
    raise AssertionError(f"Assignment {name} was not found")


def _literal_mapping(path: Path, name: str) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return dict(ast.literal_eval(node.value))
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return dict(ast.literal_eval(node.value))
    raise AssertionError(f"Assignment {name} was not found in {path.name}")


def _literal_value(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return ast.literal_eval(node.value)
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Assignment {name} was not found in {path.name}")


def test_translation_files_have_identical_leaf_keys_and_placeholders() -> None:
    english_json = _load(COMPONENT / "translations" / "en.json")
    english = _flatten(english_json)
    czech = _flatten(_load(COMPONENT / "translations" / "cs.json"))

    assert not (COMPONENT / "strings.json").exists()
    assert english.keys() == czech.keys()
    for key, english_text in english.items():
        assert set(PLACEHOLDER_PATTERN.findall(english_text)) == set(PLACEHOLDER_PATTERN.findall(czech[key])), key


def test_runtime_exception_keys_and_fallbacks_match_translations() -> None:
    messages = _literal_mapping(COMPONENT / "errors.py", "ERROR_MESSAGES")
    english = _load(COMPONENT / "translations" / "en.json")["exceptions"]
    czech = _load(COMPONENT / "translations" / "cs.json")["exceptions"]

    assert set(english) == set(czech) == set(messages)
    assert {key: item["message"] for key, item in english.items()} == messages


def test_user_visible_exceptions_are_created_only_by_translation_helpers() -> None:
    exception_names = {
        "HomeAssistantError",
        "ServiceValidationError",
        "ConfigEntryAuthFailed",
    }
    violations: list[str] = []
    for path in COMPONENT.glob("*.py"):
        if path.name == "errors.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id in exception_names:
                violations.append(f"{path.name}:{node.lineno}:{node.func.id}")
    assert not violations


def test_python_sources_do_not_embed_czech_user_interface_text() -> None:
    violations: list[str] = []
    for path in COMPONENT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and CZECH_DIACRITICS.search(node.value):
                violations.append(f"{path.name}:{node.lineno}")
    assert not violations


def test_dynamic_recipe_button_has_localized_placeholder_name() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    assert english["entity"]["button"]["start_recipe"]["name"] == ("Recipe {recipe_id}")
    assert czech["entity"]["button"]["start_recipe"]["name"] == ("Recept {recipe_id}")


def test_recipe_diagnostics_button_has_clear_localized_name() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    assert english["entity"]["button"]["dump_recipes"]["name"] == "Log recipe data"
    assert czech["entity"]["button"]["dump_recipes"]["name"] == "Zapsat data receptů"


def test_all_runtime_entity_translation_keys_exist_in_both_languages() -> None:
    const_path = COMPONENT / "const.py"
    counters = _literal_value(const_path, "COUNTER_SENSORS")
    breakdowns = _literal_value(const_path, "BREAKDOWN_COUNTER_SENSORS")
    aggregates = _literal_value(const_path, "COFFEE_LINK_AGGREGATE_SENSORS")
    beverages = _literal_value(const_path, "BEVERAGES")
    eletta_recipes = _literal_value(const_path, "ELETTA_LEARNED_BEVERAGES")

    sensor_keys = {item[1] for item in counters}
    sensor_keys.update(item[1] for item in breakdowns)
    sensor_keys.update(translation_key for definitions in aggregates.values() for _key, translation_key in definitions)
    sensor_keys.update(
        {
            "machine_status",
            "last_command_status",
            "cloud_session_app_id",
            "wifi_signal_strength",
        }
    )
    button_keys = {f"start_{item[1]}" for item in beverages}
    button_keys.update(f"start_{item[0]}" for item in eletta_recipes.values())
    button_keys.update({"start_recipe", "wake", "standby", "stop", "synchronize", "dump_recipes"})
    binary_sensor_keys = {
        "connection_status",
        "water_tank_empty",
        "waste_container_full",
        "decalcification_needed",
        "filter_change_needed",
    }

    for language_path in (
        COMPONENT / "translations" / "en.json",
        COMPONENT / "translations" / "cs.json",
    ):
        entities = _load(language_path)["entity"]
        assert set(entities["sensor"]) == sensor_keys
        assert set(entities["button"]) == button_keys
        assert set(entities["binary_sensor"]) == binary_sensor_keys


def test_all_translated_entities_and_actions_use_icon_translations() -> None:
    """Keep icons centralized and complete for every exposed translation key."""
    icons = _load(COMPONENT / "icons.json")
    entities = _load(COMPONENT / "translations" / "en.json")["entity"]

    assert icons["entity"].keys() == entities.keys()
    for platform, translated_entities in entities.items():
        platform_icons = icons["entity"][platform]
        assert platform_icons.keys() == translated_entities.keys()
        assert all(definition["default"].startswith("mdi:") for definition in platform_icons.values())

    assert icons["services"] == {
        "start_beverage": "mdi:coffee",
        "stop_beverage": "mdi:stop",
        "send_raw_command": "mdi:code-braces",
    }


def test_platforms_declare_parallel_updates_and_do_not_set_runtime_icons() -> None:
    """Follow coordinator and icon-translation platform best practices."""
    for platform in ("sensor.py", "binary_sensor.py", "button.py"):
        path = COMPONENT / platform
        assert _literal_value(path, "PARALLEL_UPDATES") == 0
        assert "_attr_icon" not in path.read_text(encoding="utf-8")


def test_diagnostic_enum_options_have_english_and_czech_translations() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    checks = {
        "cloud_session_app_id": _literal_assignment("CLOUD_SESSION_HOLDER_OPTIONS"),
        "last_command_status": _literal_assignment("LAST_COMMAND_RESULT_OPTIONS"),
    }
    for translation_key, options in checks.items():
        for translations in (english, czech):
            states = translations["entity"]["sensor"][translation_key]["state"]
            assert set(states) == set(options)


def test_machine_status_enum_states_remain_complete() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    machine_options = set(_literal_dict_assignment("MACHINE_STATUS").values())
    machine_options.add("preparing_beverage")
    for translations in (english, czech):
        sensors = translations["entity"]["sensor"]
        assert set(sensors["machine_status"]["state"]) == machine_options


def test_machine_status_nomenclature_matches_english_and_czech() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    expected_english = "Preparing beverage"
    states = english["entity"]["sensor"]["machine_status"]["state"]
    assert states["preparing_beverage"] == expected_english
    assert "grinding" not in states
    assert "brewing" not in states

    czech_states = czech["entity"]["sensor"]["machine_status"]["state"]
    assert czech_states["preparing_beverage"] == "Připravuje nápoj"
    assert "grinding" not in czech_states
    assert "brewing" not in czech_states


def test_problem_binary_sensor_names_are_neutral_in_czech() -> None:
    czech = _load(COMPONENT / "translations" / "cs.json")
    names = czech["entity"]["binary_sensor"]

    assert names["water_tank_empty"]["name"] == "Nádržka na vodu"
    assert names["waste_container_full"]["name"] == "Zásobník na sedlinu"
    assert names["decalcification_needed"]["name"] == "Odvápnění"
    assert names["filter_change_needed"]["name"] == "Vodní filtr"


def test_descale_remaining_name_describes_inverted_percentage() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    assert english["entity"]["sensor"]["descale_limit_usage"]["name"] == ("Remaining until descale")
    assert czech["entity"]["sensor"]["descale_limit_usage"]["name"] == ("Do odvápnění zbývá")


def test_eletta_counter_scopes_are_clear_in_english_and_czech() -> None:
    english = _load(COMPONENT / "translations" / "en.json")["entity"]["sensor"]
    czech = _load(COMPONENT / "translations" / "cs.json")["entity"]["sensor"]

    assert english["total_black_coffee_beverages"]["name"] == ("Total black coffee beverages")
    assert english["total_cold_brew_bev"]["name"] == ("Total cold coffee beverages")
    assert czech["total_black_coffee_beverages"]["name"] == ("Počet černých káv celkem")
    assert czech["total_espresso"]["name"] == "Počet Espresso celkem"
    assert czech["total_espresso_alt"]["name"] == "Počet Espresso"
    assert czech["total_over_ice_espresso"]["name"] == ("Počet Over Ice Espresso")
    assert czech["total_cold_brew"]["name"] == "Počet Cold Brew celkem"
    assert czech["total_cold_brew_bev"]["name"] == ("Počet studených káv celkem")


def test_beverage_sensor_names_correspond_to_czech_buttons() -> None:
    czech = _load(COMPONENT / "translations" / "cs.json")["entity"]
    sensors = czech["sensor"]
    buttons = czech["button"]

    exact_recipe_names = {
        "total_espresso_alt": "start_espresso",
        "total_long_coffee": "start_long_coffee",
        "total_doppio": "start_doppio",
        "total_americano": "start_americano",
        "total_cappuccino": "start_cappuccino",
        "total_latte_macchiato": "start_latte_macchiato",
        "total_caffelatte": "start_caffelatte",
        "total_flat_white": "start_flat_white",
        "total_espresso_macchiato": "start_espresso_macchiato",
        "total_cappuccino_doppio": "start_cappuccino_doppio",
        "total_cappuccino_reverse": "start_cappuccino_reverse",
        "total_brew_over_ice": "start_brew_over_ice",
        "total_mug_bev": "start_mug_to_go",
    }
    for sensor_key, button_key in exact_recipe_names.items():
        assert sensors[sensor_key]["name"] == f"Počet {buttons[button_key]['name']}"

    # Generic Czech nouns are intentionally inflected instead of copied.
    inflected_names = {
        "total_coffee": ("Počet káv", "start_coffee", "Káva"),
        "total_hot_milk": (
            "Počet výdejů horkého mléka",
            "start_hot_milk",
            "Horké mléko",
        ),
        "total_hot_water": (
            "Počet výdejů horké vody",
            "start_hot_water",
            "Horká voda",
        ),
        "total_tea": ("Počet čajů", "start_tea", "Čaj"),
        "total_coffee_pot": (
            "Počet konvic kávy",
            "start_coffee_pot",
            "Konvice kávy",
        ),
    }
    for sensor_key, (sensor_name, button_key, button_name) in inflected_names.items():
        assert sensors[sensor_key]["name"] == sensor_name
        assert buttons[button_key]["name"] == button_name

    assert sensors["total_mug_hot"]["name"] == ("Počet horkých nápojů Mug to Go")
    assert sensors["total_mug_cold"]["name"] == ("Počet studených nápojů Mug to Go")
    assert sensors["total_mug_iced_bev"]["name"] == ("Počet ledových nápojů Mug to Go")


def test_cloud_entities_are_distinct_and_session_holder_is_neutral() -> None:
    english = _load(COMPONENT / "translations" / "en.json")["entity"]
    czech = _load(COMPONENT / "translations" / "cs.json")["entity"]
    assert czech["binary_sensor"]["connection_status"]["name"] == ("Připojení ke cloudu")

    czech_sensor = czech["sensor"]["cloud_session_app_id"]
    english_sensor = english["sensor"]["cloud_session_app_id"]

    assert czech_sensor["name"] == "Relace Coffee Link"
    assert czech_sensor["state"] == {
        "unknown": "Neznámá",
        "free": "Volná",
        "ha": "Aktivní",
        "foreign": "Jiná aplikace",
    }
    assert english_sensor["state"] == {
        "unknown": "Unknown",
        "free": "Free",
        # Keep the internal key for compatibility. The device-specific ID is
        # shared with Coffee Link, so it cannot identify Home Assistant alone.
        "ha": "Active",
        "foreign": "Another application",
    }


def test_last_command_status_is_precise_in_both_languages() -> None:
    english = _load(COMPONENT / "translations" / "en.json")
    czech = _load(COMPONENT / "translations" / "cs.json")

    english_sensor = english["entity"]["sensor"]["last_command_status"]
    czech_sensor = czech["entity"]["sensor"]["last_command_status"]

    assert english_sensor["name"] == "Last command status"
    assert czech_sensor["name"] == "Stav posledního příkazu"
    assert "idle" not in english_sensor["state"]
    assert "idle" not in czech_sensor["state"]

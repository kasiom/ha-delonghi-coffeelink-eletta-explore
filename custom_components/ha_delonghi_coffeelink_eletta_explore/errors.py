"""Localized user-visible exceptions for De'Longhi Coffee Link."""

from __future__ import annotations

from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)

from .const import DOMAIN

ERROR_MESSAGES: dict[str, str] = {
    "target_exactly_one": "Select exactly one De'Longhi coffee maker.",
    "target_missing": "The selected Home Assistant device no longer exists.",
    "target_not_loaded": "The selected target does not resolve to exactly one loaded De'Longhi coffee maker.",
    "credentials_invalid": "Coffee Link credentials are no longer valid.",
    "coffee_maker_not_connected": "The coffee maker is not connected to the cloud.",
    "state_unverified": "The coffee maker state could not be verified; refresh its data before starting a beverage.",
    "not_ready": "The coffee maker is not ready to start a beverage.",
    "already_preparing": "The coffee maker is already preparing a beverage.",
    "water_tank_empty": "The water tank is empty.",
    "grounds_container_full": "The grounds container is full.",
    "water_tank_missing": "The water tank is missing.",
    "grounds_container_missing": "The grounds container is missing.",
    "command_not_acknowledged": "The command was sent, but the coffee maker did not acknowledge it in time.",
    "command_rejected_by_device": "The coffee machine explicitly rejected the command.",
    "cloud_session_in_use": (
        "Another application is using the Coffee Link cloud session; close it or wait for the session to be released."
    ),
    "cached_session_unverified": "The cached Coffee Link cloud session could not be verified.",
    "cloud_session_timeout": "Timed out while acquiring the Coffee Link cloud session.",
    "learned_command_invalid": (
        "The learned beverage command failed its integrity check; prepare it once in the official Coffee Link app to re-learn it."
    ),
    "command_not_learned": "This command is unavailable until its frame has been learned from the official Coffee Link app.",
    "active_beverage_unknown": "The active beverage is unknown; start a drink before using Stop.",
    "command_in_progress": "Another coffee maker command is still in progress; try again shortly.",
    "cloud_command_failed": "The Coffee Link cloud command could not be completed.",
    "command_failed": "The coffee maker command failed before completion.",
    "wake_not_learned": "Wake is unavailable until its frame has been learned from the official Coffee Link app.",
    "standby_not_learned": "Standby is unavailable until a device signature has been learned.",
    "raw_command_invalid": "The raw command failed its protocol, device-signature, or safety validation.",
}


def translated_error(key: str) -> HomeAssistantError:
    """Create a localized runtime error with an English fallback."""
    return HomeAssistantError(
        ERROR_MESSAGES[key],
        translation_domain=DOMAIN,
        translation_key=key,
    )


def translated_service_error(key: str) -> ServiceValidationError:
    """Create a localized service-validation error."""
    return ServiceValidationError(
        ERROR_MESSAGES[key],
        translation_domain=DOMAIN,
        translation_key=key,
    )


def translated_auth_error() -> ConfigEntryAuthFailed:
    """Create the localized reauthentication signal."""
    return ConfigEntryAuthFailed(
        ERROR_MESSAGES["credentials_invalid"],
        translation_domain=DOMAIN,
        translation_key="credentials_invalid",
    )

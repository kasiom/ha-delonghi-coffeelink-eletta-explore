# Installation and updates

## Requirements

- Home Assistant 2026.8.2 or newer.
- A De'Longhi Coffee Link account with the coffee maker already registered.
- Internet access from Home Assistant to the De'Longhi/Gigya and Ayla services.
- A current Home Assistant backup before installation or a major update.

## HACS installation (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kasiom&repository=ha-delonghi-coffeelink-eletta-explore&category=integration)

Until this integration is accepted into the default HACS catalog:

The [default-catalog request](https://github.com/hacs/default/pull/10136) is in
the HACS review queue. The custom-repository method below remains fully
supported while that review is pending.

1. Open HACS and choose **Custom repositories**.
2. Add
   `https://github.com/kasiom/ha-delonghi-coffeelink-eletta-explore`
   with category **Integration**. The badge above opens the same repository
   directly when My Home Assistant is configured.
3. Select **De'Longhi Coffee Link – Eletta Explore** and install the latest
   stable release.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration**, search for the
   integration and enter the account used by the official Coffee Link app.

## Manual installation

1. Download the source archive attached to the latest GitHub release.
2. Copy the complete
   `custom_components/ha_delonghi_coffeelink_eletta_explore` directory to
   `/config/custom_components/`.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **De'Longhi Coffee Link – Eletta Explore** and enter the Coffee
   Link account credentials.

Never copy the repository root into `custom_components` and never mix files from
different releases.

A successful setup creates one Home Assistant device for each supported coffee
maker returned by the account. The account device list is checked every ten
minutes; membership changes trigger a controlled integration reload and stale
registry records are removed.

## Updates

### HACS

Review the [changelog](../CHANGELOG.md), install the offered version in HACS and
restart Home Assistant.

### Manual

1. Create a Home Assistant backup.
2. Replace the integration directory with the complete directory from the new
   version; do not mix files from different releases.
3. Restart Home Assistant.
4. Confirm the loaded version in **Settings → Devices & services** and check the
   Home Assistant log for setup errors.

Learned recipe frames are stored in Home Assistant's Store and normally survive an
integration update. Do not modify the integration directory or Store files while
Home Assistant is writing data.

## Removal

1. Remove the config entry from **Settings → Devices & services**.
2. Restart Home Assistant.
3. Remove the custom component through HACS, when applicable, or delete only its
   `custom_components/ha_delonghi_coffeelink_eletta_explore` directory.

Removing the config entry removes its stored Coffee Link credentials. Recorder
history and long-term statistics follow the user's Home Assistant retention
policy and may remain until purged.

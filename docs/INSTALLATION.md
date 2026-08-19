# Installation and updates

## Requirements

- Home Assistant 2026.8.2 or newer.
- A De'Longhi Coffee Link account with the coffee maker already registered.
- Internet access from Home Assistant to the De'Longhi/Gigya and Ayla services.
- A current Home Assistant backup before installation or a major update.

## Private repository stage: manual installation

HACS custom repositories must be publicly accessible. While this repository is
private, download it using an authorized GitHub account and install it manually:

1. Copy the complete
   `custom_components/ha_delonghi_coffeelink_eletta_explore` directory to
   `/config/custom_components/`.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **De'Longhi Coffee Link – Eletta Explore**.
5. Enter the account used by the official Coffee Link app.

A successful setup creates one Home Assistant device for each supported coffee
maker returned by the account. The account device list is checked every ten
minutes; membership changes trigger a controlled integration reload and stale
registry records are removed.

## HACS installation after publication

After the repository becomes public:

1. Open HACS and select **Custom repositories**.
2. Add
   `https://github.com/kasiom/ha-delonghi-coffeelink-eletta-explore`
   as an **Integration**.
3. Install **De'Longhi Coffee Link – Eletta Explore**.
4. Restart Home Assistant and add the integration through the UI.

The HACS validation job is deliberately skipped while the repository is private
and activates automatically when it becomes public.

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

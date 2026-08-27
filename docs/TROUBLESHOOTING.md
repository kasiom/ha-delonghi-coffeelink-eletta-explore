# Troubleshooting

## Integration cannot connect

- Confirm that the official Coffee Link app works with the same account.
- Check Home Assistant internet access and vendor-cloud availability before
  changing credentials.
- A rejected Ayla session is renewed automatically through its in-memory refresh
  token or, if needed, one silent login with the saved credentials. The refused
  cloud request is replayed once.
- Temporary timeouts, rate limits, token-exchange failures and server errors do
  not start reauthentication. Home Assistant asks for the password only when
  Gigya explicitly rejects the saved account credentials.

## Beverage button is missing

- Prepare the recipe once from Coffee Link while Home Assistant is running.
- Wait for one DSS update; when the stream is unavailable, wait for at least one
  30-second polling interval.
- Reload the integration if dynamic entity discovery did not add the button.
- Review the log for a rejected checksum, recipe identity, action or device
  signature.
- Open **Settings → System → Repairs**. If Home Assistant discarded a previously
  saved command, follow the translated relearning instructions there.

## Coffee maker added to the account is missing

Account membership is refreshed every ten minutes. Keep Home Assistant running
and wait for the integration to reload automatically. If the machine still does
not appear, confirm that Coffee Link lists it under the same account and reload
the config entry once. Removing a machine from Coffee Link also removes its stale
Home Assistant entities and device record after reconciliation.

## Button is unavailable

An unavailable button normally means the command is not safely usable:

- no validated recipe or device signature has been learned;
- Stop has no known active beverage or no matching learned Stop frame;
- the cloud coordinator is unavailable;
- another application holds the Coffee Link session.

Do not bypass this state with the raw-command action.

## Coffee Link reports another active session

Close Coffee Link completely and wait for the machine's session to become free.
The **Coffee Link Session** entity distinguishes a free session, an active shared-ID
session and a different application's session. An active shared-ID session can
belong to either Home Assistant or the official app; the cloud value cannot identify
which one. Home Assistant will not take over a foreign active session.

## Counters look stale

Temporarily enable the disabled diagnostic entity **Refresh cloud data**, press
it, wait at least ten seconds and refresh the entity. The button requests a fresh
cloud session and property read, but the machine or vendor cloud can still publish
counters later. Keep the button disabled when it is not needed.

## Grounds fill is 100% while the grounds container is OK

These entities report separate vendor signals. **Grounds container fill** mirrors
a calculated cloud maintenance percentage; it is an estimate, not a physical
level measurement. **Grounds container** reports the machine's current full or
missing alarm and is the authoritative entity for notifications, safety checks
and automations. The percentage and alarm can therefore temporarily disagree.

The machine recognizes an emptied container only while it is awake. To reset its
grounds counter reliably:

1. wake the machine and wait until it is ready;
2. remove the complete drip tray and grounds container for several seconds;
3. empty and clean the grounds container, then reinsert both parts;
4. wait for the next cloud update, or temporarily use **Refresh cloud data**.

Do not remove the tray while a beverage or rinse is running. Emptying the
container in standby or while the machine is off may not reset the counter. See
[De'Longhi's official reset guidance](https://www.delonghi.com/en-us/faqs/The-grounds-container-light-is-on-but-my-ground-container-is-not-full./a/16760).

## Machine status appears wrong

Capture sanitized integration diagnostics while the wrong state is visible.
Include what the machine was physically doing. Do not infer the beverage from the
MonitorV2 step value: the same step occurs in unrelated operations.

## What to attach to an issue

Attach the integration's downloadable diagnostics, integration and Home Assistant
versions, exact model and region, reproduction steps and the smallest relevant log
excerpt. Remove e-mail addresses, credentials, DSNs, serial numbers, tokens and
raw command frames. Never publish a complete Home Assistant log.

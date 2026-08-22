# Privacy and cloud data

The integration communicates with the De'Longhi/Gigya and Ayla endpoints used by
Coffee Link. It combines an Ayla DSS cloud stream with periodic reconciliation
polls and a 30-second polling fallback. It does not communicate directly with the
coffee maker over the local network.

## Stored locally by Home Assistant

- Coffee Link e-mail and password in the Home Assistant config entry.
- Learned recipe frames in Home Assistant Store.
- Entity states and statistics according to Recorder configuration.

## Sent to vendor services

- Account credentials during Gigya authentication.
- Authentication/session tokens during subsequent cloud calls.
- Device property reads and explicitly requested commands.
- Creation of a fresh integration-owned Ayla DSS subscription for each
  account-wide cloud-stream connection, matching Coffee Link's lifecycle.

## Diagnostics

Downloadable diagnostics exclude the account e-mail and password, access tokens,
DSN, raw command/response values and app identifier. Property names and sanitized
operational metadata remain so maintainers can diagnose compatibility.
The DSS stream key and Wi-Fi network name are never stored, logged or included in
diagnostics. Connection diagnostics contain only the connectivity type and an
optional RSSI value.

## Logs

Routine cloud logs use operation names and a short one-way device reference;
they do not include request URLs, DSNs, upstream response bodies or network-error
text. Retry details are emitted at debug level. The disabled-by-default **Log
recipe data** diagnostic button is an explicit exception: when a user
presses it, recipe data reported by the machine is written to the local Home
Assistant log for protocol troubleshooting. Review and sanitize that output
before sharing it.

This project does not operate an independent server and does not receive user
telemetry. GitHub and HACS have their own privacy terms when those services are
used.

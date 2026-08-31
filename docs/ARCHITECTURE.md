# Architecture and provenance

## Data path

Home Assistant authenticates through De'Longhi's Gigya identity service, exchanges
the resulting JWT for an Ayla token and performs one initial read of the coffee
maker's Ayla properties. One account-wide Ayla DSS WebSocket then distributes
datapoint and acknowledgement events to the coordinator for each discovered
machine. A five-minute full poll reconciles state while the stream is healthy. Any
stream setup, transport or idle-timeout failure immediately restores the normal
30-second polling interval and reconnects with bounded exponential backoff.

Events are ordered independently by event type and property. Duplicate or older
events are discarded, and an older poll cannot overwrite a newer timestamped push
value. MonitorV2 frames additionally use the same signed ordering token found in
Coffee Link. Each machine coordinator remains responsible for monitor decoding,
recipe learning and serialized command execution.

## Command safety

Eletta recipe frames are learned from traffic produced by Coffee Link. Before a
frame is stored or replayed, the integration checks Base64 structure, protocol
family, internal length, CRC, beverage identity, logical action and the
device-specific signature. The timestamp is refreshed without modifying the
checksummed recipe section.

Commands are serialized, bounded by timeouts and preceded by machine-state checks.
For an ACK-enabled property, the datapoint identifier returned by a command is
matched to its exact DSS device acknowledgement. Eletta's command property is
not ACK-enabled, so ordered DSS machine-state changes provide the confirmation
used by Coffee Link. A timeout triggers one authoritative reconciliation; when
the stream is unavailable, the bounded polling confirmation path remains in
place. The push channel is therefore an improvement rather than a new single
point of failure.
When Ayla rejects an access token, one account-wide authentication lock
serializes its renewal. The client first uses the in-memory refresh token, falls
back to one full login when that token has been revoked and replays the refused
request exactly once. Temporary authentication infrastructure failures, failed
token exchanges and persistent authorization errors remain availability errors;
only a direct Gigya rejection of the saved password starts Home Assistant
reauthentication.

## Provenance and acknowledgements

The project contains substantially modified MIT-licensed work originally
published by Guillaume de Laroque (`actabi/delonghi_coffeelink`); the copyright
notice is retained in `LICENSE`.

Protocol understanding was informed by public community research, captured
Coffee Link traffic and implementations including MattG-K's DlghIoT research.
Later public work such as `sk7n4k3d/delonghi-ha` documents recipe-to-command
conversion and broader model coverage. These references do not create a runtime
dependency or endorsement.

The application-level Gigya/Ayla identifiers in the source originate from the
official Coffee Link application and identify that application, not an individual
user. The cloud protocol remains proprietary and unsupported for third-party use.

# Architecture and provenance

## Data path

Home Assistant authenticates through De'Longhi's Gigya identity service, exchanges
the resulting JWT for an Ayla token and polls the coffee maker's Ayla properties.
Each discovered machine has a coordinator responsible for cloud state, monitor
decoding, recipe learning and serialized command execution.

## Command safety

Eletta recipe frames are learned from traffic produced by Coffee Link. Before a
frame is stored or replayed, the integration checks Base64 structure, protocol
family, internal length, CRC, beverage identity, logical action and the
device-specific signature. The timestamp is refreshed without modifying the
checksummed recipe section.

Commands are serialized, bounded by timeouts and preceded by machine-state checks.
Temporary authentication infrastructure failures remain availability errors;
only an actual credential rejection starts Home Assistant reauthentication.

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

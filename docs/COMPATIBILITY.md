# Compatibility and known limitations

## Support matrix

| Model/profile | Cloud channel | Status |
|---|---|---|
| Eletta Explore ECAM450.65.G (`DL-striker-cb`) | EU Coffee Link/Ayla | Confirmed development and live-test target |
| PrimaDonna Soul (`DL-millcore`) | Coffee Link/Ayla | Experimental; retained profile, incomplete physical acceptance |
| Other models | Unknown/model-dependent | Unsupported unless validated with sanitized diagnostics and physical tests |

The 1.2.x line is tested against the actual Home Assistant 2026.8.2 runtime
interfaces. Version 1.2.0 completed deployment, clean-restart and supervised
physical acceptance on the Eletta Explore listed above. Version 1.2.1 changes
distribution metadata and documentation without changing beverage-command or
machine-state behavior; it has since been installed through HACS and verified to
load on the same target Home Assistant. Newer Home Assistant versions are
expected to work, but vendor and Home Assistant changes require continuing
validation.

Local beta 1.3.0-beta.4 supersedes beta.3 and has completed automated verification,
a backed-up live deployment, Home Assistant configuration validation, a clean
restart and read-only acceptance on the same Eletta Explore. The Ayla DSS stream
was active, received three real events during a statistics synchronization and
reported no current error. Loaded English and Czech resources were complete, all
maintenance sensors settled to available, and the machine remained in standby.
Its aggregate statistics matched Coffee Link (639 black coffees, 308 milk drinks,
10 cold milk drinks and 16 Mug to Go), while the corrected water total reported
209.925 L.

Beta.4 preserves the verified Eletta formulas and adds the legacy Coffee Link
formula used by the PrimaDonna Soul profile: `d700` is black coffee and
`d701 + d703` is the milk-beverage summary. It no longer labels `d703` as water.
Unknown OEM models expose only unambiguous direct counters until a model-specific
profile is supported. Per-recipe counters remain opt-in for newly registered
entities; existing registry choices are preserved. The beta remains local and
unpublished. Beverage commands and their exact live DSS acknowledgements have not
yet been physically repeated on beta.4.

## Verified Eletta behavior

- Account setup, reauthentication, hybrid DSS/polling and cloud-outage recovery
  logic.
- Machine, counter and maintenance-state parsing.
- Dynamic recipe learning and stable button identity.
- Wake and standby transitions.
- Cold Brew start and safe Stop on the physical machine.
- Coffee Link session ownership and command acknowledgement handling.
- English/Czech translation-key and placeholder parity.

Wake, standby and Cold Brew Start/Stop were physically repeated after deploying
1.2.0. Last Command Status recorded the expected transaction transitions and the
machine returned to standby. Other beverage recipes have not all completed the
same supervised physical matrix.

## Known limitations

- The vendor provides no public supported API for this integration.
- Operation requires internet access and availability of the vendor cloud.
- Vendor authentication, cloud-property or mobile-app changes may require an
  integration update.
- Eletta recipe controls must normally be observed once in Coffee Link.
- While DSS is unavailable, multiple app actions between two 30-second fallback
  polls can cause an intermediate command to be missed.
- Account membership is checked every ten minutes. Adding or removing a coffee
  maker triggers an automatic integration reload; the change is therefore not
  instantaneous.
- The integration cannot verify cup placement or every accessory condition.
- A command accepted by the cloud can be acknowledged later than the local timeout.
  Stop remains available when the property write is known to have succeeded.
- PrimaDonna Soul and unknown models must not be described as fully supported
  without model-specific evidence.

Compatibility reports should include the commercial model, internal OEM model,
cloud region, Home Assistant and integration versions, exact steps and sanitized
integration diagnostics.

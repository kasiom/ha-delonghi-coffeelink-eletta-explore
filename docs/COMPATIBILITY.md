# Compatibility and known limitations

## Support matrix

| Model/profile | Cloud channel | Status |
|---|---|---|
| Eletta Explore ECAM450.65.G (`DL-striker-cb`) | EU Coffee Link/Ayla | Confirmed development and live-test target |
| PrimaDonna Soul (`DL-millcore`) | Coffee Link/Ayla | Experimental; retained profile, incomplete physical acceptance |
| Other models | Unknown/model-dependent | Unsupported unless validated with sanitized diagnostics and physical tests |

The 1.2.0 release candidate is tested against the actual Home Assistant 2026.8.2
runtime interfaces. Physical acceptance evidence comes from the 1.1.x cycle on
the machine listed above; the 1.2.0 candidate still requires final deployment
acceptance before release. Newer Home Assistant versions are expected to work,
but vendor and Home Assistant changes require continuing validation.

## Verified Eletta behavior

- Account setup, reauthentication, polling and cloud-outage recovery logic.
- Machine, counter and maintenance-state parsing.
- Dynamic recipe learning and stable button identity.
- Wake and standby transitions.
- Cold Brew start and safe Stop on the physical machine.
- Coffee Link session ownership and command acknowledgement handling.
- English/Czech translation-key and placeholder parity.

Wake, standby and Cold Brew were physically accepted during the 1.1.x test cycle.
Release 1.1.26 was subsequently deployed cleanly. The 1.2.0 candidate has full
automated regression coverage and real-HA interface tests but has not yet repeated
the complete physical acceptance pass. Other beverage recipes have not all
completed the same physical matrix.

## Known limitations

- The vendor provides no public supported API for this integration.
- Operation requires internet access and availability of the vendor cloud.
- Vendor authentication, cloud-property or mobile-app changes may require an
  integration update.
- Eletta recipe controls must normally be observed once in Coffee Link.
- Multiple app actions between two 30-second polls can cause an intermediate
  command to be missed.
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

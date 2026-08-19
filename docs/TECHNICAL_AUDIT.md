# Technical audit

Audit date: 2026-08-19

Publication candidate: 1.2.1

## Verdict

The 1.2.1 publication candidate is internally consistent and unusually well tested
for an unofficial reverse-engineered appliance integration. It combines validated
learn-and-replay beverage commands, serialized cloud sessions, command
acknowledgement, MonitorV2 decoding, dynamic entity discovery, reauthentication
and privacy-safe diagnostics. Version 1.2.0 is deployed on the target Home
Assistant and has passed a clean restart plus a supervised Wake, Cold Brew
Start/Stop and Standby cycle. Version 1.2.1 retains that runtime behavior and
adds public-distribution documentation, current custom-integration localization
packaging and automatic validation on the GitHub `public` event.

The isolated suite covers every executable line and branch in all 17 Python
modules. A second suite loads the integration through actual Home Assistant
2026.8.2 interfaces. These results establish strong software confidence, but
they do not prove every vendor-cloud response, model or physical beverage path.
The confirmed support statement therefore remains deliberately limited to the
tested Eletta Explore model and documented acceptance evidence.

## Audited environment

- Source publication candidate: 1.2.1; deployed live acceptance baseline: 1.2.0.
- Home Assistant: 2026.8.2.
- Python: 3.14.6.
- Home Assistant OS: 18.2.
- Physical device: De'Longhi Eletta Explore ECAM450.65.G.
- OEM model/profile: `DL-striker-cb` / `eletta`.
- Cloud region: EU Coffee Link/Ayla.
- Deployment evidence: 1.2.0 passed Home Assistant configuration validation,
  loaded its config entry after restart and produced no relevant post-restart
  errors. All deployed text files were verified against the candidate with
  SHA-256 hashes and the previous component tree was backed up locally.
- Post-restart command state: unknown, by design until Home Assistant issues a
  command.
- Post-restart Coffee Link session: free.

## Standards baseline

The candidate was reviewed against the current Home Assistant
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/),
including typed runtime data, explicit parallel-update policy, icon translations,
dynamic/stale devices and Repairs. The tracked implementation status is in
`custom_components/ha_delonghi_coffeelink_eletta_explore/quality_scale.yaml`.
This is a self-assessment for a custom integration, not an official Home
Assistant quality certification.

Repository layout, manifest metadata, brand assets and release guidance were
checked against the current
[HACS integration publishing requirements](https://www.hacs.xyz/docs/publish/integration/).
Actual public HACS validation remains intentionally gated until the repository is
public. The workflow subscribes to GitHub's `public` event so that HACS,
hassfest and the full test suite start automatically when visibility changes.
Custom runtime localization is supplied completely by `translations/en.json`
and `translations/cs.json`; the Core-only build source `strings.json` is not
shipped.

## Automated verification

| Check | Result |
|---|---|
| Unit and integration-isolation tests | 312 passed |
| Actual Home Assistant runtime tests | 2 passed |
| Python modules measured | 17 |
| Statements | 2,050 / 2,050 |
| Branches | 628 / 628 |
| Line coverage | 100% |
| Branch coverage | 100% |
| Ruff | passed |
| Python compilation | passed |
| English/Czech leaf-key parity | 188 / 188 |
| Translation placeholders | synchronized |
| Home Assistant hassfest | passed |
| Manifest version | 1.2.1 |

Tests use deterministic local doubles and make no calls to a real account or
vendor endpoint. Covered behavior includes authentication refresh and failure
classification, rate limits, retry exhaustion, device/property discovery, config
flows, integration lifecycle, all entity platforms, command construction and
validation, session ownership, acknowledgement, delayed refresh, recipe learning
and persistence, dynamic/stale-device reconciliation, Repairs, diagnostics and
translated error paths. The separate Home Assistant suite verifies the config
flow, config-entry setup/unload, platform forwarding, real registries and
downloadable diagnostics using Home Assistant 2026.8.2 without a vendor request.

The CI coverage threshold is 100%. Any newly introduced untested line or branch
fails validation.

## Physical and live acceptance evidence

| Area | Evidence | Status |
|---|---|---|
| Installation and restart | 1.2.0 loaded cleanly on target HA | verified |
| Read-only polling | cloud data and entities available after restart | verified |
| Wake | 1.2.0 changed standby → waking up → ready | verified on Eletta |
| Standby | 1.2.0 changed ready → standby | verified on Eletta |
| Recipe learning | Espresso, Cappuccino and Cold Brew frames observed | verified |
| Cold Brew start | 1.2.0 entered preparation and enabled context-aware Stop | verified on Eletta |
| Cold Brew Stop | 1.2.0 returned to ready and disabled Stop | verified on Eletta |
| Last Command Status | unknown after restart; app traffic kept separate | verified |
| Coffee Link Session | free after deployment; history retained | verified |
| Other beverage recipes | automated protocol paths only | physical matrix incomplete |
| Foreign-session conflict | deterministic automated coverage | controlled live conflict pending |
| Fault and outage paths | deterministic automated coverage | controlled live faults pending |
| PrimaDonna Soul | profile and automated compatibility paths | experimental |

Wake, Cold Brew Start, Cold Brew Stop and Standby were physically repeated after
deploying 1.2.0. Last Command Status recorded `pending`, `sent` and
`acknowledged` for every operation. Its earlier return to `unknown` followed a
config-entry reload and is the documented runtime-only behavior, while Recorder
retained the transitions. The table does not imply that every beverage was
physically prepared.

## Security and privacy review

- Coffee Link credentials are stored in the Home Assistant config entry and sent
  only to vendor authentication endpoints over HTTPS.
- Authentication tokens, e-mail, password, DSN, serial number, raw property
  values, app identifier and command frames are excluded from downloadable
  diagnostics.
- Learned frames remain in Home Assistant Store and are never intentionally
  emitted in diagnostics.
- Current test fixtures use deterministic synthetic device signatures; the raw
  action schema contains no ready-to-send command example.
- The raw-command action is administrator-only, accepts only beverage and
  wake/standby families, validates structure/CRC and requires the selected
  Eletta machine's learned signature. Raw beverage starts run the same readiness,
  water-tank and grounds-container checks as normal starts.
- Command transactions are serialized; a second overlapping request is rejected.
- A session held by another application is not silently taken over.
- Beverage start is rejected when readiness or supported tank/container safety
  conditions cannot be established.

## Remaining limitations and release gates

1. Full automated coverage cannot validate undocumented vendor semantics or
   physical dispensing safety.
2. Every supported model requires model-specific, reproducible acceptance
   evidence. PrimaDonna Soul remains experimental.
3. Not every Eletta beverage has completed a supervised Start/Stop matrix.
4. The 30-second polling architecture can miss intermediate official-app commands.
5. Account membership is reconciled every ten minutes, not instantly.
6. Cup placement and every accessory condition cannot be detected.
7. HACS distribution requires a public GitHub repository. The public HACS
   validator remains intentionally skipped until the visibility change and is
   automatically triggered by that event.
8. Branch rulesets and public private-vulnerability reporting become available
   after publication on the current GitHub plan and must be enabled immediately
   after the visibility change.
9. The release branch is rooted at a reviewed clean baseline with no legacy
   pull-request refs or tags. The pre-clean recovery bundle was permanently
   removed after repository recreation; only a verified clean 1.2.0 release
   bundle is retained outside the repository.

## Publication activation checklist

Completed before the visibility change:

- verified 1.2.0 deployment, clean restart and supervised Wake, Cold Brew
  Start/Stop and Standby evidence retained outside the repository;
- repository history recreated with only the reviewed clean baseline, current
  release and synthetic protocol fixtures;
- credentials, account/device identifiers, private logs and real command frames
  excluded from Git history, Issues, releases and Actions artifacts;
- public-facing English/Czech installation, security, compatibility and support
  documentation prepared;
- HACS, hassfest and full validation workflows pinned to reviewed commit SHAs and
  configured to run automatically on GitHub's `public` event.

Perform immediately after changing visibility to public:

1. Confirm that HACS validation, hassfest and Validate all pass on `main` without
   ignored checks.
2. Enable GitHub private vulnerability reporting, Dependabot vulnerability
   alerts/security updates and a `main` ruleset that blocks force-push/deletion
   and requires the passing CI checks.
3. Install through HACS as a custom repository on a separate Home Assistant
   instance and verify setup, restart and removal.
4. Create tag and GitHub release `v1.2.1` only after those checks are green.
5. Request HACS default-catalog inclusion only if desired and only after checking
   its current brand and submission requirements; custom-repository installation
   does not depend on that review.

# Technical audit

Audit date: 2026-08-19

Release candidate: 1.2.0

## Verdict

The 1.2.0 release candidate is internally consistent and unusually well tested
for an unofficial reverse-engineered appliance integration. It combines validated
learn-and-replay beverage commands, serialized cloud sessions, command
acknowledgement, MonitorV2 decoding, dynamic entity discovery, reauthentication
and privacy-safe diagnostics. It is not yet declared released. Version 1.2.0 is
deployed on the target Home Assistant and has passed a clean restart plus a
supervised wake/standby cycle; the selected beverage acceptance run remains a
release gate.

The isolated suite covers every executable line and branch in all 17 Python
modules. A second suite loads the integration through actual Home Assistant
2026.8.2 interfaces. These results establish strong software confidence, but
they do not prove every vendor-cloud response, model or physical beverage path.
The confirmed support statement therefore remains deliberately limited to the
tested Eletta Explore model and documented acceptance evidence.

## Audited environment

- Source candidate and deployed live baseline: 1.2.0.
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
Actual public HACS validation remains impossible until the repository is public.

## Automated verification

| Check | Result |
|---|---|
| Unit and integration-isolation tests | 311 passed |
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
| Manifest version | 1.2.0 |

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
| Cold Brew start | command accepted and physical preparation observed | verified |
| Cold Brew Stop | machine returned to ready and Stop availability cleared | verified |
| Last Command Status | unknown after restart; app traffic kept separate | verified |
| Coffee Link Session | free after deployment; history retained | verified |
| Other beverage recipes | automated protocol paths only | physical matrix incomplete |
| Foreign-session conflict | deterministic automated coverage | controlled live conflict pending |
| Fault and outage paths | deterministic automated coverage | controlled live faults pending |
| PrimaDonna Soul | profile and automated compatibility paths | experimental |

Wake and standby were physically repeated after deploying 1.2.0. Last Command
Status recorded `pending`, `sent` and `acknowledged` for both operations; its
later return to `unknown` followed a config-entry reload and is the documented
runtime-only behavior, while Recorder retained the transitions. Cold Brew was
accepted during the earlier 1.1.x cycle and remains to be repeated on 1.2.0.
The table does not imply that every beverage was physically prepared.

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
7. HACS distribution requires a public GitHub repository. While private, the
   integration must be installed manually and the public HACS validator remains
   intentionally skipped.
8. Branch protection and the public private-vulnerability reporting endpoint are
   unavailable for this private repository on the current GitHub plan. These
   repository controls must be enabled or reassessed when publication changes
   their availability.
9. The release branch is rooted at a reviewed 1.2.0 baseline with no parent
   commits or legacy tags. A pre-clean recovery bundle is retained privately
   outside the repository and must never be published.

## Publication checklist

Before changing the repository from private to public:

- keep the verified 1.2.0 deployment and clean restart evidence with the private
  release records;
- repeat a clean manual installation from the candidate source;
- complete the selected supervised beverage acceptance matrix;
- enable private vulnerability reporting and update `SECURITY.md` with the direct
  reporting path;
- enable branch protection with required passing checks, or document the GitHub
  plan limitation if it still applies;
- confirm that no credentials, identifiers or private logs are present in Git
  history, issues, releases or Actions artifacts;
- verify that the remote branch and releases expose only the cleaned 1.2.0
  baseline and its synthetic protocol fixtures;
- make the repository public;
- confirm that HACS validation, hassfest and the 100% test workflow all pass;
- test HACS custom-repository installation on a separate Home Assistant instance;
- only then request inclusion in the HACS default repository, if desired.

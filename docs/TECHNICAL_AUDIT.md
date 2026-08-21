# Technical audit

Audit date: 2026-08-20

Audited release: 1.2.1 stable; 1.3.0-beta.3 local beta addendum

## Verdict

Release 1.2.1 is internally consistent and unusually well tested for an
unofficial reverse-engineered appliance integration. It combines validated
learn-and-replay beverage commands, serialized cloud sessions, command
acknowledgement, MonitorV2 decoding, dynamic entity discovery, reauthentication
and privacy-safe diagnostics. Version 1.2.0 passed a clean restart plus a
supervised Wake, Cold Brew Start/Stop and Standby cycle. Version 1.2.1 retains
those runtime paths, has been published and installed through HACS on the target
Home Assistant, and was verified to load with the coffee maker and cloud
connection available.

Local beta 1.3.0-beta.3 adds an account-wide Ayla DSS stream, automatic polling
fallback, ordered event application, exact datapoint acknowledgements and
privacy-safe connection diagnostics. It creates a fresh short-lived DSS
subscription for every connection, matching Coffee Link 4.9.6. It also reproduces
Coffee Link's Eletta aggregate statistics and corrects the total-water counter's
half-millilitre scale. The beta passed a backed-up deployment and clean restart on
the same Home Assistant; the fresh stream connected without retry and the live
statistics matched Coffee Link. No appliance command was sent during this
read-only beta acceptance, so exact live ACK and physical beverage paths remain
deliberately pending.

The beta isolated suite covers every executable line and branch in all 18 Python
modules. A second suite loads the integration through actual Home Assistant
2026.8.2 interfaces. These results establish strong software confidence, but
they do not prove every vendor-cloud response, model or physical beverage path.
The confirmed support statement therefore remains deliberately limited to the
tested Eletta Explore model and documented acceptance evidence.

## Audited environment

- Published and installed release: 1.2.1; physical command-acceptance baseline:
  1.2.0.
- Locally installed beta: 1.3.0-beta.3 on branch `feature/cloud-dss-hybrid`; not
  pushed to GitHub.
- Home Assistant: 2026.8.2.
- Python: 3.14.6.
- Home Assistant OS: 18.2.
- Physical device: De'Longhi Eletta Explore ECAM450.65.G.
- OEM model/profile: `DL-striker-cb` / `eletta`.
- Cloud region: EU Coffee Link/Ayla.
- Deployment evidence: 1.2.0 passed Home Assistant configuration validation,
  clean restart and supervised command acceptance. Release 1.2.1 was then
  installed through HACS and verified to load its config entry with the coffee
  maker ready, cloud connectivity available and no relevant integration error.
  All deployed text files were verified with SHA-256 hashes and the previous
  component tree was backed up locally.
- Post-restart command state: unknown, by design until Home Assistant issues a
  command.
- Post-restart Coffee Link session: free.

## Standards baseline

The release was reviewed against the current Home Assistant
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/),
including typed runtime data, explicit parallel-update policy, icon translations,
dynamic/stale devices and Repairs. The tracked implementation status is in
`custom_components/ha_delonghi_coffeelink_eletta_explore/quality_scale.yaml`.
This is a self-assessment for a custom integration, not an official Home
Assistant quality certification.

Repository layout, manifest metadata, brand assets and release guidance were
checked against the current
[HACS integration publishing requirements](https://www.hacs.xyz/docs/publish/integration/).
The repository is public. Its release validation completed successfully for
HACS, hassfest and the full test suite. A request for inclusion in the default
HACS catalog is open as
[hacs/default#10136](https://github.com/hacs/default/pull/10136); custom-repository
installation is already available and does not depend on that review.
Custom runtime localization is supplied completely by `translations/en.json`
and `translations/cs.json`; the Core-only build source `strings.json` is not
shipped.

## Automated verification

| Check | Result |
|---|---|
| Unit and integration-isolation tests | 352 passed |
| Actual Home Assistant runtime tests | 2 passed |
| Python modules measured | 18 |
| Statements | 2,547 / 2,547 |
| Branches | 824 / 824 |
| Line coverage | 100% |
| Branch coverage | 100% |
| Ruff | passed |
| Python compilation | passed |
| English/Czech leaf-key parity | 190 / 190 |
| Translation placeholders | synchronized |
| Public HACS repository validation | passed |
| Home Assistant hassfest | passed |
| Manifest version | 1.3.0-beta.3 (local beta) |

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
| Installation and restart | 1.2.0 passed clean restart; 1.2.1 installed through HACS; 1.3.0-beta.3 backed up, installed and loaded locally | verified |
| Hybrid cloud updates | Fresh DSS subscription connected without retry after beta.3 restart; fallback covered deterministically | read-only live + automated |
| Exact DSS command ACK | datapoint matching, rejection and fallback covered deterministically | physical command pending |
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
retained the transitions. Release 1.2.1 does not alter the associated runtime
paths, but the physical cycle was not repeated merely for its documentation and
packaging changes. The table does not imply that every beverage was physically
prepared.

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

## Remaining limitations and distribution status

1. Full automated coverage cannot validate undocumented vendor semantics or
   physical dispensing safety.
2. Every supported model requires model-specific, reproducible acceptance
   evidence. PrimaDonna Soul remains experimental.
3. Not every Eletta beverage has completed a supervised Start/Stop matrix.
4. DSS normally captures intermediate official-app commands immediately. During a
   stream outage, the 30-second polling fallback can still miss an intermediate
   command.
5. Account membership is reconciled every ten minutes, not instantly.
6. Cup placement and every accessory condition cannot be detected.
7. Default-catalog inclusion is pending review in
   [hacs/default#10136](https://github.com/hacs/default/pull/10136). Installation
   as a HACS custom repository and from the GitHub release is already supported.
8. The repository's own HACS and hassfest jobs passed. In the HACS catalog pull
   request, the central hassfest job currently ends with `No integrations found!`
   after the repository is cloned; its HACS-action and repository-format checks
   pass. This external review status should be revisited when HACS re-runs or
   reviews the submission.
9. The release branch is rooted at a reviewed clean baseline with no legacy
   pull-request refs or tags. The pre-clean recovery bundle was permanently
   removed after repository recreation. Published source and fixtures contain
   no known account/device identifiers or captured real command frames.

## Publication status

Completed:

- the repository is public and release `v1.2.1` is published from commit
  `1b13ce9`;
- public HACS repository validation, hassfest, the complete test suite and real
  Home Assistant interface tests passed for the release;
- release 1.2.1 was installed through HACS and verified to load on the target
  Home Assistant;
- private vulnerability reporting and protected `main` branch rules are enabled;
- repository history contains the reviewed clean baseline, current releases and
  synthetic protocol fixtures;
- credentials, account/device identifiers, private logs and real command frames
  are excluded from tracked source, releases and Actions artifacts;
- public English/Czech installation, security, compatibility, provenance and
  support documentation is available;
- the default-catalog request
  [hacs/default#10136](https://github.com/hacs/default/pull/10136) was submitted
  and is in the review queue.

Open follow-up:

1. Monitor the HACS catalog review and respond only when a maintainer requests a
   change or when material new information is required.
2. After catalog acceptance, replace the temporary custom-repository-first
   installation wording with the normal catalog search flow.
3. Never rewrite a published release tag. If a release needs correction, publish
   a new patch version and retain the previous release history.

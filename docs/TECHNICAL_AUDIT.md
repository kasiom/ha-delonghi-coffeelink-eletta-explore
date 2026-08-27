# Technical audit

Audit date: 2026-08-27

Audited release: 1.2.1 stable; 1.3.0-beta.8 prerelease candidate

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

Local beta 1.3.0-beta.4 supersedes beta.3 and is deployed on the target Home
Assistant. It adds explicit statistics families rather than inferring a formula
from whichever raw property happens to exist. The Eletta/Striker Cold Brew profile
retains the live-verified aggregate formulas. The legacy PrimaDonna Soul branch
now follows Coffee Link 4.9.6:
`d700_tot_bev_b` is black coffee and `d701_tot_bev_bw + d703_tot_bev_w` is the
milk-beverage total. Consequently, the former standalone interpretation of d703
as water is removed; physical water volume remains the independently verified
`d553_water_tot_qty / 2000`. Unknown OEM models expose no guessed d700-d703
summary. For newly registered entities, semantic summaries remain enabled while
per-recipe and recipe-group counters are disabled by default; existing registry
choices are unaffected. Its backed-up deployment, configuration check, restart,
read-only statistics synchronization and loaded English/Czech resources passed.
The machine stayed in standby, DSS received three real events, all maintenance
sensors became available and diagnostics reported no current stream error.

Release candidate 1.3.0-beta.5 retains the beta.4 protocol behavior and live
evidence while tightening the public boundary: the vendor LAN address is neither
retained nor exposed, device links cannot disclose it, and account
reconfiguration can change only the password for the existing account. English
entity names now follow sentence case, Czech/English resources remain in parity,
and De'Longhi branding is consistent. It also confirms a pending standby
maintenance snapshot during setup, avoiding five minutes of unavailable
maintenance entities after restart while retaining transient-frame protection.
The isolated suite and three actual Home Assistant runtime tests pass. Beta.5
completed backed-up deployments, configuration validation, clean restarts,
read-only acceptance and a supervised Wake, Cold Brew Start/Stop and Standby
cycle on the target Eletta. Live diagnostics proved that its command property is
not ACK-enabled, matching the absence of datapoint-ACK events; commands were
correctly confirmed from resulting machine state. Beta.5 was not published and
was superseded by beta.6.

Prerelease 1.3.0-beta.6 retains the physically verified protocol and model
semantics while simplifying the runtime and strengthening cloud reliability.
It confirms non-ACK commands directly from ordered DSS state changes, keeps one
authoritative reconciliation after a timeout, shares account-device discovery
through a lock-protected cache, forwards bounded vendor rate-limit delays and
removes duplicate lifecycle work and unused state. The candidate completed a
backed-up deployment, configuration validation, clean restart, read-only cloud
synchronization and a supervised Wake, Cold Brew Start/Stop and Standby cycle.
The stream recovered to `streaming`, received 40 datapoint events through the
physical cycle, the machine returned to standby and the Home Assistant system
log contained no integration error.

Prerelease candidate 1.3.0-beta.7 retains all beta.6 command, protocol and model
paths. It gives the two manual diagnostic buttons concise English/Czech labels,
classifies both as diagnostic and disables them for new registrations. Existing
entity identities and registry choices remain unchanged. The exact candidate was
deployed with backup, hash and configuration validation, loaded without a
relevant integration error and was verified with both diagnostic buttons
disabled. Its public HACS, hassfest, Python 3.14 and actual Home Assistant 2026.8.2
checks pass. No new appliance-command acceptance was required because beta.7 does
not change an appliance-command path; beta.6 remains the physical baseline.

Prerelease candidate 1.3.0-beta.8 retains the beta.7 entity model and appliance
command paths. It renews a server-rejected Ayla access token under one
account-wide lock, using the in-memory refresh token first and one full-login
fallback only when that refresh token has been revoked. The refused request is
replayed exactly once. Only an explicit Gigya rejection of the saved password
starts Home Assistant reauthentication; session expiry, failed token exchanges,
cloud outages and persistent authorization failures remain availability errors.
Its isolated suite, linting, formatting, compilation and focused strict typing
pass locally. Actual-Home-Assistant deployment and public CI remain pending;
beta.7 remains the installed candidate and beta.6 the physical-command baseline.

The beta isolated suite covers every executable line and branch in all 19 Python
modules. A second suite loads the integration through actual Home Assistant
2026.8.2 interfaces. These results establish strong software confidence, but
they do not prove every vendor-cloud response, model or physical beverage path.
The confirmed support statement therefore remains deliberately limited to the
tested Eletta Explore model and documented acceptance evidence.

## Audited environment

- Published and installed release: 1.2.1; physical command-acceptance baseline:
  1.2.0.
- Installed release candidate: 1.3.0-beta.7 from the draft pull-request branch
  `feature/recipe-diagnostics-label`; pushed to GitHub but not released.
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
  component tree was backed up locally. Beta.4 subsequently passed the same
  configuration and backup safeguards, a clean restart, a read-only statistics
  synchronization and privacy-safe diagnostic verification. Beta.5 then passed
  backed-up deployments, configuration checks and clean restarts; all maintenance
  conditions were available immediately, DSS was streaming and no relevant
  integration error was present. A supervised beta.5 cycle then verified Wake,
  Cold Brew Start/Stop, context-aware Stop, friendly command naming and Standby.
  Beta.6 was subsequently deployed with the same backup, hash, configuration
  and clean-restart safeguards. Its read-only synchronization restored DSS
  streaming after restart, and its supervised command cycle completed without
  an integration error before returning the machine to standby. Beta.7 then
  passed the same backed-up deployment and configuration safeguards; both
  manual diagnostic buttons were verified disabled and the integration log
  contained no relevant error.
- Post-restart command state: unknown, by design until Home Assistant issues a
  command.
- Coffee Link session behavior: free after deployment and the backward-compatible
  internal `ha` state after the explicit Home Assistant read-only statistics
  synchronization. The visible state is the neutral **Active**, because
  Coffee Link can use the same machine-derived identifier.

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
The repository is public. Release 1.2.1 and candidate beta.7 completed HACS,
hassfest, Python 3.14 and actual-Home-Assistant validation. A request for
inclusion in the default
HACS catalog is open as
[hacs/default#10136](https://github.com/hacs/default/pull/10136); custom-repository
installation is already available and does not depend on that review.
Custom runtime localization is supplied completely by `translations/en.json`
and `translations/cs.json`; the Core-only build source `strings.json` is not
shipped.

## Automated verification

| Check | Result |
|---|---|
| Unit and integration-isolation tests | 384 passed |
| Actual Home Assistant runtime tests | 3 passed |
| Python modules measured | 19 |
| Statements | 2,724 / 2,724 |
| Branches | 882 / 882 |
| Line coverage | 100% |
| Branch coverage | 100% |
| Ruff | passed |
| Ruff format | passed |
| mypy strict | passed |
| Python compilation | passed |
| English/Czech leaf-key parity | 189 / 189 |
| Translation placeholders | synchronized |
| Public HACS repository validation | 1.2.1 and beta.7 passed |
| Home Assistant hassfest | 1.2.1 and beta.7 passed |
| Manifest version | 1.3.0-beta.8 (local prerelease candidate; deployment pending) |

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
| Installation and restart | 1.2.0 passed clean restart; 1.2.1 installed through HACS; beta.4, beta.5 and beta.6 backed up, installed and loaded locally | verified through beta.6 |
| Hybrid cloud updates | Beta.4 through beta.6 DSS streamed; beta.6 received 40 live datapoint events through the physical cycle; fallback covered deterministically | live + automated |
| Command confirmation capability | Eletta cloud declared `ack_enabled: false`; live stream produced datapoints and zero datapoint ACKs; ACK-enabled matching/rejection remains covered deterministically | live on Eletta + automated |
| Wake | beta.6 changed standby → waking up → ready; cloud-state confirmation completed in 4.5 s and ready was reached in 43.2 s | verified on Eletta |
| Standby | beta.6 changed ready → going to sleep → standby; cloud-state confirmation completed in 5.4 s and standby was reached in 11.6 s | verified on Eletta |
| Recipe learning | Espresso, Cappuccino and Cold Brew frames observed | verified |
| Cold Brew start | beta.6 entered preparation, enabled context-aware Stop, reported the friendly Cold Brew name and confirmed in 6.0 s | verified on Eletta |
| Cold Brew Stop | beta.6 confirmed Stop in 1.5 s, returned to ready and disabled Stop | verified on Eletta |
| Last Command Status | pending → sent → acknowledged; unknown after restart by design; app traffic kept separate | verified |
| Coffee Link Session | free after deployment; history retained | verified |
| Other beverage recipes | automated protocol paths only | physical matrix incomplete |
| Foreign-session conflict | deterministic automated coverage | controlled live conflict pending |
| Fault and outage paths | deterministic automated coverage | controlled live faults pending |
| PrimaDonna Soul | profile and automated compatibility paths | experimental |

The beta.4 Eletta formulas, translations and runtime entity availability passed
live read-only acceptance. Beta.5 preserved those formulas and added the privacy,
reconfiguration, startup-availability, capability-aware confirmation and naming
changes described above; deployment, read-only acceptance and the supervised
physical cycle passed. Beta.6 retained those semantics and repeated the backed-up
deployment, read-only synchronization and physical command cycle. PrimaDonna
Soul formulas, unknown-model behavior and
the default policy for newly registered entities remain covered deterministically;
they require a matching physical model or a fresh registry to verify live. No
appliance command was sent during beta.4 acceptance.

Wake, Cold Brew Start, Cold Brew Stop and Standby were physically repeated after
deploying beta.6. Last Command Status recorded `pending`, `sent` and
`acknowledged` for every operation, and both beverage operations used the
friendly Cold Brew name. Diagnostics showed `ack_enabled: false`, 0 datapoint-ACK
events and healthy datapoint streaming, so state-based confirmation is the
correct Coffee Link behavior for this Eletta property. The return to `unknown`
after a config-entry reload is documented runtime-only behavior, while Recorder
retains transitions. The table does not imply that every beverage was physically
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

1. Push the reviewed beta.6 candidate, require Validate, HACS and hassfest to
   pass, then create a GitHub prerelease from the exact tested commit.
2. Monitor the HACS catalog review and respond only when a maintainer requests a
   change or when material new information is required.
3. After catalog acceptance, replace the temporary custom-repository-first
   installation wording with the normal catalog search flow.
4. Never rewrite a published release tag. If a release needs correction, publish
   a new patch version and retain the previous release history.

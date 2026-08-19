# Maintainer release process

This project uses Semantic Versioning and full GitHub releases. A tag alone is
not a release and must not be used as the HACS distribution signal.

## Prepare

1. Update `custom_components/ha_delonghi_coffeelink_eletta_explore/manifest.json`.
2. Move user-visible changes from `Unreleased` to a dated version in
   `CHANGELOG.md` and update its comparison links.
3. Keep `translations/en.json` and `translations/cs.json` complete and
   synchronized. Custom integrations do not ship a Core build-source
   `strings.json` file.
4. Update usage, compatibility, safety and troubleshooting documentation when
   behavior changes.
5. Never commit credentials, e-mail addresses, DSNs, serial numbers, access
   tokens, real raw command frames or unsanitized diagnostics.

## Validate

Run the same checks as CI:

```text
python -m compileall -q custom_components tests tests_ha
python -m ruff check custom_components tests tests_ha
python -m pytest -q --cov=custom_components/ha_delonghi_coffeelink_eletta_explore --cov-report=term-missing --cov-report=xml --cov-fail-under=100
python -m pytest -q -c pytest_ha.ini
```

For a public repository, require successful HACS validation and hassfest without
ignored checks. Behavior that can dispense liquid, move the machine between
power states or alter cloud-session ownership also requires supervised physical
acceptance on every model claimed as supported.

## Publish

1. Merge or push the reviewed version commit to `main`.
2. Wait for Validate, HACS and hassfest to complete successfully.
3. Create an annotated `vX.Y.Z` tag pointing at that exact commit.
4. Publish a non-draft, non-prerelease GitHub release with concise highlights,
   validation evidence, safety notes and a link to `CHANGELOG.md`.
5. Verify the release archive contains exactly one directory under
   `custom_components` and that its manifest version matches the tag.
6. Install or update the release through HACS on a separate Home Assistant
   instance before announcing it broadly.

Do not rewrite a published release tag. If a release is wrong, fix it in a new
patch version and document the correction.

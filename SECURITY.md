# Security Policy

## Supported versions

Security fixes are provided for the latest released version only.

## Reporting a vulnerability

Do not put vulnerability details, credentials, identifiers or command frames in
an issue, discussion or pull request.

Use GitHub's
[private vulnerability reporting](https://github.com/kasiom/ha-delonghi-coffeelink-eletta-explore/security/advisories/new).
If GitHub reports that the private form is temporarily unavailable, create only
a non-sensitive issue titled **Security contact requested**. Do not include the
vulnerability, credentials, account details or device data in that issue; the
maintainer will establish a private channel.

Include the affected version, impact, reproduction steps and a suggested fix when
available. Do not test against devices or accounts you do not own.

The maintainer will acknowledge a complete report on a best-effort basis within
seven days. Disclosure timing will be coordinated with the reporter after a fix
and supported release path are available.

## Credential handling

Coffee Link e-mail and password values are stored in the Home Assistant config
entry and transmitted only to the vendor authentication endpoints over HTTPS.
Diagnostics intentionally exclude credentials, tokens, DSNs and raw protocol
frames. The app-level API identifiers contained in the source are public values
embedded in the official Coffee Link application; they are not user credentials.

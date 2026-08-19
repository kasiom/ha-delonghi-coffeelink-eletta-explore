# Security Policy

## Supported versions

Security fixes are provided for the latest released version only.

## Reporting a vulnerability

Do not put vulnerability details, credentials, identifiers or command frames in
an issue, discussion or pull request.

During the current private staging phase, GitHub's public private-vulnerability
reporting endpoint is not available for this repository. An authorized
collaborator who cannot open a private draft security advisory should create only
a non-sensitive issue titled **Security contact requested**. The maintainer must
then establish a private reporting channel before any details are shared.

Private vulnerability reporting must be enabled and this section updated with a
direct private-reporting path before the repository is made public.

Include the affected version, impact, reproduction steps and a suggested fix when
available. Do not test against devices or accounts you do not own.

## Credential handling

Coffee Link e-mail and password values are stored in the Home Assistant config
entry and transmitted only to the vendor authentication endpoints over HTTPS.
Diagnostics intentionally exclude credentials, tokens, DSNs and raw protocol
frames. The app-level API identifiers contained in the source are public values
embedded in the official Coffee Link application; they are not user credentials.

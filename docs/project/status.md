# Project status

The SDK implements header authentication, pure request bodies, one response envelope, flat
methods/types/enums, persistent token-state ports, one reactive refresh/replay, bounded retry, and a
multi-document standard-OpenAPI generator.

The next unreleased patch candidate is defined by `pyproject.toml`. The independent generator
version is `3.0.1` with manifest version four.

The currently exported authService and accountsService OpenAPI documents contain only public
infrastructure routes. `GetToken`, `RefreshToken`, `GetJwks`, `ProvisionHuman`,
`SetPrincipalStatus`, `ReplacePrincipalScopes`, and `IssueLoginGrant` are future-facing network
stubs outside generator ownership. They do not imply implemented server routes or simulate results.

The repository ships no production token backend/refresher, credential source, signer, verifier,
service database, background worker, or route policy.

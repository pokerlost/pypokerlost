# Project status

The SDK implements header authentication, pure request bodies, one response envelope, flat
methods/types/enums, persistent token-state ports, one reactive refresh/replay, bounded retry, and a
multi-document standard-OpenAPI generator.

The package version is `0.2.0`; the generator version is `3.0.0` with manifest version four.

`GetToken` matches the implemented authService route. `RefreshToken`, `GetJwks`, `ProvisionHuman`,
`SetPrincipalStatus`, `ReplacePrincipalScopes`, and `IssueLoginGrant` are honest future-facing
network stubs. They do not imply server routes or simulate results.

The repository ships no production token backend/refresher, credential source, signer, verifier,
service database, background worker, or route policy.

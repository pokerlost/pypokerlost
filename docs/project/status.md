# Project status

`pypokerlost` implements the body-only Pokerlost SDK foundation and flat OpenAPI generator.

## Implemented surface

| Area | Current behavior |
| --- | --- |
| Client/session | `PokerlostClient` owns one restartable async session and current-client context. |
| Request protocol | Public and protected JSON envelopes; every business call uses POST. |
| Response protocol | One five-field `PokerlostResponse` for every normal status. |
| Authorization middleware | Exact-scope reuse, acquisition, refresh, single-flight, body injection, and invalidation. |
| Token store | Behavior-only consumer port with audience and exact-scope key semantics. |
| Retry middleware | Fixed bounded policy, explicit per-call opt-in, and body delay support. |
| Errors | Small canonical secret-safe client hierarchy. |
| Methods/types | Flat modules and flat public facades. |
| Generator | Multi-document global preflight, flat output, explicit scope map, and manifest v3. |
| Lifecycle | Async client context plus `PokerlostApplication` async/synchronous entrypoints. |

The SDK package version is `0.2.0`; the generator version is `2.0.0`.

## Auth method status

`GetToken` matches the currently implemented authService operation. `RefreshToken`, `GetJwks`,
`ProvisionHuman`, `SetPrincipalStatus`, `AssignPrincipalRole`, and `IssueLoginGrant` are typed
future-facing SDK stubs. They make ordinary network calls and do not simulate absent server
behavior.

## Not implemented here

The SDK has no production token-store backend, service verifier, credential loader, token signer,
key fetcher, route policy, database integration, alternate wire protocol, automatic authentication
replay, service discovery, background worker, or deployment framework.

The repository provides static checks and artifact builds. Service contract generation and
cross-repository scope comparison are performed against the relevant service OpenAPI and route
sources.

See `docs/project/non-goals.md`, `SERVICE.md`, and `docs/index.md`.

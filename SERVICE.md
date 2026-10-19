# pypokerlost

`pypokerlost` is the typed asynchronous SDK for Pokerlost's JSON protocol over HTTPS.

## Responsibilities

- Own `PokerlostClient.__call__`, HTTP transport, canonical response decoding, and safe errors.
- Own flat typed methods, types, and enums.
- Own the pure `PokerlostRequest` and canonical `PokerlostResponse` envelopes.
- Own internal `Authorization: Bearer` injection for protected calls.
- Own bounded opt-in retry and one narrow reactive expired-token recovery boundary.
- Define persistent/shared `PokerlostTokenStore` and service-owned `PokerlostTokenRefresher` ports.
- Own the explicit shared `PokerlostScopes` catalog and validate protected operation scopes against
  it while generating exact method `__scopes__` metadata from standard OpenAPI security.

## Protocol

- Every business operation is `POST /<operation>` with one JSON request and response.
- The JSON request is always `{"payload": ...}`; authentication never appears in it.
- Protected calls add `Authorization: Bearer <access-token>` at the transport adapter.
- Gateway targets explicitly select a `ServiceId` through `x-pokerlost-serviceId`, independently
  of credentials, scopes, audience and JSON payload. Direct-origin targets keep the old default.
- The response body always has `ok`, `result`, `error`, `error_message`, and `retry_after`.
- No generic headers API, cookie authentication, query token, alternate envelope, or response
  metadata side channel exists.

## Authentication boundary

- A concrete method uses `None` for no access-token scopes or a non-empty tuple of exact
  `PokerlostScopes` members. Empty and missing metadata are invalid.
- The middleware loads exact shared state by client identity, audience, and canonical scopes.
- Missing state never causes automatic acquisition. Consumers explicitly call `GetToken` and
  persist validated state before protected clients start.
- Only exact `POKERLOST_ACCESS_TOKEN_EXPIRED` may invoke the injected refresher once. Local UTC
  expiry metadata does not trigger refresh by itself; the original request may be replayed once
  with the refreshed token.
- Persistent implementations own encryption, CAS, bounded cross-process leases, and refresh-token
  rotation safety without holding a database transaction across network I/O.

## Generator boundary

- A service with no protected operations may omit `components.securitySchemes`; its public methods
  use `__scopes__ = None`.
- A protected operation requires a supported standard OAuth2 client-credentials scheme and one
  exact non-empty security requirement whose scopes all exist in `PokerlostScopes`.
- The generator neither infers planned operations from incomplete service documents nor rewrites
  the SDK-owned scope catalog. Explicit future-facing stubs remain outside its manifest until a
  compatible production route exists.

## Non-responsibilities

The SDK does not own client credential storage, token acquisition orchestration, background
refresh, production persistence, encryption keys, JWT signing/verification, service policy,
databases, business idempotency, routes, or deployment configuration. Authorization is scope-only;
there is no role lifecycle or role claim.

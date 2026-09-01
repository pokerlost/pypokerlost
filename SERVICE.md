# pypokerlost

`pypokerlost` is the typed asynchronous SDK for the private Pokerlost JSON protocol over HTTPS.

## Purpose

Provide one small Python interface for typed Pokerlost operation calls, canonical request and
response envelopes, body-only token coordination, bounded opt-in retry, and OpenAPI-to-SDK
generation while keeping service business policy outside the package.

## Responsibilities

- Own `PokerlostClient`, session targeting, JSON POST transport, response decoding, and canonical
  safe errors.
- Own flat typed methods and flat wire/value models.
- Own `PokerlostRequest`, `PokerlostAuthorizedRequest`, and `PokerlostResponse`.
- Own exact operation and scope validation.
- Own the retry and authorization middleware pipeline.
- Own the behavior-only `PokerlostTokenStore` port and monotonic token state.
- Own public body-only `GetToken` and `RefreshToken` calls plus explicitly documented
  future-facing auth method stubs.
- Own development-time generation from one or more OpenAPI 3.1 JSON documents.
- Coordinate one client lifecycle through `PokerlostApplication`.

## Protocol rules

- Every business operation is `POST /<operationId>` with one JSON request and one JSON response.
- A public operation sends only `{"payload": ...}`.
- A protected operation sends `{"authorization": {"access_token": ...}, "payload": ...}`.
- Token acquisition and refresh secrets exist only inside their JSON payloads.
- Project-owned code has no caller-facing or internal generic HTTP-header API.
- The response body is always `PokerlostResponse[ResultT]`; retry delay is its `retry_after` field.
- Production API targets use HTTPS. Loopback HTTP exists only for local development.
- This transport is private to Pokerlost and is not a standards-compatible OAuth2 wire protocol.

## Authorization and retry boundaries

- Method `required_scopes` is the exact outbound scope request; public methods use an empty tuple.
- `PokerlostAuthorizationMiddleware` coordinates token reuse, acquisition, refresh, single-flight
  locking, storage calls, and body injection.
- Consumers supply credentials, audience, and a `PokerlostTokenStore` implementation.
- The SDK does not ship production token persistence, credential loading, token signing, local
  verification, JWKS policy, role expansion, or service authorization decisions.
- Authentication failure invalidates state for a later independent call; the failed call is not
  replayed. Insufficient scope does not trigger refresh.
- Retry is explicit per logical call through `PokerlostRequestOptions.retry_policy`.
- Retry never creates or changes business operation IDs and never establishes mutation safety.

## Generator boundary

- Generated method and type files are flat and globally named across every input document.
- Generation validates all supplied documents before writing and fails on global name collisions.
- Exact protected scopes are supplied outside OpenAPI or retained from an existing hand-written
  method.
- OpenAPI body schemas show the access-token field but cannot express exact body-token scopes with
  a standard security scheme.
- Manual SDK stubs call ordinary endpoints when those endpoints exist; they never return synthetic
  results and do not imply server implementation.

## Non-responsibilities

The SDK does not own service databases, domain workflows, account or authentication server
implementations, production token storage, credentials, JWT signing or verification, background
workers, gateways, service discovery, business idempotency, reconciliation, or deployment policy.

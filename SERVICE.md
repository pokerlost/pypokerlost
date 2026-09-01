# pypokerlost

`pypokerlost` is the typed asynchronous Python SDK shared by PokerLost services.

## Purpose

Provide one canonical Python interface for describing and executing typed PokerLost API operation
calls while keeping service business rules outside the SDK.

## Responsibilities

- Own the reusable `Client`, session, request, and response pipeline.
- Own `PokerlostType` and `MutablePokerlostType` as bases for typed API objects.
- Own `PokerlostMethod` and the conventions for generated request methods and result types.
- Own client middleware and client-local JSON-compatible storage abstractions.
- Own focused outbound service authentication through OAuth2 client credentials and bearer header
  enrichment.
- Own explicit bounded transport retry primitives that remain disabled without a per-call policy.
- Own application lifecycle coordination around one client.
- Own development-time OpenAPI-to-SDK generation tooling.

## Service-specific rules

- Public API objects inherit `PokerlostType`; deliberately mutable objects inherit
  `MutablePokerlostType`.
- API method objects inherit `PokerlostMethod` and declare the operation, HTTP method, and result
  type.
- Generated request methods live under `pypokerlost.methods.<service_package>`.
- Generated returned and nested API objects live under `pypokerlost.types.<service_package>`.
- Transport request, response, session, and API-target mechanics live under `pypokerlost.client`.
- The operation string is the full operation identity; the SDK does not route by service metadata.
- Every operation string has exactly the `namespace.someOperation` shape: one dot, lowercase ASCII
  initials, and ASCII letters or digits in both segments.
- The fixed response envelope contains `ok`, `result`, `error`, and `error_message`.
- A client owns one session, one storage backend, and its immutable ordered middleware
  configuration.
- The standard PokerLost response envelope also wraps `/oauth.token`; service credentials remain
  HTTP Basic inputs and the access token exists only inside the successful result.

## Boundaries

The SDK does not own PokerLost service business logic, direct database access, accounts or
authentication service implementations, token issuance, authorization scope policy, service
credentials persistence, refresh-token flows, service discovery, service routing, business
idempotency or reconciliation, streaming, WebSocket/events, or multiple transport protocols.

Concrete service methods and API object types are generated or maintained by service consumers;
the core repository intentionally ships none.

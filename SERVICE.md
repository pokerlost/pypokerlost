# pypokerlost

`pypokerlost` is the typed asynchronous Python SDK shared by PokerLost services.

## Purpose

Provide one canonical Python interface for describing and executing typed PokerLost API operation
calls while keeping service business rules outside the SDK.

## Responsibilities

- Own the reusable `Client`, session, request, and response pipeline.
- Own `PokerlostType` and `MutablePokerlostType` as bases for typed API objects.
- Own `PokerlostMethod` and the conventions for generated request methods and result types.
- Own generic immutable per-call request headers and client-local JSON-compatible storage
  abstractions.
- Own shared cross-service authorization wire/value contracts without lifecycle behavior.
- Own one explicit bounded transport retry policy that remains disabled without per-call opt-in.
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
- A client owns one session and one storage backend.
- The standard PokerLost response envelope also wraps `/oauth.token`; its generated method uses
  generic form request serialization and caller-supplied headers.

## Boundaries

The SDK does not own PokerLost service business logic, direct database access, accounts or
authentication service implementations, token acquisition or lifecycle orchestration, token
issuance, authorization decisions, service credentials, service discovery, service routing,
business idempotency or reconciliation, streaming, WebSocket/events, or multiple transport
protocols.

Concrete service methods and API object types are generated or maintained by service consumers;
the core repository intentionally ships none.

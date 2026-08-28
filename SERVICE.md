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
- The fixed response envelope contains `ok`, `result`, `error`, and `error_message`.
- A client owns one session, one storage backend, and its ordered middleware configuration.

## Boundaries

The SDK does not own PokerLost service business logic, direct database access, accounts or
authentication implementations, token handling, authorization scope policy, service discovery,
service routing, retry policy, streaming, WebSocket/events, or multiple transport protocols.

Concrete service methods and API object types are generated or maintained by service consumers;
the core repository intentionally ships none.

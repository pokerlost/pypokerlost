# Project status

`pypokerlost` currently provides the typed asynchronous HTTP API operation foundation and
development-time generation tooling shared by PokerLost service consumers.

## Implemented surface

| Area | Status | Current behavior |
|---|---|---|
| Typed HTTP API operation | Implemented | Strict method requests produce validated typed results through the fixed PokerLost envelope. |
| Client and session | Implemented | `Client` owns one restartable asynchronous session and the request/response pipeline. |
| Client lifecycle | Implemented | Async context management and `Application` coordinate session, storage, and current-client context. |
| Middleware | Implemented | Ordered client-owned middleware uses an immutable per-request snapshot. |
| Storage | Implemented | `MemoryStorage` provides process-local JSON-compatible values with optional TTL. |
| OpenAPI generator | Implemented | OpenAPI 3.1 JSON can generate deterministic method and type packages with manifest v2 ownership. |
| Generated layout split | Implemented | Requests live under `pypokerlost.methods`; returned and nested API objects live under `pypokerlost.types`. |
| Concrete service packages | Not shipped here | Services generate or maintain their own method and type packages. |

The current SDK package version is `0.2.0`; the current generator version is `1.0.0`.

## Not implemented in the core

The core has no WebSocket or event API, authorization scope policy, token service, automatic
service discovery or routing, generic retry framework, endpoint-specific client facade, bundled
external storage backend, or alternative transport protocol. It also contains no concrete accounts
or authentication methods.

The repository provides static analysis and artifact-build tooling but currently contains no test
suite, CI workflow, or package publishing automation. These statements describe repository state,
not a speculative roadmap.

See [Project non-goals](non-goals.md) for the intentional boundary and
[`SERVICE.md`](../../SERVICE.md) for the product definition.

[Documentation index](../index.md)

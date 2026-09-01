# Project status

`pypokerlost` currently provides the typed asynchronous HTTP API operation foundation and
development-time generation tooling shared by PokerLost service consumers.

## Implemented surface

| Area | Status | Current behavior |
|---|---|---|
| Typed HTTP API operation | Implemented | Strict method requests produce validated typed results through the fixed PokerLost envelope. |
| Client and session | Implemented | `Client` owns one restartable asynchronous session and the request/response pipeline. |
| Client lifecycle | Implemented | Async context management and `Application` coordinate session, storage, and current-client context. |
| Middleware | Implemented | One immutable client-owned outbound chain exposes safe call metadata and per-call options. |
| Service authentication | Implemented | Client credentials, bearer enrichment, and a monotonic single-flight token cache use the universal response decoder. |
| Bounded retry | Implemented | Retry is disabled by default and enabled only by an explicit per-call `RetryPolicy`. |
| Storage | Implemented | `MemoryStorage` provides process-local JSON-compatible values with optional TTL. |
| OpenAPI generator | Implemented | OpenAPI 3.1 JSON can generate deterministic method and type packages with manifest v2 ownership. |
| Generated layout split | Implemented | Requests live under `pypokerlost.methods`; returned and nested API objects live under `pypokerlost.types`. |
| Concrete service packages | Not shipped here | Services generate or maintain their own method and type packages. |

The current SDK package version is `0.2.0`; the current generator version is `1.1.0`.

## Not implemented in the core

The core has no WebSocket or event API, authorization scope policy, token-issuing service,
refresh-token flow, automatic service discovery or routing, global retry policy, automatic
`401`/`403` replay, endpoint-specific client facade, bundled external storage backend, or
alternative transport protocol. It also contains no concrete accounts or authentication methods.

The SDK does not persist business idempotency, workflow, outbox, or reconciliation state. Consumer
services decide which calls are replay-safe and keep database transactions outside remote I/O and
retry backoff.

The repository provides static analysis and artifact-build tooling but currently contains no test
suite, CI workflow, or package publishing automation. These statements describe repository state,
not a speculative roadmap.

See `docs/project/non-goals.md` for the intentional boundary and `SERVICE.md` for the product
definition.

See `docs/index.md`.

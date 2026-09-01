# Architecture overview

This page explains the major runtime owners, dependency direction, and the separate development-time
generation flow in `pypokerlost`.

## Runtime flow

One typed method enters one central client. The client takes a deep semantic snapshot, validates
safe metadata, and passes immutable per-call options through one outbound middleware chain before
the client-owned session performs transport and response validation.

```text
PokerlostMethod
      │
      ▼
Client method snapshot
      │
      ▼
RetryMiddleware (optional per-call policy)
      │
      ▼
BearerTokenMiddleware (optional provider/cache)
      │
      ▼
RequestBuilder
      │
      ▼
   Request
      │
      ▼
 HttpxSession
      │
      ▼
PokerLost HTTP API
      │
      ▼
ResponseHandler
      │
      ▼
 Response
      │
      ▼
PokerlostType result
```

`PokerlostMethod` contains validated request fields plus the operation, HTTP method, and declared
result metadata. `Client` reconstructs and binds an isolated method snapshot, validates the
operation and HTTP method, and then enters its immutable middleware tuple. The declared result may
also be a supported scalar, collection, or type alias; structured API objects inherit
`PokerlostType`.

The first registered middleware is outermost. In the canonical authenticated composition,
`RetryMiddleware` wraps `BearerTokenMiddleware`, so every bounded attempt resolves bearer
credentials while a usable token remains process-local in the provider cache. Retry is inactive
without `RequestOptions.retry`.

## Runtime ownership

| Owner | Responsibility |
|---|---|
| `PokerlostType` | Base configuration and optional client binding for typed API objects. |
| `PokerlostMethod` | Strict request fields and operation metadata. |
| `Client` | Session, storage, immutable middleware, method snapshots, execution, and task-local client context. |
| `APIMiddleware` | Immutable safe call context, per-call option enrichment, and optional lifecycle. |
| `ClientCredentialsTokenProvider` | Form/Basic token acquisition, standard envelope decoding, and process-local single-flight cache. |
| `RetryMiddleware` | Explicit bounded replay of configured transport/status failures. |
| `RequestBuilder` | Transport-independent request data and headers. |
| `HttpxSession` | API target, URL, JSON codecs, UTF-8 conversion, HTTPX resources, and I/O. |
| `ResponseHandler` | Envelope validation, error mapping, and declared result validation. |
| `Application` | One client lifecycle and an optional user lifecycle. |

Transport code is grouped below `pypokerlost/client/`:

```text
client/
├── api_server.py
├── auth/
├── request/
├── response/
├── retry/
└── session/
```

Typed API objects belong under `pypokerlost/types/`; API method objects belong under
`pypokerlost/methods/`. Outbound middleware has the focused `pypokerlost/middleware/` facade.
Storage is a client-owned sibling of the session and never participates in request or response
transport.

## Generator flow

Generation is a development-time operation, not part of runtime request execution.

```text
OpenAPI 3.1
→ generator
→ methods/<service>/
→ types/<service>/
```

One generation run writes request methods and transport-free API types under separate service
packages. The generator validates the supported contract, renders deterministic Python sources,
and uses its manifest to protect manual files and remove only proven stale generated files. See
`docs/architecture/generator.md` for ownership details and `docs/generator/usage.md` for commands.

## Dependency direction

The lower transport layers do not know about the full `Client`:

```text
types/base ──→ task-local current-client lookup
methods ─────→ types
client ──────→ methods + request + session + middleware + storage
middleware ──→ immutable context + RequestOptions + auth/retry collaborators
auth provider → APIServer + private HttpxSession specialization + ResponseHandler
storage ─────→ JSON and storage semantic types
generator ───→ public runtime facades only
```

Request, response, and session modules do not import `Client`. They receive focused values such as
`PokerlostMethod`, `Request`, and `RequestOptions`. Public middleware receives no method object,
payload, result type, session, or HTTPX value. Storage does not import transport, methods, API
targeting, or OpenAPI metadata.

The SDK owns transport attempts, not a consuming service's business idempotency, workflow state,
database transactions, or reconciliation. Those boundaries are detailed in
`docs/api/middleware.md`.

## Detailed explanations

- `docs/architecture/client-lifecycle.md` covers resource order, task-local context, and
  `Application`.
- `docs/architecture/request-response-pipeline.md` covers payload preparation,
  transport, validation, and error mapping.
- `docs/architecture/types-and-methods.md` covers model behavior, client binding, and generated
  placement.
- `docs/api/client.md` covers supported imports and usage.

See `docs/index.md`.

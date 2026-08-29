# Architecture overview

This page explains the major runtime owners, dependency direction, and the separate development-time
generation flow in `pypokerlost`.

## Runtime flow

One typed method enters one central client. Middleware wraps the execution before the client-owned
session turns the method into an HTTP request and validates the response.

```text
PokerlostMethod
      │
      ▼
    Client
      │
 middleware chain
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
result metadata. `Client` copies and binds the executing method, snapshots its middleware, and
delegates to its session. The declared result may also be a supported scalar, collection, or type
alias; structured API objects inherit `PokerlostType`.

## Runtime ownership

| Owner | Responsibility |
|---|---|
| `PokerlostType` | Base configuration and optional client binding for typed API objects. |
| `PokerlostMethod` | Strict request fields and operation metadata. |
| `Client` | Session, storage, middleware, execution, and task-local client context. |
| `RequestBuilder` | Transport-independent request data and headers. |
| `HttpxSession` | API target, URL, JSON codecs, UTF-8 conversion, HTTPX resources, and I/O. |
| `ResponseHandler` | Envelope validation, error mapping, and declared result validation. |
| `Application` | One client lifecycle and an optional user lifecycle. |

Transport code is grouped below `pypokerlost/client/`:

```text
client/
├── api_server.py
├── request/
├── response/
└── session/
```

Typed API objects belong under `pypokerlost/types/`; API method objects belong under
`pypokerlost/methods/`. Storage is a client-owned sibling of the session and never participates in
request or response transport.

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
client ──────→ methods + request + response + session + middleware + storage
middleware ──→ methods + RequestOptions
storage ─────→ JSON and storage semantic types
generator ───→ public runtime facades only
```

Request, response, and session modules do not import `Client`. They receive focused values such as
`PokerlostMethod`, `Request`, and `RequestOptions`. Storage does not import transport, methods, API
targeting, or OpenAPI metadata.

## Detailed explanations

- `docs/architecture/client-lifecycle.md` covers resource order, task-local context, and
  `Application`.
- `docs/architecture/request-response-pipeline.md` covers payload preparation,
  transport, validation, and error mapping.
- `docs/architecture/types-and-methods.md` covers model behavior, client binding, and generated
  placement.
- `docs/api/client.md` covers supported imports and usage.

See `docs/index.md`.

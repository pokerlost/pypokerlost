# pypokerlost

Before every task:

1. Read `AGENTS.md`.
2. Read `SERVICE.md`.
3. Read `docs/ARCHITECTURE.md`.
4. Inspect the current repository and the relevant implementation.
5. Treat the latest direct user requirement as the highest priority.
6. Treat `SERVICE.md` as the source of truth for SDK purpose, scope, and current product decisions.
7. Treat this file as the source of truth for shared `pypokerlost` engineering conventions.

Priority:

```text
latest direct user requirement
→ SERVICE.md
→ AGENTS.md
→ docs/ARCHITECTURE.md
→ older decisions
```

## Repository identity

- The repository root is `pokerlost/`.
- The Python distribution name is `pypokerlost`.
- The import package name is `pypokerlost`.
- Runtime library code lives directly under `pypokerlost/`; do not introduce a `src/` layout.
- When already running inside the repository root, do not create another nested `pokerlost/`
  directory.
- This repository is a hand-maintained SDK, not a Copier template or generated FastAPI service.
- Do not add Copier configuration, template placeholders, service scaffolding, PostgreSQL,
  SQLAlchemy, Alembic, FastAPI, Docker, Helm, or Kubernetes files unless a later task explicitly
  requires them.

## General architecture

- Keep client lifecycle, current-client context, API method definitions, transport, response
  decoding, public models, exceptions, and package metadata separated.
- Keep the core async-first. Do not add a synchronous facade until it has a concrete requirement.
- Prefer small typed contracts over registries, dependency-injection containers, dynamic proxies,
  metaclass machinery, or generated client methods.
- Do not add abstractions without a concrete use in the SDK.
- Do not copy server-side business logic into the SDK.
- Do not define concrete PokerLost API methods until they are explicitly requested and their
  contracts are authoritative.
- WebSocket subscriptions and event decorators are a later subsystem. Do not add placeholder
  WebSocket code to the initial HTTP SDK foundation.

## Public execution API

The SDK has exactly two explicit network entry points on `Client`:

```python
await client.make_request(method)
async with client.stream_content(stream_method) as content:
    ...
```

A normal request method also supports these two convenience forms:

```python
await client(method)

async with client:
    result = await method
```

Rules:

- `Client.make_request()` executes a typed `Method[ResultT]`.
- `Client.stream_content()` opens a resource-safe stream for a typed `StreamMethod`.
- `Client.__call__()` is only a thin delegate to `make_request()` so `await client(method)` works.
- `Method.__await__()` resolves the current client from task-local context and delegates to that
  client.
- Never add endpoint-specific methods such as `client.create_account()` or
  `client.get_balance()`.
- Never implement dynamic endpoint lookup through `Client.__getattr__`.
- A method object never stores a client instance.
- Calling `await method` without an active current client raises a focused
  `ClientContextError` with a useful message.
- Explicit execution through `client.make_request(method)` and `client(method)` must work without
  installing the client into current context.

## Current-client context

- Use `contextvars.ContextVar`; never use a mutable module-global singleton.
- Context installation must be token-based and reset in `finally`.
- Nested client scopes must restore the previous client correctly.
- Context must remain task-local and safe under normal `asyncio` concurrency.
- `Client.__aenter__()` may install the client as current and `Client.__aexit__()` must always reset
  it.
- Also expose a focused `client.as_current()` context manager for cases where transport lifecycle is
  managed separately.
- Context helpers belong in a dedicated client-context module rather than inside API method models.
- Do not hide client construction or configuration. The “magic” is only current-client resolution
  for `await method`.

## Method contracts

- `Method[ResultT]` is the abstract, generic, awaitable base for ordinary request/response
  operations.
- `StreamMethod` is the abstract base for content-stream operations and is passed explicitly to
  `Client.stream_content()`.
- Method models are strict, immutable Pydantic v2 models unless a concrete requirement proves that
  another representation is necessary.
- Unknown fields are rejected.
- Public field names are alias-free `snake_case`.
- Each concrete method declares a stable RPC operation name in `namespace.method` form.
- The default RPC path derived from an operation is `/{namespace}.{method}`.
- A method may override request construction when an endpoint genuinely needs different HTTP
  semantics.
- Method validation and serialization perform no network I/O.
- Ordinary methods own typed response parsing through an explicit hook or adapter.
- The base SDK must not guess the exact `ApplicationResponse` JSON envelope until its schema is
  provided as an authoritative contract.
- Transport code must not import future concrete methods.

## Transport

- Define a small abstract `Transport` contract and provide one production `HttpxTransport`.
- The client owns orchestration; the transport owns HTTP execution and stream opening.
- Transport-facing request and response values are immutable, typed, and independent of `httpx`
  public types.
- Keep relative RPC paths separate from the configured base URL.
- Normalize base URLs once and join paths safely.
- Support explicit default headers and per-request headers without mutating caller mappings.
- Configure explicit HTTP timeouts.
- Map known `httpx` transport failures to SDK exceptions while preserving the original exception as
  `__cause__`.
- Do not catch `asyncio.CancelledError`.
- Do not add automatic retries in the foundation. RPC calls may be non-idempotent, so retry policy
  requires an explicit later design.
- Do not log authorization values, cookies, tokens, secrets, private keys, or full sensitive
  payloads.

## Streaming

- Streaming must not buffer the full body before returning control to the caller.
- `Client.stream_content()` returns an asynchronous context manager.
- The yielded content object exposes headers, status information, and asynchronous byte iteration.
- Breaking iteration or raising inside the stream context must still close the underlying response.
- Stream ownership and closing behavior must be deterministic and covered by tests.
- Do not make `StreamMethod` awaitable unless a later requirement defines precise semantics.

## Responses and exceptions

- Treat every non-success HTTP status as a typed SDK failure before method-level decoding.
- Keep transport failure, unexpected HTTP status, response decoding, current-client absence, and
  closed-client use distinguishable.
- The SDK exception hierarchy starts with `PokerLostError`.
- Exceptions may retain safe diagnostic metadata such as operation name, status code, and response
  content truncated to a small safe limit.
- Never include authorization headers or unbounded response bodies in exception messages.
- Do not convert programming errors or cancellations into transport errors.

## Client lifecycle

- `Client.close()` is asynchronous and idempotent.
- Using a closed client raises a focused `ClientClosedError`.
- If the client creates its transport, it owns and closes it.
- If a transport is injected, ownership must be explicit and unsurprising.
- `async with Client(...) as client:` must provide deterministic context installation and cleanup.
- Avoid network work during object construction.
- Do not create a process-wide default client.

## Artifact naming

For every concrete SDK artifact, express its category in both the class suffix and matching
`snake_case` module suffix. A feature or namespace directory identifies the API area; the suffix
identifies the artifact kind.

| Artifact | Concrete class | File |
| --- | --- | --- |
| Ordinary API method | `<SemanticName>Method` | `<semantic_name>_method.py` |
| Streaming API method | `<SemanticName>StreamMethod` | `<semantic_name>_stream_method.py` |
| Method result | `<SemanticName>Result` | `<semantic_name>_result.py` |
| Structured API value | `<SemanticName>` | `<semantic_name>.py` |
| SDK exception | `<SemanticName>Error` | `<semantic_name>_error.py` |
| Transport request | `TransportRequest` | `transport_request.py` |
| Transport response | `TransportResponse` | `transport_response.py` |
| Stream wrapper | `ContentStream` | `content_stream.py` |

Examples:

```text
CreateAccountMethod
create_account_method.py

CreateAccountResult
create_account_result.py

DownloadAvatarStreamMethod
download_avatar_stream_method.py

ClientContextError
client_context_error.py
```

Narrow exceptions:

- Shared and abstract bases retain their concise established names: `Client`, `Method`,
  `StreamMethod`, `Transport`, `HttpxTransport`, `PokerLostError`, `TransportRequest`,
  `TransportResponse`, and `ContentStream`.
- A concrete method may use an operation-oriented package. For example,
  `methods/accounts/create_account/` may contain `method.py` and `result.py` defining
  `CreateAccountMethod` and `CreateAccountResult`. Inside that operation package, do not repeat the
  semantic name in every filename.
- Do not create empty namespace packages for API areas that have no concrete methods yet.

## Models and typing

- Use modern Python typing consistently and keep the configured minimum Python version honest.
- Use PEP 695 syntax when supported by the configured Python baseline.
- Avoid `Any` in public contracts. When unavoidable at an external boundary, contain it and validate
  immediately.
- Represent JSON-compatible values with a focused recursive type alias.
- Use `Mapping` for read-only inputs and copy into owned immutable values where needed.
- Use `TypeAdapter` or an equivalent explicit decoder for generic Pydantic results.
- Ship `py.typed`.
- Do not use dictionaries as a substitute for stable internal transport contracts.

## Imports and public surface

- Prefer explicit imports.
- Keep `__init__.py` files focused; do not turn them into export dumps.
- The package root may expose only the small stable public surface needed by users, initially:
  `Client`, `Method`, `StreamMethod`, core errors, and `__version__`.
- Transport internals remain importable from their own package but are not all re-exported at the
  package root.
- Avoid circular imports through protocols, `TYPE_CHECKING`, and focused context helpers rather than
  runtime import tricks.
- Resolve `__version__` from installed package metadata; do not maintain a second hard-coded version
  constant.

## Configuration and security

- Accept runtime configuration through explicit constructor arguments.
- Do not read environment variables implicitly in core SDK objects.
- Do not commit or log secrets.
- Do not persist access tokens.
- Authentication semantics remain undefined until their authoritative contract is supplied.
- Static default headers are acceptable; a generic credential framework is not required yet.

## Tooling and tests

- Use `uv` for dependency management and builds.
- Use Ruff for formatting and linting, mypy for static checking, and pytest for tests.
- Keep the `Makefile` as thin wrappers around repository commands.
- Do not modify CI/CD unless the task explicitly requests it.
- New public behavior requires focused tests.
- Tests must not call external PokerLost services.
- Prefer a fake transport or `httpx.MockTransport` for deterministic unit tests.
- Test at least explicit execution, callable-client execution, implicit current-client execution,
  missing context, nested context restoration, closed-client behavior, transport error mapping,
  response parsing delegation, stream closure, and package version exposure.

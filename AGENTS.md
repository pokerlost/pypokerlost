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

- Keep client lifecycle, current-client context, API method definitions, session orchestration,
  request preparation, response decoding, public contracts, exceptions, and package metadata
  separated.
- Keep the core async-first. Do not add a synchronous facade until it has a concrete requirement.
- Prefer small typed contracts over registries, dependency-injection containers, dynamic proxies,
  metaclass machinery, or generated client methods.
- Do not add abstractions without a concrete use in the SDK.
- Do not copy server-side business logic into the SDK.
- Do not define concrete PokerLost API methods until they are explicitly requested and their
  contracts are authoritative.
- WebSocket subscriptions and event decorators are a later subsystem. Do not add placeholder
  WebSocket code to the initial HTTP SDK foundation.

## Refactoring rules

- Inspect and reuse the current implementation before creating a new abstraction.
- When an existing abstraction is replaced, remove the obsolete implementation in the same task.
- Do not preserve internal backward compatibility unless the user explicitly requires it.
- Do not create aliases or wrappers that keep both the old `Transport` API and the new `Session`
  API alive.
- Do not add registries, dependency-injection containers, middleware managers, factories, plugin
  systems, dynamic imports, runtime generic introspection, monkey patches, or dynamic attribute
  dispatch.
- Do not implement custom attribute access or assignment hooks.
- Do not add retries, authentication flows, token refresh, caching, WebSocket behavior, code
  generation, or service discovery unless directly requested.
- Do not catch broad exceptions to hide implementation defects.
- Every new abstraction must own one clear responsibility and must have a concrete use in the
  current implementation.
- A single implementation does not justify a new protocol, abstract factory, or registry.

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
- `Client` validates only its own lifecycle and delegates execution to its session.
- `Method.__await__()` resolves the current client from task-local context and delegates to that
  client.
- Never add endpoint-specific methods such as `client.create_account()` or
  `client.get_balance()`.
- Never implement dynamic endpoint lookup on `Client`.
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
- Also expose a focused `client.as_current()` context manager for cases where session lifecycle is
  managed separately.
- Context helpers belong in a dedicated client-context module rather than inside API method models.
- Do not hide client construction or configuration. The “magic” is only current-client resolution
  for `await method`.

## Method contracts

- `BaseMethod` is the shared strict, immutable Pydantic v2 base for ordinary and streaming
  operations.
- `BaseMethod.operation` is a required class-level RPC name in `namespace.method` form.
- `BaseMethod.http_method` is class-level declarative metadata and defaults to `HttpMethod.POST`.
- `Method[ResultT]` is the abstract, generic, awaitable base for ordinary request/response
  operations.
- Every concrete `Method` declares `result_type` explicitly as the runtime Pydantic result token.
  `Any` is permitted only in that local `ClassVar` annotation, never in public request or result
  data.
- `StreamMethod` is the abstract base for content-stream operations and is passed explicitly to
  `Client.stream_content()`.
- `StreamMethod` inherits the same class-level `operation` and `http_method` contract from
  `BaseMethod`; it does not redeclare `operation` as an abstract property.
- Unknown fields are rejected.
- Public field names are alias-free `snake_case`.
- The default RPC path derived from an operation is `/{namespace}.{method}`.
- Method validation and serialization perform no network I/O.
- Method objects contain only declarative operation metadata and immutable input data. They do not
  build HTTP requests, parse responses, store clients, or add arbitrary request headers.
- Do not derive `result_type` through `__orig_bases__`, `__pydantic_generic_metadata__`, or other
  runtime generic introspection.
- Session, request, and response code must depend only on the method base contracts, not on future
  concrete methods.

## Request preparation

- `RequestBuilder` is the single concrete component that converts `BaseMethod` values into
  `PreparedRequest` values.
- Do not add a request-builder protocol, abstract base, factory, registry, or middleware layer while
  there is only one implementation.
- The builder owns RPC path derivation, alias-free Pydantic serialization, HTTP method selection,
  and uniform handling of request fields including `None`.
- Methods cannot override request construction.
- `PreparedRequest` is an immutable typed SDK value and does not expose `httpx` public types.

## Sessions

- Replace the obsolete `Transport` abstraction with `BaseSession`; do not keep compatibility
  aliases or wrappers for `Transport` or `HttpxTransport`.
- `BaseSession` owns the shared template-method flow: build a request, execute or open it, and pass
  the response to `ResponseHandler`.
- `HttpxSession` is the single production adapter and owns concrete `httpx.AsyncClient` I/O.
- `BaseSession.make_request()` and `BaseSession.stream_content()` accept typed method objects;
  protected execution hooks accept only SDK-owned `PreparedRequest` values.
- `RawResponse` and `ContentStream` are immutable or resource-safe SDK values independent of
  `httpx` public types.
- The session layer, not `Client`, owns request orchestration, response handling, and stream error
  body reading.
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

## Fixed platform contracts

- `ApplicationResponse` is an authoritative, frozen public wire contract.
- Do not rename, add, remove, alias, reinterpret, or automatically populate its fields.
- Do not change its validation rules.
- All handled JSON operation outcomes use this envelope.
- Decode the envelope centrally in `ResponseHandler`; concrete methods do not parse it.
- `rpc_openapi_extra()` and the `x-pokerlost` extension are authoritative shared OpenAPI metadata.
- Concrete services import these contracts from the SDK rather than maintaining local copies.
- `ResponseModel` must retain the existing service-template configuration without functional
  changes: `extra="forbid"`, `frozen=True`, `hide_input_in_errors=True`, and
  `validate_default=True`.
- `ApplicationResponse[ResultT]` has exactly `ok`, `result`, `error`, and `error_message`, with the
  existing defaults and single envelope validator. A successful response forbids error metadata;
  a failed response forbids a non-`None` result and requires both error fields.
- `ok=True, result=None` remains valid for operations without a result.

## Streaming

- Streaming must not buffer the full body before returning control to the caller.
- `Client.stream_content()` delegates to `BaseSession.stream_content()` and returns an asynchronous
  context manager.
- The yielded content object exposes headers, status information, and asynchronous byte iteration.
- Breaking iteration or raising inside the stream context must still close the underlying response.
- Stream ownership and closing behavior must be deterministic.
- Do not make `StreamMethod` awaitable unless a later requirement defines precise semantics.
- For a non-2xx stream response, read only a bounded error body, try to decode
  `ApplicationResponse[None]`, raise `ApplicationError` for `ok=False`, otherwise raise
  `UnexpectedStatusError`, and always close the response.

## Responses and exceptions

- `ResponseHandler` is the only component that decides the meaning of an HTTP status together with
  `ApplicationResponse.ok`.
- For ordinary operations, apply this exact matrix:

  | HTTP status | Envelope | Behavior |
  | --- | --- | --- |
  | 2xx | valid and `ok=True` | Return `result`. |
  | any | valid and `ok=False` | Raise `ApplicationError`. |
  | non-2xx | valid and `ok=True` | Raise `UnexpectedStatusError` because the protocol is inconsistent. |
  | 2xx | invalid | Raise `ResponseDecodeError`. |
  | non-2xx | invalid | Raise `UnexpectedStatusError` with a bounded safe response excerpt. |

- Pydantic validation failures from envelope or result decoding must never escape the SDK boundary;
  `ResponseHandler` maps them according to the matrix.
- `ApplicationError` contains `error: str`, `error_message: str`, `operation: str`, and
  `status_code: int`. Do not add one exception class per application error code without a concrete
  requirement.
- Keep HTTP transport failure, application failure, unexpected HTTP status, response decoding,
  current-client absence, and closed-client use distinguishable.
- The SDK exception hierarchy starts with `PokerLostError`.
- Exceptions may retain safe diagnostic metadata such as operation name, status code, and response
  content truncated to a small safe limit.
- Never include authorization headers or unbounded response bodies in exception messages.
- Do not convert programming errors or cancellations into transport errors.

## Client lifecycle

- `Client.close()` is asynchronous and idempotent.
- Using a closed client raises a focused `ClientClosedError`.
- If the client creates its session, it owns and closes it.
- If a session is injected, ownership is controlled explicitly through `owns_session` and defaults
  to caller ownership.
- `base_url`, default headers, and timeout belong to `HttpxSession`; `Client` must not retain a
  second copy or expose a misleading `base_url` value.
- Construct `Client` either with HTTP configuration used to create `HttpxSession` or with an
  injected `session`, never both.
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
| Prepared session request | `PreparedRequest` | `prepared_request.py` |
| Raw session response | `RawResponse` | `raw_response.py` |
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

- Shared bases and infrastructure retain their concise established names: `Client`, `BaseMethod`,
  `Method`, `StreamMethod`, `BaseSession`, `HttpxSession`, `RequestBuilder`, `ResponseHandler`,
  `ResponseModel`, `ApplicationResponse`, `PokerLostError`, `PreparedRequest`, `RawResponse`, and
  `ContentStream`.
- A concrete method may use an operation-oriented package. For example,
  `methods/accounts/create_account/` may contain `method.py` and `result.py` defining
  `CreateAccountMethod` and `CreateAccountResult`. Inside that operation package, do not repeat the
  semantic name in every filename.
- Do not create empty namespace packages for API areas that have no concrete methods yet.

## Models and typing

- Use modern Python typing consistently and keep the configured minimum Python version honest.
- Use PEP 695 syntax when supported by the configured Python baseline.
- Avoid `Any` in public contracts. When unavoidable at an external boundary, contain it and validate
  immediately. The declared `Method.result_type` runtime type token is the narrow permitted
  exception.
- Represent JSON-compatible values with a focused recursive type alias.
- Use `Mapping` for read-only inputs and copy into owned immutable values where needed.
- Use `TypeAdapter` or an equivalent explicit decoder centrally in `ResponseHandler`, never in
  concrete methods.
- Ship `py.typed`.
- Do not use dictionaries as a substitute for stable internal session-boundary contracts.

## Imports and public surface

- Prefer explicit imports.
- Keep `__init__.py` files focused; do not turn them into export dumps.
- The package root may expose only the small stable public surface needed by users, initially:
  `Client`, `Method`, `StreamMethod`, core errors, and `__version__`.
- Session internals remain importable from their own package but are not all re-exported at the
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

## OpenAPI metadata

- `AccessRole` is a `StrEnum` with exactly `public`, `user`, `support`, `master`, and `auto`.
- `ResponseKind` is a `StrEnum` with exactly `application_response` and `content_stream`.
- `rpc_openapi_extra()` is a pure function with no FastAPI dependency. It returns a fresh, fully
  JSON-compatible dictionary under the single `x-pokerlost` key.
- The extension contract starts at `contract_version: 1`, contains deterministic `access.any_of`,
  and declares success and error response kinds. The error response kind is always
  `application_response`.
- Empty access is invalid, duplicate roles fail fast, and `public` cannot be combined with another
  role.
- Do not duplicate `operationId`, path, request bodies, or response schemas in `x-pokerlost`; those
  remain standard OpenAPI/FastAPI operation data.
- OpenAPI metadata describes a machine-readable contract only. It does not implement authorization,
  token acquisition, cross-service calls, or service discovery.

## Dependency policy

- Runtime dependencies are frozen to the dependencies already declared in `pyproject.toml`:
  `pydantic` and `httpx`.
- Existing development and build dependencies are also frozen.
- Do not add, remove, replace, upgrade, or downgrade any dependency unless the latest direct user
  requirement explicitly names that dependency and explicitly authorizes the change.
- Use the Python standard library and the already installed dependencies.
- aiogram is an architectural reference only. Do not add aiogram as a dependency and do not copy its
  implementation.
- Do not add FastAPI as an SDK dependency. OpenAPI helpers must return plain JSON-compatible Python
  values.

## Tooling

- Use `uv` for dependency management and builds.
- Use Ruff for formatting and linting and mypy for static checking.
- Keep the `Makefile` as thin wrappers around repository commands.
- Do not modify CI/CD unless the task explicitly requests it.
- Do not add or recreate a test suite unless the latest direct user requirement explicitly requests
  tests.

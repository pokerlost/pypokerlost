# pypokerlost

## Before every task

1. Read `AGENTS.md`, `SERVICE.md`, and `docs/ARCHITECTURE.md`.
2. Inspect the current repository, the relevant implementation, and `git status`/`git diff`.
3. Treat files in the current working tree as authoritative over older summaries or reports.
4. Treat the latest direct user requirement as the highest-priority instruction.

Decision priority:

```text
latest direct user requirement
→ SERVICE.md
→ AGENTS.md
→ docs/ARCHITECTURE.md
→ older decisions
```

`SERVICE.md` defines current product scope. This file defines shared engineering rules.

## Repository identity and naming

- The repository root is `pokerlost/`; the distribution and import package are `pypokerlost`.
- Runtime code lives directly under `pypokerlost/`; do not introduce a `src/` layout or another
  nested repository directory.
- This is a hand-maintained asynchronous SDK, not a generated service or application template.
- Python product-prefixed classes and documentation use the single PascalCase word `Pokerlost`.
- The package name remains `pypokerlost`, and the OpenAPI extension key remains `x-pokerlost`.
- Do not retain compatibility aliases with an older product-class spelling.
- Add an abstraction, package, or file only for a concrete current use.

## Current design principle

The core fixes how components collaborate while leaving unlearned Pokerlost product policy open.
Its ergonomic direction is a central Pyrogram-like client with aiogram-like typed RPC method
objects and a small application-level lifecycle owner; neither project is a dependency or an
implementation to copy.

The package has no concrete Pokerlost operations. The next product step is a real vertical slice
from accountsService and authService, not another speculative subsystem.

## Current lifecycle and execution API

`Application` owns the automatic lifecycle of one `Client` and composes it with one user-supplied
asynchronous context-manager callable named `lifecycle`. It supports a signal-aware synchronous
entrypoint runner, an asynchronous runner, and direct async scope management:

```python
application.run(main)
result = await application.run_async(main)

async with application as client:
    result = await method
```

The one public extension contract is used like this:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pypokerlost import Application, Client


@asynccontextmanager
async def lifecycle(application: Application) -> AsyncIterator[None]:
    await WarmupMethod()
    try:
        yield
    finally:
        await FlushMethod()


application = Application(Client(), lifecycle=lifecycle)
```

Application entry rejects overlapping use, marks the application running, enters the client, and
then enters the user lifecycle. Reverse exit leaves the lifecycle first, resets the current client,
stops the session, and clears the running state. Lifecycle setup, the entrypoint, and lifecycle
teardown therefore all execute while the application client is current. Setup failure and
cancellation still unwind every entered context. Sequential reuse is supported.

`Application.run()` owns its event loop through `asyncio.run()` and temporarily handles `SIGINT`
and `SIGTERM` where `asyncio` loop signal handlers are supported. A handled signal cancels and
awaits the application task so lifecycle/session cleanup completes, then `run()` returns `None`.
Unsupported platforms or non-main-thread execution continue normally without signal integration.
`Application.run_async()` is for a caller-owned running loop and never installs process signal
handlers. Application code must cooperate with normal asyncio cancellation; the SDK does not force
termination when user code suppresses cancellation indefinitely.

The handled-shutdown sequence is:

```text
SIGINT or SIGTERM
→ set shutdown event
→ cancel entrypoint/application task
→ exit user lifecycle
→ reset current client
→ close HttpxSession
→ remove installed signal handlers
→ Application.run() returns None
```

Every ordinary method supports these explicit execution forms anywhere:

```python
result = await client(method)
result = await client.make_request(method)
result = await method.as_(client)
```

Inside an application or client async context, the task-local current client also enables:

```python
result = await method
```

Resolution order is explicit `.as_(client)` binding, then the task-local current client, then
`ClientContextError`. `.as_(None)` clears an explicit binding and restores ambient fallback.
`Client.__call__()` executes an isolated model copy explicitly bound to itself and does not mutate
the caller's method.

Manual lifecycle is also available:

```python
async with client:
    result = await method
```

`Client` async-context entry starts the session and then installs that client as current; exit
resets the exact previous context before stopping the session. Nested client scopes restore the
outer client, concurrent tasks retain independent clients, and child tasks inherit the context
present when they are created. A background task must not outlive the application/client scope
whose session it uses. Reentrant or concurrent async-context entry of the same client is rejected.
Direct `Client.start()` and `Client.stop()` manage session resources only and never install ambient
context. The default `HttpxSession` remains lazy, idempotently closable, and restartable.

## Package and responsibility boundaries

The production package shape is:

```text
pypokerlost/
├── __init__.py
├── application.py
├── py.typed
├── client/
│   ├── __init__.py
│   ├── client.py
│   ├── context_controller.py
│   ├── current_client.py
│   └── session/
│       ├── __init__.py
│       ├── base_session.py
│       └── httpx_session.py
├── contracts/
│   ├── __init__.py
│   ├── application_response.py
│   └── response_model.py
├── enums/
│   ├── __init__.py
│   ├── access_role.py
│   └── service_name.py
├── environment/
│   ├── __init__.py
│   └── api_server.py
├── exceptions/
│   ├── __init__.py
│   ├── api.py
│   ├── application.py
│   ├── base.py
│   └── client.py
├── methods/
│   ├── __init__.py
│   ├── base.py
│   ├── accounts/
│   │   ├── __init__.py
│   │   └── base.py
│   └── auth/
│       ├── __init__.py
│       └── base.py
├── lifecycle/
│   ├── __init__.py
│   ├── application_lifecycle.py
│   └── signal_controller.py
├── openapi/
│   ├── __init__.py
│   └── rpc_openapi_extra.py
├── request/
│   ├── __init__.py
│   ├── request_value_preparer.py
│   ├── rpc_request.py
│   └── rpc_request_builder.py
├── response/
│   ├── __init__.py
│   ├── application_response_handler.py
│   └── base_response_handler.py
└── types/
    ├── __init__.py
    └── json.py
```

The documentation shape is:

```text
docs/
├── ARCHITECTURE.md
└── ADDING_METHODS.md
```

Responsibilities remain narrow:

- `Application` composes one managed client with one user lifecycle, rejects overlapping entry,
  and owns signal-aware synchronous entrypoint execution.
- `Client` chooses a default session, safely binds copied methods, delegates calls, and installs
  task-local current-client context only during async-context use.
- `current_client.py` owns the one typed task-local current-client variable and exact token-based
  nested-scope restoration.
- `ClientContextController` stores one optional explicitly bound `Client` in a Pydantic private
  attribute, resolves explicit binding before ambient context, and supports future returned SDK
  models through validation context.
- `ApplicationLifecycle` defines the single user lifecycle strategy; the default implementation is
  a no-op async context manager.
- `SignalController` temporarily registers supported loop signal handlers for one `run()` call.
- `PokerlostMethod[ResultT]` contains request fields, service/operation/result metadata, and private
  bound-client context.
- `AccountsMethod[ResultT]` and `AuthMethod[ResultT]` are abstract service-specific method bases
  that fix only `ServiceName.ACCOUNTS` and `ServiceName.AUTH`, respectively.
- `RpcRequestBuilder` and `RequestValuePreparer` own request preparation under `request/`.
- `BaseSession` composes a request builder and response handler and owns only common timeout and
  execution orchestration.
- `BaseResponseHandler` defines the response-protocol strategy boundary.
- `ApplicationResponseHandler` decodes and interprets the fixed public application envelope.
- `HttpxSession` owns restartable HTTPX resources and performs concrete async HTTP I/O.
- `ResponseModel` and `ApplicationResponse` are the fixed public response contracts.

The collaboration direction is:

```text
PokerlostMethod
→ Client
→ BaseSession
→ RpcRequestBuilder
→ HttpxSession HTTP I/O
→ BaseResponseHandler
→ ApplicationResponseHandler
→ ResultT
```

The bound-method prefix is:

```text
method.as_(client)
→ await method
→ PokerlostMethod.emit
→ Client.__call__
→ the same request pipeline
```

The implicit prefix inside an active application/client scope is:

```text
await method
→ ClientContextController.resolve_client
→ task-local current Client
→ PokerlostMethod.emit
→ Client.__call__
→ the same request pipeline
```

`request/`, `response/`, and `client/session/` do not import `Client` or pass it through their
internal pipelines. Do not replace that removed dependency with an arbitrary context dictionary,
service locator, dependency container, or middleware chain. Task-local client state exists only in
`client/current_client.py` and does not enter the lower request/response/session pipeline.

## Method metadata and enums

All SDK-owned enums live under `pypokerlost/enums/` and are exported through
`pypokerlost.enums`:

- `AccessRole`: `PUBLIC`, `USER`, `SUPPORT`, `MASTER`, and `AUTO`;
- `ServiceName`: `ACCOUNTS` and `AUTH`.

`ServiceName` identifies accountsService or authService in method and OpenAPI metadata. It does not
choose a host, route a request, or trigger authentication behavior. New services require deliberate
enum members; there is no free-form fallback.

`PokerlostMethod[ResultT]` is a strict Pydantic v2 request model. Its generic metadata contract is:

```python
__service__: ClassVar[ServiceName]
__api_method__: ClassVar[str]
__http_method__: ClassVar[str] = "POST"
__returning__: ClassVar[Any]
```

The production package also provides the abstract service-specific bases:

```python
class AccountsMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.ACCOUNTS


class AuthMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.AUTH
```

A future accounts or auth operation inherits its service metadata from the corresponding base and
declares its operation, result type, request fields, and only a non-default HTTP method when the
authoritative service contract requires one. `docs/ADDING_METHODS.md` is the mechanical guide for
that future work. Neither service base declares `__api_method__`, so neither is a concrete endpoint.

Methods contain request fields and declarative metadata only. They do not build requests, decode
responses, perform I/O, store authentication, refresh credentials, retry, resolve service URLs, or
generate endpoint wrappers. Do not add another current-client mechanism, a process-global default,
a metaclass, dynamic attribute lookup, or runtime generic/MRO/Pydantic-internal introspection.

## Server and request contract

`APIServer` is one immutable URL template value. The current fixed default is:

```python
PRODUCTION = APIServer.from_base("http://localhost:8080/api")
```

Thus `PRODUCTION.api_url("accounts.get")` returns
`http://localhost:8080/api/accounts.get`. A caller may pass a custom `APIServer` to `HttpxSession`;
there is no routing map, service discovery, settings model, or environment loading. Explicit
`ServiceName` metadata does not alter this shared local-gateway URL behavior.

`RpcRequest` is an immutable prepared request with exactly `service`, `operation`, `http_method`,
`url`, and UTF-8 `content`. It carries no client, authentication, token or retry state, response,
headers policy, generic context, HTTP framework object, or mutable JSON dictionary. Service and
operation remain explicit and are never inferred from one another or reconstructed from the URL.

`RpcRequestBuilder.build()` reads each class metadata value once, requires a `ServiceName` and
non-empty operation and HTTP method strings, and serializes only Pydantic fields with alias-free
names and `exclude_unset=True`. It prepares the resulting value, calls the configured `json_dumps`
exactly once, requires a string result, and encodes it once as UTF-8. Consequently:

- an unset field is omitted;
- an explicitly supplied `None` is retained as JSON `null`;
- private bound-client context never enters the request body.

`RequestValuePreparer` is an instantiated collaborator. Its recursive instance method preserves
JSON primitives and `None`, copies string-keyed mappings, converts lists and tuples to lists,
converts `Enum` through `.value`, and dumps nested Pydantic models alias-free with
`exclude_unset=True`. Unsupported values raise `TypeError`; they are never silently stringified.

## Session and response contract

`BaseSession` receives one `RpcRequestBuilder`, one `BaseResponseHandler`, and a timeout defaulting
to 10 seconds. Its concrete `__call__()` applies shared default/per-request timeout resolution and
delegates to abstract `make_request()`. It also provides the default no-op `start()` and common async
context-manager lifecycle; concrete adapters implement request execution and `close()`.

`BaseSession` owns neither server/JSON configuration nor request serialization, response decoding,
envelope validation, status mapping, service routing, authentication, or retries. It exposes no
response-parser session API.

`HttpxSession` is the concrete composition point for `APIServer`, JSON encoder/decoder,
`RpcRequestBuilder`, `ApplicationResponseHandler`, and its internal `httpx.AsyncClient`. Its first
concurrent-safe `start()` creates one client; `make_request()` may start it lazily; `close()` is
idempotent; and a later `start()` creates a fresh client. It sends the request's exact method, URL,
bytes, JSON headers, and timeout. It then passes only method, explicit service, explicit operation,
status code, and response text to its response handler.

No buffered status/body response wrapper exists: the concrete `httpx.Response` remains inside
`HttpxSession`. HTTPX timeouts become `ClientTimeoutError`; other HTTPX transport failures become
`ClientConnectionError`; the original exception remains the cause and cancellation is not
converted.

`ApplicationResponseHandler` owns one configured decoder, one reusable
`ApplicationResponse[JsonValue]` adapter, status-to-exception interpretation, and validation of the
method-declared result. Its algorithm is:

1. Decode response content with the configured `json_loads`; a custom-decoder failure becomes
   `ClientDecodeError` with its cause preserved.
2. Validate `ApplicationResponse[JsonValue]`; envelope validation failures become
   `ClientDecodeError`.
3. For `ok=False`, raise a status-specific `PokerlostAPIError` subtype and preserve method,
   service, operation, status, exact `error`, and exact `error_message`.
4. For `ok=True` with a status outside `200 <= status < 300`, raise
   `PokerlostProtocolError`.
5. Validate `result` with `TypeAdapter(method.__returning__)`, passing
   `context={"client": method.client}`; result validation failures become `ClientDecodeError`.
6. Return the declared `ResultT`.

The handler does not dynamically parameterize the envelope with method metadata or inspect generic
internals. Status mapping remains normal instance behavior inside this one concrete strategy.

Failed envelopes map by HTTP status as follows:

- `400`: `PokerlostBadRequestError`;
- `401`: `PokerlostUnauthorizedError`;
- `403`: `PokerlostForbiddenError`;
- `404`: `PokerlostNotFoundError`;
- `409`: `PokerlostConflictError`;
- `413`: `PokerlostEntityTooLargeError`;
- `422`: `PokerlostValidationError`;
- `429`: `PokerlostTooManyRequestsError`;
- `>=500`: `PokerlostServerError`;
- every other status: `PokerlostAPIError`.

These are response categories only. A `401` performs no login, refresh, retry, token mutation, or
special auth-service behavior. Public exceptions and logs never include request bodies, response
bodies, headers, cookies, credentials, or tokens.

## Fixed wire contract

`ResponseModel` retains this configuration:

```python
ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    validate_default=True,
)
```

`ApplicationResponse[ResultT]` is the authoritative shared envelope and retains its four fields,
defaults, and existing validator:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure forbids a result and requires both error fields. Do not add
fields, aliases, validators, automatic values, or reinterpret these semantics without an
authoritative service-contract change. `ok=True, result=None` remains valid at envelope level; the
method's declared result annotation determines whether `None` can cross the typed boundary.

An RPC operation identifier follows `namespace.method`. This is an authoring convention, not
untrusted input that needs regex policing on every model instance.

## OpenAPI metadata

`RpcOpenApiExtra` is an immutable metadata value containing a `ServiceName`, an ordered tuple of
`AccessRole` values, and `contract_version=1`. Each `as_dict()` call returns a fresh,
FastAPI-independent JSON-compatible dictionary:

```python
{
    "x-pokerlost": {
        "contract_version": 1,
        "service": "accounts",
        "access": ["auto", "master"],
    },
}
```

It preserves role order and implements no authorization policy. There is no compatibility helper,
OpenAPI fetching or parsing, method generator, schema registry, code-generation CLI, or runtime
dynamic method system.

## Dependencies, typing, tooling, and security

- Do not add, remove, replace, upgrade, or downgrade dependencies without a direct task
  requirement.
- Runtime dependencies remain `pydantic` and `httpx`; aiogram, Pyrogram, and FastAPI are design
  references rather than SDK dependencies.
- Use `uv` for locking and builds, Ruff for formatting/linting, and mypy in strict mode for static
  checks.
- Keep `Makefile` wrappers thin and leave CI/CD unchanged unless requested.
- Do not create a test suite unless directly requested. Task-specific smoke checks may use temporary
  or inline code without repository test files.
- Do not use broad `object` annotations as a shortcut. Use `JsonValue`, concrete SDK types, type
  parameters, or the narrowly permitted runtime `Any` boundaries.
- Do not add static utility methods. Use instance methods, a genuine alternative `@classmethod`, or
  a focused module-level pure function.
- Do not commit secrets, persist tokens, or log credentials, authorization values, cookies, request
  bodies, or raw/full response bodies.
- Do not run destructive Git commands, commit, or push unless directly requested.

## Current exclusions and deferred decisions

The current SDK has no authentication implementation or placeholder, streaming API, concrete
Pokerlost methods, endpoint-specific client methods, OpenAPI generator, routing layer, retry
behavior, WebSocket/update processing, SDK settings, environment loading, response wrapper, or
compatibility aliases for removed APIs.

Real accountsService and authService behavior must determine any future:

- multi-service clients, URL routing, and discovery beyond one supplied `APIServer`;
- access-token and refresh-token ownership, authorization injection, and refresh behavior;
- proxy, TLS, connection-pool, custom-header, retry, or environment policy;
- endpoint wrappers, synchronous facade, and WebSocket/update behavior;
- streaming API and its error-body protocol.

Concrete accountsService and authService operations remain future ordinary subclasses of
`AccountsMethod` and `AuthMethod`; they are not transport, lifecycle, authentication, or routing
policy.

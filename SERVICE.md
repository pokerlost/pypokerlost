# pypokerlost

SERVICE_NAME: pypokerlost  
SERVICE_SLUG: pypokerlost  
DISTRIBUTION_NAME: pypokerlost  
PACKAGE_NAME: pypokerlost  
REPOSITORY_ROOT: pokerlost  
PACKAGE_ROOT: pypokerlost

## Purpose

`pypokerlost` is the asynchronous Python SDK core for Pokerlost services. Its intended ergonomics
combine a central Pyrogram-like `Client`, aiogram-like typed RPC method objects, and a separate
`Application` lifecycle coordinator. These projects are references only and are not dependencies.

The current package provides typed ordinary-method execution, a pluggable asynchronous session,
explicit service/request metadata, isolated request preparation, strategy-based response
interpretation, automatic application-managed lifecycle, and abstract accounts/auth method bases.
It contains no concrete Pokerlost operations.

## Current product surface

One `PokerlostMethod` instance supports all three explicit public execution forms:

```python
result = await client(method)
result = await client.make_request(method)
result = await method.as_(client)
```

`Client.__call__()` executes an isolated copy bound to that client, without mutating the caller's
method. Inside an active application or client async scope, a method may also be awaited directly:

```python
result = await method
```

Client resolution is explicit object binding, then task-local current client, then
`ClientContextError`. Explicit `.as_(client)` therefore overrides an inherited current client, and
`.as_(None)` clears the override so ambient lookup applies again.

`Application` composes one managed client, one async-context-manager `lifecycle`, and one user
entrypoint:

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


async def main(client: Client) -> None:
    result = await SomeMethod()


application.run(main)
result = await application.run_async(main)
```

Entry order is overlapping-use rejection, mark running, enter the client (start the session, then
install it as task-local current), enter user lifecycle, and return the client. Reverse exit leaves
the lifecycle, resets the current client, stops the session, and clears the running state. Both
lifecycle halves and the entrypoint can therefore use implicit `await method`.

`run()` owns its loop through `asyncio.run()` and temporarily handles `SIGINT`/`SIGTERM` where loop
signal handlers are supported. A handled signal cancels and awaits the application task through
full lifecycle/session cleanup, removes its handlers, and makes `run()` return `None`. Unsupported
platforms or threads run normally without signal integration. Application tasks must cooperate
with normal asyncio cancellation. `run_async()` supports an already-running caller-owned loop and
does not register process signal handlers. Direct application scope returns the managed client:

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

```python
async with application as client:
    result = await method
```

The same `Application` cannot be entered concurrently or reentrantly. A completed application may
be entered again because the default session is restartable.

`Client` is also an async context manager for manual lifecycle:

```python
async with client:
    result = await method
```

Current-client state is task-local. Nested scopes restore the previous client, independent
concurrent tasks may use different clients, and child tasks inherit the client current at task
creation. A background task must not outlive the application/client scope whose session it uses.
The same client cannot be entered concurrently or reentrantly. Direct `start()`/`stop()` manage
session resources only and do not install current-client context.

The generic `PokerlostMethod[ResultT]` is specialized by two abstract service bases:

```python
class AccountsMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.ACCOUNTS


class AuthMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.AUTH
```

They fix service identity only and deliberately do not declare `__api_method__`. Future concrete
operations inherit from the matching service base and provide authoritative operation, request,
and result declarations. The mechanical process is documented in `docs/ADDING_METHODS.md`.

## Server, service, and session configuration

`Client()` chooses `HttpxSession()` by default. The fixed default server is:

```python
PRODUCTION = APIServer.from_base("http://localhost:8080/api")
```

Its operation URL is direct and predictable:

```python
PRODUCTION.api_url("accounts.get")
# "http://localhost:8080/api/accounts.get"
```

A caller may select another one-base RPC server without adding routing policy:

```python
from pypokerlost import Client
from pypokerlost.client.session import HttpxSession
from pypokerlost.environment import APIServer

api_server = APIServer.from_base("https://example.invalid/api")
client = Client(HttpxSession(api_server=api_server, timeout=20))
```

Every method also declares a `ServiceName`: `ACCOUNTS` for accountsService or `AUTH` for
authService. This identity remains explicit on the method, prepared request, response handler call,
API exception, and OpenAPI metadata. It does not select a server, perform routing, or activate
authentication; the current gateway is shared.

`HttpxSession` creates and owns its internal `httpx.AsyncClient`. Construction performs no network
I/O, concurrent first startup creates only one HTTP client, closing is idempotent, and a later
startup creates a fresh client. Request execution may start the session lazily. Callers do not
inject an HTTPX client or HTTPX ownership flags.

`Client` accepts any supplied `BaseSession`. A different async framework belongs in another
`BaseSession` implementation, not in an abstraction below `HttpxSession`.

## Responsibilities

- `Application`: composition of one managed `Client`, one user lifecycle, overlapping-entry
  rejection, and signal-aware synchronous execution.
- `Client`: default-session selection, isolated explicit method binding, call delegation, session
  lifecycle delegation, and task-local context during async-context use.
- `current_client`: one typed `ContextVar` and exact token restoration for task-local client scopes.
- `ClientContextController`: private bound-object client context, including future response-model
  validation context, with explicit-before-ambient resolution.
- `ApplicationLifecycle`: the single callable async-context-manager extension contract.
- `SignalController`: temporary supported `SIGINT`/`SIGTERM` integration used only by `run()`.
- `PokerlostMethod`: typed request fields plus service, operation, HTTP method, and declared result
  metadata.
- `AccountsMethod` and `AuthMethod`: abstract method bases that supply only their fixed
  `ServiceName` metadata.
- `AccessRole` and `ServiceName`: SDK-owned metadata enums in `pypokerlost.enums`.
- `APIServer`: immutable one-base operation URL template without service routing.
- `RequestValuePreparer`: strict recursive JSON-compatible value preparation.
- `RpcRequestBuilder`: one-time serialization into an explicit-service, explicit-operation
  `RpcRequest`.
- `BaseSession`: shared timeout resolution and orchestration through a request builder and response
  handler.
- `BaseResponseHandler`: response-protocol strategy contract.
- `ApplicationResponseHandler`: fixed application-envelope decoding, validation, and status
  interpretation.
- `HttpxSession`: owning, lazy, restartable HTTPX composition and I/O adapter.
- `contracts`, `openapi`, and `exceptions`: shared wire values, metadata, and public failures.

## Request and response behavior

The ordinary collaboration flow is fixed:

```text
PokerlostMethod
→ Client
→ BaseSession
→ RpcRequestBuilder
→ HttpxSession HTTP I/O
→ BaseResponseHandler
→ ApplicationResponseHandler
→ declared ResultT
```

Request model fields are dumped alias-free in JSON mode with `exclude_unset=True`. An unset field is
omitted, while an explicitly supplied `None` remains JSON `null`. Private client binding is not a
model field and cannot enter the serialized body. Unsupported remaining values are rejected rather
than stringified.

`RpcRequest` contains exactly the explicit `ServiceName`, operation, HTTP method, URL, and immutable
UTF-8 content needed at the request-builder/HTTP-adapter boundary. It contains no client, auth,
retry, response, generic context, HTTPX object, or mutable JSON value.

`BaseSession` composes a `RpcRequestBuilder` and `BaseResponseHandler`, resolves the effective
timeout, and delegates request execution. It does not configure servers or JSON, prepare request
values, decode responses, map statuses, route services, authenticate, or retry. In particular,
response interpretation is not a session method.

`ApplicationResponseHandler` decodes through the configured `json_loads`, validates the fixed
envelope as `ApplicationResponse[JsonValue]`, and validates a successful result separately against
`method.__returning__` with `context={"client": method.client}`. Decoder and Pydantic validation
failures become `ClientDecodeError`. JSON `null` crosses the result boundary only when the declared
result annotation accepts `None`.

A failed envelope preserves the method, explicit service and operation, status, exact `error`, and
exact `error_message` in a `PokerlostAPIError` subtype. Failed statuses map as follows:

- `400` bad request;
- `401` unauthorized;
- `403` forbidden;
- `404` not found;
- `409` conflict;
- `413` entity too large;
- `422` validation;
- `429` too many requests;
- `>=500` server error;
- every other status uses base `PokerlostAPIError`.

A successful envelope with a non-2xx HTTP status raises `PokerlostProtocolError`. HTTPX timeout
failures become `ClientTimeoutError`; other HTTPX transport failures become
`ClientConnectionError`. Causes are preserved. Public failures contain no request content,
response body, headers, cookies, credentials, or tokens.

The `httpx.Response` never leaves `HttpxSession`. There is no separate status/body response wrapper.
The adapter passes only the exact protocol inputs to `BaseResponseHandler.handle()`.

## Fixed contracts

`ResponseModel` keeps `extra="forbid"`, `frozen=True`, `hide_input_in_errors=True`, and
`validate_default=True`.

`ApplicationResponse[ResultT]` keeps the established fields, defaults, and validator:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure forbids a result and requires both error fields.

RPC operation identifiers follow `namespace.method`. With an `APIServer`, that operation becomes
`{base}/{namespace}.{method}`; service and operation remain explicit in `RpcRequest`.

## Enums and OpenAPI metadata

All SDK-owned enums live in focused modules under `pypokerlost.enums`. `AccessRole` provides
`public`, `user`, `support`, `master`, and `auto`; `ServiceName` provides `accounts` and `auth`.

`RpcOpenApiExtra` is immutable metadata only. For example:

```python
RpcOpenApiExtra(
    service=ServiceName.ACCOUNTS,
    access=(AccessRole.AUTO, AccessRole.MASTER),
).as_dict()
```

returns a fresh dictionary:

```python
{
    "x-pokerlost": {
        "contract_version": 1,
        "service": "accounts",
        "access": ["auto", "master"],
    },
}
```

Role order is preserved. This value neither imports FastAPI nor authorizes callers, validates role
combinations, infers a service, fetches OpenAPI, parses schemas, or generates methods.

## Current scope

The next feature work should add authoritative accountsService and authService operations as
ordinary subclasses of the matching service base, with their real request/result models and
errors. The current package intentionally has no:

- concrete API methods or endpoint-specific `Client` wrappers;
- authentication state or placeholder, token handling, authorization injection, refresh, automatic
  login during lifecycle entry, or special handling for `ServiceName.AUTH`;
- streaming API or placeholder;
- OpenAPI fetching, parsing, method generation, generated source, or code-generation CLI;
- multi-service routing, discovery, retries, WebSocket/update handling, SDK settings, or environment
  loading;
- response status/body wrapper or session-owned response parser;
- compatibility aliases for removed public names;
- committed test suite.

`PokerlostUnauthorizedError` classifies a response only and triggers no authentication behavior.
Runtime dependencies remain `pydantic` and `httpx`; dependency declaration changes require a direct
task requirement.

## Deferred decisions

Real service contracts will determine:

- multi-service client/routing shape beyond one supplied `APIServer`;
- authentication ownership and token-refresh responsibility;
- future proxy, TLS, connection-pool, custom-header, retry, or environment policy;
- endpoint wrappers, a synchronous SDK facade, and WebSocket/update behavior;
- any future streaming API and its error-body protocol.

Current URL construction, explicit service/operation metadata, request omission/null semantics,
timeout delegation, response status classification, session ownership/restart, and
`Application`/`Client` lifecycle are implemented behavior rather than deferred decisions.

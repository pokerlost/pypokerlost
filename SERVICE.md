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
interpretation, and automatic application-managed lifecycle. It contains no concrete Pokerlost
operations.

## Current product surface

One `PokerlostMethod` instance supports all three public execution forms:

```python
result = await client(method)
result = await client.make_request(method)
result = await method.as_(client)
```

`Client.__call__()` binds the method to that client. Awaiting a method uses only its explicit private
binding; an unbound method raises `ClientContextError`. The SDK has no ambient or task-local current
client.

`Application` guarantees startup and shutdown around one user entrypoint:

```python
from pypokerlost import Application, Client

application = Application(Client())


async def main(client: Client) -> None:
    result = await client(method)


application.run(main)
result = await application.run_async(main)
```

`run()` uses `asyncio.run()` and `run_async()` supports an already-running loop. Direct application
scope returns the managed client:

```python
async with application as client:
    result = await method.as_(client)
```

The same `Application` cannot be entered concurrently or reentrantly. A completed application may
be entered again because the default session is restartable.

`Client` is also an async context manager for manual lifecycle:

```python
async with client:
    result = await client(method)
```

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

- `Application`: automatic lifecycle for exactly one `Client` and overlapping-entry rejection.
- `Client`: default-session selection, explicit method binding, call delegation, and lifecycle
  delegation.
- `ClientContextController`: private bound-object client context, including future response-model
  validation context.
- `PokerlostMethod`: typed request fields plus service, operation, HTTP method, and declared result
  metadata.
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

The next feature work should add authoritative accountsService and authService operations with
their real request/result models and errors. The current package intentionally has no:

- concrete API methods or endpoint-specific `Client` wrappers;
- authentication state or placeholder, token handling, authorization injection, refresh, login
  during startup, or special handling for `ServiceName.AUTH`;
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

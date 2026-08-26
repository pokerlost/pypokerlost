# pypokerlost

`pypokerlost` is the asynchronous Python SDK foundation for Pokerlost. It combines a small
`Application` lifecycle coordinator, a central asynchronous `Client`, typed RPC method objects,
request preparation, a pluggable session, and one fixed application-response protocol.

The package currently has no concrete Pokerlost operations. It is ready for later accountsService
and authService method classes without another client, session, request, response, or lifecycle
redesign.

Before development, read [`AGENTS.md`](AGENTS.md), [`SERVICE.md`](SERVICE.md), and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Development setup

From the repository root:

```bash
uv sync --locked --all-groups
```

The distribution and import package are both named `pypokerlost`; runtime code lives directly in
`pypokerlost/` without a `src/` directory. Python 3.13 or newer is required.

Package version is declared in `pyproject.toml` and exposed from installed distribution metadata:

```bash
python -c "import pypokerlost; print(pypokerlost.__version__)"
```

## Quick start and invocation forms

`Client()` uses the owning, lazy, restartable `HttpxSession` and the fixed default server:

```text
http://localhost:8080/api/{method}
```

`Application` automatically starts and stops that client around an async entrypoint:

```python
from pypokerlost import Application, Client

client = Client()
application = Application(client)


async def main(client: Client) -> None:
    result = await client(method)


application.run(main)
```

`Application.run()` owns an event loop through `asyncio.run()`. In an already-running loop, use
`run_async()`:

```python
result = await application.run_async(main)
```

Direct application scope returns the managed client:

```python
async with application as client:
    result = await method.as_(client)
```

Every `PokerlostMethod` supports the same three execution forms:

```python
result = await client(method)
result = await client.make_request(method)
result = await method.as_(client)
```

The client-call forms bind `method` to `client` and delegate through its session. `.as_(client)`
binds that individual method object and returns it, so awaiting it reaches the same pipeline through
`PokerlostMethod.__await__()` and `emit()`. Awaiting an unbound method raises
`ClientContextError`; there is no ambient or task-local current client.

For manual lifecycle, `Client` is an async context manager:

```python
async with client:
    result = await client(method)
```

The default `HttpxSession` can also start lazily on the first request. If it is used without an
application or context manager, the caller remains responsible for `await client.stop()`.

Entering one `Application` concurrently or recursively raises `ApplicationStateError`. Startup
failure resets its running state. Exit always stops the client and resets that state in `finally`,
including when the entrypoint fails. Sequential reuse is supported.

## Package boundaries

The foundation is split by responsibility:

```text
pypokerlost/
├── application.py
├── client/                  # Client, bound context, and session adapters
│   └── session/             # BaseSession and HttpxSession only
├── contracts/               # fixed wire response models
├── enums/                   # AccessRole and ServiceName
├── environment/             # APIServer and PRODUCTION
├── exceptions/              # public error hierarchy
├── methods/                 # PokerlostMethod base only
├── openapi/                 # RpcOpenApiExtra metadata
├── request/                 # request values and preparation
├── response/                # response protocol strategies
└── types/                   # shared JSON types
```

The complete file tree and dependency rules are in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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

`request/`, `response/`, and `client/session/` do not import `Client`. Client binding remains a
private attribute of the individual method and is passed to future returned Pydantic SDK models only
through result-validation context.

## Configure the API server and session

`APIServer` is an immutable URL-template value. The focused environment facade exports the current
default:

```python
from pypokerlost.environment import APIServer, PRODUCTION

assert PRODUCTION.base == "http://localhost:8080/api/{method}"
assert PRODUCTION.api_url("accounts.get") == "http://localhost:8080/api/accounts.get"
```

Pass a custom server to `HttpxSession` when a different one-base RPC endpoint is required:

```python
from pypokerlost import Client
from pypokerlost.client.session import HttpxSession
from pypokerlost.environment import APIServer

api_server = APIServer.from_base("https://pokerlost.example/api/")
session = HttpxSession(api_server=api_server, timeout=20)
client = Client(session)
```

`from_base()` strips trailing slashes before appending `/{method}`. There is no routing map, service
discovery, settings model, or environment loading.

`HttpxSession` creates and owns its internal `httpx.AsyncClient`; callers do not inject one.
Construction performs no network I/O, concurrent first startup creates a single client, `close()`
is idempotent, and a later `start()` creates a fresh HTTP client.

Callers needing another async framework implement `BaseSession.make_request()` and `close()` and
inject that session directly. `BaseSession.__call__()` applies its default timeout, currently 10
seconds, unless the client call supplies `request_timeout=`.

## Method and service metadata

`PokerlostMethod[ResultT]` is a strict Pydantic v2 request model. Each future concrete method must
declare:

```python
__service__: ClassVar[ServiceName]
__api_method__: ClassVar[str]
__http_method__: ClassVar[str] = "POST"
__returning__: ClassVar[Any]
```

`ServiceName.ACCOUNTS` and `ServiceName.AUTH` identify accountsService and authService. This explicit
metadata does not select a host, route traffic, add auth, or change behavior for the auth service.
The current local gateway remains shared.

A method contains request fields, declarative metadata, and one private bound-client attribute. It
does not build requests, decode responses, perform I/O, authenticate, retry, route services, or
generate endpoint-specific client methods. No concrete endpoint method ships in this package.

## Request construction

`RpcRequestBuilder` reads the method's `__service__`, `__api_method__`, and `__http_method__` once. It
requires a real `ServiceName` and non-empty operation and HTTP method strings, dumps only Pydantic
fields with alias-free names in JSON mode and `exclude_unset=True`, passes the value through one
`RequestValuePreparer`, calls the configured `json_dumps` exactly once, requires a `str`, and
encodes it once as UTF-8.

An unset field is absent from the JSON object, while an explicitly supplied field whose value is
`None` remains JSON `null`. `RequestValuePreparer` recursively copies JSON primitives,
string-keyed mappings, lists, and tuples; converts `Enum` through `.value`; and handles nested
Pydantic models with the same alias-free, `exclude_unset=True` policy. Unsupported values raise
`TypeError` rather than being stringified.

The result is one immutable transport-ready value:

```python
RpcRequest(
    service=method.__service__,
    operation=method.__api_method__,
    http_method=method.__http_method__,
    url=api_server.api_url(method.__api_method__),
    content=serialized.encode("utf-8"),
)
```

Service and operation remain explicit. Neither is inferred from the other or reconstructed from the
URL. Client context, auth, headers policy, timeout, retries, response data, routing metadata,
generic context, and HTTP framework objects do not enter this value.

## Session and response handling

`BaseSession` is an orchestration contract. It composes one `RpcRequestBuilder` and one
`BaseResponseHandler`, resolves the effective timeout in its concrete `__call__()`, and delegates to
the adapter's `make_request()`. It does not own `APIServer`, JSON functions, request preparation,
response decoding, status mapping, service identity policy, authentication, or retries.

`HttpxSession` is the concrete composition point for `APIServer`, JSON encoder/decoder,
`RpcRequestBuilder`, `ApplicationResponseHandler`, and its internal HTTPX client. After receiving an
`httpx.Response`, it keeps that object inside the adapter and passes only method, explicit service,
explicit operation, status code, and response text to `BaseResponseHandler.handle()`.

There is no buffered status/body response class, renamed wrapper, or session response-parser API.

`BaseResponseHandler` defines the response-protocol strategy contract.
`ApplicationResponseHandler` implements the fixed public `ApplicationResponse` protocol: it decodes
with configured `json_loads`, validates `ApplicationResponse[JsonValue]`, interprets failed status
responses, checks successful status consistency, and validates the method-declared result with the
bound client in Pydantic context.

Every JSON operation uses this frozen wire envelope:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure requires both error fields and forbids a result. A
successful envelope-level `None` crosses the typed boundary only when the method's declared result
annotation accepts `None`.

Decoder, envelope-validation, and result-validation failures become `ClientDecodeError`. A failed
envelope raises a status-specific `PokerlostAPIError` and preserves its method, `ServiceName`,
operation, HTTP status, exact `error`, and exact `error_message`. A successful envelope with a
non-2xx status raises `PokerlostProtocolError`.

HTTPX timeout failures become `ClientTimeoutError`; other HTTPX transport failures become
`ClientConnectionError`. Causes are preserved. Public errors never include request or response
bodies, headers, cookies, credentials, or tokens.

## Enums and OpenAPI metadata

Every SDK-owned enum lives under `pypokerlost.enums`:

```python
from pypokerlost.enums import AccessRole, ServiceName
```

`AccessRole` contains `PUBLIC`, `USER`, `SUPPORT`, `MASTER`, and `AUTO`. `ServiceName` contains
`ACCOUNTS` and `AUTH`.

Service-side OpenAPI metadata uses the immutable `RpcOpenApiExtra` value:

```python
from pypokerlost.enums import AccessRole, ServiceName
from pypokerlost.openapi import RpcOpenApiExtra

openapi_extra = RpcOpenApiExtra(
    service=ServiceName.ACCOUNTS,
    access=(AccessRole.AUTO, AccessRole.MASTER),
).as_dict()
```

The result is a fresh JSON-compatible dictionary on every call, preserving role order:

```python
{
    "x-pokerlost": {
        "contract_version": 1,
        "service": "accounts",
        "access": ["auto", "master"],
    },
}
```

This metadata does not import FastAPI, authorize callers, reject role combinations, infer services,
fetch or parse OpenAPI, or generate methods.

## Explicit non-goals

The current package has no authentication implementation or placeholder, token storage, refresh,
authorization injection, login during startup, retry behavior, streaming API or placeholder,
concrete Pokerlost methods, endpoint wrappers, multi-service routing, SDK settings, environment
loading, WebSocket/update processing, OpenAPI generator, or committed test suite.

`PokerlostUnauthorizedError` only classifies a failed response; it triggers no authentication,
refresh, retry, or token mutation. `ServiceName.AUTH` only identifies the service.

Future real accountsService and authService contracts may motivate ordinary method classes and
separate product decisions. They do not change the current transport or lifecycle contracts by
implication.

## Quality checks

```bash
uv lock --check
uv run ruff format .
uv run ruff check --fix .
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv build
python -m compileall -q pypokerlost
git diff --check
```

This stage uses temporary task-specific smoke checks rather than a committed test suite. Wheel and
source-distribution contents are also inspected so removed modules are not packaged.

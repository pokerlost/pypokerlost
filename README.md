# pypokerlost

`pypokerlost` is the asynchronous Python SDK foundation for Pokerlost. It combines a small
`Application` lifecycle coordinator, a central asynchronous `Client`, typed RPC method objects,
request preparation, a pluggable session, and one fixed application-response protocol.

The package currently has no concrete Pokerlost operations. It is ready for later accountsService
and authService method classes without another client, session, request, response, or lifecycle
redesign.

Before development, read [`AGENTS.md`](AGENTS.md), [`SERVICE.md`](SERVICE.md), and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Installation

Install the distribution with the package manager used by the consuming project:

```bash
uv add pypokerlost
# or
python -m pip install pypokerlost
```

Python 3.13 or newer is required.

## Development setup

From the repository root:

```bash
uv sync --locked --all-groups
```

The distribution and import package are both named `pypokerlost`; runtime code lives directly in
`pypokerlost/` without a `src/` directory.

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
    account = await GetAccountMethod(account_id=account_id)


application.run(main)
```

While the application is active, its client is task-local and methods can be awaited without
`.as_(client)`. `Application.run()` owns an event loop through `asyncio.run()` and temporarily
handles `SIGINT` and `SIGTERM` where the running loop supports signal handlers. A handled signal
cancels the entrypoint, waits for lifecycle and session cleanup, removes the temporary handlers,
and makes `run()` return `None`.

In an already-running caller-owned loop, use `run_async()`; it never registers process signal
handlers:

```python
result = await application.run_async(main)
```

Direct application scope returns the managed client:

```python
async with application as client:
    result = await method
```

Every `PokerlostMethod` also supports the same explicit execution forms:

```python
result = await client(method)
result = await client.make_request(method)
result = await method.as_(client)
```

The client-call forms execute through that exact client and delegate through its session without
mutating the caller's method. `.as_(client)` explicitly binds an individual method and overrides
any task-local client. `.as_(None)` clears that explicit binding and restores ambient fallback.
Resolution is therefore explicit binding, task-local current client, then `ClientContextError`.
Outside an application/client scope, an implicitly awaited unbound method raises that error.

For manual lifecycle, `Client` is an async context manager:

```python
async with client:
    result = await method
```

The default `HttpxSession` can also start lazily on the first request. If it is used without an
application or context manager, the caller remains responsible for `await client.stop()`.

Entering one `Application` or one `Client` concurrently or recursively raises its focused state
error. Entry failure resets state and unwinds entered contexts; normal failure and cancellation run
the same cleanup. Sequential reuse is supported.

The current client is scoped with `ContextVar`: nested client scopes restore the outer client,
independent concurrent tasks can use different clients, and child tasks inherit the client current
when they are created. Explicit `.as_(client)` still wins over inherited context. A background task
must not outlive the application/client scope whose session it uses. Constructing `Client()` does
not install it as current; neither do direct `start()` and `stop()` calls.

## Application lifecycle

`Application` accepts one async context-manager callable named `lifecycle`; there are no separate
lifecycle callback lists:

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

The exact entry order is:

```text
reject overlapping application use
→ mark application running
→ start client session
→ install task-local current client
→ enter user lifecycle
→ run caller scope or entrypoint
```

Exit reverses the entered contexts:

```text
exit user lifecycle
→ reset current client
→ stop client session
→ mark application not running
```

Lifecycle setup, the entrypoint, and lifecycle teardown can all use `await method`. Setup failure,
entrypoint failure, and cancellation unwind the same stack. If application code suppresses normal
asyncio task cancellation indefinitely, graceful signal shutdown cannot force it to terminate.
Where loop signal handlers are unsupported, or `run()` is called outside the main thread, execution
continues normally without signal integration.

## Package boundaries

The foundation is split by responsibility:

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

Documentation is kept separately:

```text
docs/
├── ARCHITECTURE.md
└── ADDING_METHODS.md
```

The complete file tree and dependency rules are in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The authoritative procedure for adding a future
operation is [`docs/ADDING_METHODS.md`](docs/ADDING_METHODS.md).

The focused `pypokerlost.methods` facade exports `PokerlostMethod`, `AccountsMethod`, and
`AuthMethod`. The service package facades `pypokerlost.methods.accounts` and
`pypokerlost.methods.auth` export their respective service base.

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

`request/`, `response/`, and `client/session/` do not import `Client`. Explicit client binding
remains a private attribute of the individual method and is passed to future returned Pydantic SDK
models only through result-validation context. Task-local lookup is isolated in
`client/current_client.py` and does not enter the request/response/session pipeline.

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

This minimal non-production adapter shows the required boundary. A real adapter must also own and
close its transport resources and map its transport failures to the appropriate SDK exceptions:

```python
from collections.abc import Awaitable, Callable

from pypokerlost.client.session import BaseSession
from pypokerlost.methods import PokerlostMethod
from pypokerlost.request import RpcRequest, RpcRequestBuilder
from pypokerlost.response import BaseResponseHandler

type SendRequest = Callable[[RpcRequest, int], Awaitable[tuple[int, str]]]


class CustomSession(BaseSession):
    def __init__(
        self,
        *,
        request_builder: RpcRequestBuilder,
        response_handler: BaseResponseHandler,
        send_request: SendRequest,
        timeout: int = 10,
    ) -> None:
        super().__init__(
            request_builder=request_builder,
            response_handler=response_handler,
            timeout=timeout,
        )
        self._send_request = send_request

    async def make_request[ResultT](
        self,
        method: PokerlostMethod[ResultT],
        timeout: int,
    ) -> ResultT:
        request = self.request_builder.build(method)
        status_code, content = await self._send_request(request, timeout)
        return self.response_handler.handle(
            method=method,
            service=request.service,
            operation=request.operation,
            status_code=status_code,
            content=content,
        )

    async def close(self) -> None:
        return None
```

## Method and service metadata

`PokerlostMethod[ResultT]` is a strict Pydantic v2 request model. Its generic metadata contract is:

```python
__service__: ClassVar[ServiceName]
__api_method__: ClassVar[str]
__http_method__: ClassVar[str] = "POST"
__returning__: ClassVar[Any]
```

Accounts and auth methods use focused abstract bases that supply only their service identity:

```python
class AccountsMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.ACCOUNTS


class AuthMethod[ResultT](PokerlostMethod[ResultT]):
    __service__ = ServiceName.AUTH
```

Neither base declares `__api_method__`, so neither represents an endpoint. A future concrete method
inherits the appropriate base and declares `__api_method__`, `__returning__`, request fields, and a
non-default `__http_method__` only when required. See
[`docs/ADDING_METHODS.md`](docs/ADDING_METHODS.md) for the mechanical naming, implementation, export,
and verification steps.

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
authorization injection, automatic login during lifecycle entry, retry behavior, streaming API or
placeholder, concrete Pokerlost methods, endpoint wrappers, multi-service routing, SDK settings,
environment loading, WebSocket/update processing, OpenAPI generator, or committed test suite.

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

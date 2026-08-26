# pypokerlost

`pypokerlost` is the asynchronous Python SDK core for PokerLost. Its current foundation combines an
`Application` lifecycle owner, a central asynchronous `Client`, and immutable typed RPC method
objects. Concrete PokerLost operations will be added after their service contracts are
authoritative.

Operations are values executed by `Client`. The current package does not include endpoint-specific
client methods or dynamic endpoint lookup; whether convenience wrappers belong in a later public API
is a deferred product decision.

Before development, read [`AGENTS.md`](AGENTS.md), [`SERVICE.md`](SERVICE.md), and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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

## Create an application

Configure HTTP behavior with `httpx.AsyncClient`, adapt it to the SDK session interface, and give
the resulting client to `Application`:

```python
import httpx

from pypokerlost import Application, Client
from pypokerlost.client.session import HttpxSession

http_client = httpx.AsyncClient(
    base_url="https://accounts.internal",
    timeout=10.0,
    headers={"x-service-name": "accounts-service"},
)
session = HttpxSession(http_client)
client = Client(session)
application = Application(client)


async def main(client: Client) -> None:
    explicit_result = await client(some_method)
    ambient_result = await another_method


application.run(main)
```

Configuration such as base URL, timeout, headers, proxies, TLS, connection limits, and custom
transport remains in `httpx.AsyncClient`; the SDK has no settings model or environment loading.
`Application` owns the automatic lifecycle and task-local current-client scope. `Client` owns its
supplied session, and `HttpxSession` owns and closes its supplied `httpx.AsyncClient`.

`Application.run()` owns the event loop through `asyncio.run()`. In an already-running loop, use
`run_async()` instead:

```python
await application.run_async(main)
```

As another alternative, the application can be used directly as an async scope:

```python
async with application:
    result = await some_method
```

Entering the same application concurrently or reentrantly raises `ApplicationStateError`.

## Execute ordinary methods

The same typed method object supports explicit and context-resolved execution:

```python
result = await client.make_request(method)
result = await client(method)
result = await method.execute(client)
```

`Client.__call__()` delegates to `make_request()`. `Application` installs its client as current, so
`await method` resolves it inside the application entrypoint or direct async scope.

Manual lifecycle and task-local scope remain available:

```python
await client.start()
try:
    with client.as_current():
        result = await method
finally:
    await client.stop()
```

`Method.__await__()` delegates to `execute()`. Calling `await method` without a current client
raises `ClientContextError`. Requests and streams before startup raise `ClientNotStartedError`.
After terminal `stop()`, which is idempotent, they raise `ClientClosedError`. `client.as_current()`
changes only the `ContextVar`, and `Client` is deliberately not an async context manager.

## Stream content

Streaming operations use `StreamMethod` and an explicit resource scope:

```python
async with client.stream_content(stream_method) as content:
    async for chunk in content:
        process(chunk)
```

`StreamMethod` is not awaitable. A successful body is not pre-buffered, and the stream is closed
when the context exits after normal completion, early iteration exit, or an exception.

## Define future methods

No concrete endpoint is included yet. Once an operation contract is authoritative, its method is a
frozen Pydantic model with declarative class metadata and request fields:

```python
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pypokerlost import Method


class Account(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID


class GetAccount(Method[Account]):
    __api_method__ = "accounts.get"
    __http_method__ = "POST"
    __returning__: ClassVar[Any] = Account

    account_id: UUID
```

An operation identifier follows `namespace.method`, giving the standard relative path
`/{namespace}.{method}`. The HTTP method defaults to `POST` and can be overridden as class metadata.
Method fields contain request data only; methods do not build HTTP requests, parse responses,
perform I/O, refresh credentials, or retry.

`RequestBuilder` reads the operation and HTTP method metadata once, serializes the model once with
normal alias-free Pydantic JSON serialization, and stores the UTF-8 bytes in `PreparedRequest`.
The prepared value also retains the operation explicitly; later layers never reconstruct it from
the path. Per-operation omitted-field versus explicit-`null` behavior will be chosen from real
operation contracts rather than imposed as an SDK-wide policy now.

## Response contract

Handled JSON operations use the frozen `ApplicationResponse[ResultT]` wire contract:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure requires both error fields and forbids a result.
`ResponseHandler` first uses one reusable adapter for `ApplicationResponse[JsonValue]`. A valid
failure becomes `ApplicationError` with the service's public error data unchanged. For a success,
the result is then validated separately against the method's declared return type. Validation
failures become `ResponseDecodeError`; `None` therefore succeeds only for a method whose declared
result type accepts it.

HTTP status remains available as diagnostic metadata. Interpretation of status/envelope
combinations is deferred until real service behavior establishes it. Public exception messages do
not contain request bodies, authorization values, or raw/full response bodies.

## OpenAPI metadata

Services can import the shared helper without depending on FastAPI:

```python
from pypokerlost.openapi import AccessRole, rpc_openapi_extra

extra = rpc_openapi_extra(
    access=(AccessRole.MASTER, AccessRole.AUTO),
)
```

The result is a fresh plain dictionary that preserves the supplied roles:

```python
{
    "x-pokerlost": {
        "access": ["master", "auto"],
    },
}
```

`AccessRole` also includes `public`, `user`, and `support`. The helper produces metadata only; it
does not import FastAPI, authorize callers, reorder roles, or validate combinations as business
policy.

## Deferred decisions

The first real accountsService and authService methods will provide evidence for:

- one-service or multi-service routing and URL mapping;
- authentication state, authorization placement, and token refresh;
- any future SDK-level timeout, header, proxy, TLS, pool, retry, or environment policy;
- per-operation omitted-field versus explicit-`null` encoding;
- HTTP-status interpretation and streaming error bodies;
- endpoint wrappers, a synchronous SDK facade, WebSocket/update behavior, and other convenience
  APIs.

These are open product decisions, not permanent prohibitions in the current SDK. Ownership and
`Application`/`Client` lifecycle are fixed current behavior. Authentication is not implemented and
there are no auth middleware hooks, context bags, SDK settings, or environment-based configuration.
Future accounts and auth operations remain ordinary typed method and result classes.

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

The current stage uses task-specific shell smoke checks rather than a committed test suite.

## Current scope

Included now:

- an application-level owner for automatic client lifecycle and task-local execution scope;
- a lifecycle-aware asynchronous client owning one supplied session;
- explicit and task-local ordinary method execution;
- separate session, request-building, and response-handling responsibilities;
- resource-scoped content streaming;
- single-pass byte serialization with explicit operation metadata and declared-result validation;
- shared `ApplicationResponse` and minimal `x-pokerlost.access` contracts;
- a small SDK exception hierarchy.

The current package does not add concrete PokerLost endpoints, authentication, routing, retries,
SDK settings, WebSocket processing, endpoint wrappers, or a test suite. Session, request, response,
and HTTP-adapter layers do not receive `Client`.

# pypokerlost

`pypokerlost` is the asynchronous Python SDK core for PokerLost. Its current foundation combines a
central `Client` facade with immutable typed RPC method objects. Concrete PokerLost operations will
be added after their service contracts are authoritative.

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

## Create a client

Configure HTTP behavior with `httpx.AsyncClient`, then adapt it to the SDK session interface:

```python
import httpx

from pypokerlost import Client
from pypokerlost.client.session import HttpxSession

http_client = httpx.AsyncClient(
    base_url="https://accounts.internal",
    timeout=10.0,
    headers={"x-service-name": "accounts-service"},
)
session = HttpxSession(http_client)
client = Client(session)
```

Configuration such as base URL, timeout, headers, proxies, TLS, connection limits, and custom
transport remains in `httpx.AsyncClient`. When finished, explicitly call `await client.close()`;
`Client` delegates that call to its session. Broader ownership and shared-session semantics are not
yet a product contract.

## Execute ordinary methods

The same typed method object supports explicit and context-resolved execution:

```python
result = await client.make_request(method)
result = await client(method)
result = await method.execute(client)
```

`Client.__call__()` delegates to `make_request()`. Ambient execution is opt-in through an explicit
task-local scope:

```python
try:
    with client.as_current():
        result = await method
finally:
    await client.close()
```

`Method.__await__()` delegates to `execute()`. Calling `await method` without a current client raises
`ClientContextError`. The SDK currently assigns no lifecycle behavior to `async with client`.

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

`RequestBuilder` converts the method with ordinary Pydantic JSON-mode serialization. Per-operation
omitted-field versus explicit-`null` behavior will be chosen from real operation contracts rather
than imposed as an SDK-wide policy now.

## Response contract

Handled JSON operations use the frozen `ApplicationResponse[ResultT]` wire contract:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure requires both error fields and forbids a result.
`ResponseHandler` validates the envelope against the method's declared result type. Validation
failures become `ResponseDecodeError`, a valid failed envelope becomes `ApplicationError` with the
service's public error data unchanged, and a valid successful envelope returns its result.
An envelope-level `None` remains valid and is checked against the method's declared result
annotation before it is returned.

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
- session and HTTP-client ownership or sharing;
- start/stop, async context, reentrancy, and WebSocket lifecycle;
- timeout, headers, proxy, TLS, pool, retry, and environment policy;
- per-operation omitted-field versus explicit-`null` encoding;
- HTTP-status interpretation and streaming error bodies;
- endpoint wrappers, a synchronous facade, and other convenience APIs.

These are open product decisions, not permanent prohibitions in the current SDK.

## Quality checks

```bash
uv lock --check
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

- a thin asynchronous client facade over a supplied session;
- explicit and task-local ordinary method execution;
- separate session, request-building, and response-handling responsibilities;
- resource-scoped content streaming;
- typed method serialization and declared-result validation;
- shared `ApplicationResponse` and minimal `x-pokerlost.access` contracts;
- a small SDK exception hierarchy.

The current package does not add concrete PokerLost endpoints, authentication, routing, retries,
WebSocket processing, endpoint wrappers, or a test suite.

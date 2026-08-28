# Transport objects

The transport API exposes focused request, response, and session contracts without exposing the
full `Client` to lower layers.

## Public imports

```python
from pypokerlost.client.request import Request, RequestBuilder, RequestOptions
from pypokerlost.client.response import BaseResponseHandler, Response, ResponseHandler
from pypokerlost.client.session import DEFAULT_TIMEOUT, BaseSession, HttpxSession
```

`Response` is also re-exported from the package root. `APIServer` has its own focused module and is
documented in the [API server guide](api-server.md).

## Request

`Request` is a frozen, strict, extra-forbid Pydantic model:

```text
Request(
    *,
    method: APIOperation,
    http_method: HTTPMethod,
    data: dict[str, JSONValue],
    headers: tuple[tuple[str, str], ...] = (),
)
```

It is transport-independent: it carries no URL, serialized bytes, HTTPX object, client, storage,
or generic context bag.

`RequestBuilder()` takes no constructor collaborators. Its public operation is:

```python
request = RequestBuilder().build(method, options=options)
```

The builder validates method metadata, performs the standard JSON-mode model dump, adds default
JSON headers, and returns `Request`. URL construction and encoding belong to `HttpxSession`.

## RequestOptions

`RequestOptions` is a frozen strict model containing immutable ordered headers:

```python
from pypokerlost.client.request import RequestOptions

options = RequestOptions().with_headers(
    {
        "X-Trace-ID": "trace-123",
    },
)
```

`with_headers()` returns a new options object and replaces existing names case-insensitively.
Middleware is the public integration point for options; the top-level `Client` call does not accept
them directly.

## Response

`Response[ResultT]` represents the fixed wire envelope:

```text
Response(
    *,
    ok: bool,
    result: ResultT | None = None,
    error: str | None = None,
    error_message: str | None = None,
)
```

Success forbids error metadata. Failure forbids a non-null result and requires both error fields.
Extra fields are rejected.

`BaseResponseHandler` defines the synchronous protocol interpretation boundary:

```text
handler.handle(
    *,
    method=method,
    operation="accounts.get",
    status_code=200,
    content=response_text,
)
```

`ResponseHandler(json_loads=...)` is the standard implementation. It validates
`Response[JSONValue]`, maps application/protocol/decode failures, and strictly validates the
method's declared result with client context.

## Sessions

`BaseSession` owns timeout resolution and composes one `RequestBuilder` with one
`BaseResponseHandler`:

```text
BaseSession(
    *,
    request_builder: RequestBuilder,
    response_handler: BaseResponseHandler,
    timeout: int = DEFAULT_TIMEOUT,
)
```

It defines asynchronous `start()`, `make_request()`, `close()`, and async-context behavior.
Concrete sessions implement `make_request()` and `close()`.

`HttpxSession` is the included concrete transport:

```text
HttpxSession(
    *,
    api_server=PRODUCTION,
    json_dumps=...,
    json_loads=...,
    timeout=10,
)
```

It lazily owns one restartable `httpx.AsyncClient`. It builds the URL, serializes request data,
encodes UTF-8 bytes, performs HTTP I/O, and invokes `ResponseHandler`. `close()` releases the
session's HTTPX resource; client owners normally call `Client.stop()` or leave the client async
context instead of closing the session directly.

See the [request and response pipeline](../architecture/request-response-pipeline.md) for execution
order and exact error mapping.

[Documentation index](../index.md)

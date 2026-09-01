# Transport objects

The transport API exposes focused request, response, retry-option, and session contracts without
exposing HTTPX types through public SDK models.

## Public imports

```python
from pypokerlost.client.request import Request, RequestBuilder, RequestOptions
from pypokerlost.client.response import BaseResponseHandler, Response, ResponseHandler
from pypokerlost.client.retry import RetryPolicy
from pypokerlost.client.session import DEFAULT_TIMEOUT, BaseSession, HttpxSession
```

`Response` is also re-exported from the package root. `APIServer` has its own focused module,
documented in `docs/api/api-server.md`.

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
retry state, or generic context bag. Data and headers are hidden from repr; headers are also
excluded from model serialization so authorization values do not leak through ordinary model
inspection.

`RequestBuilder()` takes no constructor collaborators. Its public operations are:

```python
operation, http_method = RequestBuilder().describe(method)
request = RequestBuilder().build(method, options=options)
```

`describe()` validates immutable method metadata before middleware starts. `build()` performs the
standard JSON-mode model dump, adds default JSON headers, and returns `Request`. URL construction
and encoding belong to `HttpxSession`.

## RequestOptions

`RequestOptions` is the one frozen strict per-call transport extension:

```text
RequestOptions(
    *,
    headers: tuple[tuple[str, str], ...] = (),
    retry: RetryPolicy | None = None,
)
```

Headers are ordered, immutable, hidden from repr, and excluded from serialization.
`with_headers()` returns a new options object, replaces existing names case-insensitively, and
preserves the retry policy:

```python
from pypokerlost.client.request import RequestOptions

options = RequestOptions().with_headers(
    {
        "X-Trace-ID": "trace-123",
    },
)
```

The top-level client accepts options explicitly:

```python
result = await client(method, options=options)
```

`retry=None` means one attempt. `RetryPolicy` has no effect unless `RetryMiddleware` is configured;
the complete classification and business-safety boundary are documented in
`docs/api/middleware.md`.

## Response

`Response[ResultT]` represents the universal four-field PokerLost `ApplicationResponse` envelope:

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
Extra fields are rejected. `/oauth.token` follows this same response contract; the token provider
does not accept a raw OAuth2 response or a token-specific envelope.

`BaseResponseHandler` defines the synchronous protocol interpretation boundary:

```text
handler.handle(
    *,
    method=method,
    operation="accounts.getSelf",
    status_code=200,
    content=response_text,
    retry_after=None,
)
```

`ResponseHandler(json_loads=...)` is the standard implementation. It validates
`Response[JSONValue]`, maps application/protocol/decode failures, and strictly validates the
method's declared result with client context. When available, the already validated numeric
`Retry-After` delay is attached as safe exception metadata; raw headers and response data are not.

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
encodes UTF-8 bytes, performs HTTP I/O, parses a response `Retry-After` delta or HTTP date, and
invokes `ResponseHandler`. Invalid `Retry-After` values become `None`; past dates become a zero
delay.

Timeouts use `ClientTimeoutError`; network, proxy, and remote-protocol failures use
`ClientConnectionError`. Local HTTP request, protocol, URL, stream, or configuration failures use
non-retryable `ClientRequestError`. Public failures retain safe operation/status metadata but not
HTTPX objects, raw bodies, authorization values, or sensitive traceback locals. A preparation
failure that occurs before operation metadata is available omits the operation from its safe error
metadata.

`close()` releases the session's HTTPX resource; client owners normally call `Client.stop()` or
leave the client async context instead of closing the session directly. Concurrent start/close
transitions are protected without serializing independent requests.

The client-credentials provider uses one private session specialization solely to encode the
required form body and HTTP Basic header. It reuses the same URL, I/O, Retry-After parsing, and
`ResponseHandler` path rather than exposing another public transport or a service-owned decoder.

See `docs/architecture/request-response-pipeline.md` for execution order and exact error mapping.

See `docs/index.md`.

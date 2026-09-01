# Transport objects

## Public imports

```python
from pypokerlost.client.request import Request, RequestBuilder, RequestOptions
from pypokerlost.client.response import BaseResponseHandler, Response, ResponseHandler
from pypokerlost.client.retry import PokerLostRetryPolicy
from pypokerlost.client.session import DEFAULT_TIMEOUT, BaseSession, HttpxSession
```

## Request and options

`Request` is a frozen strict model containing:

```text
method: APIOperation
http_method: HTTPMethod
content_type: HTTPRequestContentType
data: dict[str, JSONValue]
headers: tuple[tuple[str, str], ...]
```

Data and headers are hidden from repr. Headers are also excluded from ordinary serialization.

`RequestOptions` contains immutable case-insensitively unique headers and
`PokerLostRetryPolicy | None`. Use `with_headers()` to return a new value while preserving other
headers and retry opt-in. Header values admit HTTP field content but reject CR and LF. Caller-owned
collections cannot mutate constructed options.

The generated request media type is authoritative. The current supported values are standard JSON
and form encoding; a per-call `Content-Type` replacement is rejected.

## Session

`BaseSession` owns timeout resolution, one `RequestBuilder`, and one `BaseResponseHandler`.
`HttpxSession` adds an `APIServer`, JSON codecs, deterministic generic form encoding, one
restartable `httpx.AsyncClient`, HTTP I/O, and safe `Retry-After` parsing.

JSON payloads use the configured encoder and UTF-8. Form payloads accept only the generator's
validated string or flat string-array request shape and use UTF-8 URL encoding. There is no
operation-specific transport method.

Timeout, connection, local request, protocol, API, and decode failures retain their established
canonical exception classes. Public failures include safe operation/status metadata only.

## Response

`Response[ResultT]` is the fixed strict PokerLost envelope. `ResponseHandler` decodes JSON,
validates envelope invariants, maps canonical exceptions, and validates the declared result with
the executing client's Pydantic context.

See `docs/architecture/request-response-pipeline.md` and `docs/index.md`.

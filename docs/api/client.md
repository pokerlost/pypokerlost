# Client

`PokerlostClient` is the central asynchronous entry point for typed calls.

## Construction

```python
PokerlostClient(
    session: PokerlostSession | None = None,
    *,
    middleware: Sequence[PokerlostMiddleware] = (),
)
```

The default session is `HttpxSession`. The client adds one `PokerlostRetryMiddleware` when callers
do not supply it and requires retry to remain outermost. At most one retry layer and one
authorization layer may be configured.

```python
from pypokerlost import PokerlostClient
from pypokerlost.middleware import PokerlostAuthorizationMiddleware

business_client = PokerlostClient(
    session=business_session,
    middleware=(authorization_middleware,),
)
```

The dedicated `auth_client` passed to authorization middleware is a separate client without that
middleware.

## Calls and options

```python
async def __call__[ResultT](
    method: PokerlostMethod[ResultT],
    *,
    options: PokerlostRequestOptions | None = None,
) -> ResultT: ...


async def make_request[ResultT](
    method: PokerlostMethod[ResultT],
    *,
    options: PokerlostRequestOptions | None = None,
) -> ResultT: ...
```

`PokerlostRequestOptions` has exactly one field:

```python
from pypokerlost import PokerlostRequestOptions
from pypokerlost.middleware import PokerlostRetryPolicy

options = PokerlostRequestOptions(
    retry_policy=PokerlostRetryPolicy(),
)
```

There is no generic caller metadata or request-header option.

## Lifecycle and context

`start()`, `stop()`, and `async with` own the session lifecycle. Context entry also establishes the
task-local current client used by direct method awaiting. One active client may execute concurrent
calls.

`PokerlostApplication(client, *, lifecycle=...)` wraps this lifecycle. Its
`run_async(entrypoint)` uses an existing event loop; `run(entrypoint)` is the synchronous
signal-aware entrypoint.

## Errors

The root hierarchy is:

```text
PokerlostError
└── PokerlostClientError
    ├── PokerlostConnectionError
    ├── PokerlostTimeoutError
    ├── PokerlostProtocolError
    ├── PokerlostAPIError
    │   ├── PokerlostAuthenticationError
    │   └── PokerlostAuthorizationError
    └── PokerlostConfigurationError
```

`PokerlostAPIError` contains only operation, status code, stable error, optional safe message, and
optional body retry delay. No canonical exception stores request or response bodies.

See `docs/architecture/client-lifecycle.md`, `docs/api/transport.md`, and `docs/index.md`.

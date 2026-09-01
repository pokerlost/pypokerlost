# Client

`Client` is the central asynchronous entry point for executing typed PokerLost methods and owning
their session, storage, immutable outbound middleware, and task-local context.

## Import and construction

Import the complete client from the package root:

```python
from pypokerlost import Client
```

The constructor is:

```text
Client(
    session: BaseSession | None = None,
    storage: BaseStorage | None = None,
    middleware: Sequence[APIMiddleware] | None = None,
)
```

- `session` defaults to `HttpxSession`;
- `storage` defaults to `MemoryStorage`;
- `middleware` accepts an ordered sequence of `APIMiddleware` components.

The client copies middleware into one immutable tuple at construction. It has no
`add_middleware()` or mutable registry; create another target-specific client when composition
must differ. The selected resources are available as `client.session` and `client.storage`, and
`client.middleware` returns the configured tuple.

## Async context manager

Use an async context manager for normal resource ownership:

```python
from pypokerlost import Client, PokerlostMethod


async def execute[ResultT](method: PokerlostMethod[ResultT]) -> ResultT:
    async with Client() as client:
        return await client(method)
```

Context entry starts storage, session, and middleware in registration order, then installs the
client in the current task. Context exit restores the previous current client and closes middleware
in reverse registration order, followed by the session and storage. Any partial startup failure
unwinds resources that already started.

Overlapping async-context entry on the same instance raises `ClientStateError`. This lifecycle
guard does not serialize concurrent calls made through an active client.

## Explicit lifecycle

The manual lifecycle pair is `start()` and `stop()`:

```python
from pypokerlost import Client


async def manage_client() -> None:
    client = Client()
    await client.start()
    try:
        ...
    finally:
        await client.stop()
```

`Client` does not define `close()`. Calling `start()` without entering the async context also does
not install the task-local current client. `stop()` attempts every registered cleanup in reverse
ownership order.

## Executing methods

The two execution entry points are equivalent:

```python
result = await client(method)
result = await client.make_request(method)
```

Both accept an optional request timeout and keyword-only `RequestOptions`:

```python
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.retry import RetryPolicy

result = await client(
    method,
    request_timeout=5,
    options=RequestOptions(
        retry=RetryPolicy(max_attempts=3),
    ),
)
```

No options means one transport attempt. Supplying a retry policy has an effect only when the
client contains `RetryMiddleware`; safe retry classification belongs to the caller and is
documented in `docs/api/middleware.md`.

Before middleware runs, the client creates a deep semantic snapshot by dumping the method's
explicitly supplied fields and validating a fresh instance of the same method type. The snapshot
is bound to the executing client and reused for every retry attempt. Middleware cannot access or
replace it, and later mutation of caller-owned method input cannot change an in-flight payload.

The semantic snapshot, operation, and HTTP method are validated before entering middleware. Those
failures do not enter the retry chain; later local request serialization failures propagate
without retry because they are not retryable SDK transport/status exceptions.

Inside an active client or application context, an unbound method can resolve the task-local
client:

```python
async def execute_current(method):
    async with client:
        return await method
```

Outside such a context, use `await client(method)` or `await method.as_(client)`. Awaiting a method
with neither an explicit nor current client raises `ClientContextError`.

## Middleware and storage

The first configured middleware is outermost. A service-authenticated client normally uses:

```python
from pypokerlost import Client
from pypokerlost.client.auth import AccessTokenProvider
from pypokerlost.client.session import BaseSession
from pypokerlost.middleware import BearerTokenMiddleware, RetryMiddleware


def create_client(session: BaseSession, token_provider: AccessTokenProvider) -> Client:
    return Client(
        session=session,
        middleware=(
            RetryMiddleware(),
            BearerTokenMiddleware(token_provider),
        ),
    )
```

This order lets every bounded retry attempt resolve bearer credentials again while the provider
reuses a still-valid process-local token. Authentication, retry, and custom middleware contracts
are owned by `docs/api/middleware.md`.

Storage is client-local and independent of transport:

```python
async def use_storage(client: Client) -> None:
    await client.storage.set("example", {"ready": True})
    value = await client.storage.get("example")
```

See `docs/api/storage.md` for its complete public contract.

## Application integration

`Application` adds one optional user lifecycle around a required client:

```python
from pypokerlost import Application, Client


async def main(client: Client) -> None: ...


Application(Client()).run(main)
```

`run()` owns a new event loop and supported process-signal handling. Use `await run_async(...)`
when the caller owns the running event loop. See `docs/architecture/client-lifecycle.md` for
ordering and cancellation behavior.

See `docs/index.md`.

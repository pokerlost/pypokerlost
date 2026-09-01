# Client

`Client` is the central asynchronous entry point for executing generated PokerLost methods.

## Construction and lifecycle

```python
from pypokerlost import Client

client = Client(session=session, storage=storage)
```

Both constructor arguments are optional. They default to `HttpxSession` and `MemoryStorage`.
Normally a service owns one target-specific client in its application lifespan:

```python
async with client:
    result = await client(method)
```

Manual `await client.start()` and `await client.stop()` are also available.

## Calls and options

The two execution forms are equivalent:

```python
result = await client(method)
result = await client.make_request(method)
```

They accept an optional request timeout and keyword-only `RequestOptions`:

```python
from pypokerlost.client.request import RequestOptions
from pypokerlost.client.retry import PokerLostRetryPolicy

options = RequestOptions(
    headers=(("Authorization", "Bearer <resolved-token>"),),
    retry=PokerLostRetryPolicy(),
)
result = await client(method, request_timeout=5, options=options)
```

Retry remains explicit and is suitable only for a call whose business contract is replay-safe.

The client captures a deep method snapshot and transport metadata before execution. It performs no
credential lookup or token lifecycle work. A service-owned adapter supplies any already-resolved
authorization header through generic options.

## Current-client context

Inside an active client or `Application` context, an unbound method can resolve the task-local
client. Outside that context, use `await client(method)` or `await method.as_(client)`. Missing both
bindings raises `ClientContextError`.

See `docs/api/transport.md`, `docs/api/retry.md`, and
`docs/architecture/client-lifecycle.md`.

See `docs/index.md`.

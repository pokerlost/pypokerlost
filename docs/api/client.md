# Client

`Client` is the central asynchronous entry point for executing typed PokerLost methods and owning
their session, storage, middleware, and task-local context.

## Import and construction

Import the complete client from the package root:

```python
from pypokerlost import Client
```

The `pypokerlost.client` namespace groups focused transport modules but does not re-export
`Client` itself.

```python
Client(
    session=None,
    storage=None,
    middleware=None,
)
```

- `session` accepts a `BaseSession`; the default is `HttpxSession`.
- `storage` accepts a `BaseStorage`; the default is `MemoryStorage`.
- `middleware` accepts a sequence of `BaseMiddleware` components. The client copies the sequence
  into its own ordered list.

The selected resources are available as `client.session` and `client.storage`.
`client.middleware` returns an immutable tuple snapshot.

## Async context manager

Use an async context manager for normal resource ownership:

```python
from pypokerlost import Client, PokerlostMethod


async def execute[ResultT](method: PokerlostMethod[ResultT]) -> ResultT:
    async with Client() as client:
        return await client(method)
```

Context entry starts storage, starts the session, and installs the client in the current task.
Context exit restores the previous current client, closes the session, and then closes storage.
Overlapping context entry on the same instance raises `ClientStateError`.

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
not install the task-local current client.

Startup order is storage then session. If session startup fails, the client closes the started
storage before re-raising. `stop()` attempts session close and storage close in that order.

## Executing methods

The two client entry points are equivalent:

```text
result = await client(method)
result = await client.make_request(method)
```

Both accept an optional integer `request_timeout`:

```text
result = await client(method, request_timeout=5)
```

The client copies the method and binds the copy before execution. It does not replace an explicit
binding on the caller's original method.

Inside an active client or application context, an unbound method can resolve the task-local client:

```python
async def execute_current(method):
    async with client:
        return await method
```

Outside such a context, use `await client(method)` or `await method.as_(client)`. Awaiting a method
with neither an explicit nor current client raises `ClientContextError`.

`RequestOptions` is not an argument to `Client.__call__()` or `Client.make_request()`. Middleware
owns per-request option propagation.

## Middleware and storage

`add_middleware(component)` appends one component and returns the client. Constructor middleware
remains first, and the first configured component is the outermost wrapper. Each request uses a
snapshot, so later registration does not alter an already-running chain.

Storage is client-local and independent of transport:

```python
async def use_storage(client: Client) -> None:
    await client.storage.set("example", {"ready": True})
    value = await client.storage.get("example")
```

See [middleware](middleware.md) and [storage](storage.md) for their complete public contracts.

## Application integration

`Application` adds one optional user lifecycle around a required client:

```python
from pypokerlost import Application, Client


async def main(client: Client) -> None: ...


Application(Client()).run(main)
```

`run()` owns a new event loop and supported process-signal handling. Use `await run_async(...)`
when the caller owns the running event loop. See [client lifecycle](../architecture/client-lifecycle.md)
for ordering and cancellation behavior.

[Documentation index](../index.md)

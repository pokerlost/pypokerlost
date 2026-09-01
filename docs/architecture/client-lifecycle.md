# Client lifecycle

This page explains how `Client` and `Application` start, expose, and reliably release their owned
resources.

## Client ownership

Each `Client` owns exactly one asynchronous session, one asynchronous storage backend, and one
immutable ordered middleware tuple. The defaults are `HttpxSession` and `MemoryStorage`; injected
resources and middleware follow the same lifecycle.

Direct startup order is:

```text
storage.start()
→ session.start()
→ middleware[0].start()
→ middleware[1].start()
→ ...
```

Any startup failure closes every earlier resource before re-raising the original failure. Direct
shutdown through `Client.stop()` reverses ownership order:

```text
...
→ middleware[1].close()
→ middleware[0].close()
→ session.close()
→ storage.close()
```

Every close operation is attempted. `Client` has no `close()` method; its explicit lifecycle pair
is `start()` and `stop()`.

For the canonical authenticated tuple, `RetryMiddleware` has no resource of its own and
`BearerTokenMiddleware` starts and closes its `AccessTokenProvider`. The standard
`ClientCredentialsTokenProvider` owns a dedicated token session and its process-local cache.
Closing it cancels and awaits any in-flight acquisition and clears token-bearing cache/task
references. A later `get_access_token()` fails with `ClientStateError` until `start()` makes the
provider reusable.

## Target-specific ownership

A long-running service constructs one client for each real outbound target, starts it in the
application lifespan, stores it in an explicitly typed resource field, and reuses it for concurrent
requests. Shutdown stops that client before resources on which its surrounding composition
depends.

Do not create a client, token provider, or transport per request. Do not use a module-global client,
string-keyed service locator, direct HTTP fallback, or placeholder client for a service with no real
target.

Remote execution remains outside a request-owned database transaction. Token acquisition, the
protected operation, and retry sleep can all await; none belongs inside a transaction context.
Business workflow persistence and reconciliation remain service-owned rather than client lifecycle
work.

## Async context management

The preferred lifecycle is an async context manager:

```python
from pypokerlost import Client


async def use_client() -> None:
    async with Client() as client:
        # Session, storage, and middleware are active here.
        ...
```

Context entry starts storage, session, and middleware in registration order, then installs the
client as the task-local current client. Context exit first restores the previous current-client
token, then closes middleware in reverse order, the session, and storage. A setup failure or
cancellation unwinds every resource that was successfully entered.

The same `Client` instance cannot have two overlapping async-context entries; an attempted second
entry raises `ClientStateError`. This lifecycle guard does not serialize independent method requests
made through an already-active client.

Manual lifecycle remains available when an async context manager is unsuitable:

```python
from pypokerlost import Client


async def run_manually() -> None:
    client = Client()
    await client.start()
    try:
        ...
    finally:
        await client.stop()
```

Calling `start()` alone does not install a task-local current client. Use explicit
`await client(method)` execution, or enter the client context before awaiting an unbound method.

## Explicit and task-local client binding

`PokerlostType` owns an optional private client binding. Client resolution follows this order:

1. an explicit or Pydantic-validation-context binding;
2. the current client stored in the current task context;
3. `ClientContextError` when neither exists.

Calling `method.as_(client)` binds that exact method instance and returns it, so
`await method.as_(client)` is valid. By contrast, `await client(method)` reconstructs and binds a
deep semantic snapshot for execution, leaving the caller's reusable instance unchanged.

Task-local state uses one `ContextVar`. Nested client contexts restore the outer client exactly,
and separately created tasks inherit normal Python context-variable semantics.

## Application ownership

`Application` coordinates one client and one caller-supplied async-context-manager lifecycle. It
requires a `Client`; it does not create one implicitly.

Application entry proceeds as follows:

```text
Client context
→ user lifecycle
→ application entrypoint
```

Exit reverses that order. The user lifecycle leaves before the client resets its current-client
context and closes middleware, transport, and storage resources. Re-entering an already running
application raises `ApplicationStateError`.

`Application.run_async()` runs on the caller-owned event loop and does not own process signals.
`Application.run()` is the synchronous loop-owning entry point; it uses `asyncio.run()` and handles
supported `SIGINT` and `SIGTERM` shutdown by cancelling the entrypoint and completing cleanup.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pypokerlost import Application, Client


@asynccontextmanager
async def lifecycle(application: Application) -> AsyncIterator[None]:
    # Acquire application-level resources here.
    yield
    # Release them here before the client closes.


async def main(client: Client) -> None: ...


application = Application(Client(), lifecycle=lifecycle)
application.run(main)
```

See `docs/api/client.md` for callable signatures and `docs/api/storage.md` for storage-specific
persistence semantics.

See `docs/index.md`.

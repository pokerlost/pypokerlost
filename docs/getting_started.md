# Getting started

`pypokerlost` is an asynchronous Python SDK library. It provides client and application lifecycle
primitives; it does not run as a standalone process.

## Install a local build

Build the project first, then install its wheel into the active environment:

```bash
python -m pip install dist/pypokerlost-*.whl
```

See [Building distributions](building.md) for the complete local and Docker artifact workflows.

## Create the client and application

Create one `Client` and let `Application` manage its session, storage, and task-local current-client
scope:

```python
from pypokerlost import Application, Client

client = Client()
application = Application(client)
```

The SDK contains no concrete RPC methods. Define service methods from an authoritative contract as
described in [Adding typed methods](adding_methods.md). The examples below assume such a
`GetAccountMethod` is available in the consuming project.

## Run from synchronous code

`Application.run()` owns the event loop and passes the managed client to the entrypoint. Inside the
managed scope, a method can resolve that client implicitly:

```python
from uuid import UUID

from pypokerlost import Application, Client

from my_project.methods import GetAccountMethod


async def main(client: Client) -> None:
    account = await GetAccountMethod(
        account_id=UUID("0195b4aa-7f95-7ef5-a754-4bb0eb3699de"),
    )
    print(account)


application = Application(Client())
application.run(main)
```

Implicit `await method` requires an active `Application` or `Client` context, unless the method was
bound explicitly with `method.as_(client)`.

## Execute explicitly

The client is also callable. This form selects the client at the call site and uses the same RPC
execution path:

```python
async def main(client: Client) -> None:
    account = await client(
        GetAccountMethod(
            account_id=UUID("0195b4aa-7f95-7ef5-a754-4bb0eb3699de"),
        ),
    )
    print(account)
```

Use `await client.make_request(method)` when the more explicit method name improves readability.
Both explicit forms copy and bind the method for execution without changing the caller's method
object.

## Use an existing event loop

Call `run_async()` when the surrounding program already owns the event loop:

```python
result = await application.run_async(main)
```

For direct context management, the client itself is also an asynchronous context manager:

```python
async with Client() as client:
    result = await GetAccountMethod(
        account_id=UUID("0195b4aa-7f95-7ef5-a754-4bb0eb3699de"),
    )
```

## Add a user lifecycle

`Application` accepts one asynchronous context-manager callable for user-owned setup and cleanup.
The managed client is current during lifecycle setup, the entrypoint, and lifecycle teardown:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pypokerlost import Application, Client


@asynccontextmanager
async def lifecycle(application: Application) -> AsyncIterator[None]:
    print("starting application resources")
    try:
        yield
    finally:
        print("closing application resources")


application = Application(Client(), lifecycle=lifecycle)
```

Setup failures, entrypoint exceptions, and cancellation still unwind resources that were entered
successfully. If the user lifecycle deliberately suppresses an exception around `yield`,
`Application` reports that suppression to the surrounding `async with` exactly like a normal async
context manager; `run_async()` then returns `None` because the entrypoint produced no result.

## Graceful shutdown

On supported main-thread event loops, `Application.run()` temporarily handles `SIGINT` and
`SIGTERM`. A handled signal cancels and awaits the entrypoint so the user lifecycle and client-owned
resources can close before `run()` returns. Entrypoint code should cooperate with normal asyncio
cancellation. `run_async()` uses the caller's event loop and does not install process signal
handlers.

## Focused guides

- [Building distributions](building.md)
- [RPC middleware](middleware.md)
- [Client storage](storage.md)
- [Adding typed methods](adding_methods.md)
- [Generating typed methods](generating_methods.md)
- [Architecture](ARCHITECTURE.md)

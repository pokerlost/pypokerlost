# Client lifecycle

Each `PokerlostClient` owns one asynchronous `PokerlostSession`. The default is `HttpxSession`.

## Lifecycle

```python
from pypokerlost import PokerlostClient


async def use_client(client: PokerlostClient) -> None:
    async with client:
        ...
```

`start()` starts the session and `stop()` closes it. Async context entry also installs the client as
the task-local current client; exit restores the previous context before session cleanup. The same
instance cannot have overlapping context entries, but one active instance supports independent
concurrent calls.

A long-running service creates one client per real outbound target in application lifespan,
reuses it, and closes it during shutdown. It creates no target client merely for template symmetry.

## Application owner

`PokerlostApplication(client, *, lifecycle=...)` coordinates one client and an optional async
lifecycle callback.

```python
from collections.abc import Awaitable, Callable

from pypokerlost import PokerlostApplication, PokerlostClient


async def entrypoint(client: PokerlostClient) -> int:
    return 0


application = PokerlostApplication(client)
result = await application.run_async(entrypoint)
```

`run_async()` uses the caller's event loop. `run()` owns a new event loop and supported shutdown
signals; it is the only synchronous lifecycle entrypoint.

## Transaction boundary

Services must not keep a request-owned database transaction open during token acquisition, a
remote attempt, or retry delay. Transport retry does not replace service-owned workflow recovery.

See `docs/api/client.md` and `docs/index.md`.

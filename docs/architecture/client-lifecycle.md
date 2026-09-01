# Client lifecycle

Each `Client` owns one asynchronous session and one asynchronous storage backend. Defaults are
`HttpxSession` and `MemoryStorage`.

Startup order is:

```text
storage.start()
→ session.start()
```

A startup failure closes every earlier resource. Shutdown reverses ownership:

```text
session.close()
→ storage.close()
```

Every registered cleanup is attempted. `Client` has the explicit lifecycle pair `start()` and
`stop()` and also supports `async with`.

```python
from pypokerlost import Client


async def use_client() -> None:
    async with Client() as client:
        ...
```

Context entry installs the client as the task-local current client after resources start. Context
exit restores the prior task-local value before resources close. The same instance cannot have two
overlapping context entries, but an active client supports concurrent independent calls.

A long-running service constructs one client per real outbound target, owns it in application
lifespan resources, and reuses it. Target credentials and token lifecycle state belong to separate
service-owned ports and adapters; they are not client resources.

Remote calls and retry delays remain outside request-owned database transactions.

## Binding and application

`PokerlostType` resolves an explicit or validation-context client first, then the current task-local
client, otherwise raising `ClientContextError`. `await client(method)` executes a bound semantic
snapshot and leaves the caller's method reusable.

`Application` owns one required client plus an optional caller lifecycle. `run_async()` uses the
caller's event loop; `run()` is the sole synchronous loop-owning entry point and handles supported
shutdown signals.

See `docs/api/client.md` and `docs/index.md`.

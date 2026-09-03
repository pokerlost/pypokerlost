# Client lifecycle

Each `PokerlostClient` owns or receives one asynchronous session. `start()` and `stop()` manage it;
the async context also installs a task-local current client.

```python
async with PokerlostClient(server=primary_server) as client:
    result = await Method(...)

    async with PokerlostClient(server=other_server) as local_client:
        other = await local_client(OtherMethod(...))
```

Contexts do not mutate methods. A long-running service composes only the outbound clients it really
uses and closes them in lifespan. It must not hold a request-owned database transaction while
refresh coordination, network I/O, or retry delay is in progress.

`PokerlostApplication` remains the sole synchronous event-loop owner for SDK applications.

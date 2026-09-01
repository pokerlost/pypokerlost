# Quickstart

Create an asynchronous `Client`, point its `HttpxSession` at a PokerLost HTTP API, and execute one
typed `PokerlostMethod`.

## Minimal call

The core repository intentionally ships no concrete service methods. `ExampleResult` and
`ExampleMethod` below are small illustrations of the classes normally generated from a service
OpenAPI contract; every import in the example is a real public SDK import.

```python
from __future__ import annotations

import asyncio

from pypokerlost import Client, PokerlostMethod, PokerlostType
from pypokerlost.client.api_server import APIServer
from pypokerlost.client.session import HttpxSession


class ExampleResult(PokerlostType):
    message: str


class ExampleMethod(PokerlostMethod[ExampleResult]):
    __api_method__ = "echo.sendMessage"
    __returning__ = ExampleResult

    message: str


async def main() -> None:
    api_server = APIServer.from_base("http://127.0.0.1:8000")
    session = HttpxSession(api_server=api_server)

    async with Client(session=session) as client:
        result = await client(ExampleMethod(message="Hello"))
        print(result.message)


asyncio.run(main())
```

`APIServer.from_base()` appends the API operation to the base URL, so this example sends the
request to `http://127.0.0.1:8000/echo.sendMessage`. The endpoint must return the fixed PokerLost
JSON envelope, and the successful `result` must match `ExampleResult`.

This minimal client has no outbound middleware and makes one transport attempt. A concrete service
that needs service authentication constructs one lifespan-owned target client with
`ClientCredentialsTokenProvider`, `RetryMiddleware`, and `BearerTokenMiddleware` in the order
documented in `docs/api/middleware.md`. Retry remains disabled until a replay-safe call explicitly
passes `RequestOptions(retry=RetryPolicy(...))`.

## Generated service packages

For a generated service, replace the illustrative classes with the service package exports. The
generator keeps request methods and returned API objects in separate namespaces:

```text
pypokerlost/methods/<service_package>/  request method classes
pypokerlost/types/<service_package>/    returned and nested API object types
```

`docs/generator/usage.md` describes contract acquisition and commands. `docs/api/methods.md` covers
explicit binding and implicit current-client execution.

See `docs/index.md`.

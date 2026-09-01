# API target

`PokerlostAPIServer` validates one origin root and builds `/<operationId>` URLs.

## Import and construction

```python
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.types import PokerlostOperation

api_server = PokerlostAPIServer("https://accounts.example.internal")
url = api_server.operation_url(PokerlostOperation("getBalance"))
```

The dataclass constructor signature is:

```python
PokerlostAPIServer(base_url: str)
```

The URL must identify an origin root. User information, a non-root path, query, and fragment are
rejected. A trailing slash is normalized away.

Production and other non-loopback targets must use HTTPS. Plain HTTP is accepted only for
`localhost`, `127.0.0.1`, or `::1` development targets.

## Session composition

```python
from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.session import HttpxSession

session = HttpxSession(
    api_server=PokerlostAPIServer("https://accounts.example.internal"),
    timeout=10.0,
)
client = PokerlostClient(session=session)
```

`PokerlostAPIServer` owns URL validation only. It performs no discovery, routing, I/O,
authorization, or retry.

See `docs/api/transport.md` and `docs/index.md`.

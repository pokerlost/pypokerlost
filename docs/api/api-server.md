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
PokerlostAPIServer(base_url: str, service_id: ServiceId | None = None)
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

## Gateway migration

Direct service-origin mode remains the default (`service_id=None`), preserving existing callers.
For a gateway origin, select a registered identity explicitly:

```python
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.enums import ServiceId

target = PokerlostAPIServer("https://gateway.example.invalid", service_id=ServiceId.ACCOUNTS)
```

Both modes call `POST /<operation>` without service prefixes. The transport adds
`x-pokerlost-serviceId: accountsService` only in gateway mode, including public calls.
Values are case-sensitive; HTTP field names are case-insensitive. Routing identifiers are not
credentials or audiences/scopes and do not change token handling. Unknown values fail locally.
The same operation name can target different services; the SDK never infers the service.
There is no arbitrary headers map and routing state never enters the JSON body or token store.

`PokerlostAPIServer` validates the explicit target; the gateway owns allowlisting and upstream
selection. The SDK performs no service discovery or authorization decision.

See `docs/api/transport.md` and `docs/index.md`.

The `0.3.0.dev0` SDK candidate records the layout/tooling migration and opt-in routing API.
It is unreleased; direct-origin behavior remains compatible. Generator `3.1.0` independently
changes the default source output directory to `src/pypokerlost`. No existing ref is removed.

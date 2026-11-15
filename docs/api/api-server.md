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
PokerlostAPIServer(
    base_url: str,
    service_id: ServiceId | None = None,
    environment: Environment | None = None,
)
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

## Explicit environment configuration

`Environment.MAIN`, `DEV`, `TEST` and `LOCAL` are runtime identities, independent of Git refs,
ServiceId, auth audience/scopes and package version. Nothing reads Git, HOME, dotenv or the network
on import. The caller loads its trusted settings (explicit inputs, process variables, an explicitly
chosen config file, then safe defaults) and passes this immutable mapping:

```python
from pypokerlost import Environment, PokerlostClient, PokerlostEnvironmentConfig
from pypokerlost.enums import ServiceId

config = PokerlostEnvironmentConfig(
    Environment.LOCAL,
    {Environment.LOCAL: "http://127.0.0.1:18080"},
)
client = PokerlostClient.for_environment(config, service_id=ServiceId.ACCOUNTS)
```

Remote origins are omitted until explicitly configured; selection raises `not_configured` before
creating a session or making a request. Main/dev/test require HTTPS and distinct origins. Local
requires loopback. A host-side client uses the published loopback port; a container must receive
an explicit loopback sidecar mapping or a valid HTTPS origin in its remote environment. Arbitrary
container hostnames do not gain an HTTP exception. No deployment or DNS record is created here.

Each factory call owns a fresh pool and has no credentials by default. For protected calls, build
`PokerlostAuthenticationMiddleware(..., server=config.server())` for the selected target. A client
rejects an unbound or differently bound middleware before I/O. Persistent token-store and refresher
implementations must use the entire `PokerlostTokenKey`: environment, canonical origin, client
identity, audience and scopes. Keep their database/cache namespaces separate too; do not migrate
legacy tokens into new environment keys automatically. No process-global selected environment exists.

The direct `PokerlostAPIServer(base_url, service_id)` API remains available in legacy explicit-origin
mode. URLs use HTTPX canonicalization, including IDNA ASCII hostnames and default-port removal,
so equivalent Unicode/punycode origins cannot select distinct environments. Malformed ports,
whitespace, control characters and credentials are rejected. Legacy token keys keep their original
three-field serialized representation: unset environment and origin are omitted. Legacy direct clients do not provide isolation between arbitrary origins.
Before using `for_environment`, the consuming owner must migrate persistence to full namespaced
keys and acquire explicitly scoped state carrying its exact key provenance. The SDK rejects
unbound legacy state and mismatched refreshed state before sending their tokens; it never falls
back to old records or adds this local metadata to RPC JSON. See
[header authentication](header-authentication.md) for the storage contract.

The native `0.4.0.dev0` metadata identifies this environment API integration; it does not allocate
or publish a release. Automatic CI and the full `make check` gate remain enabled.

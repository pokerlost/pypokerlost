# pypokerlost

Typed asynchronous Python SDK for Pokerlost's private body-only JSON protocol over HTTPS.

The SDK provides flat typed methods and types, one response envelope, body-only authorization,
middleware-based retry, and OpenAPI generation. It does not expose caller-supplied HTTP headers or
claim compatibility with a standard token wire protocol.

## Requirements

- Python 3.14 or newer
- [`uv`](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync --locked --all-groups
```

Build local distributions with `uv build`. See `docs/getting-started/installation.md`.

## Public call

```python
from pypokerlost import PokerlostClient
from pypokerlost.client import PokerlostAPIServer
from pypokerlost.methods import GetToken
from pypokerlost.session import HttpxSession


async def get_service_token() -> None:
    session = HttpxSession(
        api_server=PokerlostAPIServer("https://auth.example.internal"),
    )
    async with PokerlostClient(session=session) as client:
        token = await client(
            GetToken(
                client_id="service-client-id",
                client_secret="loaded-by-the-consumer",
                scopes=("accounts.self.read",),
                audience="accountsService",
            )
        )
        print(token.expires_in)
```

`GetToken` is public at the transport layer and sends credentials inside
`PokerlostRequest.payload`. Protected methods require `PokerlostAuthorizationMiddleware`, which
places the access token only in `PokerlostAuthorizedRequest.authorization.access_token`.

## Documentation

- `docs/index.md`
- `docs/getting-started/quickstart.md`
- `docs/api/client.md`
- `docs/api/transport.md`
- `docs/api/body-authorization.md`
- `docs/api/retry.md`
- `docs/generator/usage.md`
- `docs/project/status.md`

Run `make check` for the regular repository gate and `make check-full` before a release handoff.

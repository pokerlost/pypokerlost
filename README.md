# pypokerlost

Typed asynchronous Python SDK for PokerLost API operations.

## Requirements

- Python 3.14 or newer
- [`uv`](https://docs.astral.sh/uv/)

## Installation

The repository currently documents source development rather than a public package-index release.
From an existing checkout, create the locked development environment:

```bash
uv sync --locked --all-groups
```

Build an installable wheel and source distribution with `uv build`. See
[Installation](docs/getting-started/installation.md) for the supported source and local-wheel flows.

## Quick example

The core repository intentionally contains no concrete service methods. This small illustrative
method uses the same public API as generated code:

```python
from pypokerlost import Client, PokerlostMethod, PokerlostType


class HealthResult(PokerlostType):
    status: str


class HealthMethod(PokerlostMethod[HealthResult]):
    __api_method__ = "health.get"
    __returning__ = HealthResult


async def read_health() -> HealthResult:
    async with Client() as client:
        return await client(HealthMethod())
```

Generated request methods are imported from `pypokerlost.methods.<service_package>`; their returned
and nested API objects are imported from `pypokerlost.types.<service_package>`.

The runtime keeps typed methods, transport requests, response validation, and generated API
objects in separate layers. See the [architecture overview](docs/architecture/overview.md).

## Documentation

- [Documentation index](docs/index.md)
- [Getting started](docs/getting-started/quickstart.md)
- [Architecture](docs/architecture/overview.md)
- [Public API](docs/api/client.md)
- [Generator](docs/generator/usage.md)
- [Development](docs/development/commands.md)

## Development

Run the regular non-mutating repository gate from the project root:

```bash
make check
```

Use `make check-full` before a release or cross-repository handoff.

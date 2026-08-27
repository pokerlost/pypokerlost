# pypokerlost

Asynchronous Python SDK core for typed Pokerlost RPC methods.

## Prerequisites

- Python 3.13 or newer
- `uv` installed and available on `PATH`

## Build from source

Run from the repository root:

```bash
uv lock --check
uv sync --locked --all-groups
uv build
```

The wheel and source distribution are written to `dist/`.

## Documentation

- [Getting started](docs/getting_started.md)
- [Building distributions](docs/building.md)
- [Middleware](docs/middleware.md)
- [Client storage](docs/storage.md)
- [Adding typed methods](docs/adding_methods.md)
- [Generating typed methods](docs/generating_methods.md)
- [Architecture](docs/ARCHITECTURE.md)

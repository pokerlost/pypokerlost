# Installation

Install `pypokerlost` from the repository checkout with Python 3.14 or newer and `uv`; this
repository does not document a public package index or remote Git installation.

## Requirements

You need:

- Python 3.14 or newer;
- `uv` available on `PATH`;
- a local checkout of this repository.

The runtime package depends only on Pydantic and HTTPX. Typer, aiofiles, Ruff, mypy, and pre-commit
are development dependencies managed by the locked environment.

## Synchronize the source environment

Run these commands from the repository root:

```bash
uv lock --check
uv sync --locked --all-groups
```

The sync installs the project from the checkout and includes the development dependency group. A
quick import check is:

```bash
uv run python -c "import pypokerlost; print(pypokerlost.__version__)"
```

## Install a locally built wheel

Build the current package, create an isolated Python 3.14 environment, and install the local wheel:

```bash
uv build
uv venv --python 3.14 build/wheel-check
uv pip install --python build/wheel-check/bin/python \
  dist/pypokerlost-0.2.0-py3-none-any.whl
build/wheel-check/bin/python -c "import pypokerlost; print(pypokerlost.__version__)"
```

`uv build` creates both a wheel and a source distribution under `dist/`. See
`docs/development/building.md` for artifact inspection and the Docker artifact workflow.

See `docs/index.md`.

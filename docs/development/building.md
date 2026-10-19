# Building distributions

The repository builds a wheel and a source distribution for local use; neither the local nor the
Docker workflow publishes artifacts or creates a runtime application image.

## Local build

Validate the lockfile and build both distributions from the repository root:

```bash
uv lock --check
uv build --no-build-isolation
```

The default output directory is `dist/` and contains files matching:

```text
dist/pypokerlost-*.whl
dist/pypokerlost-*.tar.gz
```

## Inspect artifacts

Use Python's standard library for the wheel and `tar` for the source distribution:

```bash
uv run python -m zipfile --list dist/pypokerlost-*.whl
tar -tzf dist/pypokerlost-*.tar.gz
```

The wheel must contain the `pypokerlost` package and `pypokerlost/py.typed`. The source distribution
must contain the package sources, `pyproject.toml`, `README.md`, and repository documentation.

## Clean wheel verification

Create a dedicated Python 3.14 environment and install the current wheel into it:

```bash
uv venv --python 3.14 build/wheel-check
uv pip install --python build/wheel-check/bin/python \
  dist/pypokerlost-0.3.0.dev0-py3-none-any.whl
build/wheel-check/bin/python -c "import pypokerlost; print(pypokerlost.__version__)"
```

The printed version must match the candidate metadata in `pyproject.toml`.

## Docker artifact build

The repository `Dockerfile` uses separately digest-pinned Python 3.14 and `uv` images to validate the lockfile and
build both distributions with its locked backend and no build isolation. Its final `artifacts` stage starts from `scratch` and contains no runtime
process.

Export that stage to `dist/` with Docker BuildKit:

```bash
docker buildx build \
  --target artifacts \
  --output type=local,dest=dist \
  .
```

See `docs/development/commands.md` for the complete static verification sequence.

See `docs/index.md`.

`make build` exports this same artifact target. `make test-image` builds its installed-wheel test
environment and runs a fresh suite from `/checks` with no package source directory, network or
writable root filesystem. Test tooling stays in that test image; the scratch artifact target has
no application process or Kubernetes deployment. Private cache scope belongs to this repository,
platform and target; restoring it never skips tests. `uv build --no-build-isolation` remains a
host diagnostic build, separate from the canonical container artifact identity.

## Installed generator

Install the wheel with the `generator` extra to use `pypokerlost-generate --version` and
`pypokerlost-generate file <openapi.json> --output src/pypokerlost`. The canonical source remains
`scripts/generate_methods.py`; Hatch maps that file into the optional command package at build time.
The SDK runtime still needs only HTTPX and Pydantic. Test wheel imports from a different directory
without editable installation, a source checkout, `.git`, or `PYTHONPATH`.

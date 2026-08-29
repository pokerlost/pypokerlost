# Building distributions

The repository builds a wheel and a source distribution for local use; neither the local nor the
Docker workflow publishes artifacts or creates a runtime application image.

## Local build

Validate the lockfile and build both distributions from the repository root:

```bash
uv lock --check
uv build
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
  dist/pypokerlost-0.2.0-py3-none-any.whl
build/wheel-check/bin/python -c "import pypokerlost; print(pypokerlost.__version__)"
```

The printed version should be `0.2.0` for the current package metadata.

## Docker artifact build

The repository `Dockerfile` uses its pinned Python 3.14 `uv` image to validate the lockfile and
build both distributions. Its final `artifacts` stage starts from `scratch` and contains no runtime
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

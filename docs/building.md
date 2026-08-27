# Building distributions

The repository builds a wheel and a source distribution for local use. These workflows do not
publish either artifact and do not create a runtime application container.

## Local build

Use Python 3.13 or newer and an installed `uv`. From the repository root, validate the lockfile,
synchronize the development environment, and build both distributions:

```bash
uv lock --check
uv sync --locked --all-groups
uv build
```

The artifacts are written to `dist/`:

```text
dist/pypokerlost-*.whl
dist/pypokerlost-*.tar.gz
```

## Docker artifact build

The repository `Dockerfile` is a build tool only. Its `build` stage uses the pinned official
`ghcr.io/astral-sh/uv:0.12.6-python3.13-trixie-slim` image to validate the lockfile and build into
`/artifacts`. The final `artifacts` stage starts from `scratch` and contains only the wheel and
source distribution.

Export those files to the local `dist/` directory with Docker BuildKit:

```bash
docker buildx build \
  --target artifacts \
  --output type=local,dest=dist \
  .
```

The Dockerfile defines no runtime process, network port, health check, or application environment.
It is not a runtime image and has no package-publishing step.

## Inspect artifacts

List wheel contents with the Python standard library and inspect the source distribution with
`tar`:

```bash
python -m zipfile --list dist/pypokerlost-*.whl
tar -tzf dist/pypokerlost-*.tar.gz
```

The wheel should contain the `pypokerlost` package and `pypokerlost/py.typed`. The source
distribution should contain the package sources, `pyproject.toml`, `README.md`, and the focused
documentation under `docs/`.

## Install a locally built wheel

Create an isolated environment with Python 3.13 or newer, install the wheel, and verify the import:

```bash
python -m venv /tmp/pypokerlost-wheel-check
/tmp/pypokerlost-wheel-check/bin/python -m pip install dist/pypokerlost-*.whl
/tmp/pypokerlost-wheel-check/bin/python -c \
  "import pypokerlost; print(pypokerlost.__version__)"
```

Installation resolves the wheel's declared runtime dependencies. It does not publish the package.

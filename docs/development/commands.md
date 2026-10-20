# Development commands

The reproducible daily gate uses Make, Git and Docker/Buildx from this exact root:

```bash
make help
make version
make ci-local
```

`ci-local` runs the native checks once, reports fresh coverage, builds wheel/sdist, accepts their
installed imports and checks release metadata. It requires no Actions API, GITHUB_TOKEN or hosted
artifact. The first dependency build may use the network; `OFFLINE=1` reports missing prepared
inputs as blocked. BuildKit caches target/platform inputs without caching test execution.

For native diagnostics, prepare and verify the locked environment:

```bash
uv lock
uv lock --check
uv sync --locked --all-groups
make format
make format-check
make lint
make typecheck
make test
make docs-check
make pre-commit
make check
make build
make test-image
uv run --locked python -m compileall -q src/pypokerlost scripts
git diff --check
```

`make check` includes isolated SDK protocol tests. Add regression cases when changing HTTP,
authorization, generator, packaging, or lifecycle behavior. Make and pre-commit contain only
thin calls to canonical tools; they do not duplicate architecture checks.

Final multi-service generation uses:

```bash
uv run --locked python scripts/generate_methods.py file \
  build/auth-openapi.json \
  build/accounts-openapi.json \
  --output src/pypokerlost \
  --check
```

Run without `--check` only to intentionally update generated sources, then repeat check mode to a
fixed point.

# Development commands

Use the locked `uv` environment and existing Make targets.

## Environment

```bash
uv lock
uv lock --check
uv sync --locked --all-groups
```

`make lock`, `make lock-check`, and `make sync` expose the same repository workflows.

## Regular gate

```bash
make check
```

The regular gate runs lock validation, Ruff formatting and lint checks, strict mypy, bytecode
compilation, documentation policy, generator version, and canonical public imports.

```bash
make format-check
make lint
make typecheck
make compile
make docs-check
make generator-check
make import-check
```

`make import-check` imports the actual root client/options/method facades, middleware classes, and
canonical request/response/value types.

## Formatting and full gate

```bash
make format
make pre-commit
make check-full
```

`make format` applies Ruff fixes and formatting. `make check-full` adds distribution build and all
pre-commit hooks.

## Direct commands

```bash
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked python -m compileall -q pypokerlost scripts
uv run --locked python scripts/check_documentation.py
uv run --locked python scripts/generate_methods.py --version
uv build
git diff --check
```

## Generator fixed point

With final service contracts and an explicit scope map:

```bash
uv run --locked python scripts/generate_methods.py file \
  build/auth-openapi.json \
  build/accounts-openapi.json \
  --output pypokerlost \
  --scope-map build/method-scopes.json \
  --check
```

Run without `--check` only when intentionally updating generated sources, then rerun with
`--check` until no difference remains.

See `docs/generator/usage.md` and `docs/index.md`.

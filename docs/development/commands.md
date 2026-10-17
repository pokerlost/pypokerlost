# Development commands

Prepare and verify the locked environment:

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
uv build
python -m compileall -q pypokerlost scripts
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
  --output pypokerlost \
  --check
```

Run without `--check` only to intentionally update generated sources, then repeat check mode to a
fixed point.

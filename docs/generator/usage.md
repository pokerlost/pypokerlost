# Generator command-line usage

The generator version is `3.1.0`.

```bash
uv run --locked python scripts/generate_methods.py file \
  build/auth-openapi.json \
  build/accounts-openapi.json \
  --output src/pypokerlost
```

Every service document belongs in the same invocation so global operation/schema names are checked
together. Add `--check` to compare expected generated files and the manifest without writing.
There is no separate scope-map option: protected operation scopes come only from standard OpenAPI
security and must already exist in the explicit SDK-owned `PokerlostScopes` catalog. A document
with no protected operations may omit `components.securitySchemes`.

The `service` command can fetch one raw OpenAPI document from public `GET /getOpenApi` for focused
development, but the multi-document `file` command owns cross-service fixed-point verification.

Failures print sanitized diagnostics without raw service bodies or secrets.

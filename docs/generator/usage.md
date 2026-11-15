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

## Static SDK contract

```bash
uv run --locked python scripts/generate_methods.py contract
uv run --locked python scripts/generate_methods.py contract --check
```

This command exports `docs/api/sdk_contract.json` and its `.sha256` sidecar from the
SDK-owned catalogs and envelope schemas. JSON keys and digest bytes are deterministic;
`--check` fails on missing or changed files without writing. `make generator-check`
includes this comparison. The artifact has its own integer `contract_version`, independent
of the package version and generated-method manifest format.

The optional installed `pypokerlost-generate contract --output path/to/sdk_contract.json`
entry point exports the same bytes. Output paths are relative to the current directory
unless absolute; the command never assumes that a source checkout exists. The separate
method/type manifest does not own these JSON artifacts. See [types](../api/types.md)
for open audience/error semantics and limits of the exported schemas.

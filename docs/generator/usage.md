# Generator command-line usage

The generator version is `2.0.0`. It is development tooling and is run from the repository root.

## Prepare

```bash
uv sync --locked --all-groups
uv run --locked python scripts/generate_methods.py --version
```

Use `-h` or `--help` globally or after a command for the actual Typer interface.

## Multiple local documents

The `file` command accepts one or more OpenAPI 3.1 JSON files:

```bash
uv run --locked python scripts/generate_methods.py file \
  build/auth-openapi.json \
  build/accounts-openapi.json \
  --output pypokerlost \
  --scope-map build/method-scopes.json
```

Every source is parsed and globally preflighted before writing. `--output` defaults to
`pypokerlost`. Add `--check` to compare the expected files and manifest without changing them.

## Explicit scope map

OpenAPI body schemas distinguish public and protected requests but cannot encode exact body-token
scopes. A checked map has operation IDs as keys and exact scope arrays as values:

```json
{
  "getMe": ["accounts.self.read"],
  "provisionHuman": ["auth.internal.provisionHuman"]
}
```

Scope arrays are canonicalized and duplicates are rejected. Do not include non-empty scope arrays
for public operations. An existing hand-written method may supply the same metadata instead; if
both sources exist, they must match.

## Fetch one service

The `service` command accepts one service origin root:

```bash
uv run --locked python scripts/generate_methods.py service \
  https://accounts.example.internal \
  --output pypokerlost \
  --scope-map build/method-scopes.json \
  --timeout 10
```

It fetches public `GET /getOpenApi`, requires a successful `PokerlostResponse` body, and generates
from its `result`. Production service URLs require HTTPS; loopback HTTP is accepted for local
development. The base URL cannot contain credentials, a path prefix, query, or fragment.

Service mode validates one fetched document. Use file mode when global collisions must be checked
across multiple service documents.

## Verification and failures

```bash
uv run --locked python scripts/generate_methods.py file \
  build/auth-openapi.json \
  build/accounts-openapi.json \
  --output pypokerlost \
  --scope-map build/method-scopes.json \
  --check
```

Malformed contracts, unsupported schemas, missing protected scopes, global collisions, and unsafe
ownership state produce a sanitized `Error:` message and status `1`. Raw request or response bodies
are not included in generator diagnostics.

See `docs/generator/contract.md`, `docs/generator/generated-layout.md`, and `docs/index.md`.

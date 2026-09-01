# Generator command-line usage

Use the development CLI to generate or verify one service's method and type packages from an
OpenAPI JSON contract.

## Prerequisites

The generator requires Python 3.14 or newer and the locked development dependencies:

```bash
uv sync --locked --all-groups
```

Run commands from the repository root. The generator is development tooling and is not installed as
a runtime console script.

## Version

The current generator version is `1.2.0`:

```bash
uv run python scripts/generate_methods.py --version
```

```text
1.2.0
```

Use `-h` or `--help` globally or after a command for Typer help.

## Generate from a file

The `file` command reads a required, existing, readable raw OpenAPI JSON document:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json
```

Its options are:

- `--output DIRECTORY` or `-o DIRECTORY`: SDK package root; default `pypokerlost`;
- `--check`: compare generated state without writing; default off;
- `--force`: permit an intentional conflicting-target overwrite and bypass version policy; default
  off;
- `--openapi-operation OPERATION`: operation to exclude as the publication system route; default
  `openapi.get`.

To select an explicit SDK root:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json \
  --output pypokerlost
```

`--output` must identify the package root that will contain both `methods/` and `types/`. Do not pass
the `methods/` directory itself. File mode never fetches the selected publication operation. Pass a
non-default selector when a saved service contract publishes OpenAPI under a custom operation and
must generate the same output as service mode.

## Generate from a service

The `service` command accepts a required HTTP or HTTPS service base URL. By default it fetches
`GET /openapi.get`:

```bash
uv run python scripts/generate_methods.py service http://127.0.0.1:8000
```

It supports the same `--output`, `--check`, and `--force` options, plus:

- `--timeout FLOAT`: positive OpenAPI request timeout in seconds; default `10.0`.
- `--openapi-operation OPERATION`: publication operation validated as `APIOperation`; default
  `openapi.get`.

The base URL may include a path prefix, but it must not contain user information, a query, or a
fragment. Supply authentication through the service environment instead of embedding credentials
in the generator command.

For example:

```bash
uv run python scripts/generate_methods.py service http://127.0.0.1:8000 \
  --output pypokerlost \
  --openapi-operation contract.getOpenAPI \
  --timeout 15
```

This command fetches `GET /contract.getOpenAPI`. The selected operation must have exactly the
`namespace.someOperation` shape; `accounts.get_self`, `accounts.self.get`, and uppercase initials
are rejected before any request. The endpoint must return the document inside the fixed PokerLost
response envelope. Service mode uses a directly scoped development-time HTTP client; it does not
use the runtime SDK `Client`, session, or storage.

## Verify committed output

`--check` renders the expected sources and manifest in memory, then compares them with disk state:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json \
  --output pypokerlost \
  --check
```

The command fails when an expected file is missing or changed, a previously owned stale file still
exists, or manifest content differs. It does not write generated source or manifest state.

## Intentional force operations

`--force` has a narrow but consequential role:

- it bypasses the OpenAPI contract-version precedence guards;
- it permits replacement of a conflicting expected target without the generator header;
- it authorizes the one-time migration of a detected previous methods-only generation layout.

It does not broaden the supported OpenAPI contract, make unsafe stale-file deletion permissible,
or authorize removal of unrelated files. Review the output root and contract history before using
it:

```bash
uv run python scripts/generate_methods.py file path/to/openapi.json \
  --output pypokerlost \
  --force
```

Without `--force`, an OpenAPI version downgrade is rejected. A changed canonical contract hash also
requires an `info.version` precedence increase. The full ownership and update rules are documented
in `docs/generator/generated-layout.md`.

## Contract failures

Validated-setting failures, acquisition failures, unsupported reachable schemas, naming
collisions, version-policy violations, and unsafe output conflicts produce a concise `Error:`
message and exit with status `1`. Typer retains its standard behavior for command-line parsing
errors. No output is written until contract generation, prior ownership resolution, and version
policy have succeeded.

See `docs/generator/contract.md` for accepted operations and schemas.

See `docs/index.md`.

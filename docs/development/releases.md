# Releases and versions

The package and development-time generator have independent versions.

## Current versions

```text
SDK package: 0.2.0
Generator:   2.0.0
```

The package version lives in `pyproject.toml` and is exposed as `pypokerlost.__version__`. The
generator version lives in `scripts/generate_methods.py` and is printed with:

```bash
uv run --locked python scripts/generate_methods.py --version
```

## Package version

Before `1.0.0`, a minor release may include an incompatible public contract change. After `1.0.0`,
such a change requires a major release. Backward-compatible capability is minor; a compatible fix
is patch.

The current package remains pre-1.0 while the body-only protocol and flat public surface are
aligned across consumers. A package version change keeps `pyproject.toml` and `uv.lock` consistent.

## Generator version

Generator major versions cover incompatible output layout, generated public API, manifest, or CLI
changes. Minor versions add compatible contract/CLI capability; patch versions preserve those
interfaces.

Service OpenAPI `info.version` values remain SemVer and are recorded with source hashes in the
generator manifest.

## Release boundary

The repository builds local wheel and source distributions. Publishing and deployment automation
are outside this repository.

See `docs/development/building.md` and `docs/index.md`.

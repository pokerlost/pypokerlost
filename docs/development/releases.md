# Releases and versions

The SDK package and the development-time generator have independent versions because they protect
different public contracts.

## Current versions

```text
SDK package: 0.2.0
Generator:   1.1.0
```

The SDK version is declared in `pyproject.toml` and locked with the project environment. The
installed package exposes that distribution version as `pypokerlost.__version__`. The generator
version is declared in `scripts/generate_methods.py` and can be printed with:

```bash
uv run python scripts/generate_methods.py --version
```

## SDK package version

The SDK package version describes the hand-maintained runtime package and its documented public
surface. Versions use `MAJOR.MINOR.PATCH`:

- before `1.0.0`, `MINOR` changes may cover incompatible public imports or runtime contracts;
- from `1.0.0`, `MAJOR` changes cover incompatible public imports or runtime contracts;
- otherwise, `MINOR` changes add backward-compatible public capability;
- `PATCH` changes fix behavior without intentionally changing the public contract.

The current `0.2.0` version reflects the pre-1.0 public rename and generated-layout foundation.

A release that changes the package version must keep `pyproject.toml` and `uv.lock` consistent.

## Generator version

The generator version protects generated source layout, generated public imports, manifest format,
and CLI behavior. An incompatible change to any of those contracts requires a generator `MAJOR`
increment. Backward-compatible OpenAPI support or an optional CLI capability is `MINOR`; a bug fix
or internal refactor preserving those contracts is `PATCH`.

Service OpenAPI `info.version` values also use `MAJOR.MINOR.PATCH`. A canonical contract content
change must increase version precedence unless generation is deliberately forced.
`docs/generator/contract.md` and `docs/generator/generated-layout.md` own the detailed generation
rules.

## Release boundary

The repository provides local wheel and source-distribution builds, including a Docker artifact
target. It does not define package publishing automation, release deployment, or a runtime
container. Maintainers review version changes and built artifacts outside an automated repository
release workflow.

See `docs/development/building.md` for artifact verification.

See `docs/index.md`.

# Python style

Runtime and generator code use Python 3.14 syntax, Ruff formatting and linting, strict mypy, and
Pydantic v2 validation.

## Language baseline

Every Python source file contains exactly one `from __future__ import annotations` in its valid
module position. Prefer PEP 695 type parameters and `type` aliases when Python 3.14 syntax can
express the contract directly; do not introduce `Generic` or `TypeVar` for those cases.

Public functions, methods, properties, context managers, and stored collaborators are typed. Use
the narrowest truthful type, `collections.abc` contracts, and `Self` where appropriate. Keep `Any`
contained at genuine dynamic boundaries.

## Formatting and static analysis

Ruff is authoritative for formatting, import order, and lint. The configured line length is 100
characters and the Ruff target is `py314`. Mypy runs in strict mode against `pypokerlost/` and
`scripts/` with the Pydantic plugin enabled.

Use explicit imports grouped as standard library, third-party, then `pypokerlost`. Wildcard imports
and dependency-private imports are not accepted. Abstract classes use `import abc` with `abc.ABC`
and `abc.abstractmethod`.

## Naming

Modules, functions, parameters, and attributes use lowercase `snake_case`. Product-prefixed class
names use `Pokerlost` as one PascalCase word, while established technical acronyms retain their
casing: `APIServer`, `HTTPMethod`, `JSONValue`, `OAuthScope`, and `APIOperation`. Preserve the
external-library name `HttpxSession`.

## Pydantic models

Pydantic v2 owns validation and normalization of public or externally supplied data. Stable scalar
invariants belong in named semantic types; related fields belong in focused models. Method payloads
preserve omitted values versus explicit `None` and use JSON-mode model dumping.

The complete normative rules are in `AGENTS.md`. Run the commands in
`docs/development/commands.md` before handoff.

See `docs/index.md`.

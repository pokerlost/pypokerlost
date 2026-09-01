# Python style

Runtime and generator code use Python 3.14 syntax, Ruff, strict mypy, and Pydantic v2 validation.

## Language and typing

Every Python source contains one correctly placed `from __future__ import annotations`. Prefer PEP
695 type parameters and aliases. Public functions, methods, properties, context managers, and
stored collaborators use the narrowest truthful types.

Use `collections.abc`, `Self`, and meaningful protocols. Callable aliases with deliberately open
arguments use `Callable[..., ReturnT]`; meaningful call semantics remain a typed
`Protocol.__call__`.

Production validation and runtime invariants use Pydantic, boundary `ValueError`/`TypeError`, or
canonical SDK exceptions rather than assertions.

## Formatting

Ruff owns formatting, imports, and lint with the repository's Python target and 100-character line
length. Mypy runs strict mode over `pypokerlost/` and `scripts/` with the Pydantic plugin.

Use explicit standard-library, third-party, then package imports. Avoid wildcard imports,
dependency-private imports, and type-checking escapes that hide design problems.

## Naming

Modules, functions, parameters, and attributes use lowercase `snake_case`. Project-prefixed public
classes use `Pokerlost`: `PokerlostClient`, `PokerlostAPIServer`, `PokerlostRequestOptions`,
`PokerlostRetryPolicy`, `PokerlostScope`, and `PokerlostOperation`.

Operation values use single lowerCamelCase. Scope segments use lowerCamelCase within dotted scope
values. The distribution/package name remains `pypokerlost`.

## Pydantic and secrets

Externally supplied data is validated at focused boundaries. Secret fields remain wire-serializable
when required, but use repr hiding and `hide_input_in_errors`. Models reject impossible envelope,
token, and authorization combinations explicitly.

See `AGENTS.md`, `docs/development/commands.md`, and `docs/index.md`.

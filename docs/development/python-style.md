# Python style

Runtime and generator code use Python 3.14, Ruff, strict mypy, Pydantic v2, and focused protocols.
Use `Callable[..., ReturnT]` for deliberately open callable arguments; never use an empty callable
argument list.

Production validation uses Pydantic, `ValueError`, `TypeError`, or canonical SDK errors rather than
runtime assertions. Secret-bearing fields are repr-hidden and validation input is hidden. Code and
errors never claim Python strings have been securely zeroed.

New project-owned private modules, functions, and variables use lowerCamelCase when no existing
contract fixes the name. Current public imports, generated modules, protocol methods, published
signatures, and tool discovery paths retain their spelling until a separately checked migration.
Project classes use `Pokerlost`; operation IDs use one lowerCamelCase segment, and dotted scope
segments use lowerCamelCase. Enum definitions belong only under `pypokerlost/enums/`.

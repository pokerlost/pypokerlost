# Python style

Runtime and generator code use Python 3.14, Ruff, strict mypy, Pydantic v2, and focused protocols.
Use `Callable[..., ReturnT]` for deliberately open callable arguments; never use an empty callable
argument list.

Production validation uses Pydantic, `ValueError`, `TypeError`, or canonical SDK errors rather than
runtime assertions. Secret-bearing fields are repr-hidden and validation input is hidden. Code and
errors never claim Python strings have been securely zeroed.

Project-owned private modules, functions, methods, variables, and fields use `snake_case`; classes
use `CapWords`, and constants use `UPPER_SNAKE_CASE`. Current public imports, generated modules,
protocol methods, published signatures, and tool discovery paths retain their spelling.
The existing 100-character Ruff line length is explicit for this SDK and its generator.
Project classes use `Pokerlost`; operation IDs use one lowerCamelCase segment, and dotted scope
segments use lowerCamelCase. Enum definitions belong only under `src/pypokerlost/enums/`.

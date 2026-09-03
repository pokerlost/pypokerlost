# Types and methods

Methods, types, and enums each have one flat package. Generated and handwritten methods share the
same direct metadata contract. Class metadata is not a Pydantic field and never serializes.

`PokerlostRequest` owns only payload JSON. `PokerlostResponse` owns the complete success/failure
wire contract. `PokerlostAudience` is a constrained exact service name. All enum definitions,
including the explicit SDK-owned `PokerlostScopes` catalog, live in `pypokerlost.enums`.

The base method intentionally has no default `__scopes__` value. Every concrete subclass must
choose `None` or a non-empty tuple. The current-client convenience resolves a task-local client only
when a method is awaited; explicit `client(method)` remains the normal path.

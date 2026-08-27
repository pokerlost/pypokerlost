# pypokerlost engineering rules

## Before every task

Read `AGENTS.md`, `SERVICE.md`, and `docs/ARCHITECTURE.md`; inspect the relevant implementation,
`git status`, and `git diff`. The working tree is authoritative.

Decision priority:

```text
latest direct user requirement
→ SERVICE.md
→ AGENTS.md
→ docs/ARCHITECTURE.md
→ older decisions
```

## Repository and API discipline

- The repository root is `pokerlost/`; the distribution and import package are `pypokerlost`.
- Runtime code lives directly under `pypokerlost/`. Do not add a `src/` layout or nested repository.
- The asynchronous SDK core is hand-maintained; concrete method and result modules may be
  generator-owned.
- Runtime dependencies remain `pydantic` and `httpx`. Do not add, remove, replace, upgrade,
  downgrade, or change dependency constraints without the latest direct user requirement.
- Project-owned identifiers use `middleware` as a singular collective noun.
- Public user guides under `docs/` use lowercase `snake_case` filenames. Canonical and normative
  files such as `README.md`, `AGENTS.md`, `SERVICE.md`, and `docs/ARCHITECTURE.md` retain their
  standard uppercase names.
- `README.md` contains local source-build instructions and documentation links only.
- The repository `Dockerfile` builds wheel and source-distribution artifacts only. It is not a
  runtime application image and has no publishing responsibility.

## Fixed engineering boundaries

- Keep one generic `PokerlostMethod`, one central `Client`, and one application lifecycle owner.
- Methods declare request fields, `__api_method__`, `__http_method__`, and `__returning__` only.
- Do not add service metadata, service bases, or metaclasses.
- Keep the single task-local current-client mechanism in `client/current_client.py`. Resolution is
  explicit `.as_(client)`, then current client, then `ClientContextError`.
- `BaseMiddleware` is the single RPC middleware contract. `Client` owns a mutable ordered
  middleware list, copies optional constructor input, and supports append-only registration through
  `add_middleware()`. Each request takes an immutable tuple snapshot before building its chain; the
  first configured component is the outermost.
- `MiddlewareHandler` is polymorphic over each method it receives, so middleware may execute a
  different result type through the remaining chain. `RPCRequestOptions` is the one typed
  per-request transport extension and owns immutable ordered string headers. Omitting options in a
  next-handler call inherits the current options; supplying options replaces them for that call.
- Middleware wraps only RPC execution through `Client.make_request()`. Do not pass it into client,
  session, storage, or application lifecycle operations, or into session, request, response,
  storage, method, or OpenAPI layers. The SDK provides no built-in authorization or retry
  middleware.
- Request, response, and session layers must not import `Client`. Do not pass `Client`, arbitrary
  dictionaries, generic context bags, service locators, dependency containers, or middleware
  contexts through those layers as future extension hooks. `RPCRequestOptions` and its copied
  immutable headers are the sole typed exception to that restriction.
- `ApplicationResponse` and `ResponseModel` are the fixed public wire contracts.
- Do not add tests, CI/CD, Docker Compose, runtime containers, Helm, authentication, retries,
  streaming, service routing, or code generation unless the latest direct user requirement
  explicitly requests them.
- The runtime SDK has no token-handling behavior, predefined token keys, refresh, endpoint wrappers,
  dynamic OpenAPI generation, or concrete RPC methods.
- OAuth2 scopes are service-defined strings used only in OpenAPI metadata; they are not runtime
  authorization policy and must not become a central enum.

## Storage boundaries

- `Client` owns one `BaseSession` and one `BaseStorage`. `Client()` selects `HttpxSession` and
  `MemoryStorage` by default; injected resources use the same ownership and lifecycle.
- `BaseStorage` centrally validates `StorageKey`, `JSONValue`, and `StorageTTL` through reusable
  Pydantic adapters and owns defensive copying on both `set()` and `get()`.
- `StorageTTL` is `int | float | timedelta | None`. `BaseStorage` rejects booleans and non-positive
  or non-finite lifetimes, and normalizes accepted TTL to relative `float | None` for backends.
  Absence and expiration are both reported with `StorageKeyNotFoundError`, so a stored top-level
  `None` remains unambiguous.
- Client startup is `storage.start()` then `session.start()`. Shutdown is `session.close()` then
  `storage.close()`, and both close operations must be attempted. A session startup failure closes
  already-started storage before the original failure is re-raised.
- Storage is a client-owned sibling of the session, never part of RPC transport. Request, response,
  session, method, and OpenAPI modules must not import or automatically access storage. Storage must
  not import those layers or `Client`.
- `MemoryStorage` uses monotonic time and opportunistic expiration without a cleanup task. Reads do
  not extend TTL; replacing a key replaces its expiration, and setting it without TTL removes a
  previous expiration.
- Do not add a global storage instance, storage `ContextVar`, ownership flags, automatic request or
  response persistence, authentication behavior, predefined keys, default or sliding TTL,
  TTL mutation/introspection operations, transactions, queues, pub/sub, a cleanup worker, or an
  external backend without a latest direct user requirement.
- `MemoryStorage.close()` releases no data and does not pause TTL: it is idempotent, non-expiring
  values survive sequential stop/start cycles on the same instance, and expired values never
  reappear. Only `clear()` deliberately removes every value.

## Method-generation tooling

- `scripts/generate_methods.py` is the one authoritative generator. Its Typer `file` and `service`
  commands differ only in how they obtain a validated `OpenAPIDocument`; resolution, rendering,
  manifest policy, and writing remain one shared deterministic pipeline.
- Local JSON and generated text I/O use `aiofiles` through asynchronous context managers. Service
  discovery uses a directly scoped `httpx.AsyncClient`; it never routes through SDK runtime
  infrastructure.
- Generator code remains under `scripts/` and must not import `Client`, `Application`, sessions,
  middleware, storage, lifecycle, request builders, response handlers, current-client internals,
  private `pypokerlost` modules, or private names.
- Reuse stable public contracts through focused facades: `ApplicationResponse`, `JSONValue`,
  `HTTPMethod`, and `RPCOperation`. Generated methods import `PokerlostMethod` from
  `pypokerlost.methods` and never import `scripts` or development-only dependencies.
- OpenAPI models, local reference resolution, rendering, naming, generated-file values, canonical
  source hashing, manifest representation, safe overwrite policy, CLI settings, and generator
  SemVer policy belong to the generator script, not the runtime package.
- Typer and aiofiles remain development/tooling dependencies. Do not duplicate or move them into
  runtime dependencies, and do not add YAML input or another CLI framework.
- The manifest records generator version, OpenAPI version, canonical source hash, and owned files.
  Manifest state is scoped by the canonical output root, so distinct `--output` roots cannot share
  version or ownership history.
  Owned paths are normalized relative Python paths inside the generated service subpackage. Only
  manifest-owned generated files may be removed; manual files are not overwritten without an
  explicit `--force`.
- OpenAPI document parsing retains component schemas as JSON values. Strict generator-schema
  validation begins only when a selected request or successful response makes a schema reachable;
  unused framework-owned components cannot block generation.
- Both generator and OpenAPI contract versions use `MAJOR.MINOR.PATCH`. Generator `MAJOR` covers an
  incompatible generated layout, generated public API, manifest format, or CLI change; `MINOR`
  covers backward-compatible OpenAPI support or optional CLI capability; `PATCH` covers bug fixes
  and internal refactors that preserve those contracts. Do not increment for unreleased internal
  cleanup unless project release policy requires it.
- A canonical OpenAPI content change requires an `info.version` precedence increase. Reject a
  downgrade or same-version content change unless `--force` is deliberately supplied.

## Python code style

### Language and formatting

- Write production identifiers, comments, docstrings, exception messages, and technical
  documentation in English.
- Follow the Python version and formatting configuration declared in `pyproject.toml`.
- Ruff is the formatting, import-order, and lint authority.
- Mypy strict mode is the typing authority.
- Do not manually fight tool formatting.
- Keep lines readable; do not compress logic merely to reduce line count.
- Use trailing commas in multiline calls, collections, signatures, and type declarations so Ruff
  can format them consistently.

### Project-owned acronym naming

Product-prefixed Python names use the single PascalCase word `Pokerlost`. In project-owned
`PascalCase` identifiers, preserve established technical acronyms in uppercase:

```text
RPCRequest
RPCRequestBuilder
RPCOpenAPIExtra
APIServer
PokerlostAPIError
PokerlostProtocolError
JSONDumps
JSONLoads
JSONValue
HTTPMethod
OAuth2Scope
URL
UUID
SDK
```

These examples define casing; they do not authorize artifacts outside the fixed engineering
boundaries. Preserve official external-library and specification branding:

```text
HttpxSession
httpx
Pydantic
OpenAPI
OAuth2
PostgreSQL
SQLAlchemy
FastAPI
```

In particular, keep `HttpxSession`; do not write `HTTPXSession`.

Modules, functions, parameters, attributes, and local variables use normal lowercase `snake_case`:

```text
rpc_request.py
rpc_request_builder.py
rpc_openapi_extra.py
api_server.py
json_dumps
request_timeout
oauth2_scopes
```

Never produce acronym-split module names such as `r_p_c_request.py`.

Do not use vague artifact names:

```text
utils.py
helpers.py
common.py
misc.py
manager.py
a.py
b.py
temp.py
```

A module and its main artifact must communicate their responsibility.

### Files and public surface

- Prefer one primary public artifact per focused module.
- A module may contain small private helpers only when they exist solely to support that artifact.
- Add a package or file only for a concrete current use.
- Keep `__init__.py` files as intentional facades; do not turn them into export dumps.
- Use explicit `__all__` only for a deliberate public facade.
- Do not change public APIs without a direct requirement.
- Constructor collection defaults use `None` when runtime mutation is supported; do not use a
  mutable default or an unexplained empty tuple for that case.
- Do not keep obsolete modules, duplicate APIs, or compatibility aliases unless the latest user
  requirement explicitly requires backward compatibility.
- When replacing an internal abstraction, remove its old implementation, imports, exports,
  documentation, and packaging references in the same task.

### Imports

- Every Python source file, including package initializers, scripts, and generator-owned modules,
  must contain exactly one `from __future__ import annotations`. Place it after an optional shebang
  and encoding comment and after the module docstring, when present, but before every ordinary
  import and all executable code. Ordinary leading comments may remain before it, and Python source
  renderers must emit it in the same position.
- Use explicit imports; wildcard imports are forbidden.
- Abstract classes use `import abc` with `abc.ABC` and `abc.abstractmethod`. Do not use
  `from abc import ...`.
- Group imports as standard library, third-party, then `pypokerlost`.
- Prefer absolute `pypokerlost...` imports across package boundaries.
- A short relative import is acceptable only inside one tightly focused subpackage when it makes
  the dependency clearer and does not obscure the imported package.
- Use `TYPE_CHECKING` for type-only imports that would otherwise create a runtime cycle.
- Do not solve circular imports with dynamic imports, imports inside arbitrary methods,
  monkey-patching, string-based service locators, or facade abuse.
- Do not import from private implementation modules of dependencies.
- Every production import must resolve from the standard library, declared dependencies, or the
  current package.

### Typing

- Use modern Python typing supported by the configured minimum Python version, including PEP 695
  type parameters and `type` aliases where they improve clarity.
- Type every public function, method, property, context manager, and stored collaborator.
- Use the narrowest truthful type.
- Do not use `object` as a generic escape hatch.
- Do not spread `Any` through application code. Contain it at genuine dynamic boundaries such as
  custom JSON decoding, Pydantic runtime type metadata, or validation context.
- Prefer `collections.abc` types for callable, iterator, mapping, and context-manager contracts.
- Prefer `Self` for fluent methods and alternative constructors.
- Do not use `# type: ignore` to conceal an architectural problem. A localized ignore is allowed
  only when the type system cannot express a verified runtime boundary, and it must include the
  exact error code.
- Do not use `cast(Any, ...)`.
- Do not inspect `__orig_bases__`, MRO internals, Pydantic private metadata, or generic internals to
  recover types dynamically.
- Do not add a `Protocol`, abstract base class, or generic type parameter without a current consumer
  and a concrete reason.

### Classes and design patterns

- Every class owns one clear responsibility and one reason to change.
- Use design patterns or new abstractions to clarify an existing collaboration with a concrete
  current use, not to decorate the architecture.
- Prefer composition over inheritance for interchangeable collaborators.
- Use inheritance for a real semantic subtype or a stable execution contract.
- A single implementation does not justify an abstract factory, registry, plugin system, command
  bus, service locator, or dependency-injection container. `Client` composes its middleware list
  and request snapshot directly; do not add a middleware manager, chain, registry, or factory
  abstraction.
- Do not create `Manager`, `Helper`, `Utils`, `Service`, `Factory`, or `Registry` classes without a
  precise current responsibility that cannot be expressed by an existing component.
- Reuse an existing implementation before adding another abstraction that performs the same work.
- Remove verified duplication at the owner of the shared behavior; do not hide duplication behind
  another forwarding wrapper.

### Methods and functions

- Prefer instance methods for behavior owned by an object and using its collaborators or policy.
- Do not use `@staticmethod`.
- Use `@classmethod` only for a genuine alternative constructor, such as `APIServer.from_base()`.
- Use a module-level function for pure behavior that belongs to no object.
- Keep functions small enough that their name and control flow remain obvious, but do not split
  linear logic into one-line forwarding functions.
- Avoid boolean switches that make one method execute unrelated modes; use explicit operations when
  behaviors are genuinely different.
- An intentionally empty or default no-op method has a concise docstring explaining why no action
  is required; the docstring is its complete body. An abstract method likewise uses its contract
  docstring as the complete body. Do not use `pass` or write `return None` merely to make an empty
  method explicit. Use a bare `return` only for meaningful early control-flow termination. An
  explicit `return None` is allowed only when returning `None` is semantically significant in a
  non-empty function or required by an external protocol.
- Do not use `getattr()` as a substitute for a typed contract.
- Do not implement dynamic endpoint access through `Client.__getattr__`.

### Asynchronous code and lifecycle

- All network APIs, lifecycle hooks, and resource-lifecycle operations remain asynchronous.
  `Application.run()` remains the established synchronous loop-owning entry point.
- Never call blocking I/O from asynchronous code.
- Use async context managers and `AsyncExitStack` for deterministic multi-resource cleanup.
- Never invoke context-manager protocol methods (`__enter__`, `__exit__`, `__aenter__`, or
  `__aexit__`) directly. Use `with`, `async with`, `ExitStack`, or `AsyncExitStack`; use an exit
  stack callback only for cleanup that is not itself a context manager. `ContextVar.set()` and
  `ContextVar.reset(token)` remain valid operations owned by the focused current-client context.
- Cleanup must be correct for normal completion, exceptions, and cancellation.
- Do not catch `asyncio.CancelledError` except at an explicitly owned cancellation boundary, and
  re-raise or consume it only according to that boundary's documented contract.
- Do not catch broad exceptions around large execution blocks.
- A broad catch is acceptable only around a caller-provided dynamic decoder or guaranteed cleanup
  followed by immediate re-raise.
- Do not silently retry network operations.
- Do not create background tasks whose ownership and shutdown are undefined.
- Lifecycle state protection must not serialize independent HTTP requests.

### Pydantic and value objects

- Use Pydantic v2 models for validated public request, response, and structured SDK contracts.
- Public request fields use alias-free `snake_case`.
- Reject unknown fields unless a concrete wire contract explicitly requires extensibility.
- Do not use Pydantic private internals.
- Use:

  ```python
  model_dump(
      mode="json",
      by_alias=False,
      exclude_unset=True,
  )
  ```

  for standard RPC payload preparation unless a concrete endpoint contract requires otherwise.

- Preserve the distinction between an omitted field and an explicitly supplied `None`.
- Use frozen, slotted dataclasses for small immutable internal values that require no Pydantic
  validation.
- Do not declare a dataclass frozen while storing caller-owned mutable collections inside it.
- Do not use untyped dictionaries as substitutes for stable internal contracts.

### Validation ownership

- Pydantic v2 owns validation and normalization of all public or externally supplied data.
- Do not spread imperative `_validate_*` methods across clients, sessions, storage, request
  builders, OpenAPI values, methods, or lifecycle objects.
- A reusable scalar invariant becomes a named semantic Pydantic-backed type under
  `pypokerlost/types/`.
- A group of related fields becomes a focused Pydantic model.
- Validate named scalar types through a reusable `TypeAdapter` at the subsystem boundary.
- Use `Annotated`, `StringConstraints`, `Field`, `BeforeValidator`, and `AfterValidator` inside the
  semantic type module when necessary.
- Custom validator functions belong beside the semantic type and are invoked by Pydantic; callers
  do not call them directly.
- Do not duplicate the same validation in constructors and public methods.
- Do not use `type(value) is ...`, manual `isinstance(...)` chains, `.strip()` checks, regex checks,
  range checks, finite-number checks, or enum membership checks in orchestration classes when the
  constraint can be represented by Pydantic.
- Do not use `pydantic.validate_call` indiscriminately on every method. Prefer named types and one
  boundary adapter.
- Do not use Pydantic to validate trusted internal control flow, dictionary lookups, lifecycle
  state, or third-party runtime results already owned by another adapter.
- After Pydantic validation, internal code may rely on the validated type and must not repeat
  defensive checks.
- Preserve an established public `TypeError` or `ValueError` contract by translating
  `ValidationError` once at the subsystem boundary. Preserve only a safe failure category through
  `__cause__`; never retain an input-bearing `ValidationError`, and never expose sensitive input in
  translated messages or metadata.

### Errors and security

- Root SDK exceptions under the established `PokerlostError` hierarchy.
- Distinguish application failures, protocol failures, decoding failures, transport failures,
  timeout failures, context failures, and lifecycle-state failures only when code handles them
  differently.
- Do not create empty exception subclasses that merely mirror every HTTP status.
- Preserve stable application error codes exactly.
- Public exception messages, exception metadata, and logs must never expose raw response bodies,
  request bodies, headers, cookies, authorization values, access tokens, refresh tokens,
  credentials, private keys, or other secrets.
- Preserve transport and decoder failure categories through safe sanitized `__cause__` values.
  Never retain an external exception that owns a request, response body, headers, or other input.
- Do not swallow programming errors.

### Comments and docstrings

- Comments explain why a non-obvious decision exists, not what the next line already says.
- Do not add comments that restate type annotations or simple control flow.
- Public classes and non-obvious public operations receive concise docstrings.
- Private helpers need docstrings only when their contract or invariant is not clear from naming
  and types.
- Keep examples consistent with the current public API.
- Do not leave TODO placeholders for architecture already decided elsewhere.
- Do not preserve dead historical explanations after replacing an implementation.

### Change discipline

Before adding code:

1. inspect the current implementation and all call sites;
2. search for an existing artifact with the same responsibility;
3. identify the actual owner of the behavior;
4. make the smallest coherent change;
5. delete obsolete paths in the same task;
6. update focused facades and authoritative documentation;
7. run formatting, linting, typing, import, build, and diff checks.

Use `uv` for locking and builds. Make only task-related changes; do not perform unrelated
refactoring or formatting. Never run destructive Git commands, and do not commit or push unless the
latest direct user requirement explicitly requests it.

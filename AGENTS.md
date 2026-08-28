# pypokerlost engineering rules

This file defines the normative rules for changing the SDK. Product boundaries live in
`SERVICE.md`; explanations and user guidance live under `docs/`.

## Before every task

- Read `AGENTS.md`, `SERVICE.md`, and `docs/architecture/overview.md`.
- Inspect the relevant implementation, every call site affected by the task, `git status --short`,
  and `git diff`.
- Treat the working tree and the current implementation as authoritative.
- Make only changes required by the latest task; preserve unrelated user changes.

## Priority

Resolve conflicting guidance in this order:

```text
latest direct user requirement
→ SERVICE.md
→ AGENTS.md
→ docs/architecture/overview.md
→ older decisions
```

## Architecture

- The repository root is the Python project root. Runtime code lives directly under
  `pypokerlost/`; do not add a `src/` layout or nested repository.
- Keep one generic `PokerlostMethod`, one central `Client`, and one `Application` lifecycle owner.
- Runtime dependencies remain `pydantic` and `httpx`. Do not change dependency constraints without
  a direct requirement.
- Keep typed API objects under `pypokerlost/types/` and API method objects under
  `pypokerlost/methods/`.
- Keep transport targeting and execution under `pypokerlost/client/`:

  ```text
  client/api_server.py
  client/request/
  client/response/
  client/session/
  ```

- `OpenAPIExtra` lives at `pypokerlost/openapi_extra.py` and owns only non-authorization contract
  metadata.
- Request, response, and session layers must not import `Client`. Storage remains a client-owned
  sibling of the session and outside transport.
- Prefer focused composition. Do not add service locators, dependency containers, registries,
  factories, managers, service bases, or metaclasses without a concrete current consumer.

## Public API

- Treat package facades and documented import paths as deliberate public API.
- Do not rename, move, remove, or add compatibility aliases for public artifacts without a direct
  requirement.
- Keep `__init__.py` files focused; use explicit `__all__` only for intentional facades.
- Prefer one primary public artifact per module. Add a file or abstraction only for a current use.
- Keep constructors free of mutable collection defaults. Use `None` when runtime mutation is
  supported and copy caller-owned collections.
- Preserve established names and casing: `PokerlostType`, `MutablePokerlostType`,
  `PokerlostMethod`, `APIOperation`, `APIServer`, `HttpxSession`, `OpenAPIExtra`, `JSONValue`,
  `HTTPMethod`, `Request`, `RequestBuilder`, `RequestOptions`, `Response`, and `ResponseHandler`.
- Project-owned modules, functions, parameters, and attributes use lowercase `snake_case`.
  `middleware` is a singular collective noun.

## Python and typing

- Python 3.14 or newer is required.
- Every Python source file contains exactly one `from __future__ import annotations`, after the
  module docstring and before ordinary imports or executable code.
- Use PEP 695 type parameters and `type` aliases when modern syntax suffices; do not use
  `Generic`/`TypeVar` for those cases.
- Type every public function, method, property, context manager, and stored collaborator with the
  narrowest truthful type.
- Prefer `collections.abc`, `Self`, explicit imports, and `TYPE_CHECKING` for cycle-prone type-only
  imports.
- Do not spread `Any`, use `object` as an escape hatch, use `cast(Any, ...)`, inspect generic or
  Pydantic internals, or hide architectural problems with `# type: ignore`.
- Abstract classes use `import abc`, `abc.ABC`, and `abc.abstractmethod`.
- Do not use wildcard imports, dependency-private imports, arbitrary dynamic imports,
  `@staticmethod`, or `getattr()` as a substitute for a typed contract.
- Ruff owns formatting, import order, and linting. Mypy strict mode owns static typing. The line
  length and Python target come from `pyproject.toml`.
- Pydantic v2 owns validation of public and external data. Reusable scalar invariants belong in a
  named type under `pypokerlost/types/`; related fields belong in a focused model.
- Preserve omitted fields versus explicit `None`. Standard method payload preparation uses:

  ```python
  model_dump(
      mode="json",
      by_alias=False,
      exclude_unset=True,
  )
  ```

## PokerlostType

- `PokerlostType` is the immutable base for typed API objects. It allows extra response fields for
  forward compatibility and owns an optional private client binding.
- `MutablePokerlostType` is the deliberate mutable subtype; do not weaken the base model or add
  implicit-default or sentinel mechanics without a runtime requirement.
- Client resolution is: explicit or validation-context binding, then the single task-local current
  client in `client/current_client.py`, then `ClientContextError`.
- The private client binding is never serialized. Response validation passes the executing client
  through Pydantic context so nested typed API objects can resolve it.

## Methods and generated types

- A method declares request fields, `__api_method__`, `__http_method__`, and `__returning__` only.
- Methods inherit `PokerlostType` but override its configuration to remain strict and
  extra-forbid.
- The operation string is the complete operation identity. Do not add service metadata, routing,
  or an endpoint facade to methods or `Client`.
- Generated request methods live under `pypokerlost/methods/<service_package>/`.
- Generated returned and nested API objects and aliases live under
  `pypokerlost/types/<service_package>/`. Never place generated response models beside methods.
- Generated code imports only stable public runtime facades and never imports `scripts` or tooling
  dependencies.

## Client/request/response

- `Client` owns exactly one `BaseSession`, one `BaseStorage`, and one mutable ordered middleware
  list. `Client()` defaults to `HttpxSession` and `MemoryStorage`.
- Client startup is storage then session. Shutdown is session then storage, and both close
  operations must be attempted. A failed session startup closes already-started storage.
- `RequestBuilder` produces a frozen `Request` containing only `method`, `http_method`, `data`, and
  immutable headers. It owns no URL, JSON codec, bytes, or I/O.
- `HttpxSession` owns `APIServer`, URL construction, strict JSON encoding, UTF-8 conversion, HTTPX
  resources, concrete I/O, JSON decoding configuration, and `ResponseHandler`.
- `Response[ResultT]` is the fixed extra-forbid envelope with `ok`, `result`, `error`, and
  `error_message`.
- `ResponseHandler` validates the envelope, maps SDK errors, and validates `__returning__` with the
  executing method's client in validation context.
- All network and resource lifecycle APIs remain asynchronous. `Application.run()` is the sole
  synchronous event-loop-owning entry point.
- Cleanup must remain correct for normal completion, exceptions, and cancellation. Do not serialize
  independent requests with lifecycle state protection.

## Middleware

- `BaseMiddleware` is the single method-call middleware contract. Middleware wraps only
  `Client.make_request()` execution, never lifecycle or transport internals.
- `Client` copies constructor input; `add_middleware()` appends. Each request takes an immutable
  tuple snapshot, and the first configured component is outermost.
- `MiddlewareHandler` remains polymorphic over each method it receives, allowing an alternate method
  through the remaining chain.
- `RequestOptions` is the only typed per-request transport extension. It owns immutable ordered
  string headers; omitted next-handler options inherit, supplied options replace.
- Do not add built-in authorization, retry, credential, or replay middleware.

## Storage

- `BaseStorage` centrally validates `StorageKey`, `JSONValue`, and `StorageTTL`, and makes defensive
  copies on `set()` and `get()`.
- `StorageTTL` accepts `int | float | timedelta | None`; booleans and non-positive or non-finite
  values are invalid. Backends receive normalized relative `float | None`.
- Missing and expired keys raise `StorageKeyNotFoundError`; top-level `None` remains a valid value.
- `MemoryStorage` uses monotonic time and opportunistic expiration. Reads do not extend TTL;
  replacing a key replaces its expiration.
- `MemoryStorage.close()` is idempotent, retains values, and does not pause TTL. Only `clear()`
  deliberately removes all values.
- Do not add global storage, storage context, automatic method persistence, predefined keys,
  default or sliding TTL, cleanup tasks, transactions, queues, pub/sub, or an external backend
  without a direct requirement.

## Generator

- `scripts/generate_methods.py` is the single authoritative generator. Its `file` and `service`
  commands share validation, resolution, rendering, manifest policy, and writing.
- Local JSON and generated text I/O use `aiofiles` async context managers. Service discovery uses a
  directly scoped `httpx.AsyncClient`, not runtime SDK infrastructure.
- The generator accepts OpenAPI 3.1 JSON only. Do not add YAML or another CLI framework.
- Typer and aiofiles remain tooling dependencies, never runtime dependencies.
- `--output` identifies one SDK package root containing both `methods/` and `types/`.
- Manifest v2 records generator/OpenAPI versions, canonical source hash, service identity/package,
  and normalized owned paths in both namespaces. Only proven generator-owned files may be removed.
- Manual files are not overwritten without explicit `--force`; legacy layout migration also
  requires deliberate `--force` and proven ownership.
- Canonical contract changes require an `info.version` precedence increase unless `--force` is
  supplied.
- Generator and contract versions use `MAJOR.MINOR.PATCH`. A generator major version covers an
  incompatible generated layout, public API, manifest format, or CLI change.
- Do not move generator models, naming, rendering, hashing, manifest, or overwrite policy into the
  runtime package.

## Errors/security

- Root expected SDK failures under the established `PokerlostError` hierarchy.
- Distinguish application, protocol, decoding, transport, timeout, context, lifecycle, and storage
  failures only where callers handle them differently.
- Preserve stable API error codes exactly. Do not add empty status-specific exception subclasses.
- Public exceptions, causes, messages, metadata, comments, examples, and logs must never expose raw
  request or response bodies, headers, cookies, credentials, tokens, or private keys.
- Translate validation failures once at subsystem boundaries and retain only sanitized causes.
- Do not swallow programming errors or catch broad exceptions around large execution blocks.

## Documentation

- Update documentation in the same task when behavior, public imports, commands, versions, or
  architecture ownership changes.
- `README.md` is the concise entry point; `SERVICE.md` owns product boundaries; `AGENTS.md` owns
  normative engineering rules; `docs/index.md` owns navigation.
- Architecture pages explain internals, API pages guide public usage, generator pages own generation
  contracts/workflows, development pages own maintainer workflows, and project pages record current
  status and non-goals.
- Do not duplicate a source of truth. Link to the owning page.
- Documentation is English, uses relative internal links, current public imports, one H1 per file,
  and language-tagged code fences.
- Pages under `docs/` use lowercase kebab-case names. Root normative files retain canonical names.

## Tooling

- Use `uv` for locking, dependency synchronization, and builds.
- Use `make pre-commit`, `make check`, and `make check-full` as the canonical repository gates.
- Use only real commands and Make targets declared by the repository.
- Before handoff, run the applicable lock, sync, Ruff, mypy, compile, build, documentation-link, and
  `git diff --check` validations. Report every unavailable or failed check accurately.
- Review the complete final diff before any requested commit. Never push unless explicitly asked.

## Do not

- Do not perform unrelated refactoring, renaming, formatting, dependency changes, or public API
  changes.
- Do not add concrete service methods, authentication/token behavior, authorization policy,
  service routing, retries, streaming, WebSocket/events, direct database access, dynamic endpoint
  lookup, runtime OpenAPI generation, settings systems, or compatibility layers without a direct
  requirement.
- Do not add tests, CI/CD, Docker Compose, runtime containers, Helm, code generation, or publishing
  automation unless the latest direct requirement asks for them.
- Do not use destructive Git commands, commit, push, or alter branches unless explicitly requested.

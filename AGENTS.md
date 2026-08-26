# pypokerlost

## Before every task

1. Read `AGENTS.md`, `SERVICE.md`, and `docs/ARCHITECTURE.md`.
2. Inspect the current repository, the relevant implementation, and `git status`/`git diff`.
3. Treat files in the current working tree as authoritative over older summaries or reports.
4. Treat the latest direct user requirement as the highest-priority instruction.

Decision priority:

```text
latest direct user requirement
→ SERVICE.md
→ AGENTS.md
→ docs/ARCHITECTURE.md
→ older decisions
```

`SERVICE.md` defines current product scope. This file defines shared engineering rules.

## Repository identity

- The repository root is `pokerlost/`; the distribution and import package are `pypokerlost`.
- Runtime code lives directly under `pypokerlost/`; do not introduce a `src/` layout or another
  nested repository directory.
- This is a hand-maintained asynchronous SDK, not a generated service or application template.
- Add an abstraction, package, or file only for a concrete current use.

## Current design principle

The current core fixes how components collaborate, not product policies that have not yet been
learned from real PokerLost operations. The ergonomic direction is a central Pyrogram-like client
with aiogram-like typed RPC method objects; neither project is a dependency or implementation to
copy.

The core currently has no concrete PokerLost operations. The next product step is a real vertical
slice from accountsService and authService, not another speculative subsystem.

## Current execution API

Ordinary methods support explicit client calls:

```python
result = await client.make_request(method)
result = await client(method)
result = await method.execute(client)
```

Task-local execution requires an explicit synchronous context scope:

```python
with client.as_current():
    result = await method
```

`Method.__await__()` delegates to `execute()`. `StreamMethod` is not awaitable; callers consume it
through the context manager returned by `client.stream_content(method)`.

`async with client` has no current semantics. It is reserved for a later product decision about
start/stop, authentication, or WebSocket lifecycle.

## Component boundaries

- `Client` is a thin facade over one supplied `BaseSession`. It delegates ordinary and streaming
  calls, manages only the task-local current-client scope, and delegates explicit `close()`.
- `BaseMethod`, `Method[ResultT]`, and `StreamMethod` are frozen Pydantic v2 request objects with
  forbidden extra fields. Concrete methods declare `__api_method__` and, for an ordinary method,
  `__returning__`; `__http_method__` defaults to `POST` and may be overridden.
- `BaseSession` owns the shared execution flow and passes both `Client` and method/request values to
  its collaborators and concrete I/O hooks.
- `RequestBuilder` translates a method into a transport-neutral `PreparedRequest`.
- `ResponseHandler` validates the shared application envelope and returns the declared result or
  raises a public SDK error.
- A concrete session adapter performs I/O. `HttpxSession` adapts an already configured
  `httpx.AsyncClient`.
- `ContentStream` represents a live byte stream and provides idempotent explicit closing.

Methods contain immutable wire request data only. They do not build HTTP requests, decode
responses, perform I/O, refresh credentials, or retry.

## Fixed wire contract

`ResponseModel` retains this configuration:

```python
ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    validate_default=True,
)
```

`ApplicationResponse[ResultT]` is the authoritative shared envelope and retains its four fields,
defaults, and existing validator:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure forbids a result and requires both error fields. Do not add
fields, aliases, validators, automatic values, or reinterpret these semantics without an
authoritative service-contract change. `ok=True, result=None` remains valid at envelope level; the
ordinary method's declared result annotation determines whether `None` can cross the typed method
boundary.

An RPC operation identifier follows `namespace.method`; its standard relative HTTP path is
`/{namespace}.{method}`. This is an authoring convention, not untrusted input that needs regex
policing on every model instance.

Valid application failures preserve the service's public `error` and `error_message`. Public error
messages and logs do not contain credentials, authorization headers, request bodies, or raw/full
response bodies.

## OpenAPI metadata

`AccessRole` contains `public`, `user`, `support`, `master`, and `auto`.
`rpc_openapi_extra(access=...)` returns a fresh FastAPI-independent dictionary with only the current
shared marker:

```python
{
    "x-pokerlost": {
        "access": [role.value for role in access],
    },
}
```

The helper preserves the supplied iterable and does not implement authorization policy. Additional
metadata belongs here after a real consumer requires it.

## Dependencies, tooling, and security

- Do not add, remove, replace, upgrade, or downgrade dependencies in a task without direct user
  authorization for that change.
- Runtime dependencies currently remain `pydantic` and `httpx`; aiogram, Pyrogram, and FastAPI are
  design references rather than SDK dependencies.
- Use `uv` for locking and builds, Ruff for formatting/linting, and mypy for static checks.
- Keep `Makefile` wrappers thin and leave CI/CD unchanged unless requested.
- Do not create a test suite unless directly requested. Task-specific smoke checks may use temporary
  or inline code without repository test files.
- Do not commit secrets, persist tokens, or log credentials, authorization values, cookies, request
  bodies, or raw/full response bodies.
- Do not run destructive Git commands, commit, or push unless directly requested.

## Deferred decisions

The following are not current platform contracts. Add them only after an explicit product decision
supported by real accountsService/authService behavior:

- one-service versus multi-service clients, URL mapping, routing, and discovery;
- access-token and refresh-token state, token refresh, and authorization injection;
- ownership and sharing of sessions or `httpx.AsyncClient` instances;
- client start/stop semantics, async context management, reentrancy, and closed-state policy;
- timeouts, headers, proxies, TLS, pools, retries, and environment-variable behavior;
- per-operation omitted-field versus explicit-`null` encoding;
- HTTP-status interpretation and the streaming error-body protocol;
- endpoint wrappers on `Client`, a synchronous facade, and WebSocket/update lifecycle.

These deferred items are outside the current task scope; their future design remains open.

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
with aiogram-like typed RPC method objects and a small application-level lifecycle owner; neither
project is a dependency or implementation to copy.

The core currently has no concrete PokerLost operations. The next product step is a real vertical
slice from accountsService and authService, not another speculative subsystem.

## Current lifecycle and execution API

`Application` owns one `Client`, starts it, installs it as the task-local current client, and stops
it with guaranteed context cleanup. It supports a synchronous entrypoint runner, an asynchronous
runner, and direct async scope management:

```python
application.run(main)
result = await application.run_async(main)

async with application:
    result = await method
```

`Application.run()` owns its event loop through `asyncio.run()`. `Application.run_async()` is for an
already-running loop. Reentrant or concurrent entry of the same application is rejected.

Ordinary methods support explicit client calls:

```python
result = await client.make_request(method)
result = await client(method)
result = await method.execute(client)
```

Manual client lifecycle remains available:

```python
await client.start()
try:
    result = await client(method)
finally:
    await client.stop()
```

`Client.stop()` is terminal. Requests and streams require a started client; they fail with focused
public errors before startup and after stop. `client.as_current()` manages only the task-local
context and may be used when lifecycle is managed manually:

```python
with client.as_current():
    result = await method
```

`Method.__await__()` delegates to `execute()`. `StreamMethod` is not awaitable; callers consume it
through the context manager returned by `client.stream_content(method)`. `Client` deliberately has
no async context-manager API because `Application` is the lifecycle owner.

## Component boundaries

- `Application` owns one `Client`, its automatic lifecycle, and its task-local execution scope.
- `Client` owns one supplied `BaseSession`, exposes explicit `start()`/`stop()`, delegates ordinary
  and streaming calls, and can manage an explicit task-local current-client scope.
- `BaseMethod`, `Method[ResultT]`, and `StreamMethod` are frozen Pydantic v2 request objects with
  forbidden extra fields. Concrete methods declare `__api_method__` and, for an ordinary method,
  `__returning__`; `__http_method__` defaults to `POST` and may be overridden.
- `BaseSession` owns the shared execution flow. Session, request, response, and HTTP-adapter layers
  never receive `Client` or a replacement context bag.
- `RequestBuilder` translates a method into a transport-neutral `PreparedRequest` containing the
  explicit operation and an immutable UTF-8 JSON body.
- `ResponseHandler` first validates the shared envelope as `ApplicationResponse[JsonValue]`, then
  validates a successful result against the method's declared return type.
- A concrete session adapter performs I/O. `HttpxSession` owns and adapts an already configured
  `httpx.AsyncClient`.
- `ContentStream` represents a live byte stream and provides idempotent explicit closing.

Methods contain immutable wire request data only. They do not build HTTP requests, decode
responses, perform I/O, refresh credentials, or retry.

Authentication is not implemented. Do not introduce auth placeholders, generic hooks, arbitrary
client-state reads, or authorization injection without an authoritative contract. The SDK also has
no settings subsystem or environment loading: callers configure `httpx.AsyncClient` directly.

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
- any future SDK-level timeout, header, proxy, TLS, pool, retry, or environment policy;
- per-operation omitted-field versus explicit-`null` encoding;
- HTTP-status interpretation and the streaming error-body protocol;
- endpoint wrappers on `Client`, a synchronous SDK facade, and WebSocket/update behavior.

These deferred items are outside the current task scope; their future design remains open.
Concrete accountsService and authService operations remain future typed method and result classes;
they are not transport or lifecycle policy.

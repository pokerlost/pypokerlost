# pypokerlost

`pypokerlost` is the asynchronous Python SDK foundation for PokerLost.

It provides a typed client, an injectable session layer, declarative awaitable method objects,
centralized request/response handling, shared platform contracts, and a task-local current-client
context. The client intentionally has no endpoint-specific methods. Concrete PokerLost API methods
will be added later as separate method classes after their contracts are defined.

Before development, read [`AGENTS.md`](AGENTS.md), [`SERVICE.md`](SERVICE.md), and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

The repository directory is `pokerlost/`. The import package is directly inside it:

```text
pokerlost/
├── pypokerlost/
├── docs/
├── AGENTS.md
├── SERVICE.md
├── README.md
└── pyproject.toml
```

When commands below are run, the current directory is the repository root. Do not create another
nested `pokerlost/` directory.

## Install for development

```bash
uv lock
uv sync --locked --all-groups
```

The package is installed into the project environment in editable development form by `uv sync`.

## Show the installed version

```bash
uv run python -c "import pypokerlost; print(pypokerlost.__version__)"
```

Package metadata is the single version source. `pypokerlost.__version__` is resolved through
`importlib.metadata` rather than duplicated as a hard-coded constant.

## Core usage

Future ordinary API operations will be represented by immutable `Method` instances. The same method
can be executed in three supported forms.

### Explicit request

```python
result = await client.make_request(method)
```

### Callable client

```python
result = await client(method)
```

`Client.__call__()` is only a thin typed delegate to `make_request()`.

### Implicit current client

```python
from pypokerlost import Client

async with Client(base_url="https://api.example.invalid") as client:
    result = await method
```

Entering the client context installs that client in task-local context. `await method` resolves it
without storing the client on the method object. Calling `await method` outside an active client
scope raises `ClientContextError`.

The SDK deliberately does **not** support this style:

```python
await client.some_api_operation(...)
```

Endpoint-specific methods never belong on `Client`.

## Streaming content

A future content endpoint is represented by a `StreamMethod`. Streaming is explicit and
resource-safe:

```python
async with client.stream_content(stream_method) as content:
    async for chunk in content:
        process(chunk)
```

The stream is closed when the context exits, including when iteration stops early or an exception is
raised. The full response body is not buffered before iteration.

## Defining future methods

No concrete API methods exist in the initial foundation. When a contract becomes authoritative, add
a method class under the relevant namespace and follow the naming rules in `AGENTS.md`.

An ordinary method supplies:

- a stable RPC operation name in `namespace.method` form;
- an explicit `HttpMethod`, normally `HttpMethod.POST`;
- an explicit `result_type` runtime token;
- strict request fields.

A streaming method supplies:

- a stable operation name;
- an explicit `HttpMethod` when it differs from the default;
- strict request fields.

Both inherit class-level metadata and validation from `BaseMethod`. Methods do not implement request
building or response parsing. `RequestBuilder` creates the standard `PreparedRequest`, and
`ResponseHandler` decodes ordinary results through the declared result type. The SDK does not infer
result types through runtime generic introspection.

## Shared response contract

Every handled JSON operation outcome uses the frozen `ApplicationResponse[ResultT]` contract from
`pypokerlost.contracts`:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

A successful envelope forbids error metadata. A failed envelope requires both error fields and
forbids a result. `ok=True, result=None` remains valid for operations without a result. Concrete
services import this shared contract from the SDK rather than maintaining service-local copies.

`ResponseHandler` applies one response policy:

| HTTP status | Envelope | Outcome |
| --- | --- | --- |
| 2xx | valid, `ok=True` | Return the typed result. |
| any | valid, `ok=False` | Raise `ApplicationError` with the stable error code. |
| non-2xx | valid, `ok=True` | Raise `UnexpectedStatusError`. |
| 2xx | invalid | Raise `ResponseDecodeError`. |
| non-2xx | invalid | Raise `UnexpectedStatusError` with a bounded safe excerpt. |

Pydantic validation errors are contained at this boundary and do not leak as public SDK behavior.
For a non-2xx stream response, the SDK reads only a bounded error body, recognizes a valid
`ApplicationResponse[None]` failure as `ApplicationError`, and always closes the live response.

## Shared OpenAPI metadata

Services use the FastAPI-independent `rpc_openapi_extra()` helper to publish the versioned
`x-pokerlost` extension:

```python
rpc_openapi_extra(
    access=(AccessRole.AUTO, AccessRole.MASTER),
)
```

The extension declares deterministic `access.any_of` roles and whether a successful response is an
`application_response` or `content_stream`; its error response is always
`application_response`. Empty access, duplicate roles, and combining `public` with another role are
invalid. The helper returns a new plain JSON-compatible dictionary and has no FastAPI dependency.
It does not implement authorization, token acquisition, remote calls, or service discovery.

## Client configuration

Construction is explicit. Core SDK objects do not read environment variables automatically. Supply
either HTTP configuration for a client-created `HttpxSession`:

```python
client = Client(
    base_url="https://accounts.internal",
    default_headers={...},
)
```

or inject a configured session:

```python
client = Client(
    session=custom_session,
    owns_session=False,
)
```

Do not combine these forms. `base_url`, default headers, and timeout belong to `HttpxSession`, and
`Client` stores no competing URL. A client-created session is owned and closed by the client. An
injected session remains caller-owned by default; pass `owns_session=True` when the client should
close it. Repeated `Client.close()` calls are safe in either mode.

Authentication, token refresh, retries, and service discovery are not part of the first foundation.

## Quality checks

```bash
uv lock --check
make format
make lint
make typecheck
make build
python -m compileall -q pypokerlost
git diff --check
```

The `Makefile` contains thin wrappers only.

## Build the distribution

```bash
uv build
```

The build must produce both wheel and source distribution artifacts, include `py.typed`, and install
cleanly in an isolated environment.

## Current scope

Included:

- asynchronous client lifecycle;
- explicit and context-resolved ordinary method execution;
- `BaseMethod`, `Method`, and `StreamMethod` operation descriptions;
- centralized `RequestBuilder` and `ResponseHandler` policy;
- injectable `BaseSession` and production `HttpxSession`;
- shared `ApplicationResponse` and `x-pokerlost` contracts;
- resource-safe content streaming;
- SDK exception hierarchy;
- package typing and version metadata.

Deliberately absent:

- concrete PokerLost API methods;
- endpoint methods on `Client`;
- server-side application code;
- authentication policy;
- automatic retries;
- WebSocket subscriptions and event decorators;
- persistence, Docker, Helm, and Kubernetes configuration.

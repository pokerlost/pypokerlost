# pypokerlost

`pypokerlost` is the asynchronous Python SDK foundation for PokerLost.

It provides a typed client, an injectable HTTP transport, awaitable method objects, and a
task-local current-client context. The client intentionally has no endpoint-specific methods.
Concrete PokerLost API methods will be added later as separate method classes after their contracts
are defined.

Before development, read [`AGENTS.md`](AGENTS.md), [`SERVICE.md`](SERVICE.md), and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

The repository directory is `pokerlost/`. The import package is directly inside it:

```text
pokerlost/
├── pypokerlost/
├── tests/
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
- strict request fields;
- transport-request construction, usually using the default RPC path;
- typed response parsing.

A streaming method supplies:

- a stable operation name;
- strict request fields;
- transport-request construction.

The base SDK does not guess the final `ApplicationResponse` envelope. Add shared envelope decoding
only after the server contract is known.

## Client configuration

Construction is explicit. Core SDK objects do not read environment variables automatically.

Typical client inputs are:

- `base_url`;
- timeout configuration;
- default non-secret or caller-provided headers;
- an optional injected transport for tests or advanced integration.

A client-created transport is always owned and closed by the client. An injected transport remains
caller-owned by default; pass `owns_transport=True` when the client should close it. Repeated
`Client.close()` calls are safe in either mode.

Authentication, token refresh, retries, and service discovery are not part of the first foundation.

## Quality checks

```bash
uv lock --check
make format
make lint
make typecheck
make test
make build
python -m compileall -q pypokerlost tests
git diff --check
```

The `Makefile` contains thin wrappers only. Tests use fake or mock transports and do not call a live
PokerLost service.

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
- typed HTTP transport abstraction;
- production `httpx` transport;
- resource-safe content streaming;
- SDK exception hierarchy;
- package typing and version metadata;
- unit-tested extension points for future methods.

Deliberately absent:

- concrete PokerLost API methods;
- endpoint methods on `Client`;
- server-side application code;
- authentication policy;
- automatic retries;
- WebSocket subscriptions and event decorators;
- persistence, Docker, Helm, and Kubernetes configuration.

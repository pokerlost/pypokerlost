# pypokerlost architecture

Normative engineering rules live in [`../AGENTS.md`](../AGENTS.md); current product purpose and
scope live in [`../SERVICE.md`](../SERVICE.md).

## Design goal

The current architecture is a method-ready asynchronous SDK core. It fixes collaboration between
typed method objects, the client facade, pluggable sessions, request construction, response
interpretation, and lifecycle management without inventing Pokerlost product policy.

The dependency direction is:

```text
PokerlostMethod
→ Client
→ BaseSession
→ RpcRequestBuilder
→ HttpxSession HTTP I/O
→ BaseResponseHandler
→ ApplicationResponseHandler
→ ResultT
```

The exact ordinary execution sequence is:

```text
PokerlostMethod
→ Client.__call__
→ BaseSession.__call__
→ HttpxSession.make_request
→ RpcRequestBuilder.build
→ httpx.AsyncClient.request
→ BaseResponseHandler.handle implemented by ApplicationResponseHandler
→ declared ResultT
```

Explicitly bound method execution adds only this prefix:

```text
method.as_(client)
→ await method
→ PokerlostMethod.emit
→ Client.__call__
→ the same request pipeline
```

Application-managed execution is independent of method binding:

```text
Application
→ Client.start
→ user entrypoint(client)
→ Client.stop
```

There is no ambient or task-local current client, generic context bag, service locator,
dependency-injection container, authentication hook, route registry, middleware chain, or lower
transport abstraction.

## Package shape

```text
pypokerlost/
├── __init__.py
├── application.py
├── py.typed
├── client/
│   ├── __init__.py
│   ├── client.py
│   ├── context_controller.py
│   └── session/
│       ├── __init__.py
│       ├── base_session.py
│       └── httpx_session.py
├── contracts/
│   ├── __init__.py
│   ├── application_response.py
│   └── response_model.py
├── enums/
│   ├── __init__.py
│   ├── access_role.py
│   └── service_name.py
├── environment/
│   ├── __init__.py
│   └── api_server.py
├── exceptions/
│   ├── __init__.py
│   ├── api.py
│   ├── application.py
│   ├── base.py
│   └── client.py
├── methods/
│   ├── __init__.py
│   └── base.py
├── openapi/
│   ├── __init__.py
│   └── rpc_openapi_extra.py
├── request/
│   ├── __init__.py
│   ├── request_value_preparer.py
│   ├── rpc_request.py
│   └── rpc_request_builder.py
├── response/
│   ├── __init__.py
│   ├── application_response_handler.py
│   └── base_response_handler.py
└── types/
    ├── __init__.py
    └── json.py
```

Runtime code remains directly under `pypokerlost/`; the repository has no `src/` layout. Session
classes remain under `client/session/`, while transport-independent request and response
responsibilities live in their own top-level packages.

## Dependency direction and responsibilities

| Component | Current responsibility |
| --- | --- |
| `Application` | Coordinate automatic lifecycle for one `Client`. |
| `Client` | Choose a default session, bind a method, and delegate calls and lifecycle. |
| `ClientContextController` | Store optional private object-bound client context. |
| `PokerlostMethod` | Hold strict typed request fields and declarative service/operation/result metadata. |
| `AccessRole`, `ServiceName` | Represent closed SDK-owned metadata values. |
| `APIServer` | Turn one configured base into an operation URL. |
| `RequestValuePreparer` | Produce a strict recursively copied JSON-compatible value tree. |
| `RpcRequestBuilder` | Build one immutable HTTP-ready `RpcRequest`. |
| `BaseSession` | Resolve timeouts and orchestrate a builder, adapter execution, and handler. |
| `BaseResponseHandler` | Define the response-protocol strategy boundary. |
| `ApplicationResponseHandler` | Interpret the fixed Pokerlost application envelope. |
| `HttpxSession` | Compose concrete collaborators, own restartable HTTPX resources, and perform I/O. |
| `contracts` | Hold the authoritative response model and envelope. |
| `exceptions` | Expose focused lifecycle, client, transport, decode, protocol, and API failures. |
| `openapi` | Expose typed `x-pokerlost` service/access metadata. |

`Client` knows only the `BaseSession` interface. `BaseSession` works with method objects but receives
no separate `Client` parameter. Request construction serializes only public Pydantic fields. The
private client bound to a method is consulted only for method awaiting and future result-model
validation context.

Lower layers do not depend on the client facade:

- `request/` does not import `Client`;
- `response/` does not import `Client`;
- `client/session/` does not import or pass `Client` through its pipeline.

No arbitrary context dictionary, service locator, dependency container, or middleware chain
replaces that dependency.

## Environment and URLs

`APIServer` is an immutable `dataclass` with one format-template string:

```python
@dataclass(frozen=True, slots=True)
class APIServer:
    base: str

    def api_url(self, method: str) -> str:
        return self.base.format(method=method)

    @classmethod
    def from_base(cls, base: str) -> Self:
        normalized_base = base.rstrip("/")
        return cls(base=f"{normalized_base}/{{method}}")
```

The fixed default is:

```python
PRODUCTION = APIServer.from_base("http://localhost:8080/api")
```

Therefore `PRODUCTION.api_url("accounts.get")` is
`http://localhost:8080/api/accounts.get`. Custom one-base deployments pass another `APIServer` to
`HttpxSession`. This value does not contain tokens, local-mode flags, service routing, discovery, or
environment lookup.

`ServiceName` remains explicit metadata while this local gateway is shared. `APIServer` does not
read it or choose a host from it.

## Enums and explicit service identity

All SDK-owned enums live under `pypokerlost/enums/` and are exported from its focused facade:

```python
class AccessRole(StrEnum):
    PUBLIC = "public"
    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"


class ServiceName(StrEnum):
    ACCOUNTS = "accounts"
    AUTH = "auth"
```

`ServiceName` identifies accountsService and authService in SDK and OpenAPI metadata. It does not
choose a host, route a request, or trigger authentication. A future service requires a deliberate
new enum member; the current API has no free-form fallback.

`AccessRole` is OpenAPI metadata only and does not implement authorization policy.

## Bound client context and methods

`ClientContextController` is a Pydantic `BaseModel` with a private `_client` attribute. Pydantic
validation context may initialize it through `context={"client": client}`. Calling `.as_(client)`
sets that private attribute on the individual object and returns the same object. `.client` exposes
the optional binding.

This context belongs only to the individual object. It supports both awaiting a method and binding
future returned Pydantic SDK objects during result validation. It is the only client-binding
mechanism.

`PokerlostMethod[ResultT]` extends that controller with a strict request-model policy:

```python
ConfigDict(
    extra="forbid",
    strict=True,
    validate_default=True,
    arbitrary_types_allowed=True,
)
```

The whole model is intentionally not frozen because `.as_()` updates a private attribute. A future
concrete method declares:

```python
__service__: ClassVar[ServiceName]
__api_method__: ClassVar[str]
__http_method__: ClassVar[str] = "POST"
__returning__: ClassVar[Any]
```

Awaiting a method reads only its bound client. If none is bound, it raises `ClientContextError`.
Otherwise `emit(client)` calls `await client(self)`. The await iterator is typed at the standard
coroutine boundary rather than with a broad placeholder type.

No concrete operation exists in the package yet. A method never builds a request, decodes a
response, performs I/O, stores auth, retries, resolves service URLs, or creates endpoint wrappers.
Method behavior uses no metaclass, dynamic attribute lookup, runtime generic/MRO/Pydantic-internal
introspection, global current client, or task-local state.

## Request values and construction

The `types` facade intentionally exports:

```python
type JSONDumps = Callable[..., str]
type JSONLoads = Callable[..., Any]

type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
```

`RequestValuePreparer` is a normal instantiated collaborator. Its recursive
`prepare_value()` method:

- preserves `None`, `bool`, `int`, `float`, and `str`;
- recursively copies mappings and requires string keys;
- recursively turns lists and tuples into lists;
- converts `Enum` through `.value`;
- dumps Pydantic models with `mode="json"`, alias-free names, and `exclude_unset=True`;
- raises `TypeError` for every unsupported remaining value.

It does not remove nulls or stringify unknown values.

`RpcRequestBuilder` owns one `APIServer`, configured `JSONDumps`, and
`RequestValuePreparer`. `build(method)` reads each of `__service__`, `__api_method__`, and
`__http_method__` exactly once. It requires a `ServiceName` and non-empty operation and HTTP method
strings. It then:

1. calls `method.model_dump(mode="json", by_alias=False, exclude_unset=True)`;
2. passes the dumped value through `RequestValuePreparer`;
3. calls the configured `json_dumps` exactly once;
4. requires `json_dumps` to return `str`;
5. encodes that string once as UTF-8;
6. returns a `RpcRequest` with explicit service and operation metadata.

An unset field is omitted by `exclude_unset=True`. An explicitly supplied `None` is set and remains
JSON `null`. Private client context is not a model field and cannot enter the body.

The immutable transport-ready request is exactly:

```python
@dataclass(frozen=True, slots=True)
class RpcRequest:
    service: ServiceName
    operation: str
    http_method: str
    url: str
    content: bytes
```

It contains no client, auth, token or retry state, response, header policy, generic context, HTTP
framework object, routing metadata, or mutable JSON dictionary. Service is not inferred from the
operation prefix, operation is not reconstructed from the URL, and service does not affect URL
selection.

## Base session: orchestration only

`BaseSession` composes exactly one `RpcRequestBuilder` and one `BaseResponseHandler`, plus a timeout
defaulting to 10 seconds:

```python
class BaseSession(ABC):
    def __init__(
        self,
        *,
        request_builder: RpcRequestBuilder,
        response_handler: BaseResponseHandler,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None: ...
```

It exposes precise read-only `request_builder`, `response_handler`, and `timeout` properties. Its
concrete `__call__()` selects the session timeout only when no per-request value is supplied, then
delegates to abstract `make_request(method, timeout=effective_timeout)`. `start()` is a default
no-op; concrete adapters implement `make_request()` and `close()`. The base is an async context
manager that starts on entry and closes on exit.

`BaseSession` does not import or own:

- `APIServer`, `PRODUCTION`, `JSONDumps`, or `JSONLoads`;
- request serialization or response interpretation;
- envelope adapters or HTTP-status mapping;
- service identity logic or routing;
- authentication, retry, middleware, or arbitrary context.

There is no session response-parser method. Request building and response interpretation remain
composed collaborators rather than inherited session responsibilities.

## Response strategy

`BaseResponseHandler` is the one abstract response-protocol contract:

```python
class BaseResponseHandler(ABC):
    @abstractmethod
    def handle[ResultT](
        self,
        *,
        method: PokerlostMethod[ResultT],
        service: ServiceName,
        operation: str,
        status_code: int,
        content: str,
    ) -> ResultT: ...
```

It knows no `Client`, session class, `APIServer`, request serializer, authentication, or retry
policy.

`ApplicationResponseHandler` implements that strategy for the fixed public
`ApplicationResponse`. It owns a configured `JSONLoads`, one reusable adapter for
`ApplicationResponse[JsonValue]`, failed-status interpretation, and validation of the declared
result. Its exact algorithm is:

1. Decode `content` with configured `json_loads`. Only the customizable decoder call catches broad
   `Exception`; a failure becomes `ClientDecodeError` with its original cause.
2. Validate the decoded value as `ApplicationResponse[JsonValue]`. Envelope validation failures
   become `ClientDecodeError`.
3. If `ok` is false, raise a status-specific `PokerlostAPIError` subtype while preserving method,
   service, explicit operation, status, exact `error`, and exact `error_message`.
4. If `ok` is true but status is outside `200 <= status_code < 300`, raise
   `PokerlostProtocolError`.
5. Validate `envelope.result` using `TypeAdapter(method.__returning__)` with
   `context={"client": method.client}`. Result validation failures become `ClientDecodeError`.
6. Return the validated `ResultT` through one localized runtime adapter cast.

The handler does not dynamically construct a method-result-specific envelope, inspect generic
internals, import `Client`, or receive a generic context dictionary. Status mapping is an instance
method on this concrete strategy, not a registry, factory hierarchy, or class per status.

Failed-envelope status mapping is fixed:

| HTTP status | Exception |
| --- | --- |
| `400` | `PokerlostBadRequestError` |
| `401` | `PokerlostUnauthorizedError` |
| `403` | `PokerlostForbiddenError` |
| `404` | `PokerlostNotFoundError` |
| `409` | `PokerlostConflictError` |
| `413` | `PokerlostEntityTooLargeError` |
| `422` | `PokerlostValidationError` |
| `429` | `PokerlostTooManyRequestsError` |
| `>=500` | `PokerlostServerError` |
| every other status | `PokerlostAPIError` |

## HTTPX composition and I/O

`HttpxSession` is the concrete composition point for `APIServer`, the JSON encoder and decoder,
`RpcRequestBuilder`, `ApplicationResponseHandler`, and an internally owned `httpx.AsyncClient`:

```python
class HttpxSession(BaseSession):
    def __init__(
        self,
        *,
        api_server: APIServer = PRODUCTION,
        json_dumps: JSONDumps = json.dumps,
        json_loads: JSONLoads = json.loads,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None: ...
```

Construction creates no HTTP client. `start()` protects first initialization with an async lock,
creates one internal `httpx.AsyncClient`, and is idempotent. `make_request()` first builds the
`RpcRequest`, calls `start()` so direct client use works lazily, and sends:

```python
response = await http_client.request(
    method=request.http_method,
    url=request.url,
    content=request.content,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
    timeout=timeout,
)
```

The concrete `httpx.Response` remains inside `HttpxSession`. The adapter immediately delegates the
exact protocol inputs:

```python
return self.response_handler.handle(
    method=method,
    service=request.service,
    operation=request.operation,
    status_code=response.status_code,
    content=response.text,
)
```

There is no buffered status/body response class and no renamed wrapper for the same data.

An `httpx.TimeoutException` becomes `ClientTimeoutError`; another `httpx.TransportError` becomes
`ClientConnectionError`. Both keep the original exception as their cause. Cancellation and
unrelated exceptions are not broadly caught.

`close()` uses the same lock, removes and closes the current client once, and is idempotent. A later
`start()` creates a fresh HTTP client, so the session and its owning `Client` support sequential
reuse.

The adapter adds no auth headers, retry, streaming, environment loading, settings object, service
inference, or arbitrary context injection.

## Client lifecycle

`Client` is a thin facade:

```python
class Client:
    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session if session is not None else HttpxSession()
```

`start()` and `stop()` delegate to the session. `Client.__call__()` binds the method with
`method.as_(self)` and delegates to `session(method, timeout=request_timeout)`.
`make_request()` delegates back to `__call__()`, so both explicit call forms are identical. The
client is an async context manager.

It does not serialize requests, decode responses, inspect HTTPX internals, authenticate, route
services, own a settings model, expose concrete endpoints, implement dynamic attribute lookup, or
manage ambient current-client state.

## Application lifecycle

`Application` owns exactly one supplied `Client` and a running flag. Entry order is:

```text
reject an already-running application
→ mark running
→ await client.start()
→ return client
→ run caller scope or entrypoint
→ await client.stop()
→ reset running in finally
```

If startup fails, the flag is reset and the failure propagates. Concurrent or recursive entry raises
`ApplicationStateError`. Entrypoint and shutdown failures propagate after the guaranteed state
reset.

`run_async(entrypoint)` executes `await entrypoint(client)` inside the application context.
`run(entrypoint)` invokes that coroutine through standard-library `asyncio.run()`. A completed
application may be reused sequentially because the default session is restartable. Direct
`async with application` returns its managed client.

The class has no startup/shutdown callback registries, event dispatcher, router, polling loop,
signals, background-task owner, handler system, dependency injection, WebSockets, or decorators.

## Exception hierarchy and safety

```text
PokerlostError
├── ApplicationStateError
├── ClientError
│   ├── ClientContextError
│   ├── ClientDecodeError
│   ├── ClientConnectionError
│   └── ClientTimeoutError
└── PokerlostAPIError
    ├── PokerlostProtocolError
    ├── PokerlostBadRequestError
    ├── PokerlostUnauthorizedError
    ├── PokerlostForbiddenError
    ├── PokerlostNotFoundError
    ├── PokerlostConflictError
    ├── PokerlostEntityTooLargeError
    ├── PokerlostValidationError
    ├── PokerlostTooManyRequestsError
    └── PokerlostServerError
```

API errors keep safe typed metadata: `PokerlostMethod[Any]`, `ServiceName`, operation, status code,
and exact public error fields. Decode and transport errors keep only the safe metadata meaningful to
their stage. Public exception messages and fields never include request content, response bodies,
decoded bodies, headers, cookies, credentials, authorization values, or tokens.

The `401` category is response classification only and performs no login, refresh, retry, token
storage, or authorization mutation.

## Fixed wire contract

`ResponseModel` retains:

```python
ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    validate_default=True,
)
```

`ApplicationResponse` retains its four fields, defaults, and existing validator:

```python
ok: bool
result: ResultT | None = None
error: str | None = None
error_message: str | None = None
```

Success forbids error metadata. Failure forbids a result and requires both error fields. A
successful envelope may contain `result=None`; the method's declared return annotation decides
whether it is valid at the typed result boundary.

## OpenAPI metadata

`RpcOpenApiExtra` is one immutable FastAPI-independent value:

```python
@dataclass(frozen=True, slots=True)
class RpcOpenApiExtra:
    service: ServiceName
    access: tuple[AccessRole, ...]
    contract_version: int = 1
```

For example:

```python
RpcOpenApiExtra(
    service=ServiceName.ACCOUNTS,
    access=(AccessRole.AUTO, AccessRole.MASTER),
).as_dict()
```

returns a fresh dictionary on every call:

```python
{
    "x-pokerlost": {
        "contract_version": 1,
        "service": "accounts",
        "access": ["auto", "master"],
    },
}
```

The value preserves role order and performs no authorization-policy validation. It does not infer a
service from an operation. The old function-only helper is not exported. There is no OpenAPI
fetching, parsing, schema registry, method generator, generated source, code-generation CLI, or
runtime dynamic method system.

## Public facades

The package root intentionally exports `Application`, `Client`, `PokerlostMethod`,
`ApplicationResponse`, `ResponseModel`, the main public exception categories, and `__version__`.

Focused subpackage facades export:

- `BaseSession`, `HttpxSession`, and `DEFAULT_TIMEOUT` from `pypokerlost.client.session`;
- `ApplicationResponse` and `ResponseModel` from `pypokerlost.contracts`;
- `AccessRole` and `ServiceName` from `pypokerlost.enums`;
- `APIServer` and `PRODUCTION` from `pypokerlost.environment`;
- the full exception hierarchy from `pypokerlost.exceptions`;
- `PokerlostMethod` from `pypokerlost.methods`;
- `RpcOpenApiExtra` from `pypokerlost.openapi`;
- `RequestValuePreparer`, `RpcRequest`, and `RpcRequestBuilder` from `pypokerlost.request`;
- `ApplicationResponseHandler` and `BaseResponseHandler` from `pypokerlost.response`;
- `JSONDumps`, `JSONLoads`, `JsonScalar`, and `JsonValue` from `pypokerlost.types`.

There are no compatibility aliases for deleted or superseded architecture.

## Explicit exclusions and deferred decisions

The current SDK has no authentication implementation or placeholder, streaming API or placeholder,
concrete API method, endpoint wrapper, OpenAPI fetching/parsing/generation, generated source, schema
registry, code-generation CLI, runtime dynamic method, routing layer, retry behavior, settings
model, environment loading, status/body response wrapper, or WebSocket/update subsystem.

No static utility design exists in production code. `RequestValuePreparer` and response status
mapping are instance behavior; `APIServer.from_base()` is a genuine alternative constructor.
Production typing does not use broad `object` annotations as a substitute for precise types.

The first real accountsService and authService methods will provide evidence for future decisions
about:

- multi-service routing beyond one supplied `APIServer`;
- authentication ownership, authorization placement, and token refresh;
- proxy, TLS, connection-pool, custom-header, retry, and environment policy;
- endpoint wrappers, a synchronous SDK facade, and WebSocket/update behavior;
- any future streaming API and its error-body protocol.

Current URL construction, explicit service metadata, omission versus explicit-null encoding,
timeout delegation, status classification, response-strategy boundary, HTTPX ownership/restart
behavior, client lifecycle, and application lifecycle are implemented contracts rather than
deferred policy.

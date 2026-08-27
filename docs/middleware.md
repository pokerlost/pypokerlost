# RPC middleware

Middleware wraps RPC execution through `Client.make_request()`. It can observe a method, perform
application-specific work before and after execution, short-circuit a request, or translate an
exception. It does not wrap client, session, storage, or application startup and shutdown.

The same configured chain applies to `await client(method)`, `await client.make_request(method)`,
explicit `await method.as_(client)`, and implicit method execution through a current client.

## Registration

The constructor parameter is the singular collective noun `middleware`. Its default is `None`:

```python
from pypokerlost import Client

client = Client(
    middleware=(
        TimingMiddleware(),
        ErrorReportingMiddleware(),
    ),
)
```

The client copies the supplied sequence. Later mutation of a source list cannot change the client.
Passing `None` or an empty sequence configures no components.

Append one component to an existing client with `add_middleware()`:

```python
client = Client()
client.add_middleware(TracingMiddleware())
client.add_middleware(AuthorizationMiddleware(...))
```

The method returns the same client, so fluent registration is also possible. Registration neither
starts nor stops resources and is valid before or after client startup. Additions affect subsequent
requests.

`client.middleware` returns an immutable tuple snapshot of the current configuration:

```python
configured = client.middleware
```

The returned tuple cannot be used to modify client-owned registration state.

## Order and request snapshots

The first configured component is the outermost. Constructor components come first; each appended
component becomes the new innermost configured wrapper. Given `TimingMiddleware` followed by
`ErrorReportingMiddleware`, execution is:

```text
TimingMiddleware before
→ ErrorReportingMiddleware before
→ session execution
→ ErrorReportingMiddleware after
→ TimingMiddleware after
```

Before constructing a chain, each request takes an immutable snapshot of the current configuration.
A component appended while a request is already running is absent from that in-flight chain and is
used by the next request. Concurrent requests can therefore use different snapshots without their
chains changing partway through execution.

## Handler contract

Implement `BaseMiddleware.__call__()` and continue through the supplied `handler`:

```python
import logging
from time import monotonic

from pypokerlost import Client
from pypokerlost.methods import PokerlostMethod
from pypokerlost.middleware import BaseMiddleware, MiddlewareHandler
from pypokerlost.request import RPCRequestOptions

logger = logging.getLogger(__name__)


class TimingMiddleware(BaseMiddleware):
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler,
        method: PokerlostMethod[ResultT],
        client: Client,
        options: RPCRequestOptions,
    ) -> ResultT:
        started_at = monotonic()
        try:
            return await handler(method)
        finally:
            logger.info(
                "RPC operation completed",
                extra={
                    "operation": method.__api_method__,
                    "elapsed_seconds": monotonic() - started_at,
                },
            )
```

Each component receives the actual executing client and an isolated method copy bound to that
client. The caller's method object remains unchanged by `Client` execution.

A component may call `handler(method)` zero, one, or multiple times. Omitting `options` inherits the
immutable options received by the component. Passing `options=...` replaces them for that handler
call. Calling the handler zero times short-circuits the request; calling it more than once can
repeat the underlying RPC operation. Its return value becomes the result unless an outer component
changes it. Exceptions and cancellation propagate normally unless user code deliberately handles
them.

`MiddlewareHandler` is polymorphic rather than fixed to the outer method's result type. Passing a
different method copies and binds it to the same client, then executes it through only the remaining
middleware components. This permits a user-owned authorization component to call a refresh method
without re-entering itself.

Avoid logging method fields, stored values, headers, credentials, or exception data that may
contain secrets.

## Using client storage

Middleware may use the same explicit storage API as application code. This example records a
non-sensitive operation name before continuing:

```python
class LastOperationMiddleware(BaseMiddleware):
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler,
        method: PokerlostMethod[ResultT],
        client: Client,
        options: RPCRequestOptions,
    ) -> ResultT:
        await client.storage.set(
            "middleware.last_operation",
            method.__api_method__,
        )
        return await handler(method)
```

Storage remains outside RPC transport: the SDK does not insert stored data into requests or persist
results. See [`storage.md`](storage.md) for accepted values, expiration, and security guidance.

## Documentation-only authorization skeleton

Authorization policy is owned by the consuming application. A user-defined component can obtain
service-specific state and add a per-request header without mutating a shared HTTP client:

```python
class AuthorizationMiddleware(BaseMiddleware):
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler,
        method: PokerlostMethod[ResultT],
        client: Client,
        options: RPCRequestOptions,
    ) -> ResultT:
        access_token = await access_token_for_service(
            storage=client.storage,
            method=method,
        )
        authorized_options = options.with_headers(
            {"Authorization": f"Bearer {access_token}"},
        )
        return await handler(method, options=authorized_options)
```

`access_token_for_service()` and `AuthorizationMiddleware` are documentation-only, user-owned
artifacts, not SDK APIs. If policy requires refresh, the component can call a service-defined
`RefreshTokenMethod` through `handler(...)`; that call uses the remaining chain and may have a
different result type. It can then save the returned token with an explicit storage TTL and invoke
the original method once with updated options.

The SDK provides the typed header transport but no built-in authorization, credential model,
refresh policy, token keys, or retry behavior. Request options and transport requests are immutable
and copy-owned; never log their headers.

## Avoid recursive client calls

Continue the current operation with `handler(method)`. Calling `client(method)` for the same
operation from inside middleware starts a new configured chain and can recurse indefinitely.

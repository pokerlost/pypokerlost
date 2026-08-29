# Middleware

Middleware wraps one `Client.make_request()` execution and can observe, replace, or delegate a
typed method through the remaining client-owned chain.

## Public contract

Import the abstract component and its next-handler protocol from the focused facade:

```python
from pypokerlost.middleware import BaseMiddleware, MiddlewareHandler
```

A component implements this asynchronous call signature:

```python
from pypokerlost import Client, PokerlostMethod
from pypokerlost.client.request import RequestOptions
from pypokerlost.middleware import BaseMiddleware, MiddlewareHandler


class TraceHeaderMiddleware(BaseMiddleware):
    async def __call__[ResultT](
        self,
        handler: MiddlewareHandler,
        method: PokerlostMethod[ResultT],
        client: Client,
        options: RequestOptions,
    ) -> ResultT:
        next_options = options.with_headers(
            {
                "X-Trace-ID": "trace-123",
            },
        )
        return await handler(method, options=next_options)
```

The SDK includes no authorization, credential, or retry middleware. Components are supplied by the
caller for application-specific method-call wrapping.

## Registration and ordering

Pass initial components to the constructor or append them later:

```python
from pypokerlost import Client

client = Client(
    middleware=[
        outer,
        inner,
    ],
)
client.add_middleware(innermost)
```

Constructor input is copied. `add_middleware()` appends and returns the client. The first configured
component is outermost:

```text
outer(
    inner(
        innermost(
            session
        )
    )
)
```

Every request captures an immutable tuple snapshot before building its chain. Registration during
an active request affects later requests only. `client.middleware` returns a snapshot rather than
the mutable internal list.

## Call-next semantics

`MiddlewareHandler` is polymorphic for every method passed to it. A component may therefore execute
a different `PokerlostMethod[OtherResult]` through the remaining inner chain and return that
method's result. The replacement does not restart middleware that already ran. `Client` copies and
binds a different method before passing it onward.

A component may also short-circuit by returning its own value that satisfies its declared result
contract without calling `handler`, or call the handler more than once and repeat the underlying
operation. Middleware errors and cancellation propagate normally unless the component deliberately
handles them.

Middleware wraps only method execution. It does not wrap client startup, shutdown, application
lifecycle, session lifecycle, or storage operations.

## RequestOptions

Every component receives a concrete `RequestOptions` object. A next-handler call follows two rules:

- omitting `options` inherits the current options;
- supplying `options` replaces them for that call and all remaining inner components unless they
  replace them again.

Replacement is not an automatic merge. Use `options.with_headers(...)` to derive a new object while
retaining unrelated headers. Header replacement is case-insensitive and preserves ordered immutable
tuples.

```text
return await handler(method)

# Or replace the current options with a derived copy.
return await handler(
    method,
    options=options.with_headers({"X-Request-Mode": "audit"}),
)
```

The final `RequestBuilder` adds default JSON headers unless request options replace their names
case-insensitively. See `docs/api/transport.md` for the `RequestOptions` model and
`docs/architecture/request-response-pipeline.md` for its transport boundary.

See `docs/index.md`.

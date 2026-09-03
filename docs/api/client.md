# Client

`PokerlostClient` has one execution method:

```python
async def __call__[ResultT](
    self,
    method: PokerlostMethod[ResultT],
    *,
    options: PokerlostRequestOptions | None = None,
) -> ResultT: ...
```

Use it explicitly:

```python
result = await client(Method(...))
```

Or install a task-local current client:

```python
async with PokerlostClient(server=server) as client:
    result = await Method(...)
```

A non-default target is an explicit short-lived context. Methods are never copied, serialized for
revalidation, or mutated with a hidden client binding. `make_request` and metadata-returning paths
do not exist.

`PokerlostRequestOptions` is an immutable dataclass with only
`retry_policy: PokerlostRetryPolicy | None`. There is no public headers field.

Client errors distinguish configuration, connection, timeout, protocol, API, authentication,
expired access token, authorization, and missing authentication state. They retain only operation,
safe status/error/message fields, and optional body `retry_after`.

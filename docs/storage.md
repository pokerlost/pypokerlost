# Client storage

Every `Client` owns asynchronous storage for small pieces of JSON-compatible application state.
Storage is explicit: it does not add data to requests or save RPC results automatically.

`Client()` uses process-local `MemoryStorage` by default:

```python
await client.storage.set("client.locale", "en")
locale = await client.storage.get("client.locale")
```

## Operations

Use `contains()` before reading when a missing value is expected. `delete()` reports whether it
removed a live value, and `clear()` removes every value:

```python
if await client.storage.contains("client.locale"):
    locale = await client.storage.get("client.locale")

removed = await client.storage.delete("client.locale")
await client.storage.clear()
```

`get()` raises `StorageKeyNotFoundError` when a key is absent or expired:

```python
from pypokerlost.exceptions import StorageKeyNotFoundError

try:
    locale = await client.storage.get("client.locale")
except StorageKeyNotFoundError:
    locale = "en"
```

A stored top-level `None` is valid and is not treated as a missing value.

## Keys and values

Keys must be non-empty strings and cannot contain only whitespace. Valid keys are used exactly as
provided; storage does not strip, lowercase, prefix, hash, or otherwise rewrite them.

Values must match the recursive `JSONValue` type:

```python
from pydantic import FiniteFloat

type JSONValue = None | bool | int | FiniteFloat | str | list[JSONValue] | dict[str, JSONValue]
```

Convert domain objects explicitly before storing them. Pydantic models, dataclasses, bytes, UUIDs,
datetime objects, enums, files, callables, clients, sessions, and arbitrary Python objects are not
accepted. NaN and positive or negative infinity are not JSON values and are also rejected at any
nested depth.

Storage makes a deep copy on both `set()` and `get()`. Mutating a list or dictionary after storing
it, or mutating a value returned by `get()`, cannot change the stored value.

## Expiration

Pass a positive finite integer or floating-point number of seconds as `ttl`:

```python
await client.storage.set(
    "cache.account",
    {"id": "0195..."},
    ttl=30,
)
```

`timedelta` is also accepted:

```python
from datetime import timedelta

await client.storage.set(
    "temporary.result",
    result,
    ttl=timedelta(minutes=2),
)
```

In the second example, `result` must already be a `JSONValue`. `None` means no expiration and is the
default. Boolean, zero, negative, NaN, and infinite TTL values are rejected.

TTL is based on elapsed monotonic time. An entry expires exactly at its deadline, and reads do not
extend its lifetime. Expired entries behave like missing entries:

```text
get(expired_key)      -> StorageKeyNotFoundError
contains(expired_key) -> False
delete(expired_key)   -> False
```

Calling `set()` again replaces both the value and its expiration. Set a new TTL to refresh or
replace the lifetime, or omit `ttl` to make the replacement non-expiring:

```python
await client.storage.set("cache.account", {"id": "0195..."}, ttl=30)
await client.storage.set("cache.account", {"id": "0195..."}, ttl=120)
await client.storage.set("cache.account", {"id": "0195..."})
```

There is no default or sliding TTL. Call `set()` again when an application needs to refresh a
lifetime.

## Client reuse and custom storage

Closing `MemoryStorage` does not delete its values or pause TTL. Non-expiring values survive
sequential reuse of the same client or storage object; elapsed time can still expire temporary
values while the object is closed. A new `Client()` receives a new `MemoryStorage` instance.

To use another backend, implement the abstract `BaseStorage` contract and inject one instance:

```python
from pypokerlost import Client
from pypokerlost.storage import BaseStorage

storage: BaseStorage = CustomStorage(...)
client = Client(storage=storage)
```

The client starts and closes injected storage together with its session. Use
`application.client.storage` when working with an `Application`; `Application` has no separate
storage property.

## Security and non-goals

Do not place credentials, tokens, or other secrets in keys, because a missing-key exception keeps
the key as metadata. Do not log stored values. `MemoryStorage` keeps plain data in process memory
and is neither durable nor shared across processes.

Storage does not provide authentication, token handling, encryption, durable or external
persistence, transactions, queues, pub/sub, automatic request or response persistence, key
enumeration, TTL inspection or mutation, or background expiration workers. `MemoryStorage` is not
thread-safe or cross-process storage.

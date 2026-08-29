# Storage

Storage provides validated client-local `JSONValue` state with explicit asynchronous lifecycle and
optional relative expiration.

## Public imports

```python
from pypokerlost.storage import BaseStorage, MemoryStorage, StorageKey, StorageTTL
```

Storage exceptions are available from the exception facade:

```python
from pypokerlost.exceptions import StorageError, StorageKeyNotFoundError
```

`Client()` creates one `MemoryStorage` by default. An injected `BaseStorage` remains owned by that
client and follows the same startup and shutdown order.

## BaseStorage operations

The public asynchronous operations are:

```text
value = await storage.get(key)
await storage.set(key, value, ttl=None)
deleted = await storage.delete(key)
present = await storage.contains(key)
await storage.clear()
```

`start()` and `close()` own backend resources, and `BaseStorage` supports `async with`. Client code
normally accesses the owned backend through `client.storage` rather than managing it separately.

The base class validates every public key, value, and TTL before delegating to backend primitives.
It stores a defensive deep copy and returns another defensive deep copy, so caller mutation cannot
change stored state accidentally.

## Keys and values

`StorageKey` is a strict string that is not empty or whitespace-only. An invalid type raises
`TypeError`; an empty or whitespace-only value raises `ValueError`.

Values must satisfy `JSONValue`: exact built-in JSON scalars, lists, and string-keyed dictionaries
with finite numbers. Invalid values raise `TypeError`. A top-level `None` is valid and remains
distinct from an absent key because absence raises `StorageKeyNotFoundError`.

## TTL

`StorageTTL` accepts:

```text
int | float | timedelta | None
```

Integers and floats are relative seconds. `timedelta` is converted to seconds. `None` means no
expiration. Booleans, zero, negative values, infinity, and NaN are rejected; accepted values are
normalized to `float | None` before reaching the backend.

```python
from datetime import timedelta


async def cache_result(client) -> None:
    await client.storage.set(
        "temporary-result",
        {"ready": True},
        ttl=timedelta(minutes=5),
    )
```

Reads do not extend TTL. Replacing a key replaces its expiration, and setting the same key without
a TTL removes its previous expiration.

## MemoryStorage semantics

`MemoryStorage` keeps state in one Python process and one storage instance. It uses monotonic time
and removes expired entries opportunistically during `get()`, `set()`, `delete()`, and
`contains()`; it creates no cleanup task.

Missing and expired keys both raise `StorageKeyNotFoundError` from `get()`. `contains()` returns
`False` and `delete()` returns `False` after expiration.

`MemoryStorage.close()` is idempotent and does not clear values or pause TTL. Non-expiring values
survive sequential stop/start cycles on the same instance. Only `clear()` deliberately removes all
entries.

Storage is not a request cache, authorization store, global context, or transport extension. The
SDK provides no external backend, predefined keys, sliding TTL, expiration worker, transactions,
queues, or pub/sub behavior.

See `docs/architecture/client-lifecycle.md` for resource ordering and `docs/api/types.md` for the
underlying semantic aliases.

See `docs/index.md`.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from pypokerlost.exceptions import StorageKeyNotFoundError
from pypokerlost.types import JSONValue, StorageKey

from .base_storage import BaseStorage


@dataclass(slots=True)
class _MemoryStorageEntry:
    value: JSONValue
    expires_at: float | None


class MemoryStorage(BaseStorage):
    """Keep JSON-compatible values in memory for one storage instance."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        super().__init__()
        self._clock = clock
        self._entries: dict[str, _MemoryStorageEntry] = {}

    async def _get(self, key: StorageKey) -> JSONValue:
        self._purge_expired()
        try:
            return self._entries[key].value
        except KeyError:
            raise StorageKeyNotFoundError(key=key) from None

    async def _set(
        self,
        key: StorageKey,
        value: JSONValue,
        ttl: float | None,
    ) -> None:
        self._purge_expired()
        expires_at = None if ttl is None else self._clock() + ttl
        self._entries[key] = _MemoryStorageEntry(
            value=value,
            expires_at=expires_at,
        )

    async def _delete(self, key: StorageKey) -> bool:
        self._purge_expired()
        if key not in self._entries:
            return False
        del self._entries[key]
        return True

    async def _contains(self, key: StorageKey) -> bool:
        self._purge_expired()
        return key in self._entries

    async def _clear(self) -> None:
        self._entries.clear()

    async def close(self) -> None:
        """Close without deleting process-local values or pausing TTL."""

    def _purge_expired(self) -> None:
        now = self._clock()
        expired_keys = [
            key
            for key, entry in self._entries.items()
            if entry.expires_at is not None and entry.expires_at <= now
        ]
        for key in expired_keys:
            del self._entries[key]

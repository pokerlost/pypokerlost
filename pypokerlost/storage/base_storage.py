from __future__ import annotations

import abc
from copy import deepcopy
from types import TracebackType
from typing import Self, cast

from pydantic import ConfigDict, TypeAdapter, ValidationError

from pypokerlost.types import JSONValue, StorageKey, StorageTTL


class BaseStorage(abc.ABC):
    """Validate and isolate values around asynchronous storage primitives."""

    def __init__(self) -> None:
        self._key_adapter: TypeAdapter[StorageKey] = TypeAdapter(StorageKey)
        self._value_adapter: TypeAdapter[JSONValue] = TypeAdapter(
            JSONValue,
            config=ConfigDict(
                strict=True,
                allow_inf_nan=False,
            ),
        )
        self._ttl_adapter: TypeAdapter[StorageTTL] = TypeAdapter(StorageTTL)

    async def start(self) -> None:  # noqa: B027
        """Start backend resources; the default implementation is a no-op."""

    async def get(self, key: StorageKey) -> JSONValue:
        """Return an owned copy of the value stored under ``key``."""
        parsed_key = self._parse_key(key)
        value = await self._get(parsed_key)
        return self._copy_value(value)

    async def set(
        self,
        key: StorageKey,
        value: JSONValue,
        ttl: StorageTTL = None,
    ) -> None:
        """Validate and store an owned copy of ``value`` under ``key``."""
        parsed_key = self._parse_key(key)
        parsed_value = self._parse_value(value)
        parsed_ttl = self._parse_ttl(ttl)
        await self._set(
            parsed_key,
            self._copy_value(parsed_value),
            parsed_ttl,
        )

    async def delete(self, key: StorageKey) -> bool:
        """Delete ``key`` and report whether it existed."""
        return await self._delete(self._parse_key(key))

    async def contains(self, key: StorageKey) -> bool:
        """Report whether ``key`` exists without loading its value."""
        return await self._contains(self._parse_key(key))

    async def clear(self) -> None:
        """Remove every value from the storage backend."""
        await self._clear()

    @abc.abstractmethod
    async def close(self) -> None:
        """Release backend resources without deleting stored values."""

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _parse_key(self, key: StorageKey) -> StorageKey:
        try:
            return self._key_adapter.validate_python(key)
        except ValidationError as error:
            error_type = error.errors()[0]["type"]
            if error_type == "string_type":
                raise TypeError("Storage key must be a str") from error
            raise ValueError("Storage key must not be empty or whitespace-only") from error

    def _parse_value(self, value: JSONValue) -> JSONValue:
        try:
            return self._value_adapter.validate_python(value, strict=True)
        except ValidationError as error:
            raise TypeError("Storage value must be JSON-compatible") from error

    def _parse_ttl(self, ttl: StorageTTL) -> float | None:
        try:
            parsed_ttl = self._ttl_adapter.validate_python(ttl)
        except ValidationError as error:
            if any(detail["type"] == "value_error" for detail in error.errors()):
                raise ValueError(
                    "Storage TTL must be finite and greater than zero",
                ) from error
            raise TypeError(
                "Storage TTL must be an int, float, timedelta, or None",
            ) from error
        return cast(float | None, parsed_ttl)

    def _copy_value(self, value: JSONValue) -> JSONValue:
        return deepcopy(value)

    @abc.abstractmethod
    async def _get(self, key: StorageKey) -> JSONValue:
        """Load one value or raise ``StorageKeyNotFoundError``."""

    @abc.abstractmethod
    async def _set(
        self,
        key: StorageKey,
        value: JSONValue,
        ttl: float | None,
    ) -> None:
        """Store one already validated and owned value with normalized TTL."""

    @abc.abstractmethod
    async def _delete(self, key: StorageKey) -> bool:
        """Delete one value and report whether it existed."""

    @abc.abstractmethod
    async def _contains(self, key: StorageKey) -> bool:
        """Check whether one key exists without loading its value."""

    @abc.abstractmethod
    async def _clear(self) -> None:
        """Remove every value from the backend."""

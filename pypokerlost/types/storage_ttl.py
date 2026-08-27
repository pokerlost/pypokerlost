from datetime import timedelta
from math import isfinite
from typing import Annotated

from pydantic import AfterValidator, InstanceOf, StrictFloat, StrictInt

type _StorageTTLInput = StrictInt | StrictFloat | InstanceOf[timedelta] | None


def _normalize_storage_ttl(value: _StorageTTLInput) -> float | None:
    if value is None:
        return None

    try:
        seconds = value.total_seconds() if isinstance(value, timedelta) else float(value)
    except OverflowError as error:
        raise ValueError("Storage TTL must be finite") from error

    if not isfinite(seconds):
        raise ValueError("Storage TTL must be finite")
    if seconds <= 0:
        raise ValueError("Storage TTL must be greater than zero")
    return seconds


type StorageTTL = Annotated[
    _StorageTTLInput,
    AfterValidator(_normalize_storage_ttl),
]

"""Public PokerLost SDK exception facade."""

from __future__ import annotations

from pypokerlost.exceptions.api import (
    PokerlostAPIError,
    PokerlostProtocolError,
)
from pypokerlost.exceptions.application import ApplicationStateError
from pypokerlost.exceptions.base import PokerlostError
from pypokerlost.exceptions.client import (
    ClientConnectionError,
    ClientContextError,
    ClientDecodeError,
    ClientError,
    ClientRequestError,
    ClientStateError,
    ClientTimeoutError,
    MiddlewareConfigurationError,
)
from pypokerlost.exceptions.storage import StorageError, StorageKeyNotFoundError

__all__ = (
    "ApplicationStateError",
    "ClientConnectionError",
    "ClientContextError",
    "ClientDecodeError",
    "ClientError",
    "ClientRequestError",
    "ClientStateError",
    "ClientTimeoutError",
    "MiddlewareConfigurationError",
    "PokerlostAPIError",
    "PokerlostError",
    "PokerlostProtocolError",
    "StorageError",
    "StorageKeyNotFoundError",
)

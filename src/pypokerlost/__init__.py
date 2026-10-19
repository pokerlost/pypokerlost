"""Public package facade for the Pokerlost SDK."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

from pypokerlost.application import PokerlostApplication
from pypokerlost.client import PokerlostClient, PokerlostRequestOptions
from pypokerlost.errors import (
    PokerlostAccessTokenExpiredError,
    PokerlostAPIError,
    PokerlostAuthenticationError,
    PokerlostAuthenticationStateError,
    PokerlostAuthorizationError,
    PokerlostClientError,
    PokerlostConfigurationError,
    PokerlostConnectionError,
    PokerlostError,
    PokerlostProtocolError,
    PokerlostTimeoutError,
)
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import PokerlostResponse, PokerlostType

try:
    __version__ = _distribution_version("pypokerlost")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = (
    "PokerlostAPIError",
    "PokerlostAccessTokenExpiredError",
    "PokerlostApplication",
    "PokerlostAuthenticationError",
    "PokerlostAuthenticationStateError",
    "PokerlostAuthorizationError",
    "PokerlostClient",
    "PokerlostClientError",
    "PokerlostConfigurationError",
    "PokerlostConnectionError",
    "PokerlostError",
    "PokerlostMethod",
    "PokerlostProtocolError",
    "PokerlostRequestOptions",
    "PokerlostResponse",
    "PokerlostTimeoutError",
    "PokerlostType",
    "__version__",
)

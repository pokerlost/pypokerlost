"""Public package facade for the Pokerlost SDK."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

from pypokerlost.application import PokerlostApplication
from pypokerlost.client import PokerlostClient, PokerlostEnvironmentConfig, PokerlostRequestOptions
from pypokerlost.enums import Environment
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
    "Environment",
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
    "PokerlostEnvironmentConfig",
    "PokerlostError",
    "PokerlostMethod",
    "PokerlostProtocolError",
    "PokerlostRequestOptions",
    "PokerlostResponse",
    "PokerlostTimeoutError",
    "PokerlostType",
    "__version__",
)

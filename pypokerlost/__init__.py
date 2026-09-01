"""Public package facade for the PokerLost SDK."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

from pypokerlost import exceptions
from pypokerlost.application import Application
from pypokerlost.client.client import Client
from pypokerlost.client.response import Response
from pypokerlost.exceptions import (
    ApplicationStateError,
    ClientConnectionError,
    ClientContextError,
    ClientDecodeError,
    ClientError,
    ClientRequestError,
    ClientStateError,
    ClientTimeoutError,
    MiddlewareConfigurationError,
    PokerlostAPIError,
    PokerlostError,
    PokerlostProtocolError,
)
from pypokerlost.methods import PokerlostMethod
from pypokerlost.types import MutablePokerlostType, PokerlostType

from .openapi_extra import OpenAPIExtra

try:
    __version__ = _distribution_version("pypokerlost")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = (
    "Application",
    "ApplicationStateError",
    "Client",
    "ClientConnectionError",
    "ClientContextError",
    "ClientDecodeError",
    "ClientError",
    "ClientRequestError",
    "ClientStateError",
    "ClientTimeoutError",
    "MiddlewareConfigurationError",
    "MutablePokerlostType",
    "OpenAPIExtra",
    "PokerlostAPIError",
    "PokerlostError",
    "PokerlostMethod",
    "PokerlostProtocolError",
    "PokerlostType",
    "Response",
    "__version__",
    "exceptions",
)

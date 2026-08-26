from importlib.metadata import PackageNotFoundError, version as _distribution_version

from pypokerlost.application import Application
from pypokerlost.client import Client
from pypokerlost.contracts import ApplicationResponse, ResponseModel
from pypokerlost.exceptions import (
    ApplicationStateError,
    ClientConnectionError,
    ClientContextError,
    ClientDecodeError,
    ClientError,
    ClientTimeoutError,
    PokerlostAPIError,
    PokerlostError,
)
from pypokerlost.methods import PokerlostMethod

try:
    __version__ = _distribution_version("pypokerlost")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = (
    "Application",
    "ApplicationResponse",
    "ApplicationStateError",
    "Client",
    "ClientConnectionError",
    "ClientContextError",
    "ClientDecodeError",
    "ClientError",
    "ClientTimeoutError",
    "PokerlostAPIError",
    "PokerlostError",
    "PokerlostMethod",
    "ResponseModel",
    "__version__",
)

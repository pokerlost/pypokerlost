from importlib.metadata import version as _distribution_version

from pypokerlost.client import Client
from pypokerlost.errors import (
    ClientClosedError,
    ClientContextError,
    PokerLostError,
    ResponseDecodeError,
    TransportError,
    UnexpectedStatusError,
)
from pypokerlost.methods import Method, StreamMethod

__version__ = _distribution_version("pypokerlost")

__all__ = [
    "Client",
    "ClientClosedError",
    "ClientContextError",
    "Method",
    "PokerLostError",
    "ResponseDecodeError",
    "StreamMethod",
    "TransportError",
    "UnexpectedStatusError",
    "__version__",
]

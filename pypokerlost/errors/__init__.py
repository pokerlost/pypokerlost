"""Public Pokerlost SDK error facade."""

from __future__ import annotations

from .pokerlost_api_error import PokerlostAPIError
from .pokerlost_authentication_error import PokerlostAuthenticationError
from .pokerlost_authorization_error import PokerlostAuthorizationError
from .pokerlost_client_error import PokerlostClientError
from .pokerlost_configuration_error import PokerlostConfigurationError
from .pokerlost_connection_error import PokerlostConnectionError
from .pokerlost_error import PokerlostError
from .pokerlost_protocol_error import PokerlostProtocolError
from .pokerlost_timeout_error import PokerlostTimeoutError

__all__ = (
    "PokerlostAPIError",
    "PokerlostAuthenticationError",
    "PokerlostAuthorizationError",
    "PokerlostClientError",
    "PokerlostConfigurationError",
    "PokerlostConnectionError",
    "PokerlostError",
    "PokerlostProtocolError",
    "PokerlostTimeoutError",
)

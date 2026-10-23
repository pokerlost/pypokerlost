"""Immutable, caller-supplied environment selection without ambient I/O."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pypokerlost.enums import Environment, ServiceId
from pypokerlost.errors import PokerlostConfigurationError

from .pokerlost_api_server import PokerlostAPIServer


@dataclass(frozen=True, slots=True)
class PokerlostEnvironmentConfig:
    """Select one explicit endpoint; no DNS discovery, dotenv or Git inspection."""

    environment: Environment
    endpoints: Mapping[Environment, str] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.environment, Environment):
            raise PokerlostConfigurationError("Environment must be an Environment member")
        checked: dict[Environment, str] = {}
        for environment, endpoint in self.endpoints.items():
            if not isinstance(environment, Environment):
                raise PokerlostConfigurationError("Endpoint keys must be Environment members")
            try:
                target = PokerlostAPIServer(endpoint, environment=environment)
            except TypeError, ValueError:
                raise PokerlostConfigurationError(
                    "Invalid environment endpoint configuration"
                ) from None
            if target.base_url in checked.values():
                raise PokerlostConfigurationError("Environments must use distinct origins")
            checked[environment] = target.base_url
        object.__setattr__(self, "endpoints", MappingProxyType(checked))

    @property
    def configured(self) -> bool:
        return self.environment in self.endpoints

    def server(self, service_id: ServiceId | None = None) -> PokerlostAPIServer:
        endpoint = self.endpoints.get(self.environment)
        if endpoint is None:
            raise PokerlostConfigurationError("Selected environment is not_configured")
        return PokerlostAPIServer(endpoint, service_id, environment=self.environment)

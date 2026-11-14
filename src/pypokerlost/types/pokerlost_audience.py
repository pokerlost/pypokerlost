"""Canonical exact Pokerlost service audiences."""

from __future__ import annotations

import re

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from pypokerlost.enums import ServiceId

_AUDIENCE_PATTERN = re.compile(r"^[a-z][A-Za-z0-9]*$")


class PokerlostAudience(str):
    """An exact service name used consistently as a token audience."""

    def __new__(cls, value: str) -> PokerlostAudience:
        if isinstance(value, cls):
            return value
        if type(value) is not str:
            raise TypeError("Pokerlost audience must be a str")
        if _AUDIENCE_PATTERN.fullmatch(value) is None:
            raise ValueError("Pokerlost audience must be an exact service name")
        return str.__new__(cls, value)

    @classmethod
    def for_service(cls, service_id: ServiceId) -> PokerlostAudience:
        """Explicitly choose the established audience for a registered service."""
        if not isinstance(service_id, ServiceId):
            raise TypeError("Pokerlost audience mapping requires a ServiceId member")
        return cls(service_id.value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(strict=True),
        )

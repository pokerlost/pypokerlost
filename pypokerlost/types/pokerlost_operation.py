"""Validated Pokerlost operation identifiers."""

from __future__ import annotations

import re

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

_OPERATION_PATTERN = re.compile(r"^[a-z][A-Za-z0-9]*$")


class PokerlostOperation(str):
    """A single lowerCamelCase Pokerlost operation identifier."""

    def __new__(cls, value: str) -> PokerlostOperation:
        if isinstance(value, cls):
            return value
        if type(value) is not str:
            raise TypeError("Pokerlost operation must be a str")
        if _OPERATION_PATTERN.fullmatch(value) is None:
            raise ValueError("Pokerlost operation must be a single lowerCamelCase identifier")
        return str.__new__(cls, value)

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

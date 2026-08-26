from enum import StrEnum


class AccessRole(StrEnum):
    """Actor role declared in Pokerlost OpenAPI metadata."""

    PUBLIC = "public"
    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"

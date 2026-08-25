from enum import StrEnum


class AccessRole(StrEnum):
    """Actor roles understood by the shared PokerLost OpenAPI contract."""

    PUBLIC = "public"
    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"

from enum import StrEnum


class ServiceName(StrEnum):
    """Pokerlost service identity carried as explicit method metadata."""

    ACCOUNTS = "accounts"
    AUTH = "auth"

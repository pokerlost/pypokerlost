"""Registered case-sensitive HTTP routing identities, independent of scopes."""

from __future__ import annotations

from enum import StrEnum


class ServiceId(StrEnum):
    """SDK-owned catalog; deployment addresses are owned by platformInfra."""

    AUTH = "authService"
    ACCOUNTS = "accountsService"
    VIRTUAL_MONEY = "virtualMoney"
    POKER = "pokerService"
    CRYPTO = "cryptoService"

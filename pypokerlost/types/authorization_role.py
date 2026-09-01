"""Persisted Pokerlost authorization roles."""

from __future__ import annotations

from enum import StrEnum


class AuthorizationRole(StrEnum):
    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"

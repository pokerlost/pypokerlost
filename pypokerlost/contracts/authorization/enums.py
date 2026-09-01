"""Shared authorization wire enums."""

from __future__ import annotations

from enum import StrEnum


class OAuthTokenType(StrEnum):
    """OAuth2 access-token types supported by PokerLost services."""

    BEARER = "bearer"


class PrincipalType(StrEnum):
    """Authorization principal categories."""

    HUMAN = "human"
    SERVICE = "service"


class AuthorizationRole(StrEnum):
    """Persisted authorization roles shared across PokerLost services."""

    USER = "user"
    SUPPORT = "support"
    MASTER = "master"
    AUTO = "auto"


class PrincipalStatus(StrEnum):
    """Authorization principal lifecycle states."""

    ACTIVE = "active"
    DISABLED = "disabled"

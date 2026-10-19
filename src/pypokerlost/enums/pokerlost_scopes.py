"""Explicit shared catalog of Pokerlost access-token scopes."""

from __future__ import annotations

from enum import StrEnum


class PokerlostScopes(StrEnum):
    """SDK-owned scopes available to typed cross-service contracts."""

    ACCOUNTS_ACCOUNT_DISABLE = "accounts.account.disable"
    ACCOUNTS_ACCOUNT_ENABLE = "accounts.account.enable"
    ACCOUNTS_ACCOUNT_READ = "accounts.account.read"
    ACCOUNTS_ACCOUNT_REPLACE_SCOPES = "accounts.account.replaceScopes"
    ACCOUNTS_SELF_GET_ME = "accounts.self.getMe"
    ACCOUNTS_SELF_UPDATE_NICKNAME = "accounts.self.updateNickname"
    ACCOUNTS_STAFF_CREATE = "accounts.staff.create"
    AUTH_CLIENT_MANAGE = "auth.client.manage"
    AUTH_INTERNAL_ISSUE_LOGIN_GRANT = "auth.internal.issueLoginGrant"
    AUTH_INTERNAL_PROVISION_HUMAN = "auth.internal.provisionHuman"
    AUTH_INTERNAL_REPLACE_PRINCIPAL_SCOPES = "auth.internal.replacePrincipalScopes"
    AUTH_INTERNAL_SET_PRINCIPAL_STATUS = "auth.internal.setPrincipalStatus"
    AUTH_PRINCIPAL_REPLACE_SCOPES = "auth.principal.replaceScopes"
    AUTH_SCOPE_MANAGE = "auth.scope.manage"

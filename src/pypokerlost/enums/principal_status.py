"""Pokerlost authorization principal lifecycle states."""

from __future__ import annotations

from enum import StrEnum


class PrincipalStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"

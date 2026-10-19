"""Pokerlost authorization principal categories."""

from __future__ import annotations

from enum import StrEnum


class PrincipalType(StrEnum):
    HUMAN = "human"
    SERVICE = "service"

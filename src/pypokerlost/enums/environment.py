"""Explicit runtime environments, independent from Git refs and service identity."""

from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    MAIN = "main"
    DEV = "dev"
    TEST = "test"
    LOCAL = "local"

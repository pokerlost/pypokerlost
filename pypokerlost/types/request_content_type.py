"""Supported generated request-body media types."""

from __future__ import annotations

from typing import Literal

type HTTPRequestContentType = Literal[
    "application/json",
    "application/x-www-form-urlencoded",
]

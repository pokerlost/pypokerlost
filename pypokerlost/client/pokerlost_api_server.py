"""Validated Pokerlost API target."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from pypokerlost.types import PokerlostOperation


@dataclass(frozen=True, slots=True)
class PokerlostAPIServer:
    """An HTTPS API base, with loopback HTTP allowed only for local development."""

    base_url: str

    def __post_init__(self) -> None:
        if type(self.base_url) is not str:
            raise TypeError("Pokerlost API base URL must be a str")
        parsed = urlsplit(self.base_url)
        is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
            raise ValueError("Pokerlost API base URL must use HTTPS outside loopback development")
        if (
            not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Pokerlost API base URL must identify the origin root")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    def operation_url(self, operation: PokerlostOperation) -> str:
        return f"{self.base_url}/{operation}"


DEFAULT_POKERLOST_API_SERVER = PokerlostAPIServer("https://localhost:8080")

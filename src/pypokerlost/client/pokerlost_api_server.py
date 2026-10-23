"""Validated Pokerlost API target."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from pypokerlost.enums import Environment, ServiceId
from pypokerlost.types import PokerlostOperation

SERVICE_ID_HEADER = "x-pokerlost-serviceId"


@dataclass(frozen=True, slots=True)
class PokerlostAPIServer:
    """An HTTPS API base, with loopback HTTP allowed only for local development."""

    base_url: str
    service_id: ServiceId | None = None
    environment: Environment | None = None

    def __post_init__(self) -> None:
        if self.service_id is not None and not isinstance(self.service_id, ServiceId):
            raise TypeError("Gateway service_id must be a ServiceId member")
        if type(self.base_url) is not str:
            raise TypeError("Pokerlost API base URL must be a str")
        if self.environment is not None and not isinstance(self.environment, Environment):
            raise TypeError("Environment must be an Environment member")
        if any(character.isspace() or ord(character) < 32 for character in self.base_url):
            raise ValueError("Pokerlost API base URL contains invalid characters")
        if "\\" in self.base_url:
            raise ValueError("Pokerlost API base URL contains invalid characters")
        try:
            parsed = urlsplit(self.base_url)
            port = parsed.port
        except ValueError:
            raise ValueError("Invalid Pokerlost API origin") from None
        if not parsed.hostname or "%" in parsed.hostname or port == 0:
            raise ValueError("Invalid Pokerlost API origin")
        is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
            raise ValueError("Pokerlost API base URL must use HTTPS outside loopback development")
        if self.environment is not None:
            if self.environment is Environment.LOCAL and not is_loopback:
                raise ValueError("Local environment requires an explicit loopback origin")
            if self.environment is not Environment.LOCAL and parsed.scheme != "https":
                raise ValueError("Remote environments require HTTPS")
        if (
            not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Pokerlost API base URL must identify the origin root")
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        suffix = (
            f":{port}"
            if port is not None and port != {"http": 80, "https": 443}[parsed.scheme]
            else ""
        )
        object.__setattr__(self, "base_url", f"{parsed.scheme}://{host}{suffix}")

    def operation_url(self, operation: PokerlostOperation) -> str:
        return f"{self.base_url}/{operation}"


DEFAULT_POKERLOST_API_SERVER = PokerlostAPIServer("https://localhost:8080")

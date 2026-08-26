from pypokerlost.exceptions.base import PokerlostError


class ApplicationStateError(PokerlostError):
    """Raised when an application lifecycle entry is invalid."""

    def __init__(self) -> None:
        super().__init__("Application is already running")

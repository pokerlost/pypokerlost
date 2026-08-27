from pypokerlost.exceptions.base import PokerlostError


class StorageError(PokerlostError):
    """Base class for storage subsystem failures."""


class StorageKeyNotFoundError(StorageError):
    """Raised when a storage key is absent or expired."""

    key: str

    def __init__(self, *, key: str) -> None:
        self.key = key
        super().__init__("Storage key was not found")

from .pokerlost_error import PokerLostError


class ClientContextError(PokerLostError):
    """Raised when an awaitable method has no task-local current client."""

    def __init__(self) -> None:
        super().__init__(
            "No current Client is installed; use an explicit client or enter a client context."
        )

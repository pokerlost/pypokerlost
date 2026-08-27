from pypokerlost.enums import ServiceName
from pypokerlost.methods.base import PokerlostMethod


class AuthMethod[ResultT](PokerlostMethod[ResultT]):
    """Base method for requests carrying authService metadata."""

    __service__ = ServiceName.AUTH

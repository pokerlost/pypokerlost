from pypokerlost.enums import ServiceName
from pypokerlost.methods.base import PokerlostMethod


class AccountsMethod[ResultT](PokerlostMethod[ResultT]):
    """Base method for requests carrying accountsService metadata."""

    __service__ = ServiceName.ACCOUNTS

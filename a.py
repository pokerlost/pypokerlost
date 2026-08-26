from pypokerlost import Application, Client, PokerlostMethod, ResponseModel
from pypokerlost.client.session import HttpxSession
from pypokerlost.enums import ServiceName
from pypokerlost.environment import APIServer


class AccountsMethod[ResultT](PokerlostMethod[ResultT]):
    """Base method for requests carrying accountsService metadata."""

    __service__ = ServiceName.ACCOUNTS


class EchoResult(ResponseModel):
    message: str


class EchoMethod(AccountsMethod[EchoResult]):
    __api_method__ = "accounts.echo"
    __returning__ = EchoResult

    message: str


async def main(client: Client) -> None:
    request = EchoMethod(message="Привет из pypokerlost")
    result = await client(request)
    print(result.message)


if __name__ == "__main__":
    api_server = APIServer.from_base("http://127.0.0.1:8080/api")
    client = Client(HttpxSession(api_server=api_server))
    Application(client).run(main)

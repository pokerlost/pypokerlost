from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from pypokerlost.contracts import ApplicationResponse, ResponseModel


app = FastAPI(title="Pokerlost example service")


class EchoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: str


class EchoResult(ResponseModel):
    message: str


@app.post("/api/accounts.echo")
async def echo(request: EchoRequest) -> ApplicationResponse[EchoResult]:
    return ApplicationResponse(
        ok=True,
        result=EchoResult(message=f"Сервис получил: {request.message}"),
    )

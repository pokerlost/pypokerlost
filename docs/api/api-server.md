# API server

`APIServer` validates one PokerLost API URL template and expands a complete operation identifier
into its HTTP endpoint.

## Import and construction

Use the focused client transport module:

```python
from pypokerlost.client.api_server import APIServer, PRODUCTION
```

The usual constructor is `from_base()`:

```python
api_server = APIServer.from_base("https://pokerlost.example/api")

url = api_server.api_url("accounts.get")
assert url == "https://pokerlost.example/api/accounts.get"
```

`from_base()` accepts a strict HTTP(S) string, rejects user information, a query, or a fragment,
normalizes away a trailing slash, and appends `/{method}`. A non-string raises `TypeError`; an
invalid URL or URL with any rejected component raises `ValueError`.

Direct construction accepts the full template:

```python
api_server = APIServer(
    base="https://pokerlost.example/api/{method}",
)
```

The frozen, strict, extra-forbid model requires the template to end with exactly one `/{method}`.
`RequestBuilder` validates an operation before `HttpxSession` passes it to `api_url()`.

## Default target

The included constant is exactly:

```python
PRODUCTION = APIServer.from_base("http://localhost:8080/api")
```

Its normalized template is:

```text
http://localhost:8080/api/{method}
```

Despite the constant name, the current default is a localhost endpoint. It does not discover a
remote production service or derive a target from service metadata. Applications that use another
gateway must inject an explicit `APIServer` into `HttpxSession`.

```python
from pypokerlost import Client
from pypokerlost.client.api_server import APIServer
from pypokerlost.client.session import HttpxSession

session = HttpxSession(
    api_server=APIServer.from_base("http://127.0.0.1:8000/api"),
)
client = Client(session=session)
```

`APIServer` owns URL targeting only. It performs no network I/O, service discovery, routing,
authorization, or retry behavior. See [transport objects](transport.md) for `HttpxSession` and the
[pipeline architecture](../architecture/request-response-pipeline.md) for URL ownership.

[Documentation index](../index.md)

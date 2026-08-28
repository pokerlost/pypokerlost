# pypokerlost documentation

Use this index to find setup instructions, architecture explanations, public API guidance, generator
contracts, and maintainer workflows for `pypokerlost`.

## Getting started

- [Installation](getting-started/installation.md) — prepare the locked source environment or install
  a locally built wheel.
- [Quickstart](getting-started/quickstart.md) — create a client and execute a typed method.

## API

- [Client](api/client.md)
- [Types](api/types.md)
- [Methods](api/methods.md)
- [Transport objects](api/transport.md)
- [Middleware](api/middleware.md)
- [Storage](api/storage.md)
- [API server](api/api-server.md)
- [OpenAPI extra metadata](api/openapi-extra.md)

## Architecture

- [Overview](architecture/overview.md) — package ownership and the two canonical data flows.
- [Client lifecycle](architecture/client-lifecycle.md) — session/storage ownership, context, and
  `Application`.
- [Request and response pipeline](architecture/request-response-pipeline.md) — runtime execution
  from method fields to a validated result.
- [Types and methods](architecture/types-and-methods.md) — immutable API objects, method contracts,
  and client binding.
- [Generator architecture](architecture/generator.md) — validation, rendering, and safe ownership.

## Generator

- [Supported contract](generator/contract.md)
- [Command-line usage](generator/usage.md)
- [Generated layout and ownership](generator/generated-layout.md)

## Development

- [Commands](development/commands.md)
- [Python style](development/python-style.md)
- [Building distributions](development/building.md)
- [Releases and versions](development/releases.md)
- [Documentation style](development/documentation-style.md)

## Project

- [Current status](project/status.md)
- [Non-goals](project/non-goals.md)

Normative product boundaries live in [`SERVICE.md`](../SERVICE.md). Contributors and coding agents
must also follow [`AGENTS.md`](../AGENTS.md).

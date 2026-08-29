# pypokerlost documentation

Use this index to find setup instructions, architecture explanations, public API guidance, generator
contracts, and maintainer workflows for `pypokerlost`.

## Getting started

- `docs/getting-started/installation.md` — prepare the locked source environment or install
  a locally built wheel.
- `docs/getting-started/quickstart.md` — create a client and execute a typed method.

## API

- `docs/api/client.md`
- `docs/api/types.md`
- `docs/api/methods.md`
- `docs/api/transport.md`
- `docs/api/middleware.md`
- `docs/api/storage.md`
- `docs/api/api-server.md`
- `docs/api/openapi-extra.md`

## Architecture

- `docs/architecture/overview.md` — package ownership and the two canonical data flows.
- `docs/architecture/client-lifecycle.md` — session/storage ownership, context, and
  `Application`.
- `docs/architecture/request-response-pipeline.md` — runtime execution
  from method fields to a validated result.
- `docs/architecture/types-and-methods.md` — immutable API objects, method contracts,
  and client binding.
- `docs/architecture/generator.md` — validation, rendering, and safe ownership.

## Generator

- `docs/generator/contract.md`
- `docs/generator/usage.md`
- `docs/generator/generated-layout.md`

## Development

- `docs/development/commands.md`
- `docs/development/python-style.md`
- `docs/development/building.md`
- `docs/development/releases.md`
- `docs/development/documentation-style.md`

## Project

- `docs/project/status.md`
- `docs/project/non-goals.md`

Normative product boundaries live in `SERVICE.md`. Contributors and coding agents must also follow
`AGENTS.md`.

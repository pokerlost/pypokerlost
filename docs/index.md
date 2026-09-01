# pypokerlost documentation

Use this index to find setup instructions, architecture explanations, public API guidance, generator
contracts, and maintainer workflows for `pypokerlost`.

## Getting started

- `docs/getting-started/installation.md` — prepare the locked source environment or install
  a locally built wheel.
- `docs/getting-started/quickstart.md` — create a client and execute a typed method.

## API

- `docs/api/client.md` — client construction, execution, options, and lifecycle.
- `docs/api/types.md`
- `docs/api/methods.md`
- `docs/api/transport.md` — request options, transport, envelope decoding, and Retry-After.
- `docs/api/authorization-contracts.md` — shared scopes, token results, claims, and verified
  authorization contexts.
- `docs/api/retry.md` — the canonical explicit bounded transport retry policy.
- `docs/api/storage.md`
- `docs/api/api-server.md`

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

- `docs/project/status.md` — implemented runtime and generator surface.
- `docs/project/non-goals.md` — service, authorization-policy, and business-idempotency boundaries.

Normative product boundaries live in `SERVICE.md`. Contributors and coding agents must also follow
`AGENTS.md`.

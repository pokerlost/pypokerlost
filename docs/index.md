# pypokerlost documentation

This index covers installation, public API, runtime architecture, generation, and maintenance for
the body-only Pokerlost SDK.

## Getting started

- `docs/getting-started/installation.md` — prepare the locked environment or install a local wheel.
- `docs/getting-started/quickstart.md` — make public and protected calls.

## Public API

- `docs/api/client.md` — client, options, targeting, lifecycle, and errors.
- `docs/api/types.md` — canonical flat wire/value types.
- `docs/api/methods.md` — method metadata, imports, and current stubs.
- `docs/api/transport.md` — exact JSON envelopes and POST transport.
- `docs/api/body-authorization.md` — body authorization, token lifecycle, and token store port.
- `docs/api/retry.md` — explicit bounded retry and body delay handling.
- `docs/api/api-server.md` — HTTPS target validation.

## Architecture

- `docs/architecture/overview.md` — ownership and primary flows.
- `docs/architecture/client-lifecycle.md` — session and current-client lifecycle.
- `docs/architecture/request-response-pipeline.md` — middleware-to-transport execution.
- `docs/architecture/types-and-methods.md` — flat contracts and binding.
- `docs/architecture/generator.md` — global preflight, rendering, and ownership.

## Generator

- `docs/generator/contract.md` — accepted OpenAPI subset.
- `docs/generator/usage.md` — actual CLI commands and scope-map input.
- `docs/generator/generated-layout.md` — flat output and manifest ownership.

## Development

- `docs/development/commands.md`
- `docs/development/python-style.md`
- `docs/development/building.md`
- `docs/development/releases.md`
- `docs/development/documentation-style.md`

## Project

- `docs/project/status.md` — implemented runtime and future-facing stubs.
- `docs/project/non-goals.md` — service and business boundaries.

Normative product boundaries live in `SERVICE.md`; repository rules live in `AGENTS.md`.

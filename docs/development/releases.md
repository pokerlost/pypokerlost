# Releases and versions

The package has one canonical version in `pyproject.toml`. The generator and its ownership
manifest retain their independent versions and compatibility contracts. See [versioning](versioning.md).

## Exact-event delivery

The existing CI runs its complete native checks once for PRs and pushes to `test`, `dev` and
`main`. On every `dev` or `main` push, including documentation changes, its successful `required`
job feeds the pinned [Python release provider](https://github.com/pokerlost/.github/blob/e5cac33af228224af9deaef308e39c1b9f788033/docs/python_release_contract.md).
The provider allocates a version for that original event. The native builder exports the exact
commit to a separate directory, injects the allocated PEP 440 version with uv, builds wheel/sdist
with the existing locked backend, and verifies a fresh installed wheel outside the checkout.
The original source and lock are unchanged. Actual backend/frontend versions and native metadata
are recorded in `python-build-receipt.json`; all distributions and the receipt are attested.

A separate read-only verifier checks immutable artifact identity, archive metadata and signed
provenance. Its dependent publisher repeats verification before creating the GitHub Release.
Only the provider owns tags, version allocation and publication. The builder has no `contents:write`
permission or publication secret. This workflow does not publish to PyPI or deploy a service.

Tags are `vX.Y.Z-dev.N` for development releases and `vX.Y.Z` for stable releases. Native package
versions are `X.Y.Z.devN` and `X.Y.Z`. The source version declares the reviewed floor; the shared
allocator chooses the actual version above existing allocations. Development releases are
prereleases and never latest. Permanent promotions use merge commits and preserve ancestry.

## Local verification

Run `make ci-local` for fresh source checks, canonical distributions and separate installed-wheel
acceptance. The latter verifies metadata, typing and the installed generator from outside a checkout.
It does not repeat the source suite. Reports and checksums are ignored under `coverage/`;
`coverage/artifacts/` contains native artifacts. `make release-check` never publishes.

## Recovery

Rerun the complete original CI run with `gh run rerun RUN_ID --repo pokerlost/pypokerlost`.
The current attempt must repeat preflight. Existing immutable allocation identity is reused;
when a verified build record exists, the builder is skipped and publication reuses its original
artifact, receipt and proof bytes. Do not rerun only failed jobs, change the source SHA, move a tag,
overwrite assets or manually create a duplicate release. Conflicting metadata or unavailable
native/provenance evidence remains blocked. The provider contract defines the read-only audit
and artifact-retention limits.

See [the documentation index](../index.md) for the public SDK and generator contracts.

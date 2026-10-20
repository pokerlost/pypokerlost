# Releases and versions

Current versions:

```text
SDK package: read pyproject.toml (unreleased candidate)
Generator:   read GENERATOR_VERSION (independent)
Manifest:    read MANIFEST_VERSION (format contract)
```

The package version lives in `pyproject.toml`. The independent generator version is printed by
`uv run --locked python scripts/generate_methods.py --version`. Generator major version three owns
standard OpenAPI scope extraction and explicit tri-state method metadata. The shared
`PokerlostScopes` catalog is an SDK-owned source contract, not generated output.

Service OpenAPI SemVer and canonical source hashes are recorded in the manifest. Publishing and
deployment automation remain outside this repository.

Run `make ci-local` for one fresh full source suite, canonical distributions and a separate
installed-wheel acceptance check. The latter verifies metadata, typing and installed generator
entrypoint from outside a checkout; it does not repeat the source suite. Reports, JUnit, coverage
and checksums live under ignored `coverage/`; `coverage/artifacts/` contains the native delivery artifacts.
Report identity includes source SHA, dirty state and actual content hash. Below-100% coverage
warns; missing/stale reports and test/type/build failures fail.

Decide compatibility, update canonical version/changelog, run checks, review and integrate into
main. Check the exact clean integrated commit before creating an annotated `v<version>` tag.
Inspect workflow triggers first; the current CI runs on main/PR, not tags. Push only the specific
new tag and verify its remote tag object and peeled commit. Never replace a published tag.
A billing-blocked required check keeps its PR and branch open; local success is not hosted success.
GitHub Releases, package publication and deployment remain separate authorization decisions.

See [versioning](versioning.md) and [the documentation index](../index.md).

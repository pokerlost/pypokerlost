# Releases and versions

Current versions:

```text
SDK package: read pyproject.toml (unreleased candidate)
Generator:   3.0.1
Manifest:    4
```

The package version lives in `pyproject.toml`. The independent generator version is printed by
`uv run --locked python scripts/generate_methods.py --version`. Generator major version three owns
standard OpenAPI scope extraction and explicit tri-state method metadata. The shared
`PokerlostScopes` catalog is an SDK-owned source contract, not generated output.

Service OpenAPI SemVer and canonical source hashes are recorded in the manifest. Publishing and
deployment automation remain outside this repository.

The current patch candidate fixes generator schema collection/nullable unions and controlled
inspection errors, without changing the runtime wire protocol. Source and installed-wheel suites
must both pass, including valid fresh coverage reports with advisory percentages, before a release decision. CI retains private
candidate artifacts; it does not publish them. Existing service pins remain on their reviewed
main-branch SDK revision until a separately reviewed dependency update. A tag, merge or release is
not implied by candidate metadata.

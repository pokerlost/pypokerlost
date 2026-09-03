# Releases and versions

Current versions:

```text
SDK package: 0.2.0
Generator:   3.0.0
Manifest:    4
```

The package version lives in `pyproject.toml`. The independent generator version is printed by
`uv run --locked python scripts/generate_methods.py --version`. Generator major version three owns
standard OpenAPI scope extraction and explicit tri-state method metadata. The shared
`PokerlostScopes` catalog is an SDK-owned source contract, not generated output.

Service OpenAPI SemVer and canonical source hashes are recorded in the manifest. Publishing and
deployment automation remain outside this repository.

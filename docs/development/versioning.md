# Versioning

The SDK distribution has one canonical PEP 440 version in `pyproject.toml`; runtime metadata
is derived by `importlib.metadata`. The generator has its existing independent version in
`GENERATOR_VERSION`, and its generated ownership-manifest format is `MANIFEST_VERSION` in
`scripts/generate_methods.py`. `make version` shows all three without changing them.
The current tooling change does not alter the SDK version, generator contract or manifest format.

The generator is shipped in the SDK wheel but records its own generation behavior version.
Primary package tags use `v<package-version>`; independently reviewed generator milestones use
`generator/v<generator-version>`. A manifest format revision changes only when consumers need a
new format contract, never for a README edit or packaging-tool change. Existing generated files
and service pins remain on their reviewed revisions until an explicit generator/dependency update.

Apply the shared major/minor/patch policy: stable major breaks contracts, minor adds compatible
functionality, patch fixes compatible behavior. Before 1.0, minor changes may break contracts only
with migration notes and consumer tests; patch preserves compatibility. PEP 440 development, alpha,
beta and release-candidate versions require explicit opt-in and are not automatic stable defaults.
Check public imports, HTTP/auth/header semantics, generator CLI, manifest ownership and preserved
user-written files, configuration and minimum Python before a version decision.

`make release-check` checks wheel/sdist metadata against the canonical source. It neither creates
a tag nor publishes an artifact. See [releases](releases.md) and [the documentation index](../index.md).

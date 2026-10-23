# pypokerlost

Read selected [baseRules](https://raw.githubusercontent.com/serrja/baseRules/bafcb63ed94b9769a0ca098e5db4b33c55dbc1b9/docs/engineering.md),
then [Pokerlost norms](https://raw.githubusercontent.com/pokerlost/projectRules/904c65a3daab88802fb5e414cdaccc7ad2b555a8/docs/project.md),
then the full [local SDK contracts](docs/development/agent-contracts.md), `SERVICE.md`
and the affected architecture/API page. This override owns SDK imports, typed
routing/scopes, redaction/retry and generator behavior. Runtime remains under
`src/pypokerlost`; public imports remain `pypokerlost`.

Pins are reading sources, not automatic loaders or grants. Review source diff,
change full-SHA links explicitly and run documentation checks for rule updates.

Daily work uses `dev` and lint only. `main` and `test` stay unchanged until an
explicit promotion. Full acceptance, template render/update checks, builds and
releases are manual; a dev snapshot is not a verified release.

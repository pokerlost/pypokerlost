# pypokerlost

Read selected [baseRules](https://raw.githubusercontent.com/serrja/baseRules/730418d3cc480b4f05b88b4c8275296c4845a75a/docs/engineering.md),
then [Pokerlost norms](https://raw.githubusercontent.com/pokerlost/projectRules/4785546cffa58f7ae1c22b6d6b8846a0141793eb/docs/project.md),
then the full [local SDK contracts](docs/development/agent-contracts.md), `SERVICE.md`
and the affected architecture/API page. This override owns SDK imports, typed
routing/scopes, redaction/retry and generator behavior. Runtime remains under
`src/pypokerlost`; public imports remain `pypokerlost`.

Pins are reading sources, not automatic loaders or grants. Review source diff,
change full-SHA links explicitly and run documentation checks for rule updates.

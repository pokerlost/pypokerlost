# pypokerlost

Read selected [baseRules](https://raw.githubusercontent.com/serrja/baseRules/8434509933feaa71ba312f8d02caad7362766d5a/docs/engineering.md),
then [Pokerlost norms](https://raw.githubusercontent.com/pokerlost/projectRules/c3bfb397c46c2fa1021009e13f9e1090d9078176/docs/project.md),
then the full [local SDK contracts](docs/development/agent-contracts.md), `SERVICE.md`
and the affected architecture/API page. This override owns SDK imports, typed
routing/scopes, redaction/retry and generator behavior. Runtime remains under
`src/pypokerlost`; public imports remain `pypokerlost`.

Pins are reading sources, not automatic loaders or grants. Review source diff,
change full-SHA links explicitly and run documentation checks for rule updates.

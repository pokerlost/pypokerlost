# Documentation style

Repository documentation is concise, English-language guidance organized by a single owner for
each subject.

## Document ownership

- `README.md` is the short repository entry point.
- `SERVICE.md` defines the product boundary.
- `AGENTS.md` defines normative engineering rules.
- `docs/index.md` is the navigation hub.
- `docs/architecture/` explains internal collaborations.
- `docs/api/` guides use of the public SDK surface.
- `docs/generator/` owns the generation contract and workflow.
- `docs/development/` owns maintainer workflows.
- `docs/project/` records current state and non-goals.

Do not copy a long rule or procedure between owners. Keep the authoritative explanation in one
place and reference its repository-root path from related pages.

## Page structure

Every Markdown page has exactly one H1 followed by a short introductory paragraph. Use H2 and H3
headings in logical order, and use tables only when a real comparison or matrix is clearer than
prose. Public guide filenames use lowercase kebab-case.

Every fenced block declares its language, such as `python`, `bash`, `toml`, `json`, or `text`.
Leaf pages end by referring to `docs/index.md`.

## Links and paths

Do not use Markdown links between repository files. Refer to an internal file by its repository-root
path in inline code, such as `docs/architecture/overview.md` or `SERVICE.md`. HTTP(S) links,
`mailto:` links, and same-document `#anchor` links remain allowed. Documentation must not contain
workstation-specific absolute paths. The repository-local checker enforces these rules. When a page
is replaced before stable public documentation URLs exist, remove the obsolete page after migrating
its unique content rather than keeping a redirect stub.

## Examples

Examples use current public imports and Python 3.14 syntax. Compile or import-check them when
practical. If an example shows a class or service package not tracked in this repository, label it
as illustrative instead of presenting it as an available import.

Do not include credential values, token values, authorization header values, private repository
URLs, raw sensitive request or response bodies, or unimplemented streaming or WebSocket APIs.
Update examples when a public import, command, minimum Python version, or behavior changes.

See `docs/index.md`.

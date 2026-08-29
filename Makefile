.DEFAULT_GOAL := help

UV ?= uv

.PHONY: help lock lock-check sync format format-check lint typecheck compile build \
	docs-check generator-check import-check pre-commit check check-full

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

lock: ## Resolve dependencies and update uv.lock.
	$(UV) lock

lock-check: ## Verify that uv.lock matches project metadata.
	$(UV) lock --check

sync: ## Install every locked dependency group.
	$(UV) sync --locked --all-groups

format: ## Apply safe Ruff fixes and formatting.
	$(UV) run --locked ruff check --fix .
	$(UV) run --locked ruff format .

format-check: ## Check Ruff formatting without changing files.
	$(UV) run --locked ruff format --check .

lint: ## Run Ruff lint without changing files.
	$(UV) run --locked ruff check .

typecheck: ## Run strict mypy.
	$(UV) run --locked mypy

compile: ## Compile runtime and tooling sources.
	$(UV) run --locked python -m compileall -q pypokerlost scripts

build: ## Build the wheel and source distribution.
	$(UV) build

docs-check: ## Enforce Markdown reference policy.
	$(UV) run --locked python scripts/check_documentation.py

generator-check: ## Verify that the generator imports and reports its version.
	$(UV) run --locked python scripts/generate_methods.py --version

import-check: ## Import the canonical public SDK foundation.
	$(UV) run --locked python -c "from pypokerlost import Client, PokerlostMethod; from pypokerlost.types import APIOperation; print(Client.__name__, PokerlostMethod.__name__, APIOperation)"

pre-commit: ## Run every configured hook against all files.
	$(UV) run --locked pre-commit run --all-files --show-diff-on-failure

check: lock-check format-check lint typecheck compile docs-check generator-check import-check ## Run the regular non-mutating gate.

check-full: check build pre-commit ## Run the complete repository gate.

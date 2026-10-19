ifneq ($(CONTAINERIZED),1)
QUALITY_IMAGE := pypokerlost:quality
RUNTIME_IMAGE := pypokerlost:candidate
QUALITY_EXTRA_TARGETS := docs-check compile lock-check format-check
QUALITY_EXTRA_TARGETS += generator-check import-check
IMAGE_COMMAND = printf "%s\n" "notApplicable: SDK library; wheel and sdist are the delivery artifacts"
VERIFY_COMMAND = $(MAKE) CONTAINERIZED=1 test-image && $(QUALITY_RUN) python docker/coverage_report.py coverage/container/coverage.json --after coverage/container/.started --output coverage/container/summary.md
verify: quality-image
include docker/quality-python.mk
else
.DEFAULT_GOAL := help

UV ?= uv

.PHONY: help lock lock-check sync format format-check lint typecheck test compile build \
	docs-check generator-check import-check pre-commit check check-full test-image

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

test: ## Run runtime and generator tests with full statement/branch coverage.
	$(UV) run --locked pytest --cov --cov-report=term-missing --cov-report=json --cov-report=xml

compile: ## Compile runtime and tooling sources.
	$(UV) run --locked python -m compileall -q pypokerlost scripts

build: ## Export the canonical wheel and source distribution from Docker.
	docker buildx build --target artifacts --output type=local,dest=dist .

test-image: ## Run fresh installed-wheel checks without network or a source checkout.
	@mkdir -p coverage/container
	docker buildx build $(DOCKER_BUILD_ARGS) --target test --load --tag pypokerlost:test .
	@touch coverage/container/.started
	docker run --rm --read-only --network none --tmpfs /tmp:rw,noexec,nosuid,size=128m --user "$$(id -u):$$(id -g)" --mount type=bind,source="$$(pwd)/coverage/container",target=/checks/coverage pypokerlost:test

docs-check: ## Enforce Markdown reference policy.
	$(UV) run --locked python scripts/check_documentation.py

generator-check: ## Verify that the generator imports and reports its version.
	$(UV) run --locked python scripts/generate_methods.py --version

import-check: ## Import the canonical public SDK foundation.
	$(UV) run --locked python -c "from pypokerlost import PokerlostClient, PokerlostMethod, PokerlostRequestOptions; print(PokerlostClient.__name__, PokerlostMethod.__name__, PokerlostRequestOptions.__name__)"
	$(UV) run --locked python -c "from pypokerlost.methods import GetToken, RefreshToken, ReplacePrincipalScopes; from pypokerlost.middleware import PokerlostAuthenticationMiddleware, PokerlostRetryMiddleware, PokerlostRetryPolicy; print(GetToken.__name__, RefreshToken.__name__, ReplacePrincipalScopes.__name__, PokerlostAuthenticationMiddleware.__name__, PokerlostRetryMiddleware.__name__, PokerlostRetryPolicy.__name__)"
	$(UV) run --locked python -c "from pypokerlost.enums import PokerlostScopes, PrincipalStatus, PrincipalType; from pypokerlost.types import PokerlostAudience, PokerlostOperation, PokerlostRequest, PokerlostResponse, PokerlostStoredToken, PokerlostToken; print(PokerlostScopes.__name__, PrincipalStatus.__name__, PrincipalType.__name__, PokerlostAudience.__name__, PokerlostOperation.__name__, PokerlostRequest.__name__, PokerlostResponse.__name__, PokerlostStoredToken.__name__, PokerlostToken.__name__)"

pre-commit: ## Run every configured hook against all files.
	$(UV) run --locked pre-commit run --all-files --show-diff-on-failure

check: lock-check format-check lint typecheck test compile docs-check generator-check import-check ## Run the regular non-mutating gate.

check-full: check build pre-commit ## Run the complete repository gate.

endif

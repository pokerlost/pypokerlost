ifeq ($(CONTAINERIZED),1)
RUFF ?= ruff
else
RUFF ?= uvx --from ruff==0.16.4 ruff
endif
# Quick dev commands never prepare a product/build image.
ifneq ($(filter lint format format-check check,$(MAKECMDGOALS)),)
override CONTAINERIZED := 1
endif
ifneq ($(CONTAINERIZED),1)
QUALITY_IMAGE := pypokerlost:quality
RUNTIME_IMAGE := pypokerlost:candidate
QUALITY_EXTRA_TARGETS := docs-check compile lock-check format-check
QUALITY_EXTRA_TARGETS += generator-check import-check
IMAGE_COMMAND = printf "%s\n" "notApplicable: SDK library; wheel and sdist are the delivery artifacts"
BUILD_COMMAND = $(DOCKER) buildx build --file $(BUILD_DOCKERFILE) $(DOCKER_BUILD_ARGS) $(LOCAL_BUILD_NETWORK) --target $(ARTIFACT_TARGET) --output type=local,dest=coverage/artifacts .
BUILD_RECEIPT_COMMAND = $(QUALITY_RUN) python docker/release.py capture-build --artifact-dir coverage/artifacts
RELEASE_CHECK_COMMAND = $(QUALITY_RUN) python docker/release.py release-check --artifact-dir coverage/artifacts
VERIFY_COMMAND = $(MAKE) CONTAINERIZED=1 test-image LOCAL_BUILD_NETWORK='$(LOCAL_BUILD_NETWORK)'
OFFLINE_PREFLIGHT_COMMAND = $(MAKE) sdk-offline-preflight
ifeq ($(OFFLINE),1)
BUILD_COMMAND = $(RELEASE_CHECK_COMMAND)
VERIFY_COMMAND = $(MAKE) sdk-offline-preflight && $(MAKE) CONTAINERIZED=1 test-image
endif
VERSION_COMMAND = $(QUALITY_RUN) python docker/release.py version && $(QUALITY_RUN) python -c 'from scripts.generate_methods import GENERATOR_VERSION, MANIFEST_VERSION; print("generator:", GENERATOR_VERSION, "manifest:", MANIFEST_VERSION)'
verify: quality-image
QUALITY_EXTRA_TARGETS += acceptance
CI_LOCAL_TARGETS ?= acceptance coverage build verify release-check
include docker/quality-python.mk
.PHONY: sdk-offline-preflight
sdk-offline-preflight:
	$(RELEASE_CHECK_COMMAND)
	@test -s coverage/container/test-image-id.txt -a -s coverage/container/source.json || { echo 'BLOCKED: prepare installed acceptance online.' >&2; exit 3; }
	@test "$$(cat coverage/container/test-image-id.txt)" = "$$($(DOCKER) image inspect pypokerlost:test --format '{{.Id}}')" || { echo 'BLOCKED: cached installed image missing or replaced.' >&2; exit 3; }
	@test "$$(sed -n 's/.*"contentSha256":"\([a-f0-9]*\)".*/\1/p' coverage/source.json)" = "$$(sed -n 's/.*"contentSha256":"\([a-f0-9]*\)".*/\1/p' coverage/container/source.json)" || { echo 'BLOCKED: cached installed acceptance source changed.' >&2; exit 3; }
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
	$(RUFF) check --fix .
	$(RUFF) format .

format-check: ## Check Ruff formatting without changing files.
	$(RUFF) format --check .

lint: ## Run Ruff lint without changing files.
	$(RUFF) check .

typecheck: ## Run strict mypy.
	$(UV) run --locked mypy

test: ## Run runtime and generator tests with full statement/branch coverage.
	$(UV) run --locked pytest --cov --cov-report=term-missing --cov-report=json --cov-report=xml --junitxml=coverage/junit.xml

compile: ## Compile runtime and tooling sources.
	$(UV) run --locked python -m compileall -q src/pypokerlost scripts

build: ## Export the canonical wheel and source distribution from Docker.
	docker buildx build --target artifacts --output type=local,dest=dist .

test-image: ## Accept installed metadata/imports/generator without repeating the unit suite.
	@mkdir -p coverage/container
ifneq ($(OFFLINE),1)
	docker buildx build $(DOCKER_BUILD_ARGS) $(LOCAL_BUILD_NETWORK) --target test --load --tag pypokerlost:test .
endif
	@touch coverage/container/.started
	docker run --rm --read-only --network none --tmpfs /tmp:rw,noexec,nosuid,size=128m --user "$$(id -u):$$(id -g)" --mount type=bind,source="$$(pwd)/coverage/container",target=/checks/coverage --mount type=bind,source="$$(pwd)/coverage/artifacts",target=/verified-artifacts,readonly pypokerlost:test
	@docker image inspect pypokerlost:test --format '{{.Id}}' > coverage/container/test-image-id.txt
	@cp coverage/source.json coverage/container/source.json

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

check: lint format-check ## Fast lint-only gate; no tests/build.

acceptance: lock-check format-check lint typecheck test compile docs-check generator-check import-check ## Run the regular non-mutating gate.

check-full: acceptance build pre-commit ## Run the complete repository gate.

endif

.PHONY: dev-policy-help
help: dev-policy-help
dev-policy-help:
	@printf '%s\n' 'Daily: make lint; explicit git push origin dev.' \
	  'Manual only: test, typecheck, coverage, build, acceptance, ci-local.' \
	  'Native lint tools must be installed; lint never syncs/builds the application.'

# Nexus monorepo foundation Makefile
# Commands skip unavailable language work cleanly and fail on real errors.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := check

.PHONY: setup format lint typecheck test test-unit test-integration eval eval-embedded-initialization contracts policy check build clean generate-contract-types dev dev-api dev-web dev-db db-migrate db-reset-local test-e2e

export PATH := $(CURDIR)/.venv/bin:$(PATH)
export PYTHON ?= $(shell if [ -x "$(CURDIR)/.venv/bin/python" ]; then printf '%s\n' "$(CURDIR)/.venv/bin/python"; else command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3; fi)
PYTHON_PATH := apps/api/src:agents/embedded-systems/src:packages/contracts/src:packages/contracts/generated/python:packages/model-gateway/src:packages/observability/src:packages/persistence/src

setup:
	@./scripts/setup.sh
	@pnpm install

format:
	@FORMAT_CHECK="$(FORMAT_CHECK)" ./scripts/run-format.sh

lint:
	@./scripts/run-lint.sh

typecheck:
	@./scripts/run-typecheck.sh

test: test-unit test-integration

test-unit:
	@./scripts/run-tests.sh unit
	@pnpm run test

test-integration:
	@./scripts/run-tests.sh integration

eval:
	@./scripts/run-evals.sh

# Runs the full embedded-project-initialization eval suite (golden + adversarial
# cases). Defaults to the fake provider, so it never requires model credentials.
# Not part of `make check`; run it directly when iterating on prompts or the
# eval harness itself. Pass PROVIDER=llm for a live run (requires
# NEXUS_MODEL_API_KEY).
eval-embedded-initialization:
	@PYTHONPATH="$(PYTHON_PATH)" $(PYTHON) -m evals.embedded_project_initialization.runners.run_eval --provider $(or $(PROVIDER),fake)

contracts:
	@./scripts/validate-contracts.sh

generate-contract-types:
	@$(PYTHON) packages/contracts/scripts/generate_contract_types.py

policy:
	@./scripts/check-repository-policy.sh

check: policy
	@$(MAKE) format FORMAT_CHECK=1
	@$(MAKE) lint
	@$(MAKE) typecheck
	@$(MAKE) contracts
	@$(MAKE) test
	@$(MAKE) eval
	@$(MAKE) build

build:
	@./scripts/run-build.sh

clean:
	@./scripts/clean.sh

dev-db:
	@docker compose -f infra/docker/docker-compose.yml up -d postgres

db-migrate:
	@cd packages/persistence && PYTHONPATH=src $(PYTHON) -m alembic -c alembic.ini upgrade head

db-reset-local:
	@if [[ "$(CONFIRM)" != "1" ]]; then \
	  echo "Refusing to reset local DB. Re-run with CONFIRM=1 (local-only)."; \
	  exit 1; \
	fi
	@docker compose -f infra/docker/docker-compose.yml down -v
	@$(MAKE) dev-db
	@sleep 3
	@$(MAKE) db-migrate

dev-api:
	@PYTHONPATH="$(PYTHON_PATH)" NEXUS_STORAGE_BACKEND="$${NEXUS_STORAGE_BACKEND:-memory}" NEXUS_INITIALIZATION_PROVIDER="$${NEXUS_INITIALIZATION_PROVIDER:-fixture}" $(PYTHON) -m uvicorn nexus_api.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	@pnpm --filter @nexus/web dev

dev:
	@echo "Starting API and web. Use Ctrl-C to stop."
	@PYTHONPATH="$(PYTHON_PATH)" NEXUS_STORAGE_BACKEND="$${NEXUS_STORAGE_BACKEND:-memory}" NEXUS_INITIALIZATION_PROVIDER="$${NEXUS_INITIALIZATION_PROVIDER:-fixture}" $(PYTHON) -m uvicorn nexus_api.main:app --host 127.0.0.1 --port 8000 & \
	  API_PID=$$!; \
	  pnpm --filter @nexus/web dev & \
	  WEB_PID=$$!; \
	  trap 'kill $$API_PID $$WEB_PID 2>/dev/null || true' INT TERM EXIT; \
	  wait

test-e2e:
	@./scripts/run-e2e.sh

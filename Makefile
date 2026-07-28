# Nexus monorepo foundation Makefile
# Commands skip unavailable language work cleanly and fail on real errors.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := check

.PHONY: setup format lint typecheck test test-unit test-integration eval contracts policy check build clean generate-contract-types dev dev-api dev-web

PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)
PYTHON_PATH := apps/api/src:agents/embedded-systems/src:packages/contracts/src:packages/contracts/generated/python

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
	@pnpm --filter @nexus/web test

test-integration:
	@./scripts/run-tests.sh integration

eval:
	@./scripts/run-evals.sh

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

dev-api:
	@PYTHONPATH="$(PYTHON_PATH)" $(PYTHON) -m uvicorn nexus_api.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	@pnpm --filter @nexus/web dev

dev:
	@echo "Starting API and web. Use Ctrl-C to stop."
	@PYTHONPATH="$(PYTHON_PATH)" $(PYTHON) -m uvicorn nexus_api.main:app --host 127.0.0.1 --port 8000 & \
	  API_PID=$$!; \
	  pnpm --filter @nexus/web dev & \
	  WEB_PID=$$!; \
	  trap 'kill $$API_PID $$WEB_PID 2>/dev/null || true' INT TERM EXIT; \
	  wait

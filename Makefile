# Nexus monorepo foundation Makefile
# Commands skip unavailable language work cleanly and fail on real errors.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := check

.PHONY: setup format lint typecheck test test-unit test-integration eval contracts policy check build clean

setup:
	@./scripts/setup.sh

format:
	@FORMAT_CHECK="$(FORMAT_CHECK)" ./scripts/run-format.sh

lint:
	@./scripts/run-lint.sh

typecheck:
	@./scripts/run-typecheck.sh

test: test-unit test-integration

test-unit:
	@./scripts/run-tests.sh unit

test-integration:
	@./scripts/run-tests.sh integration

eval:
	@./scripts/run-evals.sh

contracts:
	@./scripts/validate-contracts.sh

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

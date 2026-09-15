.PHONY: doctor bootstrap contracts-check lint typecheck test-unit test-contract \
  test-integration test-e2e test-security test-recovery test-load test-evals \
  infra-validate demo-smoke evidence-check

PYTHON ?= uv run python
NODE ?= node

doctor:
	$(NODE) scripts/doctor.mjs

bootstrap:
	uv sync --locked
	@if command -v pnpm >/dev/null 2>&1; then pnpm install --frozen-lockfile; elif command -v corepack >/dev/null 2>&1; then corepack pnpm install --frozen-lockfile; else echo 'pnpm (or corepack) is required for web bootstrap' >&2; exit 1; fi

contracts-check:
	$(NODE) scripts/contracts-check.mjs

lint:
	$(PYTHON) -m ruff check packages services tests
	corepack pnpm --filter @vda-agent/web exec eslint .

typecheck:
	$(PYTHON) -m mypy packages services
	corepack pnpm --filter @vda-agent/web typecheck

test-unit:
	$(PYTHON) -m pytest tests/unit

test-contract:
	$(PYTHON) -m pytest tests/contract

test-integration:
	$(PYTHON) -m pytest tests/integration

test-e2e:
	$(PYTHON) -m pytest tests/e2e

test-security:
	$(PYTHON) -m pytest tests/security

test-recovery:
	$(PYTHON) -m pytest tests/recovery

test-load:
	$(PYTHON) -m pytest tests/load

test-evals:
	$(PYTHON) -m pytest tests/evals

infra-validate:
	$(NODE) scripts/infra-validate.mjs

demo-smoke:
	$(NODE) scripts/demo-smoke.mjs

evidence-check:
	$(NODE) scripts/evidence-check.mjs

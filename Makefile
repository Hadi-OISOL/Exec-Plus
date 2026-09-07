# Use case: Provides a stable command surface for common developer and CI workflows.
# What it does: Wraps environment setup, local services, applications, tests, and static analysis.

.PHONY: install dev-infra down api web format lint typecheck test check migrate init-storage test-integration test-browser

COMPOSE ?= docker-compose

install:
	python3 -m pip install -e '.[dev]'
	npm install

dev-infra:
	$(COMPOSE) up -d postgres minio
	python3 scripts/wait_infra.py

down:
	$(COMPOSE) down

api:
	python3 -m uvicorn execplus.main:app --app-dir apps/api/src --reload --no-access-log --host 0.0.0.0 --port 8000

web:
	npm run dev:web

format:
	python3 -m ruff format apps/api/src apps/api/tests tests migrations scripts
	python3 -m ruff check --fix apps/api/src apps/api/tests tests migrations scripts

lint:
	python3 -m ruff check apps/api/src apps/api/tests tests migrations scripts
	npm run lint:web

typecheck:
	python3 -m mypy
	npm run typecheck:web

test:
	python3 -m pytest
	npm run test:web

check: lint typecheck test
	npm run build:web

migrate:
	python3 -m alembic upgrade head

init-storage:
	python3 -m execplus.manage init-storage

test-integration:
	@test -n "$(EXECPLUS_TEST_DATABASE_URL)" || (echo "Set EXECPLUS_TEST_DATABASE_URL" && exit 1)
	python3 -m pytest apps/api/tests/test_workspace_integration.py apps/api/tests/test_profile_integration.py

test-browser:
	python3 scripts/check_browser.py

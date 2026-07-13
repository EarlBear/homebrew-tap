# ebtranscripts — local dev targets (pure-Python venv, no Docker).
.DEFAULT_GOAL := help

.PHONY: help venv install test lint check self-test portable-sql bench roundtrip-local

DB_URL ?= postgres://earlbear:earlbear@localhost:54329/telemetry

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv
	uv venv --python 3.11 .venv

install: ## Install the package with dev deps into .venv
	. .venv/bin/activate && uv pip install -e ".[dev]"

test: ## Run the test suite
	. .venv/bin/activate && python -m pytest -q

lint: ## Lint with ruff
	. .venv/bin/activate && ruff check src/ tests/

self-test: ## Run the runtime planted-secret sanitizer gate
	. .venv/bin/activate && ebtranscripts sanitize --self-test

portable-sql: ## Static guard: no Supabase-only SQL in portable migrations (claim C13)
	./scripts/check-portable-sql.sh

bench: ## Profile the sanitizer: per-layer cost (regex / entropy / scrub / gitleaks)
	. .venv/bin/activate && python scripts/bench-sanitizer.py

check: lint test self-test portable-sql ## Lint + tests + sanitizer gate + portable-SQL guard

roundtrip-local: ## Prove G2/G4 live: bring up Docker Postgres, migrate, run the round-trip test
	./scripts/db.sh up
	./scripts/db.sh migrate
	. .venv/bin/activate && EBT_LOCAL_DB_URL=$(DB_URL) \
		python -m pytest tests/test_local_roundtrip.py -v
	@echo "roundtrip-local passed: push is idempotent + local mart == per-session counts."
	@echo "(stop the DB with ./scripts/db.sh down; wipe with ./scripts/db.sh reset)"

# Jira CLI (ebjira) targets
# Included by root Makefile

ebjira-build: ## Build ebjira Docker image
	docker build -t ebjira jira-cli/
	@echo "ebjira Docker image built"

ebjira-rebuild: ebjira-clean ## Rebuild ebjira Docker image (no cache)
	docker build -t ebjira --no-cache jira-cli/
	@echo "ebjira Docker image rebuilt"

ebjira-test: ## Run ebjira tests in Docker (src/ and tests/ bind-mounted; edits take effect without rebuild)
	docker run --rm \
		-v $(PWD)/jira-cli/src/ebjira:/usr/local/lib/python3.11/site-packages/ebjira:ro \
		-v $(PWD)/jira-cli/tests:/app/tests:ro \
		--entrypoint python ebjira -m pytest tests/ -v

ebjira-lint: ## Lint ebjira code in Docker
	docker run --rm --entrypoint ruff ebjira check src/ tests/

ebjira-clean: ## Clean ebjira build artifacts
	@rm -rf jira-cli/src/ebjira.egg-info jira-cli/src/ebjira/__pycache__ jira-cli/tests/__pycache__
	@echo "ebjira build artifacts cleaned"

ebjira-help: ## Show ebjira command tree
	./bin/ebjira --help

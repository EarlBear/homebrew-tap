# Shopify CLI (ebshop) targets
# Included by root Makefile

ebshop-build: ## Build ebshop Docker image
	docker build -t ebshop shopify-cli/
	@echo "ebshop Docker image built"

ebshop-rebuild: ebshop-clean ## Rebuild ebshop Docker image (no cache)
	docker build -t ebshop --no-cache shopify-cli/
	@echo "ebshop Docker image rebuilt"

ebshop-test: ## Run ebshop tests in Docker (src/ and tests/ bind-mounted; edits take effect without rebuild)
	docker run --rm \
		-v $(PWD)/shopify-cli/src/ebshop:/usr/local/lib/python3.11/site-packages/ebshop:ro \
		-v $(PWD)/shopify-cli/tests:/app/tests:ro \
		--entrypoint python ebshop -m pytest tests/ -v

ebshop-lint: ## Lint ebshop code in Docker
	docker run --rm --entrypoint ruff ebshop check src/ tests/

ebshop-clean: ## Clean ebshop build artifacts
	@rm -rf shopify-cli/src/ebshop.egg-info shopify-cli/src/ebshop/__pycache__ shopify-cli/tests/__pycache__
	@echo "ebshop build artifacts cleaned"

ebshop-help: ## Show ebshop command tree
	./bin/ebshop --help

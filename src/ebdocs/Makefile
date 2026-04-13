# Google Docs CLI (ebdocs) targets
# Included by root Makefile

ebdocs-build: ## Build ebdocs Docker image
	docker build -t ebdocs gdocs-cli/
	@echo "ebdocs Docker image built"

ebdocs-rebuild: ebdocs-clean ## Rebuild ebdocs Docker image (no cache)
	docker build -t ebdocs --no-cache gdocs-cli/
	@echo "ebdocs Docker image rebuilt"

ebdocs-mermaid-build: ## Build ebdocs-mermaid sidecar image (mmdc + chromium)
	docker build -f gdocs-cli/Dockerfile.mermaid -t ebdocs-mermaid gdocs-cli/
	@echo "ebdocs-mermaid sidecar image built"

ebdocs-mermaid-rebuild: ## Rebuild ebdocs-mermaid sidecar image (no cache)
	docker build -f gdocs-cli/Dockerfile.mermaid -t ebdocs-mermaid --no-cache gdocs-cli/
	@echo "ebdocs-mermaid sidecar image rebuilt"

ebdocs-test: ## Run ebdocs tests in Docker (src/ and tests/ bind-mounted; edits take effect without rebuild)
	docker run --rm \
		-v $(PWD)/gdocs-cli/src/ebdocs:/usr/local/lib/python3.11/site-packages/ebdocs:ro \
		-v $(PWD)/gdocs-cli/tests:/app/tests:ro \
		--entrypoint python ebdocs -m pytest tests/ -v

ebdocs-lint: ## Lint ebdocs code in Docker
	docker run --rm --entrypoint ruff ebdocs check src/ tests/

ebdocs-clean: ## Clean ebdocs build artifacts
	@rm -rf gdocs-cli/src/ebdocs.egg-info gdocs-cli/src/ebdocs/__pycache__ gdocs-cli/tests/__pycache__
	@echo "ebdocs build artifacts cleaned"

ebdocs-help: ## Show ebdocs command tree
	./bin/ebdocs --help

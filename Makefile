.PHONY: help sync-sources bump-and-release \
        validate validate-audit validate-docker validate-smoke validate-vm \
        clean

GREEN  := \033[0;32m
YELLOW := \033[0;33m
BLUE   := \033[0;34m
NC     := \033[0m

EARLBEAR_ROOT ?= $(shell cd .. && pwd)

help: ## Show this help
	@echo "$(BLUE)EarlBear Homebrew Tap$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-22s$(NC) %s\n", $$1, $$2}'

# ── Source sync ────────────────────────────────────────────────────────────────

sync-sources: ## Copy latest source from sibling repos into src/ and plugins-bundle/
	@echo "$(BLUE)Syncing sources from $(EARLBEAR_ROOT)...$(NC)"
	rsync -a --delete \
		--exclude='tests/' --exclude='.venv/' --exclude='__pycache__/' \
		--exclude='*.pyc' --exclude='dist/' \
		$(EARLBEAR_ROOT)/earlbear-clis/jira-cli/    src/ebjira/
	rsync -a --delete \
		--exclude='tests/' --exclude='.venv/' --exclude='__pycache__/' \
		--exclude='*.pyc' --exclude='dist/' \
		$(EARLBEAR_ROOT)/earlbear-clis/gdocs-cli/   src/ebdocs/
	rsync -a --delete \
		--exclude='tests/' --exclude='.venv/' --exclude='__pycache__/' \
		--exclude='*.pyc' --exclude='dist/' \
		$(EARLBEAR_ROOT)/earlbear-clis/shopify-cli/ src/ebshop/
	rsync -a --delete \
		--exclude='tests/' --exclude='.venv/' --exclude='__pycache__/' \
		--exclude='*.pyc' --exclude='poc-figma/' --exclude='poc-marp/' \
		--exclude='poc-pptx/' --exclude='poc-slidev/' --exclude='dist/' \
		--exclude='assets/' --exclude='brands/' --exclude='content/' \
		$(EARLBEAR_ROOT)/earlbear-clis/deck-cli/    src/ebdeck/
	cp $(EARLBEAR_ROOT)/earlbear/bin/agent-cli src/agent-cli/agent-cli.sh
	chmod +x src/agent-cli/agent-cli.sh
	rsync -a --delete \
		$(EARLBEAR_ROOT)/earlbear-claude-plugin-marketplace/plugins/ plugins-bundle/
	rsync -a \
		$(EARLBEAR_ROOT)/earlbear-claude-plugin-marketplace/.claude-plugin/ plugins-bundle/.claude-plugin/
	@echo "$(GREEN)✓ Sources synced$(NC)"

# ── Release ────────────────────────────────────────────────────────────────────

bump-and-release: ## Tag a new release (usage: make bump-and-release VERSION=1.0.1)
	@if [ -z "$(VERSION)" ]; then \
		read -p "Version (e.g. 1.0.1): " v; \
	else \
		v="$(VERSION)"; \
	fi; \
	echo "Releasing v$$v..."; \
	git tag -a "v$$v" -m "Release v$$v"; \
	git push origin main "v$$v"; \
	echo "$(GREEN)✓ Released v$$v$(NC)"

# ── Validation ─────────────────────────────────────────────────────────────────

validate-audit: ## Tier 1 — brew audit + style in Docker (~30s)
	@echo "$(BLUE)==> Tier 1: Formula audit$(NC)"
	docker build -t earlbear-audit -f validation/audit/Dockerfile .
	@echo "$(GREEN)✓ Audit passed$(NC)"

validate-docker: ## Tier 2 — brew install in Docker (~5min, non-Docker formulas)
	@echo "$(BLUE)==> Tier 2: Docker clean-install$(NC)"
	docker build --no-cache -t earlbear-install-test -f validation/docker/Dockerfile .
	@echo "$(GREEN)✓ Docker install test passed$(NC)"

validate-smoke: ## Tier 4 — smoke test locally installed formulas (~10s)
	@echo "$(BLUE)==> Tier 4: Smoke tests$(NC)"
	bash validation/smoke/smoke-test.sh

validate-vm: ## Tier 3 — full brew install in Tart macOS VM (~15min, Apple Silicon)
	@command -v tart >/dev/null 2>&1 || { \
		echo "$(YELLOW)tart not found. Install with: brew install cirruslabs/cli/tart$(NC)"; \
		exit 1; \
	}
	bash validation/tart/tart-test.sh

validate: ## Run tiers 1 + 2 + 4 (add CI=1 to include VM)
	@$(MAKE) --no-print-directory validate-audit
	@$(MAKE) --no-print-directory validate-docker
	@$(MAKE) --no-print-directory validate-smoke
	@if [ "$${CI:-0}" = "1" ]; then \
		$(MAKE) --no-print-directory validate-vm; \
	fi
	@echo "$(GREEN)✓ All validation tiers passed$(NC)"

# ── Misc ───────────────────────────────────────────────────────────────────────

clean: ## Remove Docker build cache for earlbear images
	docker rmi earlbear-audit earlbear-install-test 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

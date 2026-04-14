.PHONY: help sync-sources bump-and-release release-plugin-binaries lfs-status \
        validate validate-audit validate-docker validate-smoke validate-vm validate-cowork validate-plugin-binaries \
        build-plugin-binaries build-plugin-ebjira build-plugin-ebdocs build-plugin-ebshop build-plugin-ebdeck \
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

bump-and-release: ## Full release: tag + push + GitHub Release + upload plugin binaries
	@command -v gh >/dev/null 2>&1 || { \
		echo "$(YELLOW)gh CLI not found. Install with: brew install gh$(NC)"; \
		exit 1; \
	}
	@if [ -z "$(VERSION)" ]; then \
		read -p "Version (e.g. 1.0.1): " v; \
	else \
		v="$(VERSION)"; \
	fi; \
	echo "$(BLUE)Releasing v$$v...$(NC)"; \
	git tag -a "v$$v" -m "Release v$$v"; \
	git push origin main "v$$v"; \
	echo "$(BLUE)Creating GitHub Release v$$v...$(NC)"; \
	gh release create "v$$v" --title "v$$v" --notes "Release v$$v" --latest; \
	BINS=$$(find plugins-bundle -path "*/bin/*-linux" -type f 2>/dev/null); \
	if [ -n "$$BINS" ]; then \
		echo "$(BLUE)Uploading plugin binaries...$(NC)"; \
		gh release upload "v$$v" $$BINS --clobber; \
		echo "$(GREEN)✓ Plugin binaries uploaded$(NC)"; \
	else \
		echo "$(YELLOW)⚠ No plugin binaries found — run 'make build-plugin-binaries' then 'make release-plugin-binaries' to add them$(NC)"; \
	fi; \
	echo "$(GREEN)✓ Released v$$v$(NC)"

release-plugin-binaries: ## Upload cowork plugin binaries to the current tag's GitHub Release
	@command -v gh >/dev/null 2>&1 || { \
		echo "$(YELLOW)gh CLI not found. Install with: brew install gh$(NC)"; \
		exit 1; \
	}
	$(eval TAG := $(shell git describe --tags --abbrev=0 2>/dev/null))
	@if [ -z "$(TAG)" ]; then \
		echo "$(YELLOW)No git tag found. Run 'make bump-and-release VERSION=x.y.z' first.$(NC)"; \
		exit 1; \
	fi
	@BINS=$$(find plugins-bundle -path "*/bin/*-linux" -type f 2>/dev/null); \
	if [ -z "$$BINS" ]; then \
		echo "$(YELLOW)No plugin binaries found. Run 'make build-plugin-binaries' first.$(NC)"; \
		exit 1; \
	fi; \
	echo "$(BLUE)Uploading plugin binaries to $(TAG)...$(NC)"; \
	gh release upload "$(TAG)" $$BINS --clobber; \
	echo "$(GREEN)✓ Plugin binaries uploaded to $(TAG)$(NC)"; \
	gh release view "$(TAG)" --json assets --jq '.assets[].name' | sort

lfs-status: ## Show which plugin binaries are tracked in git LFS
	@echo "$(BLUE)Git LFS tracked files in plugins-bundle/:$(NC)"
	@git lfs ls-files 2>/dev/null | grep "plugins-bundle" || echo "  (none yet — stage the binaries with 'git add plugins-bundle/*/bin/*-linux')"

# ── Cowork plugin binaries ─────────────────────────────────────────────────────
#
# Cross-compile Python CLIs into self-contained single-file binaries for cowork
# plugin delivery. Uses Docker with PyInstaller (--onefile) so the resulting
# binary runs in the cowork VM with zero runtime deps (no Python, no pip).
#
# Outputs are written to plugins-bundle/<plugin>/bin/ and committed with the
# plugin. The cowork shim (bin/<cli>) dispatches to the right arch binary.
#
# Usage:
#   make build-plugin-binaries          # build all four CLIs
#   make build-plugin-ebjira            # single CLI
#   SKIP_ARM=1 make build-plugin-ebjira # skip aarch64 (faster CI on x86_64 host)
#   SKIP_AMD=1 make build-plugin-ebjira # skip x86_64

_PYINSTALLER_FLAGS := --onefile --clean --noconfirm

define build-cli  # $(1)=cli $(2)=plugin
# Strategy: pip install the package so its console_script entry point lands at
# /usr/local/bin/$(1); then PyInstaller bundles that script + all deps into a
# single self-contained binary. No standalone main.py required.
	@echo "$(BLUE)==> Building $(1) binaries for cowork plugin delivery$(NC)"
	@mkdir -p plugins-bundle/$(2)/bin
	@if [ "$${SKIP_ARM:-0}" != "1" ]; then \
		echo "  Building $(1)-aarch64-linux..."; \
		docker run --rm --platform linux/arm64 \
			-v "$(PWD)/src/$(1):/src" -w /src \
			python:3.11-slim \
			bash -c "apt-get update -qq && apt-get install -y -q binutils && \
			         pip install pyinstaller -q && \
			         pip install . -q && \
			         pyinstaller $(_PYINSTALLER_FLAGS) --name $(1)-aarch64-linux \$$(which $(1))" && \
		cp src/$(1)/dist/$(1)-aarch64-linux plugins-bundle/$(2)/bin/ && \
		chmod +x plugins-bundle/$(2)/bin/$(1)-aarch64-linux; \
	fi
	@if [ "$${SKIP_AMD:-0}" != "1" ]; then \
		echo "  Building $(1)-x86_64-linux..."; \
		docker run --rm --platform linux/amd64 \
			-v "$(PWD)/src/$(1):/src" -w /src \
			python:3.11-slim \
			bash -c "apt-get update -qq && apt-get install -y -q binutils && \
			         pip install pyinstaller -q && \
			         pip install . -q && \
			         pyinstaller $(_PYINSTALLER_FLAGS) --name $(1)-x86_64-linux \$$(which $(1))" && \
		cp src/$(1)/dist/$(1)-x86_64-linux plugins-bundle/$(2)/bin/ && \
		chmod +x plugins-bundle/$(2)/bin/$(1)-x86_64-linux; \
	fi
	@echo "$(GREEN)✓ $(1) binaries ready in plugins-bundle/$(2)/bin/$(NC)"
endef

build-plugin-ebjira: ## Build ebjira binaries for cowork (aarch64 + x86_64, ~5min)
	$(call build-cli,ebjira,jira-manager)

build-plugin-ebdocs: ## Build ebdocs binaries for cowork (aarch64 + x86_64, ~5min)
	$(call build-cli,ebdocs,earlbear-docs-manager)

build-plugin-ebshop: ## Build ebshop binaries for cowork (aarch64 + x86_64, ~5min)
	$(call build-cli,ebshop,shopify-manager)

build-plugin-ebdeck: ## Build ebdeck binaries for cowork (aarch64 + x86_64, ~5min)
	$(call build-cli,ebdeck,deck-manager)

build-plugin-binaries: build-plugin-ebjira build-plugin-ebdocs build-plugin-ebshop build-plugin-ebdeck ## Build all cowork plugin binaries (all CLIs, both arches, ~20min)

# ── Validation ─────────────────────────────────────────────────────────────────

validate-audit: ## Tier 1 — brew audit + style in Docker (~30s)
	@echo "$(BLUE)==> Tier 1: Formula audit$(NC)"
	docker build --platform linux/amd64 -t earlbear-audit -f validation/audit/Dockerfile .
	@echo "$(GREEN)✓ Audit passed$(NC)"

validate-docker: ## Tier 2 — brew install in Docker (~5min, non-Docker formulas)
	@echo "$(BLUE)==> Tier 2: Docker clean-install$(NC)"
	docker build --no-cache --platform linux/amd64 -t earlbear-install-test -f validation/docker/Dockerfile .
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

validate-plugin-binaries: ## Tier 5b — compile ebjira + run in ubuntu:24.04 ARM64 container (~8min, Apple Silicon + Docker + apple/container)
	@command -v docker >/dev/null 2>&1 || { \
		echo "$(YELLOW)Docker not found — required for PyInstaller compile step.$(NC)"; \
		exit 1; \
	}
	@command -v container >/dev/null 2>&1 || { \
		echo "$(YELLOW)apple/container not found.$(NC)"; \
		echo "$(YELLOW)Install from: https://github.com/apple/container/releases$(NC)"; \
		echo "$(YELLOW)Then run: container system start$(NC)"; \
		exit 1; \
	}
	@[ "$$(uname -m)" = "arm64" ] || { \
		echo "$(YELLOW)validate-plugin-binaries requires Apple Silicon (arm64). Skipping.$(NC)"; \
		exit 1; \
	}
	bash validation/plugin-binaries/test.sh

validate-cowork: ## Tier 5 — cowork devcontainer via apple/container (~10min, Apple Silicon + macOS 26+)
	@command -v container >/dev/null 2>&1 || { \
		echo "$(YELLOW)apple/container not found.$(NC)"; \
		echo "$(YELLOW)Install from: https://github.com/apple/container/releases$(NC)"; \
		echo "$(YELLOW)Then run: container system start$(NC)"; \
		exit 1; \
	}
	@[ "$$(uname -m)" = "arm64" ] || { \
		echo "$(YELLOW)validate-cowork requires Apple Silicon (arm64). Skipping.$(NC)"; \
		exit 1; \
	}
	bash validation/cowork/cowork-test.sh

validate: ## Run tiers 1+2+4 (CI=1: +VM; COWORK=1: +cowork devcontainer; PLUGINS=1: +plugin binaries)
	@$(MAKE) --no-print-directory validate-audit
	@$(MAKE) --no-print-directory validate-docker
	@$(MAKE) --no-print-directory validate-smoke
	@if [ "$${CI:-0}" = "1" ]; then \
		$(MAKE) --no-print-directory validate-vm; \
	fi
	@if [ "$${COWORK:-0}" = "1" ]; then \
		$(MAKE) --no-print-directory validate-cowork; \
	fi
	@if [ "$${PLUGINS:-0}" = "1" ]; then \
		$(MAKE) --no-print-directory validate-plugin-binaries; \
	fi
	@echo "$(GREEN)✓ All validation tiers passed$(NC)"

# ── Misc ───────────────────────────────────────────────────────────────────────

clean: ## Remove Docker/container build cache and PyInstaller dist artifacts
	docker rmi earlbear-audit earlbear-install-test 2>/dev/null || true
	command -v container >/dev/null 2>&1 && container image rm earlbear-cowork-test:local 2>/dev/null || true
	rm -rf src/ebjira/dist src/ebjira/build src/ebjira/*.spec \
	       src/ebdocs/dist src/ebdocs/build src/ebdocs/*.spec \
	       src/ebshop/dist src/ebshop/build src/ebshop/*.spec \
	       src/ebdeck/dist src/ebdeck/build src/ebdeck/*.spec 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

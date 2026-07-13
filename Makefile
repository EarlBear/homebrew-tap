.PHONY: help sync-sources bump-and-release release-plugin-wheels lfs-status install-hooks \
        validate validate-audit validate-docker validate-smoke validate-vm tart-pull tart-build-base validate-cowork validate-plugin-wheels validate-cowork-sim cowork-sim-build-base \
        build-plugin-wheels build-plugin-ebjira build-plugin-ebdocs build-plugin-ebshop build-plugin-ebdeck \
        clean clean-container-cache

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
	rsync -a --delete \
		--exclude='tests/' --exclude='scripts/' --exclude='.venv/' --exclude='__pycache__/' \
		--exclude='*.pyc' --exclude='dist/' --exclude='.transcript-preview/' \
		--exclude='transcripts/' \
		$(EARLBEAR_ROOT)/earlbear-clis/transcripts-cli/ src/ebtranscripts/
	cp $(EARLBEAR_ROOT)/earlbear-claude-agent/bin/agent-cli src/agent-cli/agent-cli.sh
	chmod +x src/agent-cli/agent-cli.sh
	rsync -a --delete \
		--exclude='*/bin/' \
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
	BUNDLES=$$(find plugins-bundle -name "*-bundle.zip" -type f 2>/dev/null); \
	if [ -n "$$BUNDLES" ]; then \
		echo "$(BLUE)Uploading plugin wheel bundles...$(NC)"; \
		gh release upload "v$$v" $$BUNDLES --clobber; \
		echo "$(GREEN)✓ Plugin wheel bundles uploaded$(NC)"; \
	else \
		echo "$(YELLOW)⚠ No wheel bundles found — run 'make build-plugin-wheels' then 'make release-plugin-wheels' to add them$(NC)"; \
	fi; \
	echo "$(GREEN)✓ Released v$$v$(NC)"

release-plugin-wheels: ## Upload cowork plugin wheel bundles (*-bundle.zip) to the current tag's GitHub Release
	@command -v gh >/dev/null 2>&1 || { \
		echo "$(YELLOW)gh CLI not found. Install with: brew install gh$(NC)"; \
		exit 1; \
	}
	$(eval TAG := $(shell git describe --tags --abbrev=0 2>/dev/null))
	@if [ -z "$(TAG)" ]; then \
		echo "$(YELLOW)No git tag found. Run 'make bump-and-release VERSION=x.y.z' first.$(NC)"; \
		exit 1; \
	fi
	@BUNDLES=$$(find plugins-bundle -name "*-bundle.zip" -type f 2>/dev/null); \
	if [ -z "$$BUNDLES" ]; then \
		echo "$(YELLOW)No wheel bundles found. Run 'make build-plugin-wheels' first.$(NC)"; \
		exit 1; \
	fi; \
	echo "$(BLUE)Uploading plugin wheel bundles to $(TAG)...$(NC)"; \
	gh release upload "$(TAG)" $$BUNDLES --clobber; \
	echo "$(GREEN)✓ Plugin wheel bundles uploaded to $(TAG)$(NC)"; \
	gh release view "$(TAG)" --json assets --jq '.assets[].name' | sort

lfs-status: ## Show which plugin binaries are tracked in git LFS
	@echo "$(BLUE)Git LFS tracked files in plugins-bundle/:$(NC)"
	@git lfs ls-files 2>/dev/null | grep "plugins-bundle" || echo "  (none yet — stage the binaries with 'git add plugins-bundle/*/bin/*-linux')"

install-hooks: ## Install git hooks (secrets scan + large-file guard) into .git/hooks/
	@echo "$(BLUE)==> Installing git hooks...$(NC)"
	@cp scripts/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "$(GREEN)✓ Installed .git/hooks/pre-commit (gitleaks secrets scan + large-file guard)$(NC)"
	@echo "$(BLUE)  Requires: brew install gitleaks$(NC)"

# ── Cowork plugin wheels ────────────────────────────────────────────────────────
#
# Build pure-Python wheels for cowork plugin delivery. Because all EarlBear CLIs
# are pure Python (no C extensions), a single wheel works on any architecture and
# any glibc version — no PyInstaller, no cross-compilation needed.
#
# The wheel is pip-installed into bin/.venv inside the cowork project folder by
# the EarlBear installer. The cowork shim calls bin/.venv/bin/<cli> directly.
#
# Outputs: plugins-bundle/<plugin>/wheels/<cli>-*.whl  (committed, no LFS needed)
#
# Usage:
#   make build-plugin-wheels          # build wheels for all CLIs (~30s)
#   make build-plugin-ebjira         # single CLI wheel

define build-wheel  # $(1)=cli $(2)=plugin
# Strategy: build the CLI wheel + all its transitive dependencies into a single
# zip archive that can be pip-installed completely offline (no PyPI access needed
# in the cowork VM). The archive is architecture-independent (py3-none-any) since
# all EarlBear CLIs are pure Python with pure-Python dependencies.
#
# Install in cowork:
#   unzip -o <cli>-bundle.zip -d bin/.wheels/
#   pip install --no-index --find-links=bin/.wheels/ --target=bin/.deps <cli>
#   export PYTHONPATH=bin/.deps PATH=bin/.deps/bin:$$PATH
	@echo "$(BLUE)==> Building $(1) wheel bundle for cowork plugin delivery$(NC)"
	@mkdir -p plugins-bundle/$(2)/wheels
	@docker run --rm \
		-v "$(PWD)/src/$(1):/src" \
		-v "$(PWD)/plugins-bundle/$(2)/wheels:/out" -w /src \
		python:3.11-slim \
		bash -c "set -e && \
		         pip install build -q && \
		         python -m build --wheel --outdir /out . -q && \
		         pip wheel . --wheel-dir /out -q" && \
	cd plugins-bundle/$(2)/wheels && \
	zip -qr $(1)-bundle.zip *.whl && \
	echo "$(GREEN)✓ $(1)-bundle.zip ready in plugins-bundle/$(2)/wheels/$(NC)" && \
	ls -lh *.whl *.zip
endef

build-plugin-ebjira: ## Build ebjira wheel for cowork (~30s)
	$(call build-wheel,ebjira,jira-manager)

build-plugin-ebdocs: ## Build ebdocs wheel for cowork (~30s)
	$(call build-wheel,ebdocs,earlbear-docs-manager)

build-plugin-ebshop: ## Build ebshop wheel for cowork (~30s)
	$(call build-wheel,ebshop,shopify-manager)

build-plugin-ebdeck: ## Build ebdeck wheel for cowork (~30s)
	$(call build-wheel,ebdeck,deck-manager)

build-plugin-wheels: build-plugin-ebjira build-plugin-ebdocs build-plugin-ebshop build-plugin-ebdeck ## Build pure-Python wheels for all CLIs (~2min total)

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

tart-pull: ## Pull the Tart macOS base image (~6GB, one-time setup for validate-vm)
	@command -v tart >/dev/null 2>&1 || { \
		echo "$(YELLOW)tart not found. Install with: brew install cirruslabs/cli/tart$(NC)"; \
		exit 1; \
	}
	tart pull ghcr.io/cirruslabs/macos-sequoia-base:latest
	@echo "$(GREEN)✓ Base image pulled. Run 'make validate-vm' to use it.$(NC)"

tart-build-base: ## Build Tart base VM snapshot with Homebrew pre-installed (~10min, saves time on every validate-vm run)
	@command -v tart >/dev/null 2>&1 || { \
		echo "$(YELLOW)tart not found. Install with: brew install cirruslabs/cli/tart$(NC)"; \
		exit 1; \
	}
	@command -v sshpass >/dev/null 2>&1 || { \
		echo "$(YELLOW)sshpass not found. Install: brew install hudochenkov/sshpass/sshpass$(NC)"; \
		exit 1; \
	}
	@[ "$$(uname -m)" = "arm64" ] || { \
		echo "$(YELLOW)tart-build-base requires Apple Silicon (arm64).$(NC)"; \
		exit 1; \
	}
	bash validation/tart/tart-build-base.sh

validate-vm: ## Tier 3 — full clean-room brew install from local source in Tart macOS VM (~15min, Apple Silicon)
	@command -v tart >/dev/null 2>&1 || { \
		echo "$(YELLOW)tart not found. Install: brew install cirruslabs/cli/tart$(NC)"; \
		exit 1; \
	}
	@command -v sshpass >/dev/null 2>&1 || { \
		echo "$(YELLOW)sshpass not found. Install: brew install hudochenkov/sshpass/sshpass$(NC)"; \
		exit 1; \
	}
	bash validation/tart/tart-test.sh

validate-plugin-wheels: ## Tier 5b — build wheel bundles for all 4 CLIs + run in ubuntu:24.04 ARM64 container (~5min, SKIP_BUILD=1 ~1min, CLI=ebjira for single)
	@command -v docker >/dev/null 2>&1 || { \
		echo "$(YELLOW)Docker not found — required for wheel build step.$(NC)"; \
		exit 1; \
	}
	@command -v container >/dev/null 2>&1 || { \
		echo "$(YELLOW)apple/container not found.$(NC)"; \
		echo "$(YELLOW)Install from: https://github.com/apple/container/releases$(NC)"; \
		echo "$(YELLOW)Then run: container system start$(NC)"; \
		exit 1; \
	}
	@[ "$$(uname -m)" = "arm64" ] || { \
		echo "$(YELLOW)validate-plugin-wheels requires Apple Silicon (arm64). Skipping.$(NC)"; \
		exit 1; \
	}
	bash validation/plugin-binaries/test.sh

cowork-sim-build-base: ## Build linuxbrew base image for cowork-sim (~2min, one-time; speeds up validate-cowork-sim rebuilds)
	@command -v container >/dev/null 2>&1 || { \
		echo "$(YELLOW)apple/container not found.$(NC)"; \
		echo "$(YELLOW)Install from: https://github.com/apple/container/releases$(NC)"; \
		echo "$(YELLOW)Then run: container system start$(NC)"; \
		exit 1; \
	}
	@[ "$$(uname -m)" = "arm64" ] || { \
		echo "$(YELLOW)cowork-sim-build-base requires Apple Silicon (arm64).$(NC)"; \
		exit 1; \
	}
	@echo "$(BLUE)==> Building linuxbrew base image (earlbear-cowork-base:local)...$(NC)"
	container build \
		--platform linux/arm64 \
		-f validation/cowork-sim/Dockerfile.base \
		-t earlbear-cowork-base:local \
		.
	@echo "$(GREEN)✓ Base image built. Subsequent validate-cowork-sim builds skip the ~2min Homebrew install.$(NC)"

validate-cowork-sim: ## Tier 5c — fresh brew + plugin shims in ubuntu:24.04 ARM64 (~10min first run, ~2min with SKIP_BREW=1, Apple Silicon + apple/container)
	@command -v container >/dev/null 2>&1 || { \
		echo "$(YELLOW)apple/container not found.$(NC)"; \
		echo "$(YELLOW)Install from: https://github.com/apple/container/releases$(NC)"; \
		echo "$(YELLOW)Then run: container system start$(NC)"; \
		exit 1; \
	}
	@[ "$$(uname -m)" = "arm64" ] || { \
		echo "$(YELLOW)validate-cowork-sim requires Apple Silicon (arm64). Skipping.$(NC)"; \
		exit 1; \
	}
	bash validation/cowork-sim/cowork-sim-test.sh

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
		$(MAKE) --no-print-directory validate-plugin-wheels; \
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

clean-container-cache: ## Remove stopped buildkit container (frees up ~20-30GB of build cache disk space)
	@echo "$(BLUE)==> Stopping and removing buildkit build cache container...$(NC)"
	@command -v container >/dev/null 2>&1 || { echo "apple/container not installed"; exit 0; }
	@container stop buildkit 2>/dev/null || true
	@container rm   buildkit 2>/dev/null || true
	@container system df
	@echo "$(GREEN)✓ Build cache cleared. Next build will re-create buildkit (~5s overhead).$(NC)"

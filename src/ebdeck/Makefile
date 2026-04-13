# ebdeck — EarlBear deck CLI per-package Makefile.
#
# Unlike jira-cli/gdocs-cli/shopify-cli, ebdeck is NOT Docker-wrapped.
# ebdeck runs on the host and orchestrates the existing
# deck-cli/docker-compose.yaml services (marp, slidev, python-pptx,
# figma, thumbnails, gallery) via subprocess. Installing this package
# gives you the `ebdeck` executable in your venv/PATH.
#
# For the heavy-lifting toolchain images (marp/slidev/pptx/figma):
#   ebdeck build images                 # docker compose build
#   ebdeck build images --no-cache      # docker compose build --no-cache
#
# For generating decks, packaging, galleries, and publishing:
#   ebdeck build all --brand brands/matcha.yaml
#   ebdeck permutations --max-parallel 6
#   ebdeck gallery build
#   ebdeck package
#   ebdeck publish --site ../../earlbear-sites --name investor-pitch

.PHONY: help install test lint clean plugins-update

help: ## Show ebdeck command tree
	@which ebdeck >/dev/null 2>&1 && ebdeck --help || \
		echo "ebdeck not on PATH. Add deck-cli/bin to PATH or run: make install"

install: ## Symlink deck-cli/bin/ebdeck into ~/bin (auto-bootstraps venv on first run)
	@mkdir -p "$$HOME/bin"
	@if [ -L "$$HOME/bin/ebdeck" ] || [ -e "$$HOME/bin/ebdeck" ]; then \
		echo "~/bin/ebdeck already exists — leaving it alone."; \
	else \
		ln -s "$(CURDIR)/bin/ebdeck" "$$HOME/bin/ebdeck"; \
		echo "Symlinked $(CURDIR)/bin/ebdeck -> ~/bin/ebdeck"; \
	fi
	@echo ""
	@echo "Ensure ~/bin is on your PATH, then run: ebdeck --help"
	@echo "(First invocation auto-bootstraps $(CURDIR)/.venv — ~10s one-time.)"

test: ## Run ebdeck tests
	pytest tests/ -v

lint: ## Lint ebdeck source
	ruff check src/ tests/

plugins-update: ## Update all EarlBear Claude plugins to latest versions
	@cd /Users/omareid/Workspace/git/earlbear-claude-plugin-marketplace && make update

clean: ## Remove Python build artifacts (does NOT touch dist/output deck artifacts)
	@rm -rf src/ebdeck.egg-info src/ebdeck/__pycache__ \
		src/ebdeck/commands/__pycache__ tests/__pycache__ \
		build *.egg-info .pytest_cache .mypy_cache .ruff_cache
	@echo "ebdeck Python build artifacts cleaned"
	@echo "(deck artifacts under dist/output left intact — use 'ebdeck build clean --all' to remove)"

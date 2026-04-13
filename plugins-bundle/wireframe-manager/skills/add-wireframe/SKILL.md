# Add Wireframe

> **Context:** This skill adds a new wireframe type to the monorepo. Wireframes are React/Vite apps built as self-contained HTML files and published to `dist/public/wireframes/{type}/`. The existing `landing-page` wireframe is the reference implementation.

## When to trigger

User says things like:
- "add a wireframe", "new wireframe"
- "create a checkout wireframe", "build a product page wireframe"
- "I want another wireframe type"

## Current structure

```
wireframes/
├── docker-compose.yml         # Shared services (backend, screenshots)
├── frontend/                  # Landing page wireframe (reference implementation)
│   ├── Dockerfile
│   ├── vite.config.ts         # vite-plugin-singlefile for self-contained HTML
│   ├── scripts/build-all.sh   # Builds 12 themes + strips non-HTML
│   └── src/
│       ├── themes/            # 12 theme configs (shared across wireframes)
│       ├── components/        # Landing page components
│       └── data/landing.ts    # Landing page mock data
```

Published to: `dist/public/wireframes/landing-page/{theme}.html`

## Workflow

### Step 1: Gather info

Ask the user:
1. **What type of wireframe?** (e.g., checkout, product page, pricing, onboarding)
2. **How many pages/sections?** Get a rough scope
3. **Same 12 themes?** Almost certainly yes — the theme system is shared
4. **Name?** Kebab-case (e.g., `checkout-flow`, `product-page`)

### Step 2: Decide approach

Two options:

**A. New directory alongside frontend/ (recommended for different page types)**
```
wireframes/
├── frontend/              # existing landing page
├── checkout/              # new wireframe type
│   ├── Dockerfile         # copy from frontend/, adjust
│   ├── vite.config.ts     # same singlefile setup
│   ├── scripts/build-all.sh
│   └── src/
│       ├── themes/        # symlink or copy from frontend/src/themes/
│       ├── components/    # new components for this wireframe
│       └── data/          # new mock data
```

**B. New page within frontend/ (for variations of the landing page)**
- Add new entry point (e.g., `checkout.html` + `checkout-entry.tsx`)
- Add new vite config (e.g., `vite.config.checkout.ts`)
- Update `build-all.sh` to build both page types

### Step 3: Scaffold the wireframe

For approach A (new directory):
1. Copy `wireframes/frontend/` as starting point
2. Strip landing-page-specific components
3. Keep the theme system (`src/themes/`)
4. Update `package.json` name
5. Create new components for the wireframe type
6. Update `build-all.sh` if needed

### Step 4: Update Makefile

Add a new `wire-export-{type}` target or update `wire-export` to handle multiple wireframe types:

```makefile
wire-export-{type}: ## Export {type} wireframe static builds
	@docker build -t earlbear-wire-{type} -f wireframes/{type}/Dockerfile wireframes/{type}/
	@docker rm -f wire-{type}-tmp 2>/dev/null || true
	@docker create --name wire-{type}-tmp earlbear-wire-{type}
	@rm -rf wireframes/{type}-dist && mkdir -p wireframes/{type}-dist
	@docker cp wire-{type}-tmp:/usr/share/nginx/html/. wireframes/{type}-dist/
	@docker rm wire-{type}-tmp
	# ... flatten and clean as with landing-page
```

### Step 5: Update dist-collect

Add the new wireframe type to `dist-collect` in the Makefile:

```makefile
@# {Type} wireframes
@if [ -d wireframes/{type}-dist ]; then \
    mkdir -p dist/public/wireframes/{type}; \
    cp wireframes/{type}-dist/*.html dist/public/wireframes/{type}/; \
    echo "  + wireframes/{type}/"; \
fi
```

### Step 6: Update generate-index.sh

Add a new card for the wireframe type in `scripts/generate-index.sh`. Follow the same pattern as the Landing Page Wireframes card.

### Step 7: Update CLAUDE.md

- Add the new wireframe type to the architecture tree
- Add any new living documents to the table
- Update the wireframes section description

### Step 8: Build and test

```bash
make wire-export             # or wire-export-{type}
make dist
make dist-validate
make dist-preview
```

### Step 9: Commit

Remind the user to commit the new wireframe type.

## Key constraints

- **Self-contained HTML**: All wireframes MUST use `vite-plugin-singlefile` to produce single HTML files. No separate JS/CSS/SVG assets (tenet #5).
- **Flat file structure**: Each theme produces `{theme}.html`, not `{theme}/index.html`.
- **12 themes**: Use the shared theme system. All wireframe types should support all 12 themes.
- **No nginx artifacts**: Strip `50x.html` and default `index.html` from exports.
- **Theme chooser**: Each wireframe type should have its own `index.html` that lets users pick a theme.

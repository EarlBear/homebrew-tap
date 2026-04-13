# EarlBear — Three-Repo Overview

> Use this skill when you (or a new contributor) need a map of the whole EarlBear system: which repo owns what, how they relate, and where to go for which task. This is the orientation skill — it answers "where do I work on X?" and "which repo do I clone for Y?"

## The three repos

EarlBear is split across three sibling checkouts under `~/Workspace/git/`:

| Repo | Owns | You're here when... |
|---|---|---|
| **`earlbear/`** | CLIs entry point, cloud agent, MCP servers, Jira/Shopify manifests, delivery SOPs | You're running CLI commands, managing the cloud agent, or editing Jira/Shopify source of truth |
| **`earlbear-clis/`** | Python source for `ebjira`, `ebdocs`, `ebshop`, `ebdeck` | You're adding CLI commands, fixing CLI bugs, or extending ebjira/ebdocs/ebshop/ebdeck |
| **`earlbear-sites/`** | Wireframes, ecommerce stores, claude-artifacts, dist pipeline, gh-pages publishing | You're editing frontend code, running `/design-review`, importing artifacts, or publishing |

```
~/Workspace/git/
├── earlbear/                   ← CLIs, cloud agent, Jira/Shopify manifests, MCP
│   ├── bin/agent-cli
│   ├── manifests/jira/manifest.yaml
│   ├── docs/                   (living docs: delivery SOPs, architecture, design)
│   ├── .claude/skills/         (Jira, Shopify, agent, CLI skills)
│   └── Makefile                (jira-cli-*, gdocs-cli-*, shopify-cli-*, deck-cli-*, mcp-*, agent-*)
│
├── earlbear-clis/              ← Python CLI source
│   ├── jira-cli/               (ebjira)
│   ├── gdocs-cli/              (ebdocs)
│   ├── shopify-cli/            (ebshop)
│   ├── deck-cli/               (ebdeck — host-installed orchestrator)
│   └── .claude/skills/         (6 deck-authoring skills)
│
├── earlbear-sites/             ← All frontend/visual assets
│   ├── wireframes/             (12-theme React landing page)
│   ├── ecommerce-stores/       (aura-coffee, golden-crema-coffee)
│   ├── claude-artifacts/       (10 hand-built HTML artifacts)
│   ├── scripts/                (dist pipeline: collect/index/encrypt/validate)
│   ├── Dockerfile.staticrypt
│   ├── Makefile                (wire-*, ecomm-*, dist-*, publish)
│   └── .claude/skills/         (8 frontend skills)
│
└── earlbear-claude-agent/      ← Autonomous cloud agent (Watson) — separate repo
```

## Decision tree: which repo?

- **Editing Python CLI source?** → `earlbear-clis/`
- **Running a CLI command?** → `earlbear/` (Docker-wrapped via `make jira-cli-*`, `make gdocs-cli-*`, `make shopify-cli-*`; host-wrapped via `make deck-cli-*`)
- **Editing a Jira or Shopify manifest, or running `/sync-catalog`, `/validate-catalog`, `/conform-jira`, `/conform-store`?** → `earlbear/`
- **Cloud agent management (status, queue, feedback, approvals)?** → `earlbear/` (`make agent-*` targets)
- **MCP server setup (Jira, Supabase)?** → `earlbear/` (`make mcp-jira`, `make mcp-supabase`)
- **Living docs / architecture docs / delivery SOPs?** → `earlbear/docs/`
- **Editing a wireframe theme, or building/reviewing/QA-ing the 12-theme landing page?** → `earlbear-sites/`
- **Building or exporting an ecommerce store?** → `earlbear-sites/` (`make ecomm-*`)
- **Importing a Claude share URL as a catalog artifact?** → `earlbear-sites/` (`/import-artifact`)
- **Publishing to `bytesofpurpose.github.io/earlbear/`?** → `earlbear-sites/` (`/publish` or `make publish`) — it force-pushes through `../earlbear/`'s git worktree, which is why the gh-pages URL stays stable.
- **Rotating `STATICRYPT_PASSWORD`?** → `earlbear-sites/` (`/reset-password`)
- **Authoring or generating a deck?** → `earlbear-clis/deck-cli/` via `ebdeck`, or from `earlbear/` via `make deck-cli-*` targets. The deck-authoring skills live at `earlbear-clis/.claude/skills/`.

## Single-publisher model

Only **`earlbear-sites/`** writes to the `bytesofpurpose/earlbear` gh-pages branch. The live site URL stays `bytesofpurpose.github.io/earlbear/` because `make publish` stages `dist/public/` into a git worktree checked out inside `../earlbear/`, then force-pushes from there. This keeps the URL stable while cleanly owning the build in one repo.

**Never run publish targets from `earlbear/`.** It has no `publish` target anymore — that capability moved.

## Skills at a glance

### In `earlbear/.claude/skills/`

- **Jira workflow**: `setup-jira`, `manage-jira-manifest`, `conform-jira`, `add-backlog-item`, `refine-working-model`, `validate-catalog`, `sync-catalog`, `leveraging-jira-cli`
- **Shopify workflow**: `setup-shopify`, `manage-shopify-store`, `conform-store`, `seed-shopify-store`, `customize-theme`, `leveraging-shopify-cli`
- **Cloud agent**: `manage-cloud-agent`, `extend-cloud-agent`
- **CLI development**: `developing-clis`, `leveraging-gdocs-cli`, `leveraging-image-cli`
- **Infrastructure**: `setup-supabase`, `refresh-living-docs`
- **This skill**: `earlbear-overview` (you're reading it)

### In `earlbear-sites/.claude/skills/`

- **Build & QA**: `design-frontend`, `design-review`, `qa-test`
- **Authoring**: `add-wireframe`, `import-artifact`
- **Publish & operate**: `publish`, `reset-password`, `manage-previews`

### In `earlbear-clis/.claude/skills/`

- **Deck authoring**: `add-deck`, `generate-deck` (with per-tool nuances for figma/marp/python-pptx/slidev), `review-slides`, `slide-design-review`, `setup-figma-plugin`, `run-figma-plugin`

## The CLI wrapping pattern

Every CLI follows the same shape and is exposed in `earlbear/Makefile`:

| CLI | Source | Docker image | Make targets |
|---|---|---|---|
| `ebjira` | `earlbear-clis/jira-cli/` | built by `make jira-cli-build` | `jira-cli-help`, `jira-cli-test`, `jira-cli-lint`, `jira-cli-rebuild` |
| `ebdocs` | `earlbear-clis/gdocs-cli/` | built by `make gdocs-cli-build` | `gdocs-cli-help`, `gdocs-cli-test`, `gdocs-cli-lint`, `gdocs-cli-rebuild`, `gdocs-cli-login`, `gdocs-cli-smoke`, `gdocs-cli-reference` |
| `ebshop` | `earlbear-clis/shopify-cli/` | built by `make shopify-cli-build` | `shopify-cli-help`, `shopify-cli-test`, `shopify-cli-lint`, `shopify-cli-rebuild`, `shopify-cli-login`, `shopify-cli-smoke`, `shopify-cli-integ`, `shopify-cli-conform`, `shopify-cli-export`, `shopify-cli-diagram`, `shopify-cli-seed`, `shopify-cli-seed-dry` |
| `ebdeck` | `earlbear-clis/deck-cli/` | host install (no Docker image) | `deck-cli-install`, `deck-cli-help`, `deck-cli-build`, `deck-cli-rebuild`, `deck-cli-test`, `deck-cli-lint`, `deck-cli-clean`, `deck-cli-clean-all` |

Three of the CLIs (`ebjira`, `ebdocs`, `ebshop`) are pure Python CLIs fully Docker-wrapped — `make <cli>-build` builds an image, and every subsequent target runs inside it. `ebdeck` deviates: it is installed on the host via `pip install -e ../earlbear-clis/deck-cli/` (one-time `make deck-cli-install`) and then shells out to `docker compose` against `deck-cli/docker-compose.yaml` to run the heavy marp/slidev/python-pptx/figma containers. Avoiding docker-in-docker keeps volume-mount paths sane for an orchestrator whose job is to launch other containers.

All four Python CLIs share conventions (pyproject.toml, click/typer entry points, Pydantic models, `output.py` Rich renderers) — see `earlbear/.claude/skills/developing-clis/SKILL.md` for the methodology.

**`.egg-info` gotcha**: `*-cli-clean` targets exist for ebdocs and ebshop because stale `.egg-info` directories can break Docker rebuilds. Use `make gdocs-cli-clean`/`shopify-cli-clean` before a rebuild if you see editable-install weirdness.

## The cloud agent

The cloud agent ("Watson") is autonomous and lives in a separate `earlbear-claude-agent/` repo. You interact with it from `earlbear/` via `make agent-*` targets:

- `make agent-status` — dashboard of queued/drafting/in-review/rework/paused issues
- `make agent-queue` — show issues queued for next run
- `make agent-checkins` — recent daily check-in/check-out reports
- `make agent-assign ISSUE=EARL-42` — assign an issue to the agent
- `make agent-feedback ISSUE=EARL-42 MSG="tone too formal"`
- `make agent-approve ISSUE=EARL-42`
- `make agent-pause ISSUE=EARL-42 MSG="waiting on X"`
- `make agent-history ISSUE=EARL-42` — agent's paper trail for an issue
- `make agent-simulate` — run the agent loop locally (against the earlbear-claude-agent repo)
- `make agent-trigger` — ad-hoc run (opens scheduled tasks page)

See `earlbear/.claude/skills/manage-cloud-agent/SKILL.md` and `extend-cloud-agent/SKILL.md` for detail.

## Supabase catalog

The artifact catalog at `bytesofpurpose.github.io/earlbear/` fetches card data from Supabase at runtime. The `artifacts` table stores metadata for each card. Both repos touch this:

- **`earlbear/`** owns the Supabase MCP setup (`make mcp-supabase`) and the catalog validation skill (`/validate-catalog`). The design doc is `earlbear/docs/design-supabase-catalog.md`.
- **`earlbear-sites/`** owns the rendering — `scripts/generate-index.sh` builds `dist/public/index.html`, which fetches from Supabase at runtime. Preview assignment is managed via `/manage-previews` (in earlbear-sites).

The anon key is a Supabase `sb_publishable_*` key, intentionally public and RLS-protected. The service-role key is server-side only and **never** baked into dist/ output.

## Common workflows

### Working on a Jira-routed issue end-to-end

```bash
cd earlbear
make agent-status                    # see queue
make agent-assign ISSUE=EARL-42      # grab it
# ...implement...
make jira-cli-test                   # run tests
# ...review...
make agent-approve ISSUE=EARL-42
```

### Updating the Jira manifest (source of truth)

```bash
cd earlbear
$EDITOR manifests/jira/manifest.yaml
# Then invoke /conform-jira or /validate-catalog
```

### Adding a new CLI command

```bash
cd earlbear-clis/jira-cli
$EDITOR src/ebjira/commands/<group>.py
cd ../../earlbear
make jira-cli-test                   # Docker-wrapped tests
make jira-cli-rebuild                # rebuild image
```

### Designing/iterating on a wireframe theme

```bash
cd earlbear-sites
make wire-build
make wire-up                         # http://localhost:3010
# ...edit wireframes/frontend/src/themes/<theme>.ts...
# then invoke /design-review and /qa-test
```

### Publishing updates to the live site

```bash
cd earlbear-sites
make wire-export                     # build all 12 themes
make ecomm-export                    # build stores into claude-artifacts/
make dist                            # collect + index + encrypt
make dist-validate                   # assert encryption coverage
make dist-preview                    # eyeball it
make publish                         # force-push through ../earlbear worktree
```

## When this overview goes stale

This skill is the single source of truth for the "where does X live?" question. Update it when:

- A repo boundary changes (something moves between earlbear / earlbear-clis / earlbear-sites)
- A new CLI is added (extend the CLI wrapping pattern table)
- A new skill is added to any repo (extend the Skills section)
- The publish model changes (single-publisher → multi-publisher or similar)

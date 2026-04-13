---
name: qa-test
description: Functional QA and regression testing for EarlBear wireframes. Tests builds, service health, all 12 themes serve, feedback system works end-to-end (toggle, pin, form, backend, persistence, report generation), API correctness, and Docker health. Catches regressions after code changes.
user_invocable: true
---

# QA Test Skill

> **Context:** This skill operates in the `wireframes/` directory. After making changes, run `make wire-export` to export static builds, then `make dist` to rebuild `dist/public/` with encryption.

Functional QA and regression testing. Tests that things **work** — not how they look (that's `/design-review`).

## What This Tests

### 1. Build Health
- All 12 themes build via `build-all.sh` without errors
- Index page builds alongside theme pages
- No TypeScript compilation errors or missing imports

### 2. Service Health
- Frontend container starts, nginx serves on port 3000
- Backend container starts, Express on port 3001
- `GET /api/health` returns `{"status":"ok"}`
- nginx proxies `/api/*` to backend

### 3. Theme Serving
- `GET /` serves index/theme-picker (not nginx default page)
- `GET /{theme}/` returns 200 for all 12 themes
- Each theme page includes correct `<title>` with theme name
- CSS variables are applied per theme
- Footer theme links point to valid sibling paths

### 4. Feedback — Frontend
- Bar renders at top on load
- `F` toggles feedback mode (bar visual state changes)
- `F` does NOT toggle when focused in input/textarea
- Clicking in feedback mode creates a pending pin
- Form appears anchored to pin, has email + comment fields
- Email pre-fills from localStorage
- Submit creates a visible numbered pin
- `Escape` dismisses form without saving
- Click-outside dismisses form
- Pin hover shows tooltip (comment + email)
- Pins hidden when feedback mode OFF
- Cursor changes to comment bubble in feedback mode

### 5. Feedback — Backend API
- `POST /api/feedback` with valid payload → 201 + saved entry
- `POST /api/feedback` missing fields → 400
- `POST /api/feedback` with screenshot → saves sanitized PNG to `reports/images/`
- `POST /api/feedback` with non-PNG data → 400
- `POST /api/feedback` > 10MB payload → rejected
- `GET /api/feedback?theme=espresso` → only espresso entries
- `GET /api/feedback` → all entries
- `GET /api/feedback/report` → markdown content

### 6. Feedback — Persistence & Reports
- `reports/feedback.json` on host contains submitted entries
- `reports/feedback-report.md` regenerated with new entries
- Report includes: email, date, comment, viewport, browser, section
- Report references `![Screenshot](./images/fb-XXX-theme-section.png)`
- Screenshot PNG exists at referenced path, is valid PNG, max 1920px wide
- Page reload fetches existing pins from `GET /api/feedback`

### 7. Feedback — Isolation
- Espresso feedback does NOT appear on latte page
- Each theme scoped by `theme` field
- localStorage fallback works when backend unavailable

### 8. Screenshot Service
- `docker compose --profile qa run --rm -e RUN_ID=test screenshots` completes
- Creates `qa-feedback/test-screenshots/` with 25 PNGs (1 index + 12x2 themes)
- All PNGs non-empty (> 10KB)

### 9. Docker Compose
- `docker compose up --build -d` starts without errors
- `docker compose down` cleanly stops
- Volume mounts work (`./reports`, `./qa-feedback`)
- Frontend rebuild picks up code changes

## How to Run

### Automated smoke test (curl)

```bash
# Service health
curl -sf http://localhost:3010/ | grep -q "EarlBear" && echo "✓ Index" || echo "✗ Index"
curl -sf http://localhost:3011/api/health | grep -q "ok" && echo "✓ Backend" || echo "✗ Backend"

# All 12 themes
for t in espresso latte matcha mocha cold-brew investor customer internal spring summer autumn winter; do
  curl -sf "http://localhost:3010/$t/" | grep -q "EarlBear" && echo "✓ $t" || echo "✗ $t"
done

# API
curl -sf http://localhost:3011/api/feedback | grep -q "\[" && echo "✓ GET feedback" || echo "✗ GET"
curl -sf http://localhost:3011/api/feedback/report && echo "✓ GET report" || echo "✗ report"

# POST feedback
curl -sf -X POST http://localhost:3011/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"email":"qa@test.com","comment":"QA smoke test","x":50,"y":200,"section":"hero","theme":"espresso","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","userAgent":"QA-Bot","viewportWidth":1440,"viewportHeight":900}' \
  | grep -q "fb-" && echo "✓ POST feedback" || echo "✗ POST"

# Persistence
test -f reports/feedback.json && echo "✓ feedback.json" || echo "✗ feedback.json"
test -f reports/feedback-report.md && echo "✓ report.md" || echo "✗ report.md"
```

### Browser-based tests (feedback interaction)

Requires a browser (manual or Puppeteer/Chrome MCP):

1. Navigate to `/espresso/`
2. Verify feedback bar visible
3. Press `F` → bar glows, cursor changes
4. Click Hero section → form appears
5. Fill email + comment, submit → pin appears
6. Hover pin → tooltip shows
7. Press `F` → pins hide
8. Refresh → pins reload from backend
9. Check `./reports/feedback-report.md` for entry

### Regression after changes

1. `docker compose build && docker compose up -d`
2. Run automated smoke test
3. If feedback modified → run browser tests
4. If themes modified → also run `/design-review`

## Documenting Results

Create `qa-feedback/{RUN_ID}-qa-round-{N}.md`:

```markdown
# QA Test Results — Round {N}

**Date**: {YYYY-MM-DD}
**Trigger**: {what changed}

## Results

### Build Health
- [x] All 12 themes build @done({timestamp})

### Service Health
- [x] Frontend :3010 @done({timestamp})
- [x] Backend :3011 @done({timestamp})

### Theme Serving
- [x] All 12 themes return 200 @done({timestamp})
...

## Failures

### {Title}
**Repro**: ...
**Expected**: ...
**Actual**: ...
**Screenshot**: ![](./{RUN_ID}-screenshots/{file}.png)

## Summary
**Pass**: {X}/{Y} | **Fail**: {Z} | **Blocked**: {N}
```

Same `- [ ]` / `- [x] @done()` / timestamped screenshot conventions as `/design-review`.

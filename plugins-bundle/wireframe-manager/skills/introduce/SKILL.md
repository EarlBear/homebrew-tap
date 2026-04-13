---
name: introduce
description: Introduce the wireframe-manager plugin and its capabilities
type: user-invocable
---

# Introduce Wireframe Manager

The **wireframe-manager** plugin covers the full lifecycle of EarlBear landing-page wireframes in `earlbear-sites/wireframes/` — architecture design, visual review, functional QA, and adding new themes or wireframe types.

## Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `design-frontend` | `/wireframe-manager:design-frontend` | Principal-engineer frontend architecture: Research → BRD → Design Doc → QA Review for hosting, auth, CI/CD, and AI integration decisions |
| `design-review` | `/wireframe-manager:design-review` | Principal product-designer visual review of all 12 themes — capture screenshots via Docker, evaluate typography/spacing/contrast/warmth, document findings as actionable `- [ ]` tasks |
| `qa-test` | `/wireframe-manager:qa-test` | Functional and regression testing — build health, service health, all 12 themes serve, feedback system end-to-end (toggle → pin → form → API → persistence → report), Docker health |
| `add-wireframe` | `/wireframe-manager:add-wireframe` | Scaffold a new wireframe type alongside `frontend/`, wire it into the Makefile and dist-collect pipeline, and update CLAUDE.md |

## Typical iteration loop

1. Edit `wireframes/frontend/src/…`
2. Rebuild: `docker compose build frontend && docker compose up -d --force-recreate frontend`
3. `/wireframe-manager:design-review` — screenshots + checklist → `wireframes/qa-feedback/…`
4. `/wireframe-manager:qa-test` — smoke tests services, API, feedback flow
5. Fix findings, repeat until all Critical/Moderate items are `- [x] @done`

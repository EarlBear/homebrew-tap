---
name: introduce
description: Introduce the cloud-agent-manager plugin and its capabilities
type: user-invocable
---

# Introduce Cloud Agent Manager

The **cloud-agent-manager** plugin covers the full lifecycle of Watson (a.k.a. Earl), the EarlBear autonomous Claude Code agent, in the `earlbear` repo. It spans day-to-day operations (setup, run, assign, debug, review) and developer-facing extension work (adding deliverable kinds, modifying quality checklists, changing agent behavior).

## Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `manage-cloud-agent` | `/cloud-agent-manager:manage-cloud-agent` | Manage Watson end-to-end — setup, run, assign work, debug failures, review runs, and run retrospectives. Routes to the right sub-workflow based on intent. |
| `extend-cloud-agent` | `/cloud-agent-manager:extend-cloud-agent` | Extend Earl's capabilities — add new deliverable kinds, modify quality checklists, and change agent behavior. Developer-facing operations that modify Earl's working model. |

## Key systems

- **Jira** (EARL project) — issue queue, board columns, status transitions
- **Supabase** (`agent_runs` table) — execution metrics and audit trail
- **GitHub** (`earlbear` repo) — agent source, operating model, identity
- **Anthropic Cloud** — execution environment

## Typical flows

**Assign and run:**
1. `/cloud-agent-manager:manage-cloud-agent` with intent "assign" — tag Jira issues as `ai-eligible` or assign to `watson@earlbear.com`
2. `/cloud-agent-manager:manage-cloud-agent` with intent "run" — trigger or simulate an agent loop
3. `/cloud-agent-manager:manage-cloud-agent` with intent "review" — check run results and dashboard

**Debug a failure:**
- `/cloud-agent-manager:manage-cloud-agent` with intent "debug" — investigate paused issues, error logs, and agent state

**Add a new deliverable type:**
1. `/cloud-agent-manager:extend-cloud-agent` with intent "add kind" — scaffold new kind in `docs/draft-checklists.yaml` and operating model
2. `/cloud-agent-manager:manage-cloud-agent` with intent "test" — smoke test end-to-end before deploying

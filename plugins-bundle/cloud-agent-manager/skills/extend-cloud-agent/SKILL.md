---
name: extend-cloud-agent
description: Extend Earl's capabilities — add new deliverable kinds, modify quality checklists, and change agent behavior
type: user-invocable
---

# Extend Cloud Agent

> **Context:** This skill extends Earl's capabilities -- adding new deliverable kinds, modifying quality checklists, and changing agent behavior. These are developer-facing operations that modify Earl's working model. All changes are tested locally before deploying to the cloud environment.
>
> **Key files:**
> - `docs/draft-checklists.yaml` -- per-kind quality gates
> - `docs/earlbear-agent-responsibilities.md` -- the prompt Earl executes each run
> - `earlbear-claude-agent` repo: `OPERATING-MODEL.md` -- tenets, templates, transitions
> - `earlbear-claude-agent` repo: `CLAUDE-CLOUD-AGENT.md` -- agent identity and rules (copied to CLAUDE.md at deploy)

## When to trigger

User says things like:
- "add a new kind", "new deliverable type", "Earl should handle docs"
- "add a checklist", "modify quality checks", "update the blog-post checklist"
- "change agent behavior", "modify Earl's prompt", "update the operating model"
- "extend Earl", "teach Earl to do X"

## Router

Detect the user's intent and read the appropriate sibling file, then execute its instructions.

| Intent | Phrases | Sibling File |
|--------|---------|-------------|
| **Add kind** | "add a new kind", "new deliverable type", "Earl should handle X" | `add-kind.md` |
| **Add/modify checklist** | "add checklist", "modify checks", "update quality gates" | `add-checklist.md` |
| **Modify behavior** | "change behavior", "modify prompt", "update tenets", "edit operating model" | `modify-behavior.md` |

## Execution

1. Identify which intent matches the user's request
2. Read the corresponding sibling markdown file from this directory
3. Follow its step-by-step instructions
4. All changes must be tested before deploying — use `/manage-cloud-agent test` for a full end-to-end smoke test (creates test Deliverable, triggers agent, verifies Google Doc output + checklist + paper trail)
5. Update the relevant living documents in the same changeset (per Tenet 2 in CLAUDE.md)

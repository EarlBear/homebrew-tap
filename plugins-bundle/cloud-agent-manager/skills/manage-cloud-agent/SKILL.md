---
name: manage-cloud-agent
description: Manage Watson (Earl), the EarlBear cloud agent — setup, run, assign work, debug failures, review runs, and retrospectives
type: user-invocable
---

# Manage Cloud Agent

> **Context:** This skill manages Watson (a.k.a. Earl), the EarlBear cloud agent. Watson is an autonomous Claude Code agent that runs on a schedule, picks up Jira issues that are **assigned to him** (`watson@earlbear.com`) or labeled `ai-eligible`, drafts artifacts, validates them against quality checklists, and leaves them for human review. Watson is **column-aware** — his behavior depends on the board status (Planning → plan, Prioritized → draft, In Progress → rework, Review → QA). He never self-approves work. See `earlbear-claude-agent` repo: `OPERATING-MODEL.md` for tenets and `CLAUDE.md` for identity.
>
> **Key systems:** Jira (EARL project), Supabase (agent_runs metrics), GitHub (earlbear repo), Anthropic Cloud (execution environment).

## When to trigger

User says things like:
- "set up the cloud agent", "bootstrap Earl", "configure cloud agent"
- "run the agent", "trigger Earl", "test agent", "simulate a run"
- "assign work to Earl", "queue issues for the agent", "tag for agent"
- "debug the agent", "troubleshoot Earl", "why did the agent fail"
- "agent status", "review agent runs", "show me the dashboard"
- "agent retro", "analyze Earl's performance", "how is Earl doing"

## Router

Detect the user's intent and read the appropriate sibling file, then execute its instructions.

| Intent | Phrases | Sibling File |
|--------|---------|-------------|
| **Setup** | "set up", "bootstrap", "configure cloud agent", "install Earl" | `setup.md` |
| **Run** | "run", "trigger", "test agent", "simulate", "execute agent loop" | `run.md` |
| **Assign** | "assign", "queue", "tag for agent", "make eligible", "give Earl work" | `assign.md` |
| **Debug** | "debug", "troubleshoot", "why did agent fail", "agent error", "paused issues" | `debug.md` |
| **Review** | "status", "review runs", "dashboard", "what did Earl do", "check-ins" | `review.md` |
| **Test** | "test agent", "smoke test", "verify agent", "test Earl", "end-to-end test" | `test.md` |
| **Retrospective** | "retro", "analyze", "how is Earl doing", "agent metrics", "throughput" | `retrospective.md` |

## Execution

1. Identify which intent matches the user's request
2. Read the corresponding sibling markdown file from this directory
3. Follow its step-by-step instructions
4. If the intent is ambiguous, ask the user to clarify before proceeding

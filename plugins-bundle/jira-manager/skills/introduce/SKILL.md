---
name: introduce
description: Introduce the jira-manager plugin and its capabilities
type: user-invocable
---

# jira-manager

Manage Jira issues and backlog health for the EarlBear project. Covers creation, grooming, stub handling, epic taxonomy, and the ebjira CLI.

## Skills

| Skill | Purpose | Invoke |
|---|---|---|
| `creating-jira-issues` | Systematic workflow for creating Jira issues — search for duplicates, pick the right type and parent, sync locally | `/jira-manager:creating-jira-issues` |
| `grooming-jira-issues` | Run a structured grooming campaign — snapshot, triage findings into reshape/rewrite/migrate classes, drain in waves | `/jira-manager:grooming-jira-issues` |
| `handling-jira-stubs` | Classify and process stub tickets — scope, defer, or retire thin placeholder tickets via the Stubs Epic lifecycle | `/jira-manager:handling-jira-stubs` |
| `managing-epic-taxonomy` | Add, remove, rename, or reclassify epic categories; audit existing classifications | `/jira-manager:managing-epic-taxonomy` |
| `leveraging-jira-cli` | Quick reference for all ebjira CLI commands — issues, epics, boards, bulk ops, seed YAML, dev workflow | `/jira-manager:leveraging-jira-cli` |
| `add-backlog-item` | Create Jira issues via the Jira MCP tools with dynamic project discovery, duplicate checking, and Supabase sync | `/jira-manager:add-backlog-item` |
| `conform-jira` | Ensure the live Jira project matches the declarative manifest — diff, apply, regenerate diagrams | `/jira-manager:conform-jira` |

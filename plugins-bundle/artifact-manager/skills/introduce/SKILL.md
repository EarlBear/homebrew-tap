---
name: introduce
description: Introduce the artifact-manager plugin and its capabilities
type: user-invocable
---

# Introduce Artifact Manager

The **artifact-manager** plugin manages the earlbear-sites catalog lifecycle — importing HTML artifacts, managing Supabase previews, publishing the encrypted dist to GitHub Pages, and rotating the StatiCrypt password.

## Skills

| Skill | Invoke | Purpose |
|---|---|---|
| `import-artifact` | `/artifact-manager:import-artifact` | Import a Claude-generated HTML artifact into `claude-artifacts/`, create a Supabase catalog entry, and wire it into `make dist` |
| `manage-previews` | `/artifact-manager:manage-previews` | Audit and write working-backwards previews (code/email/sequence/personas/catalog) to Supabase for each artifact |
| `publish` | `/artifact-manager:publish` | Full publish flow: `make dist` → validate encryption → browser preview → force-push to the `../earlbear` gh-pages worktree |
| `reset-password` | `/artifact-manager:reset-password` | Rotate the StatiCrypt password, rebuild, revalidate, republish, and distribute the new password to all recipients |

## Typical publish flow

1. `/artifact-manager:import-artifact` — add new artifact, get Supabase draft entry
2. `/artifact-manager:manage-previews` — add working-backwards preview before publishing
3. `/artifact-manager:publish` — build + encrypt + push to gh-pages
4. `/artifact-manager:reset-password` — when access needs to be revoked and re-issued

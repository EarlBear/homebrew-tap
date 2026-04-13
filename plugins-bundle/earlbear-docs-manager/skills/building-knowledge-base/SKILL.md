---
name: building-knowledge-base
description: Mental model and folder semantics for the EarlBear knowledge base under earlbear-content/gdocs/knowledge-base/. Use when placing new reference content, deciding whether something belongs in KB vs Jira, promoting research → final findings, or proposing structural changes to the KB layout.
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(./bin/ebdocs *), Bash(git *)
---

# Building the Knowledge Base

This skill captures the mental model for `earlbear-content/gdocs/knowledge-base/` — the single reference-content tree that agents and humans consult for "what good looks like" across the EarlBear ecosystem. Read this before creating a new folder, placing a new doc, or proposing structural changes.

## Core mental model

The knowledge base has **two axes** that must stay orthogonal:

1. **Descriptive vs prescriptive**
   - **Descriptive** = *what a thing IS*. Anatomy, taxonomy, catalogs, benchmarks.
   - **Prescriptive** = *what to DO*. Playbooks, SOPs, decision trees, checklists.
   - Never mix them in the same folder. `shopify-anatomy/` answers "what are the parts of a Shopify store?"; `shopify-playbooks/` answers "which parts should we use for this client?"

2. **Platform-agnostic vs platform-specific**
   - **Agnostic** = `ecommerce-fundamentals/`, `conversion-playbook/`. Applies to any ecommerce stack.
   - **Specific** = `shopify-anatomy/`, `shopify-playbooks/`. Shopify-only know-how.
   - If you catch yourself writing "and on Shopify, X" inside `ecommerce-fundamentals/`, the content belongs in a `shopify-*` folder instead.

These two axes give a 2×2 for every piece of content. Use it:

|  | Descriptive | Prescriptive |
|---|---|---|
| **Platform-agnostic** | `ecommerce-fundamentals/` | `conversion-playbook/`, per-topic playbooks |
| **Platform-specific** | `shopify-anatomy/` | `shopify-playbooks/` |

## Folder inventory (current topology)

```
gdocs/
├── knowledge-base/
│   ├── discovery/              # Who we sell to, how we find them
│   │   ├── personas/           # One doc per persona
│   │   ├── playbooks/          # Per-persona search strategies
│   │   └── signals/            # Buy signals, disqualifiers, store health tells
│   │
│   ├── sales-enablement/       # What we say to convert prospects
│   │   ├── credibility/        # Data-backed claims, proof points
│   │   ├── outreach/           # Email sequences, cadences, templates
│   │   ├── pitch-assets/       # Decks, one-pagers, talk tracks
│   │   └── objection-handling/ # Common pushbacks + responses
│   │
│   ├── ecommerce-fundamentals/ # DESCRIPTIVE + agnostic — what good looks like
│   ├── conversion-playbook/    # PRESCRIPTIVE + agnostic — conversion tactics
│   │
│   ├── shopify-anatomy/        # DESCRIPTIVE + shopify — module library, page types
│   ├── shopify-playbooks/      # PRESCRIPTIVE + shopify — themes, apps, store-buildout
│   │
│   ├── tech-designs/           # Per-agent designs — locked topology
│   │   ├── ecomm-agent/
│   │   ├── shopify-agent/
│   │   ├── discovery-agent/
│   │   ├── store-analyzer/
│   │   ├── earlbear-platform/
│   │   └── _shared/            # Cross-agent designs
│   │
│   ├── strategies/             # Company-level strategic thinking
│   │   ├── gtm/
│   │   ├── partnerships/       # Shopify Partner, commissions, alliances
│   │   └── pricing/
│   │
│   ├── research/               # Exploratory work — NOT yet reference
│   │   └── final-findings/     # Promoted outputs worth keeping
│   │
│   ├── artifacts/              # Rendered outputs (append-only)
│   │   ├── store-analyses/
│   │   ├── mockups/
│   │   └── reports/
│   │
│   ├── ops/                    # How the team runs
│   │   ├── sops/
│   │   ├── meetings/
│   │   ├── onboarding/
│   │   └── business-process-dag/
│   │
│   └── runbooks/               # Operational runbooks (existing)
│
└── vision/                     # Aspirational/north-star — sibling to knowledge-base
```

`vision/` lives at the `gdocs/` root, not inside `knowledge-base/`. Vision is future-state thinking; knowledge base is current-state reference.

## Placement rules

Use these in order. First rule that applies wins.

1. **Is it aspirational future-state thinking?** → `gdocs/vision/`
2. **Is it a rendered output, not authored source?** → `gdocs/knowledge-base/artifacts/<subtype>/`
3. **Is it exploratory, unfinished, or uncertain?** → `gdocs/knowledge-base/research/`
4. **Is it how the team operates (not what the product is)?** → `gdocs/knowledge-base/ops/`
5. **Is it a tech design for an agent or platform component?** → `gdocs/knowledge-base/tech-designs/<agent>/`
6. **Is it company strategy (GTM, pricing, partnerships)?** → `gdocs/knowledge-base/strategies/<subtype>/`
7. **Is it about finding/qualifying prospects?** → `gdocs/knowledge-base/discovery/`
8. **Is it about converting prospects (email, pitch, credibility)?** → `gdocs/knowledge-base/sales-enablement/`
9. **Is it Shopify-specific descriptive?** → `gdocs/knowledge-base/shopify-anatomy/`
10. **Is it Shopify-specific prescriptive?** → `gdocs/knowledge-base/shopify-playbooks/`
11. **Is it platform-agnostic descriptive ecom fundamentals?** → `gdocs/knowledge-base/ecommerce-fundamentals/`
12. **Is it platform-agnostic prescriptive conversion tactics?** → `gdocs/knowledge-base/conversion-playbook/`

If nothing fits, **don't improvise a folder**. Stop and ask the user — either the taxonomy needs an addition or the content doesn't belong in the KB at all.

## One-file-per-concept rule (critical)

**The knowledge base holds exactly one canonical file per concept.** Never create sibling versions like `shopify-themes-v2.md`, `shopify-themes-2026-04.md`, `shopify-themes-updated.md`, or `shopify-themes-old.md`. Multiple files for the same concept confuse agents and humans — they can't tell which is authoritative.

Rules:

- **Updates overwrite.** When content changes, edit the canonical file in place. Git history is the version trail. Never keep "the old version just in case" as a sibling file.
- **No dated filenames in canonical folders.** Dates belong only in `research/` (workbench entries), never in `ecommerce-fundamentals/`, `shopify-playbooks/`, `conversion-playbook/`, etc.
- **No `supersedes:` frontmatter in canonical folders.** If a doc supersedes another, overwrite the file — don't leave both with a pointer. `supersedes:` is only meaningful across *different* canonical concepts when a concept itself is retired and absorbed into a renamed doc (rare).
- **No redirect stubs.** Don't leave a file saying "see X" — just delete it. Broken links surface in review; redirect stubs rot silently.
- **Agents must never find two answers to the same question in KB.** If you catch yourself writing a "new version" of an existing doc, stop and edit the existing one instead.

**Exception**: `research/` is the only folder where multiple date-stamped files on the same topic are allowed, because it's explicitly the workbench for exploring. Once promoted out of research, the overwrite rule applies.

## Research → canonical promotion

`research/` is the workbench. `research/final-findings/` is a staging area for validated outputs that haven't found their canonical home yet. Promotion rules:

- **Into `research/`**: anything exploratory, partially-validated, or in-progress. Date-stamp the filename (e.g., `2026-04-08-shopify-checkout-abtest-notes.md`). No README requirement.
- **Into `research/final-findings/`**: validated content worth citing that *does not yet fit* an existing canonical folder. If it fits a canonical folder (playbook, anatomy, fundamentals), promote directly there — skip `final-findings/`.
- **Promotion signal**: if you catch yourself wanting to cite a research doc from a playbook, promote the cited content first. Research docs are never cited as canonical.
- **Graduation to canonical**: when a `final-findings/` entry fits a canonical folder, **overwrite or create** the canonical file (one per concept, per the rule above) and **delete** the `final-findings/` copy. Do not leave a stub. Do not keep both.
- **Graduation from research/**: after promoting content out, the source research doc stays as an audit trail (dated, in `research/`). That is the one place sibling files on a topic are acceptable.

Research docs are kept indefinitely — they're the audit trail. Canonical folders are continuously edited in place.

## README-per-folder rule

Every top-level folder under `knowledge-base/` (and every immediate subfolder like `discovery/personas/`) MUST have a `README.md` with:

1. **One-line purpose**: "This folder holds X."
2. **Scope boundary**: "This is NOT for Y — that goes in Z."
3. **Naming convention**: if the folder enforces one (e.g., date prefix, kebab-case).
4. **Current contents**: a bullet list of the notable docs, kept rough but not stale.

READMEs prevent drift. If a teammate or agent can't tell from the README where a new doc belongs, the README is insufficient — fix the README, not the placement.

## Frontmatter conventions (local-only)

Every KB doc gets frontmatter (preserved by `ebdocs sync` as local-only). Required fields:

```yaml
---
tags: [discovery, personas, b2c]       # searchable topic tags
agent_hints:                            # who should use this and how
  - "ecomm-agent reads this when evaluating client fit"
specifies: []                           # Jira keys this doc specifies (doc -> Jira)
refs: []                                # KB slugs this doc references (doc -> doc, intra-KB only)
---
```

Two distinct link namespaces (do not conflate):

- **`specifies:`** — crosses the Jira/KB boundary. Entries are Jira keys like `EARL-99`. Use for canonical spec → implementation ticket relationships. Drives the `jira/links.yaml` reverse index.
- **`refs:`** — intra-KB only. Entries are KB-root-relative slugs without the `.md` suffix, e.g. `tech-designs/shopify-agent/overview`. Use when one KB doc builds on or cites another. Drives the `gdocs/knowledge-base/links.yaml` `doc_to_docs` index.

Both are validated at commit time by the `ebdocs links validate` pre-commit hook. Broken `refs:` block the commit — fix by editing the entry or running `ebdocs links rename <old> <new> --apply`. Stale indexes block the commit — fix with `ebdocs links rebuild` and stage the updated `links.yaml` files. See also `ebdocs links show <slug>` for reverse lookups.

Optional fields:

- `title:` — human-readable doc title (string). Falls back to the first `# Heading` if absent.
- `components:` — list of system component names this doc describes or references (list of strings). Used by tooling to build component → doc reverse indexes.
- `history:` — migration provenance (object). Append-only. Fields:
  - `migrated_from:` — source reference (Jira key like `EARL-133`, or previous path)
  - `migrated_at:` — ISO date the migration happened
  - `structured_by:` — who did the structuring (`human`, `agent`, or a name)
  - `structured_at:` — ISO date the structuring happened
  - `split_from_siblings:` — list of sibling doc paths if this doc was split out of one or more existing docs
- `promoted_from:` — path to research doc (for `final-findings/` entries only; the research source remains in `research/` as audit trail)
- `status: draft|canonical|stale` — for reference docs that need lifecycle tracking

Example using all three optional fields:

```yaml
---
title: Funnel Architecture — Conversion Rules
tags: [conversion, funnel, tofu, mofu, bofu]
components:
  - store-analyzer
agent_hints:
  - Canonical spec for e-commerce funnel architecture rules
specifies:
  - EARL-99
history:
  migrated_from: EARL-99
  migrated_at: 2026-04-06
  structured_by: heuristic-v1
  structured_at: 2026-04-06
  split_from_siblings:
    - gdocs/knowledge-base/conversion-playbook/legacy-funnel-notes.md
---
```

**Do not use** `supersedes:` in canonical folders. Per the one-file-per-concept rule, updates overwrite the canonical file in place; git history is the version trail.

See `.claude/skills/authoring-drive-docs/SKILL.md` for Drive-rendering constraints.

## When KB vs Jira vs Vision

This is the most common mis-placement. Use this decision tree:

- **Is someone going to DO work on it?** → Jira
- **Is it the long-term picture of where we're heading?** → `gdocs/vision/`
- **Is it a canonical answer to "how do we think about X"?** → `gdocs/knowledge-base/<appropriate-folder>/`
- **Is it exploratory or not-yet-canonical?** → `gdocs/knowledge-base/research/`

KB content is **stable reference**. If it changes monthly, it's probably a tracking doc and belongs in Jira or ops/. If it changes rarely and is meant to be cited, it's KB.

## Proposing structural changes

Taxonomy drift is the biggest risk. Before adding or renaming a top-level folder:

1. **Write a one-paragraph rationale** in `gdocs/knowledge-base/README.md` under a "Taxonomy changelog" section.
2. **Check if existing content needs to move**. If yes, plan the moves as a single commit.
3. **Update this skill** — the folder inventory and placement rules must match reality.
4. **Get user sign-off** before creating the folder. The taxonomy is a user-facing contract.

Never add a folder silently. Never leave the skill out of sync with the actual tree.

## Anti-patterns

- **Creating sibling versions of the same concept** (`shopify-themes.md` + `shopify-themes-v2.md`). Overwrite the canonical file. Git tracks history.
- **Dated filenames in canonical folders** (`shopify-themes-2026-04.md`). Dates belong only in `research/`.
- **Redirect stubs** ("this moved to X"). Just delete the old file — broken links get caught in review; stubs rot silently.
- **`supersedes:` frontmatter in canonical folders.** Overwrite instead.
- **Improvising folders** under time pressure. Stop and ask instead.
- **Mixing descriptive + prescriptive** ("Shopify themes: overview and recommendations"). Split it — overview → anatomy, recommendations → playbooks.
- **Putting Shopify content in `ecommerce-fundamentals/`**. If it's Shopify-specific, it goes in a `shopify-*` folder.
- **Citing research docs as canonical**. Promote to `final-findings/` or a playbook first.
- **Dumping half-finished drafts in canonical folders**. Use `research/`. Promote when validated.
- **Creating a `misc/` or `other/` folder**. If nothing fits, the taxonomy is wrong — fix the taxonomy.
- **Duplicating content across folders**. Use `_shared/` or cross-link with relative paths.
- **Overwriting or deleting `history:` entries.** `history:` is append-only — when a doc is split or migrated again, append a new entry; never rewrite or remove existing provenance.

## Interaction with the grooming skill

When `grooming-jira-issues` Wave 3 (migration) runs, the destinations MUST come from this skill's folder inventory. If the migration target doesn't fit an existing folder, pause the campaign, resolve the taxonomy question here, then resume.

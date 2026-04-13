# Capture CLI Use Case

> Frictionless capture skill. At the end of a CLI-heavy task, record what just happened as a reusable use case so the next agent (or the next you) can find it via `ebjira discover` / `ebdocs discover` / `ebshop discover`.

## When to invoke

Invoke this skill whenever you finish a task that leaned on `ebjira`, `ebdocs`, or `ebshop` in a non-trivial way. Triggers include:

- **After a non-trivial CLI task** — you just chained 3+ commands, used a clever JQL, stitched together two CLIs, or worked around an API quirk.
- **When the user says "that was clever"** — or "save that pattern", "remember this one", "we'll want this again".
- **When you would otherwise edit a skill file** — but the pattern is smaller than a skill. Use cases are cheaper than skills and travel with the CLI source, not the host repo.
- **When a hard-won gotcha surfaced** — you learned a field was renamed, an endpoint needs a specific flag, a status only transitions via a particular workflow. Capture the pattern *with* the gotcha in `notes`.
- **Before ending a session** — quick sanity sweep: "did I do anything worth recording?"

If the task was a single `--help` lookup or a stock command, do not capture. See Anti-patterns below.

## Inputs

The skill takes one argument: the CLI name.

- `ebjira` → `/Users/omareid/Workspace/git/earlbear-clis/jira-cli/src/ebjira/use-cases.yaml`
- `ebdocs` → `/Users/omareid/Workspace/git/earlbear-clis/gdocs-cli/src/ebdocs/use-cases.yaml`
- `ebshop` → `/Users/omareid/Workspace/git/earlbear-clis/shopify-cli/src/ebshop/use-cases.yaml`

If no argument is given, ask: "Which CLI is this for — ebjira, ebdocs, or ebshop?" Do not guess.

## Schema

Each entry appended to the `use_cases:` list follows this shape:

```yaml
- id: kebab-case-id
  title: Short title (under 70 chars)
  when: One-line trigger — when would you reach for this?
  commands:
    - ebjira issue search --jql "..."
    - ebjira issue transition ...
  notes: |
    Multi-line markdown notes: gotchas, why this pattern, what to watch for.
  tags: [bulk, release, workflow]
  last_verified: 2026-04-11
```

Rules:

- `id` — kebab-case, unique within the file. Auto-suggest from the title (lowercase, dashes, drop stop-words). If a collision exists, append `-2`, `-3`, etc.
- `title` — under 70 chars, imperative voice ("Bulk transition issues after release cut").
- `when` — single line. The one-sentence trigger an agent would Ctrl-F for.
- `commands` — real commands as run (or lightly sanitized: redact tokens, replace project-specific IDs with placeholders like `EARL-XXX`). Order matters.
- `notes` — markdown. Explain *why*, not just *what*. Call out gotchas, linked CLAUDE.md sections, API version quirks.
- `tags` — flat list, lowercase. Prefer reusing existing tags in the file over inventing new ones.
- `last_verified` — today's ISO date (`YYYY-MM-DD`). Never fabricate — if you didn't just run the commands, say so in `notes` and use the date you *did* last verify.

## Steps

1. **Resolve the target file.** Map the CLI argument to its `use-cases.yaml` path. If the file does not exist yet, create it with a top-level `use_cases: []` list before appending.

2. **Read existing entries.** Load the YAML and collect all existing `id` values and common tags. Show the user a one-line summary ("18 existing use cases; common tags: bulk, release, workflow, gotcha"). This avoids duplicates and nudges tag reuse.

3. **Draft the entry.** Walk through the fields in order, pulling from session history where possible:
   - **title** — propose one, let the user edit.
   - **id** — auto-suggested kebab-case from the title; confirm uniqueness against step 2.
   - **when** — one-line trigger.
   - **commands** — pull the actual commands you ran in this session. Sanitize secrets and stabilize IDs.
   - **notes** — ask yourself: *what made this interesting?* Capture the gotcha, the reason, the linked doc.
   - **tags** — suggest 2–4 tags, reusing existing ones where possible.
   - **last_verified** — today's date.

4. **Validate before writing.**
   - `id` is unique in the file
   - `title`, `when`, `commands`, `notes`, `tags`, `last_verified` all present
   - `last_verified` is today in `YYYY-MM-DD` format
   - `commands` contains no obvious secrets (grep for `shpat_`, `sk-`, `ghp_`, real tokens)

5. **Append, don't rewrite.** Read the file, parse, append the new dict to `use_cases`, write it back. Preserve the ordering and formatting of existing entries — do not re-sort, re-indent, or re-flow unrelated items. If the YAML library round-trips poorly, prefer a targeted text append over a full re-serialize.

6. **Confirm.** Print the appended entry back to the user (just the new block), then suggest: *"Run `/git-commit` in ../earlbear-clis to land this — or batch it with your next commit."*

## Anti-patterns

Do not capture:

- **Single-command "how to use --format json" entries.** That is CLI help surface, not a use case.
- **Hypotheticals.** If you didn't actually run the commands this session, don't file it. Or if you must (e.g., documenting a known pattern from a teammate), set `last_verified` to the real date it was last run and say so in `notes`.
- **Fabricated `last_verified` dates.** Today's date only, and only if you actually verified it today.
- **Secrets, real issue keys that leak plans, customer emails, or draft-in-progress content.** Sanitize to placeholders.
- **Entries that duplicate an existing `id` or are near-identical to an existing use case.** If close, *edit* the existing entry's `notes` / `last_verified` instead of appending.
- **Vague `when` triggers** like "sometimes" or "when working with Jira". Be specific: the agent is going to Ctrl-F this line.

## End-of-skill instruction

Suggest to the user: *"Add `/capture-cli-use-case` to your typical end-of-task rhythm — right before `/git-commit`. The corpus only grows if we feed it."*

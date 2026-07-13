# ebtranscripts

Extract Claude Code session telemetry, sanitize it at the edge, and publish sanitized
transcripts. Powers the metrics dashboard and transcript viewer at workflow.earlbear.com.

## What it does

- **scan** — discover in-scope sessions under `~/.claude/projects` (deny-by-default:
  only project slugs matched by `[stages]` in `transcripts.toml` are ever opened).
- **extract** — parse each session's JSONL, build normalized records from a safe-field
  allowlist (never raw content), and write them to a staging dir. Incremental via
  byte-offset state.
- **sanitize** — the redaction layer. `--self-test` runs a planted-secret fixture and
  fails closed if any secret survives. Runs automatically before every push/render.
- **push** — idempotent upsert of derived metrics to Supabase (`cc_*` tables), then
  refresh the marts the dashboard reads.
- **sync** — scan → extract → push. The automation entrypoint (`brew services` / cron).
- **status / doctor** — health and coverage checks.

## Secret handling (two independent layers)

1. **Structural first.** Records are *constructed* from an allowlist of safe fields;
   file bodies and full prompts are never staged. Only two bounded, redacted excerpts
   exist (the first prompt and each tool call's coarse summary).
2. **Pattern + entropy redaction** (`sanitizer.py`) over every excerpt — a Gitleaks-style
   named-format pass (JWTs, provider/cloud/Stripe/Shopify/Slack keys, PEM blocks, bearer
   tokens, URL userinfo, emails) plus a Shannon-entropy sweep for unknown high-randomness
   tokens.
3. **Independent verification** (`verify.py`) — if `gitleaks` is installed, an independent
   scan of the redacted output must also come back clean before anything is pushed or
   published. This mirrors the 2026 best practice of pairing a fast rule scanner with a
   separate verifier.

## Develop

```bash
make venv install     # create .venv and install with dev deps
make check            # ruff + pytest + the runtime sanitizer self-test
```

Config lives in `~/.config/earlbear/transcripts.toml` (consent gate, stage mapping,
allowlist, redaction extras, pricing) and credentials in `~/.config/earlbear/.env`
(`SUPABASE_PROJECT_URL`, `SUPABASE_SERVICE_ROLE_KEY`).

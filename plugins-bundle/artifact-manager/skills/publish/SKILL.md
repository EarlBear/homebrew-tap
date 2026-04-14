# Publish to GitHub Pages

> **Context:** This skill manages the full publish workflow for `dist/public/` to the `gh-pages` branch of the sibling `../earlbear` checkout. earlbear-sites owns the build pipeline, but the live URL stays at `earlbear.github.io/landing/` — so `make publish` uses a git worktree inside `../earlbear` to force-push from there.

## When to trigger

User says things like:
- "publish", "deploy", "push to gh-pages"
- "let's publish the site"
- "make it live"
- "update the hosted site"
- "ready to publish?"

## The cross-repo publish model

```
earlbear-sites/           ← you are here. Owns the build.
  dist/public/            ← built by `make dist`
  Makefile                ← has `publish` target
         │
         │ make publish
         ▼
earlbear/                 ← sibling checkout. Owns the git remote.
  .gh-pages-worktree/     ← temporary worktree created by publish
         │
         │ git push --force origin gh-pages
         ▼
earlbear.github.io/landing/   ← live site
```

`make publish` in earlbear-sites:
1. Builds `dist/public/` (via `make dist`)
2. Validates everything is encrypted (via `make dist-validate`)
3. Sanity-checks `../earlbear` is a clean git repo with no uncommitted changes
4. Creates a worktree at `../earlbear/.gh-pages-worktree` checked out to `gh-pages`
5. Copies `dist/public/` contents into the worktree
6. Commits and force-pushes from inside the worktree (so the push uses earlbear's remote)
7. Removes the worktree

## When the sibling path is non-standard

Override the path via `EARLBEAR_REPO=`:

```bash
make publish EARLBEAR_REPO=/absolute/path/to/earlbear
```

Default is `../earlbear`.

## Workflow

Track all steps as tasks using TaskCreate/TaskUpdate.

### Step 1: Check prerequisites

Verify before proceeding:

1. **Sibling earlbear exists**: Check `test -d ../earlbear/.git` (or the overridden `EARLBEAR_REPO`). If missing, stop and tell the user to clone it or set `EARLBEAR_REPO=`.

2. **Sibling earlbear is clean**: `cd ../earlbear && git status --short`. Must be empty. If not, tell the user to commit or stash first — the publish worktree step will fail on a dirty tree.

3. **dist/public/ exists**: If not, plan to run `make dist` in Step 2.

4. **StatiCrypt image built**: `docker image inspect earlbear-staticrypt`. If missing, run `make dist-staticrypt-build`.

5. **`.env` has `STATICRYPT_PASSWORD`**: `grep STATICRYPT_PASSWORD .env`. If missing or empty, generate with `./scripts/generate-password.sh --write`. Check strength with `./scripts/generate-password.sh --check`.

6. **earlbear-sites working tree clean**: `git status`. Warn if uncommitted changes exist — they won't be published, but the user should know the publish reflects only what's committed AND built.

### Step 2: Build `dist/public/`

```bash
make dist
```

This runs: `dist-collect` → `dist-index` → `dist-encrypt`.

### Step 3: Validate encryption

```bash
make dist-validate
```

Checks:
- `.nojekyll` exists
- `index.html` is NOT encrypted
- All other HTML files ARE encrypted
- No non-HTML files are exposed in encrypted directories
- Reports file counts and total size

**If validation fails, STOP.** Do not proceed. Fix the issue first.

### Step 4: Preview locally

```bash
make dist-preview
```

Opens `dist/public/index.html` in the browser. Ask the user to confirm:
- The catalog page loads correctly
- Cards show the right artifacts (wireframes and claude artifacts)
- Clicking an encrypted link shows the StatiCrypt password prompt
- After entering the password, content renders correctly

**Wait for explicit user confirmation before proceeding.**

### Step 5: Publish

Only after the user confirms the preview looks good:

```bash
! make publish
```

Use the `!` prefix so the user runs it in their own shell — the target is interactive (requires pressing Enter to confirm the force-push).

`make publish` will:
1. Run `make dist` + `make dist-validate` again (safety net)
2. Verify `../earlbear` is a git repo with no uncommitted changes
3. Print a summary: HTML count, encrypted count, total size, target remote URL
4. Prompt: "Press Enter to continue, Ctrl-C to abort"
5. Create a worktree `../earlbear/.gh-pages-worktree` on the `gh-pages` branch
6. Replace its contents with `dist/public/`
7. Commit with message: `publish from earlbear-sites <UTC timestamp>`
8. Force-push to `origin gh-pages` from within the worktree
9. Clean up the worktree

### Step 6: Verify deployment

After publishing, check:

1. The live site: `https://earlbear.github.io/landing/`
2. If GitHub Pages isn't configured yet on the earlbear repo, tell the user to enable it: Settings → Pages → Source: Deploy from branch → `gh-pages` / `/ (root)`.
3. Propagation typically takes 1–5 minutes.

## Quick reference

```bash
make dist                 # Build everything (collect + index + encrypt)
make dist-validate        # Verify encryption is correct
make dist-preview         # Open in browser for manual review
make publish              # Cross-repo force-push to earlbear gh-pages (interactive)
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `../earlbear is not a git repo` | Clone earlbear as a sibling, or override with `EARLBEAR_REPO=/path` |
| `../earlbear has uncommitted changes` | In earlbear, commit or stash first (`cd ../earlbear && git status`) |
| `STATICRYPT_PASSWORD not set` | Run `./scripts/generate-password.sh --write` to generate and save one |
| Validation fails: HTML not encrypted | Run `make dist-encrypt` (or full `make dist`) |
| Validation fails: `index.html` encrypted | Rebuild: `rm -rf dist/ && make dist` |
| `earlbear-staticrypt` image not found | Run `make dist-staticrypt-build` |
| worktree add fails | The worktree directory may be stale: `cd ../earlbear && git worktree remove --force .gh-pages-worktree` and retry |
| gh-pages push fails | Check `cd ../earlbear && git remote -v` points to a GitHub repo you have push access to |
| Site not loading after publish | Enable GitHub Pages in earlbear repo: Settings → Pages → Source: `gh-pages` branch |

## Important notes

- **earlbear-sites is the ONLY publisher.** Do not run `make publish` from `../earlbear` — that's the old pipeline and no longer exists after the migration.
- **The live URL is stable.** Even though the build lives here, the published URL is `earlbear.github.io/landing/` because the push targets earlbear's remote.

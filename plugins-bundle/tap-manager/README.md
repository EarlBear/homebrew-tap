# tap-manager

Homebrew tap maintenance skills for `bytesofpurpose/earlbear`.

## Skills

| Skill | Purpose |
|---|---|
| `/introduce` | Overview of the tap and what this plugin does |
| `/add-formula` | Scaffold a new formula (Docker-wrapped or Python venv) |
| `/bump-version` | Bump all formula versions to a new release |
| `/validate-tap` | Run the 4-tier validation suite (style, audit, docker, smoke) |

## Tap structure

```
earlbear-homebrew/
├── Formula/         # 7 Homebrew formulas
├── src/             # CLI sources (synced via make sync-sources)
├── plugins-bundle/  # marketplace snapshot
├── scripts/         # setup-env.sh, install-plugins.sh
├── validation/      # audit, docker, smoke, tart validation
├── devcontainer/    # Ubuntu+Linuxbrew cowork container
└── Makefile         # entry point for all operations
```

## Repo

`~/Workspace/git/earlbear-homebrew`

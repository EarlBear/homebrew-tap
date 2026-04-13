# ebdeck — EarlBear deck CLI

A thin Python CLI (typer-based) that wraps the existing deck generation
toolchain living in `deck-cli/docker-compose.yaml`. Replaces the hand-written
`Makefile` entry point that used to drive marp / slidev / python-pptx /
thumbnails / gallery / figma directly.

## Deviation from other CLIs in this repo

Unlike `jira-cli` (`ebjira`), `gdocs-cli` (`ebdocs`), and `shopify-cli`
(`ebshop`), **ebdeck is NOT itself Docker-wrapped**. It runs on the host and
shells out to `docker compose` against this directory's `docker-compose.yaml`
to spin up marp/slidev/python-pptx/figma/thumbnails/gallery containers.

This is intentional. The alternative — running ebdeck inside Docker and
having it exec `docker compose` against the outer compose file — is
docker-in-docker, which requires bind-mounting the docker socket and causes
volume-mount path confusion (the inner container sees host paths via the
socket, not the paths inside its own filesystem). For an orchestrator whose
entire job is to launch other containers, running on the host is simpler.

Practical consequence: you get `ebdeck` on your PATH by pointing at the
shell wrapper under `deck-cli/bin/ebdeck`. That wrapper auto-bootstraps a
hidden `deck-cli/.venv/` on first invocation (editable-install of this
package, ~10s one-time), then execs the real Python entry point on every
call after. The heavy-lifting toolchains (marp, slidev, python-pptx, figma,
thumbnails, gallery) still run inside the same Docker images they always
have.

## Install

Either add `deck-cli/bin` to your PATH:

```bash
export PATH="$HOME/Workspace/git/earlbear-clis/deck-cli/bin:$PATH"
ebdeck --help
```

Or symlink the wrapper into a directory already on your PATH:

```bash
ln -s "$PWD/deck-cli/bin/ebdeck" ~/bin/ebdeck   # or /usr/local/bin/ebdeck
ebdeck --help
```

The first `ebdeck` invocation bootstraps a hidden `deck-cli/.venv/` and
editable-installs the package into it (~10s). Every invocation after is
instant.

Or, via the per-package Makefile:

```bash
make install
make help
```

## Subcommand groups

| Group           | Maps to (old Makefile target)                  |
|-----------------|------------------------------------------------|
| `build images`  | `make build` / `make rebuild --no-cache`       |
| `build marp`    | `make marp`                                    |
| `build marp-pdf` / `build marp-pptx` | `make marp-pdf` / `make marp-pptx` |
| `build slidev` / `build slidev-pptx` | `make slidev` / `make slidev-pptx` |
| `build pptx`    | `make pptx`                                    |
| `build all`     | `make all`                                     |
| `build dist`    | `make dist`                                    |
| `build clean`   | `make clean` (`--all` adds `make clean-all`)   |
| `permutations`  | `make permutations`                            |
| `gallery thumbnails` / `gallery build` / `gallery open` | `make thumbnails` / `gallery` / `gallery-open` |
| `package`       | `make package`                                 |
| `figma install` / `figma build` / `figma build-local` / `figma watch` | `make figma-install` / `figma-build` / `figma-build-local` / `figma-watch` |
| `publish`       | NEW — copies `dist/output/` + `dist/gallery.html` into a sibling earlbear-sites checkout |

## Defaults

Match the previous Makefile:

- `--content` / `-c` defaults to `investor-pitch.yaml`
- `--brand` / `-b` defaults to `brand.yaml`
- `--max-parallel` / `-j` defaults to `6` (permutations)

## Publishing into earlbear-sites

```bash
ebdeck permutations --content investor-pitch.yaml
ebdeck gallery build
ebdeck publish --site ../../earlbear-sites --name investor-pitch
```

This copies everything under `dist/output/` plus `dist/gallery.html` into
`<site>/decks/investor-pitch/`. Commit from inside the earlbear-sites repo
as usual. earlbear-sites's `dist-collect` / `scripts/generate-index.sh`
auto-discover every `decks/*/` directory and emit a card for each deck —
no per-deck wiring required on the earlbear-sites side.

## Locating the deck-cli root

ebdeck finds `docker-compose.yaml` by:

1. Reading `$EBDECK_ROOT` if set
2. Walking up from `$PWD` looking for `docker-compose.yaml` next to `brands/`
3. Falling back to the package's source tree (editable install)

Run ebdeck from anywhere inside the deck-cli checkout and it Just Works.

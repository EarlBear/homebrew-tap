# The plugins now come from the GitHub marketplace, not a copy in this tap

**Decided 2026-11-16 (Omar):** the Mac installer stays, and the `earlbear-plugins` formula
installs the plugins from the real marketplace instead of from a copy kept here.

## What was tried

`make sync-sources` copied `../earlbear-claude-plugin-marketplace/plugins/` into
`plugins-bundle/`. The formula shipped that folder inside the Homebrew install as
`libexec/marketplace` and `install-plugins.sh` registered it as a local marketplace.

## What the evidence showed

- **The copy went stale.** The old script installed a fixed list of 9 plugins while the
  marketplace has 21, and the copy only changed when someone re-ran the sync and cut a release.
- **The released copy installed nothing.** In v1.1.0, `plugins-bundle/.claude-plugin/marketplace.json`
  lists each plugin at `./plugins/<name>`, but the copy puts the plugins at the top level. Every
  `claude plugin install` from it failed with "Source path does not exist".
- **The copy name clashed.** It was registered as `earlbear-claude-plugins`, the same name as the
  real marketplace, so `claude plugin marketplace add EarlBear/marketplace-claude-plugins` fails
  on a Mac that still has the old copy registered.

## What replaced it

- `scripts/install-plugins.sh` adds the GitHub marketplace and installs every plugin it lists.
  It reads the names from the marketplace's own `.claude-plugin/marketplace.json` once the
  marketplace is added, so no list in this repo can go stale. If that file is missing or has
  no plugins, it stops with an error (exit 1); if some plugins fail, it says which (exit 2).
  If the old Homebrew copy (or a folder that no longer exists) is registered under that name, it
  removes it first. A developer's own checkout registered under the name is left alone.
- The formula installs only that script; post_install runs it with no arguments.
- The parts the Claude Desktop cowork VM needs and the marketplace does not ship (the `bin/<cli>`
  shims, the old `*-linux` builds and the `wheels/<cli>-bundle.zip` files) moved to
  `cowork-payload/<plugin>/`. The copied skills, READMEs and plugin.json files were deleted.

## Things to know

- The marketplace repo is private, so a Mac needs GitHub access to EarlBear to install.
- Removing a registered marketplace also uninstalls its plugins and deletes their saved options.
  That only happens when the old Homebrew copy is replaced, and that copy installed no plugins.
- Adding the marketplace tries SSH first and falls back to HTTPS, so a Mac with `gh auth
  setup-git` but no SSH key works too.
- The formula's `url` points at a release tag, so the new script reaches users only at the next
  release. Until then the new formula runs the v1.1.0 script, which fails without a path and
  Homebrew reports it as a warning; no worse than v1.1.0, which installed no plugins either.

# The smoke test stopped counting exit 2 as a pass

## What it did before

`validation/smoke/smoke-test.sh` (Tier 4, `make validate-smoke`) ran a hand-typed list of
commands, some of them real calls (`ebjira issue list`, `ebdocs doc list`). Any exit 2 counted as
a pass, on the idea that exit 2 meant "no settings file yet" (CONFIG_MISSING).

## Why that had to change

- **Exit 2 is also a usage error.** "No such option: --help" exits 2, so a renamed or broken
  command passed. Before the planned company-name change, a renamed command must make this test
  fail, and it couldn't.
- **It touched real things.** `ebjira issue list` read the real settings file and called live
  Jira. `earlbear-setup --help` started the set-up wizard, which ran `touch` on the real
  `~/.config/earlbear/.env`.
- **The list was typed by hand**, so a new or renamed command had to be added in two places.

## What replaced it

- Formulas come from `Formula/*.rb` and commands from each installed formula's `bin/`. Nothing
  is typed by name except the extra `ebtranscripts sanitize --self-test` check.
- Each command must answer `--help` with **exit 0** and print **its own name as a whole word**
  on standard output (a whole word, so a `shop` whose help still says `ebshop` fails).
- Every run is boxed in: empty standard input, a scratch settings folder with an empty `.env`
  (`EARLBEAR_CONFIG_DIR`), a stand-in `security` that never finds a Keychain entry, and a time
  limit that kills the command's whole process group (a plain alarm doesn't stop `docker run`).
- A command is put down to "Docker is off" only when its formula needs Docker **and** the
  command itself runs docker. ebdeck's formula lists Docker but its `--help` is plain Python.

## Still open (found by the new test, not fixed here)

- `agent-cli` exits 1 when `.env` is missing, before it reads `--help`, and reads the Keychain
  first. The fix belongs in its source repo (EarlBear/claude-agent-env `bin/agent-cli`), then a
  sync. `src/` is not hand-edited here.
- `ebdeck` on one Mac had a broken Python environment ("bad interpreter"); `brew reinstall ebdeck`.

## Don't bring back

Counting exit 2 as a pass in this tier. Tier 5c (cowork-sim) still treats exit 2 as
CONFIG_MISSING on purpose; that is a different check and is left as it is.

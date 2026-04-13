# /add-formula

Scaffold a new Homebrew formula for the `bytesofpurpose/earlbear` tap.

## Usage

```
/add-formula <name> [--type docker|python-venv|script]
```

If `--type` is omitted, ask the user which type applies.

## Formula types

### `docker` — Docker-wrapped CLI
Use when the CLI runs inside a Docker container (ebjira, ebdocs, ebshop pattern).

Structure:
- `install` block: copies `src/<name>/*` + `wrappers/<name>/wrapper.sh` into `libexec/<name>/`, symlinks wrapper to `bin/<name>`
- `post_install` block: `docker build -t <name> libexec/<name>` if Docker available, else `opoo`
- `test` block: assert binary is executable, run a known-failing command and assert `CONFIG_MISSING`

Must create:
1. `Formula/<name>.rb` — from docker template below
2. `wrappers/<name>/wrapper.sh` — reads `~/.config/earlbear/.env`, runs `docker run --rm -v ... <name> <args>`

### `python-venv` — Python virtualenv formula
Use when the CLI is a Python package using `Language::Python::Virtualenv` (ebdeck pattern).

Structure:
- `include Language::Python::Virtualenv`
- `depends_on "python@3.11"` + `depends_on "libyaml"`
- Resources for: hatchling + 4 deps, all runtime deps from `pyproject.toml`
- `install` block: `libexec.install "src/<name>"`, `virtualenv_create(libexec/"venv", "python3.11")`, `venv.pip_install resources`, `venv.pip_install_and_link libexec/"<name>"`
- `test` block: `assert_match "<name>", shell_output("#{bin}/<name> --help")`

Must create:
1. `Formula/<name>.rb` — from python-venv template, with correct resource list from `src/<name>/pyproject.toml`

### `script` — Shell script formula
Use for simple shell script wrappers (agent-cli, earlbear-plugins pattern).

Structure:
- `install` block: install script files, chmod +x, symlink to bin
- No `post_install`

## Templates

### Docker formula template

```ruby
class <ClassName> < Formula
  desc "EarlBear <Name> CLI - Docker-wrapped <name>"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"<name>").install Dir["src/<name>/*"]
    (libexec/"<name>").install "wrappers/<name>/wrapper.sh"
    bin.install_symlink libexec/"<name>/wrapper.sh" => "<name>"
  end

  def post_install
    if which("docker")
      system "docker", "build", "-t", "<name>", "-q", libexec/"<name>"
    else
      opoo "docker not found - run `docker build -t <name> #{libexec}/<name>` after installing Docker"
    end
  end

  test do
    assert_predicate bin/"<name>", :executable?
    output = shell_output("#{bin}/<name> <subcommand> 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
```

### Python venv formula template

```ruby
class <ClassName> < Formula
  include Language::Python::Virtualenv

  desc "EarlBear <Name> - <description>"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "libyaml"
  depends_on "python@3.11"

  # hatchling build backend (required to build from source without network)
  resource "hatchling" do
    url "https://files.pythonhosted.org/packages/cf/9c/b4cfe330cd4f49cff17fd771154730555fa4123beb7f292cf0098b4e6c20/hatchling-1.29.0.tar.gz"
    sha256 "793c31816d952cee405b83488ce001c719f325d9cda69f1fc4cd750527640ea6"
  end

  resource "packaging" do
    url "https://files.pythonhosted.org/packages/65/ee/299d360cdc32edc7d2cf530f3accf79c4fca01e96ffc950d8a52213bd8e4/packaging-26.0.tar.gz"
    sha256 "00243ae351a257117b6a241061796684b084ed1c516a08c48a3f7e147a9d80b4"
  end

  resource "pathspec" do
    url "https://files.pythonhosted.org/packages/fa/36/e27608899f9b8d4dff0617b2d9ab17ca5608956ca44461ac14ac48b44015/pathspec-1.0.4.tar.gz"
    sha256 "0210e2ae8a21a9137c0d470578cb0e595af87edaa6ebf12ff176f14a02e0e645"
  end

  resource "pluggy" do
    url "https://files.pythonhosted.org/packages/f9/e2/3e91f31a7d2b083fe6ef3fa267035b518369d9511ffab804f839851d2779/pluggy-1.6.0.tar.gz"
    sha256 "7dcc130b76258d33b90f61b658791dede3486c3e6bfb003ee5c9bfb396dd22f3"
  end

  resource "trove-classifiers" do
    url "https://files.pythonhosted.org/packages/d8/43/7935f8ea93fcb6680bc10a6fdbf534075c198eeead59150dd5ed68449642/trove_classifiers-2026.1.14.14.tar.gz"
    sha256 "00492545a1402b09d4858605ba190ea33243d361e2b01c9c296ce06b5c3325f3"
  end

  # --- runtime deps from pyproject.toml below ---

  def install
    libexec.install "src/<name>"
    venv = virtualenv_create(libexec/"venv", "python3.11")
    venv.pip_install resources
    venv.pip_install_and_link libexec/"<name>"
  end

  test do
    assert_match "<name>", shell_output("#{bin}/<name> --help")
  end
end
```

## Steps to implement

1. Read `src/<name>/pyproject.toml` (for python-venv) to get the full dependency list
2. For each dep: look up the latest stable sdist URL + sha256 on PyPI (`https://pypi.org/pypi/<pkg>/json`)
3. Write `Formula/<name>.rb` from the appropriate template
4. For docker type: write `wrappers/<name>/wrapper.sh`
5. Run `make validate-audit` to check for Ruby/style issues
6. Run `make validate-docker` to verify install works end-to-end
7. Update `README.md` formula status table
8. Commit: `feat(<name>): add Homebrew formula`

## Key gotchas (learned from ebdeck)

- `virtualenv_create` second arg must be the **binary name** (`python3.11`), NOT the formula name (`python@3.11`)
- `pip_install_and_link` has no network access in Docker — ALL deps (including hatchling + its deps) must be declared as `resource` blocks
- `typer >= 0.9` requires `typing-extensions` at import time — add it as a resource even if not in `dependencies` (it's in `requires-python`)
- Formula `url` and `sha256` must match the actual GitHub release tarball

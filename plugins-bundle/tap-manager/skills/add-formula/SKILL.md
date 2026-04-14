# /add-formula

Scaffold a new Homebrew formula in `earlbear-homebrew/Formula/`.

## Usage

```
/add-formula NAME=ebnewtool TYPE=docker-wrapped
/add-formula NAME=ebpython  TYPE=python-venv
```

## Formula types

### Docker-wrapped (ebjira/ebdocs/ebshop pattern)

1. **Create source directory** in sibling repo, ensure it has:
   - `Dockerfile` — the CLI image
   - `wrapper.sh` — calls `docker run --rm --env-file $ENV_FILE image args`

2. **Add rsync rule** to `earlbear-homebrew/Makefile` `sync-sources` target:
   ```makefile
   rsync -a --delete \
       --exclude='tests/' --exclude='.venv/' --exclude='__pycache__/' \
       --exclude='*.pyc' --exclude='dist/' \
       $(EARLBEAR_ROOT)/earlbear-clis/newtool-cli/ src/ebnewtool/
   ```

3. **Run sync**:
   ```bash
   make sync-sources
   ```

4. **Scaffold formula** at `Formula/ebnewtool.rb`:
   ```ruby
   class Ebnewtool < Formula
     desc "EarlBear NewTool CLI - Docker-wrapped ebnewtool"
     homepage "https://github.com/EarlBear/homebrew-tap"
     url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.0.0.tar.gz"
     sha256 "0000000000000000000000000000000000000000000000000000000000000000"
     license "MIT"

     depends_on "docker"

     def install
       (libexec/"ebnewtool").install Dir["src/ebnewtool/*"]
       bin.install_symlink libexec/"ebnewtool/wrapper.sh" => "ebnewtool"
     end

     def post_install
       if which("docker")
         system "docker", "build", "-t", "ebnewtool", "-q", libexec/"ebnewtool"
       else
         opoo "docker not found - run `docker build -t ebnewtool #{libexec}/ebnewtool` after installing Docker"
       end
     end

     test do
       assert_predicate bin/"ebnewtool", :executable?
       output = shell_output("#{bin}/ebnewtool --help 2>&1", 2)
       assert_match "CONFIG_MISSING", output
     end
   end
   ```

5. **Adapt wrapper.sh** — ensure it uses `EARLBEAR_CONFIG_DIR` pattern:
   ```bash
   ENV_FILE="${EARLBEAR_CONFIG_DIR:-$HOME/.config/earlbear}/.env"
   ```

### Python venv (ebdeck pattern)

1. Ensure the CLI has a `setup.py` or `pyproject.toml`
2. Scaffold formula with `include Language::Python::Virtualenv`
3. Run `brew update-python-resources earlbear/tap/ebnewtool` to populate resource sha256s
4. Install block:
   ```ruby
   def install
     libexec.install "src/ebnewtool"
     venv = virtualenv_create(libexec/"venv", "python@3.11")
     venv.pip_install resources
     venv.pip_install_and_link libexec/"ebnewtool"
   end
   ```

## After scaffolding

1. Add to `earlbear.rb` `depends_on` list (alphabetically)
2. Run Tier 1: `brew style Formula/*.rb && brew audit --skip-style ...`
3. Run Tier 2: `make validate-docker`
4. Commit: `git add Formula/ src/ Makefile && git commit -m "feat: add ebnewtool formula"`

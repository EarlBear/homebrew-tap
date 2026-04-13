# Tart macOS VM Validation

Full clean-room `brew install` test using a macOS VM. Requires Apple Silicon.

## One-time setup

```bash
brew install cirruslabs/cli/tart
tart pull ghcr.io/cirruslabs/macos-sequoia-base:latest
```

## Run

```bash
make validate-vm
# or directly:
bash validation/tart/tart-test.sh
```

## What it does

1. Clones the base macOS image into a temp VM
2. Starts the VM
3. Installs Homebrew
4. Taps `bytesofpurpose/earlbear`
5. Runs `brew install earlbear`
6. Runs smoke tests
7. Destroys the VM

Takes ~15 minutes on Apple Silicon.

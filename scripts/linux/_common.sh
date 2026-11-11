#!/usr/bin/env bash
# Shared helpers for the Linux launchers. Source it, do not run it:
#   source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
#
# Provides:
#   ROOT            absolute path of the repository root
#   require_uv      exits with a helpful message when uv is not installed
#   cli [args...]   runs `audio-cleanup [args...]` inside the project environment

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# uv's default install location (the installer puts it here).
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

require_uv() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Run scripts/linux/setup.sh first." >&2
    exit 1
  fi
}

# `--extra deepfilternet` makes sure the neural denoiser is installed (a no-op once it is).
cli() {
  uv run --project "$ROOT" --extra deepfilternet audio-cleanup "$@"
}

#!/usr/bin/env bash
# One-time setup on Linux: uv + Python 3.11 + PyTorch/DeepFilterNet, and a check for ffmpeg.
# Safe to run again at any time.
#
#   scripts/linux/setup.sh                    # install everything except ffmpeg
#   scripts/linux/setup.sh --install-ffmpeg   # also install ffmpeg with your package manager (sudo)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
cd "$ROOT"

INSTALL_FFMPEG=0
for arg in "$@"; do
  case "$arg" in
    --install-ffmpeg) INSTALL_FFMPEG=1 ;;
    -h|--help) sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Prints the command that installs ffmpeg on this distribution (empty if unknown).
ffmpeg_install_cmd() {
  if   command -v apt-get >/dev/null 2>&1; then echo "sudo apt-get update && sudo apt-get install -y ffmpeg"
  elif command -v dnf     >/dev/null 2>&1; then echo "sudo dnf install -y ffmpeg-free   # or ffmpeg from RPM Fusion"
  elif command -v pacman  >/dev/null 2>&1; then echo "sudo pacman -S --needed ffmpeg"
  elif command -v zypper  >/dev/null 2>&1; then echo "sudo zypper install ffmpeg"
  elif command -v apk     >/dev/null 2>&1; then echo "sudo apk add ffmpeg"
  fi
}

echo "=== audio-cleanup - setup ==="
echo

# ---- 1/4 uv ----------------------------------------------------------------
if command -v uv >/dev/null 2>&1; then
  echo "[1/4] uv found."
else
  echo "[1/4] Installing uv..."
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "ERROR: curl or wget is needed to install uv." >&2
    exit 1
  fi
fi
require_uv
uv --version
echo

# ---- 2/4 ffmpeg ------------------------------------------------------------
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  echo "[2/4] ffmpeg found."
else
  cmd="$(ffmpeg_install_cmd)"
  if [ "$INSTALL_FFMPEG" = 1 ] && [ -n "$cmd" ]; then
    echo "[2/4] Installing ffmpeg: $cmd"
    bash -c "${cmd%%#*}"
  else
    echo "[2/4] ffmpeg NOT found. Install it with:" >&2
    echo "        ${cmd:-your package manager (package name: ffmpeg)}" >&2
    echo "      or re-run this script with --install-ffmpeg." >&2
    exit 1
  fi
fi
echo

# ---- 3/4 Python environment --------------------------------------------------
echo "[3/4] Creating the environment: Python 3.11 + PyTorch + DeepFilterNet"
echo "      (about 3 GB the first time, it can take a while)..."
uv sync --extra deepfilternet
echo

# ---- 4/4 check ---------------------------------------------------------------
echo "[4/4] Checking the installation..."
cli doctor
echo
echo "Setup complete. Try: scripts/linux/clean.sh /path/to/recording.mp4"

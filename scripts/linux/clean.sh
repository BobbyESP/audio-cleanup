#!/usr/bin/env bash
# Clean the audio of a video.
#   scripts/linux/clean.sh /path/to/recording.mp4 [--atten 24] [--lufs -14] [--engine nr] ...
# Run "scripts/linux/clean.sh --help" for every option.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_uv

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 /path/to/recording.mp4 [--atten 24] [--lufs -14] ..." >&2
  exit 1
fi

cli clean "$@"

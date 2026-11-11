#!/usr/bin/env bash
# Fix the wrong duration of an already processed video (bogus OBS chapter markers).
# Nothing is re-encoded; it takes a few seconds.
#   scripts/linux/fix-duration.sh /path/to/recording_clean.mp4 [--drop]
# The result is written next to the original as <name>_fixed.mp4.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_uv

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 /path/to/recording_clean.mp4 [--drop]" >&2
  exit 1
fi

cli fix-chapters "$@"

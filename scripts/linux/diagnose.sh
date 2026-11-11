#!/usr/bin/env bash
# Report durations, start times and timestamp gaps of recordings (can take a minute or two).
#   scripts/linux/diagnose.sh a.mp4 b.mp4   # analyse the given files
#   scripts/linux/diagnose.sh                # analyse every .mp4 in the current directory
# The report is also saved as diagnose_report.txt in the current directory.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_uv

echo "Analysing timestamps (can take a minute or two)..."
cli diagnose -o diagnose_report.txt "$@"

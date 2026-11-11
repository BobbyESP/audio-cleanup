"""Timestamp diagnostics: durations, start times and gaps in each stream of a recording.

Useful to understand why a player shows a wrong duration or why audio drifts from video.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from pathlib import Path

from audio_cleanup import ffmpeg

_PROBE_ENTRIES = (
    "format=duration,start_time,size,bit_rate:"
    "stream=index,codec_type,codec_name,start_time,duration,nb_frames,time_base,"
    "avg_frame_rate,r_frame_rate,sample_rate,channels"
)

#: A step between packets is reported as a gap above max(MIN_GAP_S, GAP_FACTOR * median step).
MIN_GAP_S = 0.5
GAP_FACTOR = 20
MAX_GAPS_LISTED = 20


def summarize_packets(label: str, pts: list[float]) -> str:
    """Describe the packet timestamps (seconds) of one stream, listing any large gaps."""
    if not pts:
        return f"  {label}: no packets\n"
    srt = sorted(pts)
    steps = [b - a for a, b in itertools.pairwise(srt)]
    median = sorted(steps)[len(steps) // 2] if steps else 0.0
    gaps = [(srt[i], s) for i, s in enumerate(steps) if s > max(MIN_GAP_S, GAP_FACTOR * median)]
    backward = sum(1 for a, b in itertools.pairwise(pts) if b < a - 1.0)
    span = srt[-1] - srt[0]
    report = (
        f"  {label}: {len(pts)} packets, first pts {srt[0]:.3f}s, last pts {srt[-1]:.3f}s, "
        f"span {span:.1f}s ({span / 3600:.3f} h), median step {median * 1000:.2f} ms, "
        f"expected span from count {len(pts) * median:.1f}s\n"
        f"  {label}: {len(gaps)} gaps > max({MIN_GAP_S} s, {GAP_FACTOR}x median), "
        f"{backward} big backward jumps\n"
    )
    for t, d in gaps[:MAX_GAPS_LISTED]:
        report += f"     gap of {d:.3f}s at t={t:.3f}s\n"
    return report


def _packet_timestamps(path: Path, stream: str) -> list[float]:
    proc = ffmpeg.run(
        [
            "ffprobe", "-v", "error", "-select_streams", stream,
            "-show_entries", "packet=pts_time,duration_time", "-of", "csv=p=0", path,
        ]
    )  # fmt: skip
    pts: list[float] = []
    for line in proc.stdout.splitlines():
        try:
            pts.append(float(line.split(",")[0]))
        except ValueError:
            continue
    return pts


def diagnose_file(path: Path) -> str:
    """Full text report for one media file."""
    probe = ffmpeg.run(
        ["ffprobe", "-v", "error", "-show_entries", _PROBE_ENTRIES, "-of", "compact", path]
    )
    lines = [
        "=" * 100,
        str(path),
        (probe.stdout + probe.stderr).strip(),
        summarize_packets("v:0", _packet_timestamps(path, "v:0"))
        + summarize_packets("a:0", _packet_timestamps(path, "a:0")),
    ]
    return "\n".join(lines)


def diagnose(paths: Iterable[Path]) -> Iterable[str]:
    """Yield one report per file (lazily, because packet analysis of long files takes a while)."""
    for path in paths:
        yield diagnose_file(path)

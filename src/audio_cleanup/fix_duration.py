"""Repair an already processed video whose duration shows up too long.

This happens when an OBS chapter track has a bogus end. The fix is a stream-copy remux
(a few seconds per GB, nothing is re-encoded) that rewrites the chapters.
"""

from __future__ import annotations

import logging
from pathlib import Path

from audio_cleanup import chapters, ffmpeg
from audio_cleanup.errors import AudioCleanupError

log = logging.getLogger(__name__)


def fix_duration(src: Path, out: Path | None = None, *, drop_chapters: bool = False) -> Path:
    """Remux ``src`` with chapters clamped to the real video length (or removed).

    Returns the path of the written file (default ``<src>_fixed.mp4``).
    """
    ffmpeg.require_tools()
    if not src.is_file():
        raise AudioCleanupError(f"Input file not found: {src}")
    out = out or src.with_name(f"{src.stem}_fixed.mp4")
    if out.resolve() == src.resolve():
        raise AudioCleanupError("The output file must be different from the input file")

    chapters_file = out.with_name(f"{out.stem}_chapters.txt")
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-i", str(src)]
    try:
        use_chapters = not drop_chapters and chapters.write_clamped_chapters(
            src, ffmpeg.probe_video_duration(src), chapters_file
        )
        if use_chapters:
            cmd += ["-f", "ffmetadata", "-i", str(chapters_file), "-map_chapters", "1"]
        else:
            cmd += ["-map_chapters", "-1"]
        cmd += [
            "-map", "0:v", "-map", "0:a", "-map_metadata", "0",
            "-c", "copy", "-movflags", "+faststart", str(out),
        ]  # fmt: skip
        ffmpeg.run(cmd, capture=False)
    finally:
        chapters_file.unlink(missing_ok=True)
    log.info("Done -> %s", out)
    return out

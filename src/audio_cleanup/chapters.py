"""Chapter marker handling.

OBS can write a last chapter that ends far past the end of the recording. Players then
report a much longer duration than the real one (e.g. 1:57:57 for a 59:55 video). We copy the
input's chapters with every end clamped to the real length of the video.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_cleanup import ffmpeg

#: Minimum chapter length (seconds), so a clamped chapter never ends up with zero length.
MIN_CHAPTER_S = 0.001


@dataclass(frozen=True)
class Chapter:
    start_s: float
    end_s: float
    title: str | None = None


def clamp_chapters(raw: list[dict[str, Any]], end_s: float) -> list[Chapter]:
    """Clamp ffprobe chapter dicts to ``end_s``.

    Chapters starting at or after ``end_s`` are dropped. Each remaining chapter ends at the
    earliest of: its own end, the start of the next chapter, and ``end_s``.
    """
    chapters: list[Chapter] = []
    for i, c in enumerate(raw):
        start = float(c["start_time"])
        if start >= end_s:
            continue
        next_start = float(raw[i + 1]["start_time"]) if i + 1 < len(raw) else end_s
        end = max(start + MIN_CHAPTER_S, min(float(c["end_time"]), next_start, end_s))
        chapters.append(Chapter(start, end, c.get("tags", {}).get("title")))
    return chapters


def _escape(value: str) -> str:
    """Escape a value for the ffmetadata format."""
    return "".join("\\" + ch if ch in "=;#\\\n" else ch for ch in str(value))


def render_ffmetadata(chapters: list[Chapter]) -> str:
    """Render chapters as an ffmetadata document (millisecond timebase)."""
    lines = [";FFMETADATA1"]
    for ch in chapters:
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={round(ch.start_s * 1000)}",
            f"END={round(ch.end_s * 1000)}",
        ]
        if ch.title:
            lines.append(f"title={_escape(ch.title)}")
    return "\n".join(lines) + "\n"


def write_clamped_chapters(src: Path, end_s: float, out_txt: Path) -> bool:
    """Write the clamped chapters of ``src`` to ``out_txt``.

    Returns ``False`` (and writes nothing) when the input has no usable chapters.
    """
    chapters = clamp_chapters(ffmpeg.probe_chapters(src), end_s)
    if not chapters:
        return False
    out_txt.write_text(render_ffmetadata(chapters), encoding="utf-8")
    return True

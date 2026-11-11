"""Thin wrappers around the ``ffmpeg`` / ``ffprobe`` command line tools.

All subprocess handling lives here so the rest of the package never builds a shell command
by hand and every failure is reported as an :class:`~audio_cleanup.errors.AudioCleanupError`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from audio_cleanup.constants import SAMPLE_RATE
from audio_cleanup.errors import FFmpegError, ToolNotFoundError

REQUIRED_TOOLS = ("ffmpeg", "ffprobe")

PathLike = str | Path


def require_tools() -> None:
    """Raise :class:`ToolNotFoundError` if ffmpeg or ffprobe are not on PATH."""
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        raise ToolNotFoundError(
            f"{', '.join(missing)} not found on PATH. Install ffmpeg "
            "(see the README, section 'Installing ffmpeg') and open a new terminal."
        )


def run(cmd: Sequence[PathLike], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command and raise :class:`FFmpegError` on a non-zero exit code."""
    args = [str(c) for c in cmd]
    try:
        proc = subprocess.run(args, capture_output=capture, text=True, check=False)
    except FileNotFoundError as exc:
        raise ToolNotFoundError(f"{args[0]} not found on PATH.") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip()[-2000:]
        raise FFmpegError(f"{args[0]} failed with exit code {proc.returncode}.\n{detail}".strip())
    return proc


# ---------------------------------------------------------------------------- ffprobe
def _probe_value(path: PathLike, *extra: str) -> str:
    cmd = ["ffprobe", "-v", "error", *extra, "-of", "default=nw=1:nk=1", path]
    return run(cmd).stdout.strip()


def probe_duration(path: PathLike) -> float:
    """Container duration in seconds."""
    out = _probe_value(path, "-show_entries", "format=duration")
    try:
        return float(out)
    except ValueError as exc:
        raise FFmpegError(f"Could not read the duration of {path}") from exc


def probe_video_duration(path: PathLike) -> float:
    """Duration of the first video stream, falling back to the container duration.

    OBS recordings may carry a bogus container duration (see :mod:`audio_cleanup.chapters`),
    so the video stream is the more trustworthy figure.
    """
    out = _probe_value(path, "-select_streams", "v:0", "-show_entries", "stream=duration")
    try:
        return float(out.splitlines()[0])
    except (IndexError, ValueError):
        return probe_duration(path)


def probe_chapters(path: PathLike) -> list[dict[str, Any]]:
    """Chapters as reported by ``ffprobe -show_chapters`` (empty list when there are none)."""
    cmd = ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", path]
    try:
        return list(json.loads(run(cmd).stdout or "{}").get("chapters", []))
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------- decoding
def decode_args(path: PathLike) -> list[str]:
    """ffmpeg arguments that decode the first audio stream to raw mono float32 on stdout."""
    return [
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-vn",
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ]  # fmt: skip


def read_audio_segment(path: PathLike, start: float, duration: float) -> np.ndarray:
    """Decode ``duration`` seconds starting at ``start`` as mono float32 samples."""
    cmd = [
        "ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration), "-i", str(path),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise FFmpegError(
            f"Could not decode audio from {path}:\n{proc.stderr.decode(errors='replace')[-2000:]}"
        )
    return np.frombuffer(proc.stdout, np.float32)

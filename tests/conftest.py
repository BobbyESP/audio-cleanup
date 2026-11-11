"""Shared fixtures and helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


def ffmpeg(*args: str | Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


@pytest.fixture
def noisy_video(tmp_path: Path) -> Path:
    """A 12 s test video: a 330 Hz "speech-like" tone + 50 Hz mains hum + white noise.

    The tone only starts after 2 s, so the first seconds are hum + noise only and the
    automatic noise profile has something quiet to find.
    """
    video = tmp_path / "noisy.mp4"
    ffmpeg(
        "-f", "lavfi", "-i", "testsrc=size=160x90:rate=25",
        "-f", "lavfi", "-i", "sine=f=330:sample_rate=48000",
        "-f", "lavfi", "-i", "sine=f=50:sample_rate=48000",
        "-f", "lavfi", "-i", "anoisesrc=color=white:amplitude=0.01:sample_rate=48000",
        "-filter_complex",
        "[1:a]volume=0.2:enable='gte(t,2)'[tone];[2:a]volume=0.1[hum];"
        "[tone][hum][3:a]amix=inputs=3:normalize=0[a]",
        "-map", "0:v", "-map", "[a]", "-t", "12", "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", video,
    )  # fmt: skip
    return video

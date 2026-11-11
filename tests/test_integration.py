"""End-to-end tests on a tiny synthetic video. They need ffmpeg and use the lightweight engine."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy.signal as sps

from audio_cleanup import ffmpeg as ff
from audio_cleanup.config import CleanConfig
from audio_cleanup.constants import SAMPLE_RATE
from audio_cleanup.fix_duration import fix_duration
from audio_cleanup.pipeline import clean
from conftest import ffmpeg, requires_ffmpeg

pytestmark = [pytest.mark.integration, requires_ffmpeg]


def band_db(audio: np.ndarray, freq: float, width: float = 3.0) -> float:
    f, p = sps.welch(audio, SAMPLE_RATE, nperseg=2**15)
    sel = (f > freq - width) & (f < freq + width)
    return float(10 * np.log10(p[sel].sum() + 1e-20))


def test_clean_with_nr_engine_removes_hum_and_keeps_video(noisy_video: Path, tmp_path: Path):
    out = tmp_path / "out" / "clean.mp4"
    progress: list[tuple[float, float]] = []
    result = clean(
        CleanConfig(noisy_video, out, engine="nr", chunk_s=5),
        progress=lambda done, total: progress.append((done, total)),
    )

    assert result == out
    assert out.exists()
    assert progress
    assert progress[-1][0] == pytest.approx(progress[-1][1], abs=0.5)
    assert not list(out.parent.glob("audio-cleanup-*")), "temporary directory should be removed"

    # The video stream is copied, not re-encoded.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
         "-of", "json", str(out)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert {"codec_type": "video", "codec_name": "h264"} in json.loads(probe.stdout)["streams"]
    assert ff.probe_duration(out) == pytest.approx(ff.probe_duration(noisy_video), abs=0.3)

    before = ff.read_audio_segment(noisy_video, 3, 8)
    after = ff.read_audio_segment(out, 3, 8)
    # Loudness normalization changes the absolute level, so compare hum relative to the tone.
    hum_to_tone_before = band_db(before, 50) - band_db(before, 330)
    hum_to_tone_after = band_db(after, 50) - band_db(after, 330)
    assert hum_to_tone_after < hum_to_tone_before - 20, "50 Hz hum should be strongly reduced"


def test_audio_only_and_keep_intermediate(noisy_video: Path, tmp_path: Path):
    out = clean(
        CleanConfig(
            noisy_video, engine="nr", audio_only=True, keep_intermediate=True, workdir=tmp_path
        )
    )
    assert out.suffix == ".m4a"
    assert out.exists()
    assert len(list(tmp_path.glob("audio-cleanup-*/denoised.flac"))) == 1


def test_missing_df_falls_back_to_nr(noisy_video: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # make the df engine unavailable
    out = clean(CleanConfig(noisy_video, tmp_path / "o.mp4", engine="df"))
    assert out.exists()


def test_fix_duration_clamps_bogus_chapter(noisy_video: Path, tmp_path: Path):
    meta = tmp_path / "meta.txt"
    meta.write_text(
        ";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=7000000\ntitle=Only chapter\n"
    )
    bogus = tmp_path / "bogus.mp4"
    ffmpeg(
        "-i", noisy_video, "-f", "ffmetadata", "-i", meta, "-map_chapters", "1", "-c", "copy", bogus
    )

    fixed = fix_duration(bogus)
    assert fixed.name == "bogus_fixed.mp4"
    chapters = ff.probe_chapters(fixed)
    assert len(chapters) == 1
    assert float(chapters[0]["end_time"]) <= ff.probe_video_duration(fixed) + 0.1

    dropped = fix_duration(bogus, tmp_path / "nochapters.mp4", drop_chapters=True)
    assert ff.probe_chapters(dropped) == []

"""Speech clarity processing and two-pass EBU R128 loudness normalization (all via ffmpeg)."""

from __future__ import annotations

import json
from pathlib import Path

from audio_cleanup import ffmpeg
from audio_cleanup.constants import SAMPLE_RATE
from audio_cleanup.errors import FFmpegError

#: Clarity chain: -2 dB at 250 Hz (mud), +2.5 dB at 3.5 kHz (presence), a touch of air,
#: gentle compression and a de-esser.
CLARITY_CHAIN = (
    "equalizer=f=250:t=q:w=1:g=-2,"
    "equalizer=f=3500:t=q:w=0.8:g=2.5,"
    "highshelf=f=10000:g=1,"
    "acompressor=threshold=-24dB:ratio=3:attack=8:release=200:makeup=2,"
    "deesser=i=0.3"
)

TRUE_PEAK_DBTP = -1.5
LOUDNESS_RANGE_LU = 9


def _loudnorm(lufs: float) -> str:
    return f"loudnorm=I={lufs}:TP={TRUE_PEAK_DBTP}:LRA={LOUDNESS_RANGE_LU}"


def measure_loudness(audio: Path, lufs: float) -> dict[str, str]:
    """Pass 1: run the clarity chain + loudnorm in analysis mode and return its measurements."""
    graph = f"{CLARITY_CHAIN},{_loudnorm(lufs)}:print_format=json"
    proc = ffmpeg.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af", graph, "-f", "null", "-"]
    )
    text = proc.stderr
    try:
        measured = json.loads(text[text.rfind("{") : text.rfind("}") + 1])
        for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
            measured[key]
    except (json.JSONDecodeError, KeyError) as exc:
        raise FFmpegError("Could not parse the loudnorm measurement from ffmpeg output") from exc
    return dict(measured)


def build_audio_filter(lufs: float, measured: dict[str, str]) -> str:
    """Pass 2 filter graph: clarity chain + linear loudnorm using the pass-1 measurements."""
    loudnorm = (
        f"{_loudnorm(lufs)}"
        f":measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}"
        ":linear=true"
    )
    return f"{CLARITY_CHAIN},{loudnorm},aresample={SAMPLE_RATE}"


def audio_only_command(denoised: Path, audio_filter: str, out: Path) -> list[str]:
    """ffmpeg command that writes a stereo AAC ``.m4a`` from the denoised audio."""
    return [
        "ffmpeg", "-v", "error", "-stats", "-y", "-i", str(denoised), "-af", audio_filter,
        "-ac", "2", "-c:a", "aac", "-b:a", "192k", str(out),
    ]  # fmt: skip


def mux_command(
    source_video: Path,
    denoised: Path,
    audio_filter: str,
    out: Path,
    chapters_file: Path | None,
) -> list[str]:
    """ffmpeg command that remuxes the original video (copied, never re-encoded) with new audio."""
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-i", str(source_video), "-i", str(denoised)]
    if chapters_file is not None:
        cmd += ["-f", "ffmetadata", "-i", str(chapters_file), "-map_chapters", "2"]
    else:
        cmd += ["-map_chapters", "-1"]
    cmd += [
        "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "0", "-af", audio_filter,
        "-ac", "2", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(out),
    ]  # fmt: skip
    return cmd

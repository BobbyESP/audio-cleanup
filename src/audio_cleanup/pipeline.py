"""The cleanup pipeline.

Stages (each is a small function so it can be tested or reused on its own):

1. :func:`estimate_noise`   - find (or read) a noise-only stretch and detect the hum frequency.
2. :func:`select_engine`    - instantiate the requested denoising engine, with fallback.
3. :func:`denoise_to_flac`  - stream decode -> hum filter -> denoise -> FLAC, in overlapping blocks.
4. :func:`finalize`         - clarity EQ, two-pass loudnorm and remux with the original video.

The library never prints: it reports through :mod:`logging` and an optional progress callback.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.signal as sps
from numpy.typing import NDArray

from audio_cleanup import chapters, ffmpeg, postprocess
from audio_cleanup.config import CleanConfig
from audio_cleanup.constants import BYTES_PER_SAMPLE, FALLBACK_ENGINE, SAMPLE_RATE
from audio_cleanup.engines import DenoiseEngine, EngineSettings, create_engine
from audio_cleanup.errors import AudioCleanupError, EngineUnavailableError, FFmpegError
from audio_cleanup.filters import build_hum_filter, detect_hum_frequency
from audio_cleanup.noise_profile import find_quiet_windows

log = logging.getLogger(__name__)

#: ``progress(processed_seconds, total_seconds)``
ProgressCallback = Callable[[float, float], None]

#: Search window (seconds) of the automatic noise profile detection.
NOISE_SEARCH_S = 600
#: Seconds of context kept on each side of a processing block, so block edges are seamless.
OVERLAP_S = 1.0
_PIPE_BUFFER = 10**7


@dataclass(frozen=True)
class NoiseEstimate:
    """Result of :func:`estimate_noise`."""

    hum_hz: float
    hum_filter: NDArray[np.float64]
    #: Noise-only audio after the hum filter, as used by profile-based engines.
    noise: NDArray[np.float32]


# ------------------------------------------------------------------------------ stage 1
def estimate_noise(config: CleanConfig, total_s: float) -> NoiseEstimate:
    """Find a noise-only stretch, detect the mains hum and build the hum filter."""
    if config.noise_range is not None:
        t0, t1 = config.noise_range
        log.info("Noise profile: %.1fs -> %.1fs (manual)", t0, t1)
        raw = ffmpeg.read_audio_segment(config.input, t0, t1 - t0)
        if len(raw) == 0:
            raise AudioCleanupError(f"No audio found in the requested noise range {t0}-{t1}s")
    else:
        profile = find_quiet_windows(config.input, min(NOISE_SEARCH_S, total_s))
        raw = profile.samples
        starts = profile.window_starts_s
        log.info(
            "Automatic noise profile: %d windows of 0.4 s, %.1f dBFS (from %.1fs to %.1fs)",
            len(starts), profile.level_dbfs, starts[0], starts[-1],
        )  # fmt: skip

    f0 = detect_hum_frequency(raw)
    sos = build_hum_filter(f0)
    log.info("Mains hum detected at %.2f Hz -> %d notch filters", f0, len(sos) - 1)
    noise = sps.sosfilt(sos, raw).astype(np.float32)
    return NoiseEstimate(f0, sos, noise)


# ------------------------------------------------------------------------------ stage 2
def select_engine(config: CleanConfig, noise: NDArray[np.float32]) -> DenoiseEngine:
    """Create the requested engine, falling back to ``nr`` if it is not installed."""
    settings = EngineSettings(noise=noise, strength=config.strength, atten_db=config.atten_db)
    try:
        engine = create_engine(config.engine, settings)
    except EngineUnavailableError as exc:
        if config.engine == FALLBACK_ENGINE:
            raise
        log.warning("%s", exc)
        log.warning("Falling back to the %r engine.", FALLBACK_ENGINE)
        engine = create_engine(FALLBACK_ENGINE, settings)
    log.info("Engine: %s", engine.describe())
    return engine


# ------------------------------------------------------------------------------ stage 3
def denoise_to_flac(
    src: Path,
    dst: Path,
    engine: DenoiseEngine,
    hum_filter: NDArray[np.float64],
    *,
    chunk_s: float,
    total_s: float,
    progress: ProgressCallback | None = None,
) -> None:
    """Stream ``src`` through hum filter + ``engine`` into a 24-bit FLAC at ``dst``.

    Audio is processed in blocks of ``chunk_s`` seconds with :data:`OVERLAP_S` of context on
    each side, so memory use is constant no matter how long the recording is.
    """
    chunk = int(chunk_s * SAMPLE_RATE)
    overlap = int(OVERLAP_S * SAMPLE_RATE)

    decoder = subprocess.Popen(
        ffmpeg.decode_args(src), stdout=subprocess.PIPE, bufsize=_PIPE_BUFFER
    )
    encoder = subprocess.Popen(
        [
            "ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-i", "-", "-c:a", "flac", "-sample_fmt", "s32", "-bits_per_raw_sample", "24", str(dst),
        ],
        stdin=subprocess.PIPE,
        bufsize=_PIPE_BUFFER,
    )  # fmt: skip
    assert decoder.stdout is not None and encoder.stdin is not None

    zi = sps.sosfilt_zi(hum_filter) * 0  # filter state carried across reads
    prev_tail = np.zeros(0, np.float32)  # left context (already hum-filtered)
    leftover = b""  # bytes of an incomplete float left by the previous read
    buf = np.zeros(0, np.float32)
    done = 0
    eof = False
    try:
        while True:
            while len(buf) < chunk + overlap and not eof:
                raw = decoder.stdout.read((chunk + overlap - len(buf)) * BYTES_PER_SAMPLE)
                if not raw:
                    eof = True
                    break
                raw = leftover + raw
                usable = len(raw) // BYTES_PER_SAMPLE * BYTES_PER_SAMPLE
                leftover = raw[usable:]
                x = np.frombuffer(raw[:usable], np.float32)
                y, zi = sps.sosfilt(hum_filter, x, zi=zi)
                buf = np.concatenate([buf, y.astype(np.float32)])
            if len(buf) == 0:
                break

            core_len = min(chunk, len(buf))
            block = np.concatenate([prev_tail, buf[: core_len + overlap]])
            out = engine.process(block)
            core = out[len(prev_tail) : len(prev_tail) + core_len]
            encoder.stdin.write(np.clip(core, -1, 1).astype(np.float32).tobytes())

            prev_tail = buf[max(0, core_len - overlap) : core_len]
            buf = buf[core_len:]
            done += core_len
            if progress:
                progress(done / SAMPLE_RATE, total_s)
            if eof and len(buf) == 0:
                break

        encoder.stdin.close()
        if encoder.wait() != 0 or decoder.wait() != 0:
            raise FFmpegError(f"ffmpeg failed while streaming the audio of {src}")
    except BrokenPipeError as exc:
        raise FFmpegError("The ffmpeg FLAC encoder exited unexpectedly (disk full?)") from exc
    finally:
        for proc in (decoder, encoder):
            if proc.poll() is None:
                proc.kill()
                proc.wait()


# ------------------------------------------------------------------------------ stage 4
def finalize(config: CleanConfig, denoised: Path, workdir: Path, out: Path) -> None:
    """Clarity EQ + two-pass loudnorm, then write the audio or remux with the video."""
    log.info("Measuring loudness (pass 1)...")
    measured = postprocess.measure_loudness(denoised, config.lufs)
    audio_filter = postprocess.build_audio_filter(config.lufs, measured)

    log.info("Applying and %s (pass 2)...", "encoding" if config.audio_only else "muxing")
    if config.audio_only:
        cmd = postprocess.audio_only_command(denoised, audio_filter, out)
    else:
        chapters_file = workdir / "chapters.txt"
        has_chapters = chapters.write_clamped_chapters(
            config.input, ffmpeg.probe_video_duration(config.input), chapters_file
        )
        cmd = postprocess.mux_command(
            config.input, denoised, audio_filter, out, chapters_file if has_chapters else None
        )
    ffmpeg.run(cmd, capture=False)


# ------------------------------------------------------------------------------ orchestration
def clean(config: CleanConfig, progress: ProgressCallback | None = None) -> Path:
    """Run the whole pipeline and return the path of the output file."""
    ffmpeg.require_tools()
    if not config.input.is_file():
        raise AudioCleanupError(f"Input file not found: {config.input}")
    out = config.output_path
    if out.resolve() == config.input.resolve():
        raise AudioCleanupError("The output file must be different from the input file")
    out.parent.mkdir(parents=True, exist_ok=True)

    total_s = ffmpeg.probe_duration(config.input)
    log.info("Duration: %.2f h", total_s / 3600)

    estimate = estimate_noise(config, total_s)
    engine = select_engine(config, estimate.noise)

    workdir = Path(tempfile.mkdtemp(prefix="audio-cleanup-", dir=config.workdir or out.parent))
    try:
        denoised = workdir / "denoised.flac"
        start = time.time()
        denoise_to_flac(
            config.input, denoised, engine, estimate.hum_filter,
            chunk_s=config.chunk_s, total_s=total_s, progress=progress,
        )  # fmt: skip
        log.info("Denoising done in %.1f min", (time.time() - start) / 60)
        finalize(config, denoised, workdir, out)
    finally:
        if config.keep_intermediate:
            log.info("Intermediate files kept in %s", workdir)
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    log.info("Done -> %s", out)
    return out

"""Configuration of a cleanup run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from audio_cleanup.constants import DEFAULT_ENGINE


@dataclass
class CleanConfig:
    """All the knobs of :func:`audio_cleanup.pipeline.clean`. Defaults match the CLI defaults."""

    input: Path
    #: Output file. Defaults to ``<input>_clean.mp4`` (or ``.m4a`` with ``audio_only``).
    output: Path | None = None
    #: Denoising engine name, see :func:`audio_cleanup.engines.available_engines`.
    engine: str = DEFAULT_ENGINE
    #: Noise-only stretch ``(start_s, end_s)``. Detected automatically when ``None``.
    noise_range: tuple[float, float] | None = None
    #: ``nr`` engine: fraction of the noise to remove (0-1).
    strength: float = 0.9
    #: ``df`` engine: maximum attenuation in dB (100 or more = unlimited).
    atten_db: float = 30.0
    #: Target integrated loudness (LUFS). -16 for speech/podcasts, -14 for YouTube.
    lufs: float = -16.0
    #: Seconds of audio per processing block.
    chunk_s: float = 30.0
    #: Only write a clean ``.m4a``; do not remux the video.
    audio_only: bool = False
    #: Keep the intermediate files (denoised FLAC, chapter file) instead of deleting them.
    keep_intermediate: bool = False
    #: Where to put intermediate files. Defaults to the directory of the output file.
    workdir: Path | None = None

    @property
    def output_path(self) -> Path:
        """Resolved output file."""
        if self.output is not None:
            return self.output
        suffix = ".m4a" if self.audio_only else ".mp4"
        return self.input.with_name(f"{self.input.stem}_clean{suffix}")

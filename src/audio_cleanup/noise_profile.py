"""Automatic discovery of a noise-only stretch of audio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from audio_cleanup import ffmpeg
from audio_cleanup.constants import SAMPLE_RATE

#: Windows within this many dB of the quietest one are treated as "noise only".
QUIET_TOLERANCE_DB = 3.0


@dataclass(frozen=True)
class NoiseProfile:
    """Noise-only audio plus where (and how loud) it was found."""

    samples: NDArray[np.float32]
    window_starts_s: list[float]
    level_dbfs: float


def find_quiet_windows(
    path: Path, search_s: float = 600, window_s: float = 0.4, want_s: float = 3.0
) -> NoiseProfile:
    """Collect the quietest windows in the first ``search_s`` seconds of ``path``.

    Windows within :data:`QUIET_TOLERANCE_DB` of the minimum are gathered until ``want_s``
    seconds of noise-only audio are available.
    """
    x = ffmpeg.read_audio_segment(path, 0, search_s)
    hop = int(window_s * SAMPLE_RATE)
    n = len(x) // hop
    if n == 0:
        raise ValueError(f"Not enough audio in {path} to estimate the noise profile")
    blocks = x[: n * hop].reshape(n, hop)
    db = 10 * np.log10((blocks.astype(np.float64) ** 2).mean(1) + 1e-12)
    order = np.argsort(db)
    selected = [i for i in order if db[i] <= db[order[0]] + QUIET_TOLERANCE_DB]
    selected = sorted(selected[: max(1, int(want_s / window_s))])
    return NoiseProfile(
        samples=blocks[selected].reshape(-1),
        window_starts_s=[i * window_s for i in selected],
        level_dbfs=float(db[selected].mean()),
    )

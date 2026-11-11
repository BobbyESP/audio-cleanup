"""``nr`` engine: stationary spectral gating with a measured noise profile (CPU, lightweight)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from audio_cleanup.constants import SAMPLE_RATE
from audio_cleanup.engines.base import DenoiseEngine, EngineSettings, register_engine
from audio_cleanup.errors import EngineUnavailableError


class NoiseReduceEngine(DenoiseEngine):
    name = "nr"

    def __init__(self, noise: NDArray[np.float32], strength: float) -> None:
        try:
            import noisereduce
        except ImportError as exc:  # pragma: no cover - noisereduce is a core dependency
            raise EngineUnavailableError(f"noisereduce is not installed ({exc})") from exc
        self._nr = noisereduce
        self._noise = noise
        self._strength = strength

    def process(self, block: NDArray[np.float32]) -> NDArray[np.float32]:
        out = self._nr.reduce_noise(
            y=block,
            sr=SAMPLE_RATE,
            y_noise=self._noise,
            stationary=True,
            prop_decrease=self._strength,
            n_fft=4096,
            freq_mask_smooth_hz=150,
            time_mask_smooth_ms=60,
            n_std_thresh_stationary=1.5,
        )
        return out.astype(np.float32)

    def describe(self) -> str:
        return f"noisereduce (stationary spectral gating, strength {self._strength})"


@register_engine("nr")
def _create(settings: EngineSettings) -> DenoiseEngine:
    if settings.noise is None or len(settings.noise) == 0:
        raise EngineUnavailableError("The 'nr' engine needs a noise profile")
    return NoiseReduceEngine(settings.noise, settings.strength)

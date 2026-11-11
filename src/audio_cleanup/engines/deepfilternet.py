"""``df`` engine: DeepFilterNet 3, a neural network trained for speech.

Needs the optional ``deepfilternet`` extra (PyTorch + DeepFilterNet):
``uv sync --extra deepfilternet``. Heavy imports happen in the constructor so that merely
importing this package stays cheap.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from audio_cleanup.constants import SAMPLE_RATE
from audio_cleanup.engines.base import DenoiseEngine, EngineSettings, register_engine
from audio_cleanup.errors import AudioCleanupError, EngineUnavailableError

#: ``atten_db`` values at or above this mean "no attenuation limit".
UNLIMITED_ATTEN_DB = 100


class DeepFilterNetEngine(DenoiseEngine):
    name = "df"

    def __init__(self, atten_db: float) -> None:
        try:
            import df.logger
            import df.utils
            import torch
            from df.enhance import enhance, init_df
        except ImportError as exc:
            raise EngineUnavailableError(
                f"DeepFilterNet is not installed ({exc}). Install it with: "
                "uv sync --extra deepfilternet"
            ) from exc

        # DeepFilterNet shells out to `git` to log its version and crashes when git is missing.
        for module in (df.utils, df.logger):
            for fn in ("get_commit_hash", "get_branch_name"):
                if hasattr(module, fn):
                    setattr(module, fn, lambda *args, **kwargs: None)

        self._torch = torch
        self._enhance = enhance
        self._model, self._state, _ = init_df(log_level="ERROR")
        if self._state.sr() != SAMPLE_RATE:
            raise AudioCleanupError(
                f"DeepFilterNet expects {self._state.sr()} Hz audio, pipeline uses {SAMPLE_RATE} Hz"
            )
        self._atten = None if atten_db >= UNLIMITED_ATTEN_DB else atten_db
        self._device = (
            f"GPU ({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else "CPU"
        )

    def process(self, block: NDArray[np.float32]) -> NDArray[np.float32]:
        tensor = self._torch.from_numpy(np.ascontiguousarray(block, np.float32))[None]
        out = self._enhance(self._model, self._state, tensor, atten_lim_db=self._atten)
        return out[0].cpu().numpy().astype(np.float32)

    def describe(self) -> str:
        return f"DeepFilterNet 3 running on {self._device}"


@register_engine("df")
def _create(settings: EngineSettings) -> DenoiseEngine:
    return DeepFilterNetEngine(settings.atten_db)

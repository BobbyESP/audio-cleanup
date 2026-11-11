import sys

import numpy as np
import pytest

from audio_cleanup.engines import (
    DenoiseEngine,
    EngineSettings,
    available_engines,
    create_engine,
    register_engine,
)
from audio_cleanup.engines import base as engines_base
from audio_cleanup.errors import EngineUnavailableError, UnknownEngineError

NOISE = np.random.default_rng(0).normal(0, 0.01, 48_000).astype(np.float32)


def test_builtin_engines_are_registered():
    assert {"df", "nr"} <= set(available_engines())


def test_unknown_engine():
    with pytest.raises(UnknownEngineError, match="Available"):
        create_engine("does-not-exist", EngineSettings())


def test_nr_engine_preserves_length_and_reduces_noise():
    engine = create_engine("nr", EngineSettings(noise=NOISE, strength=0.9))
    block = np.random.default_rng(1).normal(0, 0.01, 96_000).astype(np.float32)
    out = engine.process(block)
    assert out.shape == block.shape
    assert out.dtype == np.float32
    assert np.std(out) < np.std(block) * 0.7


def test_nr_engine_requires_a_noise_profile():
    with pytest.raises(EngineUnavailableError):
        create_engine("nr", EngineSettings(noise=None))


def test_df_engine_reports_missing_dependencies_cleanly(monkeypatch):
    # `sys.modules[name] = None` makes `import name` raise ImportError.
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(EngineUnavailableError, match="uv sync --extra deepfilternet"):
        create_engine("df", EngineSettings())


def test_third_party_engines_can_be_registered(monkeypatch):
    monkeypatch.setattr(engines_base, "_REGISTRY", dict(engines_base._REGISTRY))

    class Passthrough(DenoiseEngine):
        name = "passthrough"

        def process(self, block):
            return block

    register_engine("passthrough")(lambda settings: Passthrough())
    assert "passthrough" in available_engines()
    block = NOISE[:100]
    assert create_engine("passthrough", EngineSettings()).process(block) is block

    with pytest.raises(ValueError, match="already registered"):
        register_engine("passthrough")(lambda settings: Passthrough())

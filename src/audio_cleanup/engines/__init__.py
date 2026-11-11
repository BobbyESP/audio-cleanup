"""Pluggable denoising engines.

Importing this package registers the built-in engines. They load their heavy dependencies
lazily, so importing it is cheap.
"""

# Importing the modules runs their ``@register_engine`` decorators.
from audio_cleanup.engines import deepfilternet, spectral_gating  # noqa: F401
from audio_cleanup.engines.base import (
    DenoiseEngine,
    EngineSettings,
    available_engines,
    create_engine,
    register_engine,
)

__all__ = [
    "DenoiseEngine",
    "EngineSettings",
    "available_engines",
    "create_engine",
    "register_engine",
]

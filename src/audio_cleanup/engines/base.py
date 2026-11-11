"""Engine interface and registry.

To add a denoising engine, create a module in this package with a class deriving from
:class:`DenoiseEngine` and decorate a factory with :func:`register_engine`. See
``docs/architecture.md`` for a complete example.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from audio_cleanup.errors import UnknownEngineError


@dataclass(frozen=True)
class EngineSettings:
    """Everything an engine factory may need. Engines read only the fields they care about."""

    #: Noise-only audio (already hum-filtered), mono float32 at the pipeline sample rate.
    noise: NDArray[np.float32] | None = None
    #: ``nr`` engine: fraction of the noise to remove, 0-1.
    strength: float = 0.9
    #: ``df`` engine: maximum attenuation in dB (>= 100 means unlimited).
    atten_db: float = 30.0


class DenoiseEngine(ABC):
    """A denoiser that processes one block of mono float32 audio at a time."""

    #: Registry name, also what the user passes to ``--engine``.
    name: str = ""

    @abstractmethod
    def process(self, block: NDArray[np.float32]) -> NDArray[np.float32]:
        """Denoise ``block`` and return an array of exactly the same length."""

    def describe(self) -> str:
        """One-line human readable description (e.g. which device is used)."""
        return self.name


EngineFactory = Callable[[EngineSettings], DenoiseEngine]

_REGISTRY: dict[str, EngineFactory] = {}


def register_engine(name: str) -> Callable[[EngineFactory], EngineFactory]:
    """Decorator that registers an engine factory under ``name``."""

    def decorator(factory: EngineFactory) -> EngineFactory:
        if name in _REGISTRY:
            raise ValueError(f"Engine {name!r} is already registered")
        _REGISTRY[name] = factory
        return factory

    return decorator


def available_engines() -> list[str]:
    """Names of all registered engines (they may still fail to load if a dependency is missing)."""
    return sorted(_REGISTRY)


def create_engine(name: str, settings: EngineSettings) -> DenoiseEngine:
    """Instantiate the engine registered as ``name``.

    Raises:
        UnknownEngineError: ``name`` is not registered.
        EngineUnavailableError: the engine exists but cannot be loaded (missing dependency).
    """
    try:
        factory = _REGISTRY[name]
    except KeyError:
        known = ", ".join(available_engines())
        raise UnknownEngineError(f"Unknown engine {name!r}. Available: {known}") from None
    return factory(settings)

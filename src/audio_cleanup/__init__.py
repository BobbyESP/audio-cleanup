"""Audio cleanup for long recordings: hum removal, denoising and loudness normalization."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("audio-cleanup")
except PackageNotFoundError:  # pragma: no cover - running from a source tree that is not installed
    __version__ = "0.0.0"

__all__ = ["__version__"]

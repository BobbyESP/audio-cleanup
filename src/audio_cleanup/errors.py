"""Exception hierarchy.

Every error that is expected to reach the user derives from :class:`AudioCleanupError`,
so the CLI can print a clean message instead of a traceback.
"""


class AudioCleanupError(Exception):
    """Base class for all expected, user-facing errors."""


class ToolNotFoundError(AudioCleanupError):
    """An external program (ffmpeg, ffprobe) is not available on PATH."""


class FFmpegError(AudioCleanupError):
    """ffmpeg or ffprobe failed or produced output we could not understand."""


class EngineUnavailableError(AudioCleanupError):
    """A denoising engine cannot be used (missing optional dependency, unsupported setup...)."""


class UnknownEngineError(AudioCleanupError):
    """The requested denoising engine name is not registered."""

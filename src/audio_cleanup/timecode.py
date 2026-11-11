"""Small time helpers."""

from __future__ import annotations

from audio_cleanup.errors import AudioCleanupError


def parse_timestamp(value: str | float) -> float:
    """Convert ``hh:mm:ss.x``, ``mm:ss`` or plain seconds to seconds.

    >>> parse_timestamp("01:02:03.5")
    3723.5
    >>> parse_timestamp("12:03")
    723.0
    >>> parse_timestamp(90)
    90.0
    """
    try:
        parts = [float(p) for p in str(value).split(":")]
    except ValueError as exc:
        raise AudioCleanupError(f"Invalid timestamp: {value!r}") from exc
    return float(sum(p * 60**i for i, p in enumerate(reversed(parts))))


def parse_time_range(value: str) -> tuple[float, float]:
    """Parse ``START-END`` (each side accepted by :func:`parse_timestamp`) into seconds.

    >>> parse_time_range("00:12:03.2-00:12:04.8")
    (723.2, 724.8)
    """
    start, sep, end = value.partition("-")
    if not sep:
        raise AudioCleanupError(f"Invalid time range {value!r}: expected START-END")
    t0, t1 = parse_timestamp(start), parse_timestamp(end)
    if t1 <= t0:
        raise AudioCleanupError(f"Invalid time range {value!r}: END must be after START")
    return t0, t1

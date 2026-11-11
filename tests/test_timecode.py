import doctest

import pytest

from audio_cleanup import timecode
from audio_cleanup.errors import AudioCleanupError
from audio_cleanup.timecode import parse_time_range, parse_timestamp


def test_doctests():
    assert doctest.testmod(timecode).failed == 0


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("90", 90.0), ("1:30", 90.0), ("01:00:00", 3600.0), ("00:12:03.5", 723.5)],
)
def test_parse_timestamp(text, seconds):
    assert parse_timestamp(text) == seconds


def test_parse_timestamp_rejects_garbage():
    with pytest.raises(AudioCleanupError):
        parse_timestamp("abc")


def test_parse_time_range():
    assert parse_time_range("00:12:03-00:12:06") == (723.0, 726.0)


@pytest.mark.parametrize("bad", ["12:03", "10-5", "10-10"])
def test_parse_time_range_rejects_bad_ranges(bad):
    with pytest.raises(AudioCleanupError):
        parse_time_range(bad)

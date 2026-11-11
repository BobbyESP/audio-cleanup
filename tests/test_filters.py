import numpy as np
import scipy.signal as sps

from audio_cleanup.constants import SAMPLE_RATE
from audio_cleanup.filters import build_hum_filter, detect_hum_frequency


def tone(freq, seconds=4.0, amp=0.1):
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def rms_db(x):
    return 10 * np.log10(np.mean(x.astype(np.float64) ** 2) + 1e-20)


def test_detects_off_nominal_mains_frequency():
    hum = tone(49.8) + tone(149.4, amp=0.05)
    assert abs(detect_hum_frequency(hum) - 49.8) < 0.1


def test_filter_has_one_highpass_and_notches_below_the_limit():
    sos = build_hum_filter(50.0)
    # Notches at 50, 100, ... 2050 Hz -> 41 notches + the high-pass section.
    assert len(sos) == 42


def test_filter_removes_hum_harmonics_but_keeps_speech_band():
    sos = build_hum_filter(49.8)
    for freq in (49.8 * k for k in (1, 3, 7, 20)):
        out = sps.sosfilt(sos, tone(freq))[SAMPLE_RATE:]  # skip the transient
        assert rms_db(out) < rms_db(tone(freq)) - 30, freq
    for freq in (224.0, 2400.0):  # between two harmonics / above the last notch
        out = sps.sosfilt(sos, tone(freq))[SAMPLE_RATE:]
        assert rms_db(out) > rms_db(tone(freq)) - 1.5, freq

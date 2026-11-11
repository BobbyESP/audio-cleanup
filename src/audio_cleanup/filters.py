"""Mains-hum filtering.

Ground-loop hum shows up as a fundamental at the mains frequency (50 or 60 Hz, often slightly
off, e.g. 49.8 Hz) plus many harmonics. We detect the real fundamental from a noise-only stretch
and build a cascade of: a high-pass filter and one narrow notch per harmonic.
"""

from __future__ import annotations

import numpy as np
import scipy.signal as sps
from numpy.typing import NDArray

from audio_cleanup.constants import SAMPLE_RATE

#: Search window (Hz) for the hum fundamental.
HUM_SEARCH_BAND = (45.0, 55.0)
HIGHPASS_HZ = 70.0
MAX_HARMONICS = 40
#: No notches above this frequency (Hz): speech content lives there.
MAX_NOTCH_HZ = 2100.0
#: Notch quality factor below / above 500 Hz. Higher = narrower notch.
NOTCH_Q_LOW = 35
NOTCH_Q_HIGH = 60


def detect_hum_frequency(noise: NDArray[np.float32]) -> float:
    """Return the hum fundamental (Hz) found in ``noise``, within :data:`HUM_SEARCH_BAND`."""
    freqs, power = sps.welch(noise, SAMPLE_RATE, nperseg=min(len(noise), 65536))
    band = (freqs > HUM_SEARCH_BAND[0]) & (freqs < HUM_SEARCH_BAND[1])
    return float(freqs[band][np.argmax(power[band])])


def build_hum_filter(f0: float, n_harmonics: int = MAX_HARMONICS) -> NDArray[np.float64]:
    """Second-order-sections for a 70 Hz high-pass followed by notches at ``k * f0``.

    Returns an ``(n_sections, 6)`` array usable with :func:`scipy.signal.sosfilt`. The first
    section is the high-pass; every other one is a notch, so the number of notches is
    ``len(sos) - 1``.
    """
    sections = [sps.butter(4, HIGHPASS_HZ, "hp", fs=SAMPLE_RATE, output="sos")]
    for k in range(1, n_harmonics + 1):
        fk = f0 * k
        if fk >= MAX_NOTCH_HZ:
            break
        q = NOTCH_Q_LOW if fk < 500 else NOTCH_Q_HIGH
        b, a = sps.iirnotch(fk, q, fs=SAMPLE_RATE)
        sections.append(sps.tf2sos(b, a))
    return np.vstack(sections)

"""Constants shared by the whole package."""

#: Internal processing sample rate (Hz). Video audio is resampled to this rate and mixed down
#: to mono before denoising. 48 kHz is also what DeepFilterNet expects.
SAMPLE_RATE = 48_000

#: Bytes per sample of the raw ``f32le`` stream exchanged with ffmpeg.
BYTES_PER_SAMPLE = 4

#: Default denoising engine. Falls back to :data:`FALLBACK_ENGINE` if it is not installed.
DEFAULT_ENGINE = "df"
FALLBACK_ENGINE = "nr"

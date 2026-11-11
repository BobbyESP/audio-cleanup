# Audio samples

A short speech excerpt (about 14 s) from a DevFest recording, processed with each engine so you can compare them on headphones.

| File | What it is |
|---|---|
| `1_original.wav` | Original audio: 49.8 Hz mains hum with harmonics, plus hiss. |
| `2_noisereduce.wav` | Hum notches + `nr` engine (spectral gating). |
| `3_deepfilternet_30dB.wav` | Hum notches + `df` engine, 30 dB attenuation limit (the default, recommended). |
| `4_deepfilternet_unlimited.wav` | Hum notches + `df` engine, unlimited attenuation (`--atten 100`). Cleanest, but with less natural room tone. |
| `clip_clean_deepfilternet.mp4` | A short clip run through the full pipeline (video copied, audio cleaned). |
| `spectrograms.png` | Spectrograms of the four audio files. The horizontal lines at 50, 150, 350 Hz… in the original are the hum. |

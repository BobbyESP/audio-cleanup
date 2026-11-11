# Architecture

`audio-cleanup` is a small, layered Python package. The goals behind the design:

- **Constant memory** for recordings of any length (streaming, never the whole file in RAM).
- **Pluggable denoisers**: adding an engine must not require touching the pipeline.
- **Testable stages**: each step of the pipeline is a function with explicit inputs and outputs.
- **A lean core**: the heavy dependency (PyTorch) is optional.
- **Same behavior on Windows and Linux**: platform differences live only in `scripts/`.

## Layers

```
            ┌────────────────────────────┐
 user ────► │ scripts/*.bat, scripts/*.sh│  thin launchers (uv run …)
            └──────────────┬─────────────┘
                           ▼
            ┌────────────────────────────┐
            │ cli.py                     │  argument parsing, logging setup, exit codes
            └──────────────┬─────────────┘
                           ▼
            ┌────────────────────────────┐
            │ pipeline.py                │  orchestrates the stages, owns temp files
            │ fix_duration.py, diagnose.py│  the other commands
            └───┬─────────┬─────────┬────┘
                ▼         ▼         ▼
        engines/      filters.py   postprocess.py   chapters.py   noise_profile.py
   (DenoiseEngine)    (hum)        (EQ, loudnorm)   (OBS fix)     (quiet windows)
                           └─────────┬─────────┘
                                     ▼
                              ffmpeg.py   ← the only module that spawns ffmpeg/ffprobe
```

Dependencies only point downwards. The library layer (`pipeline`, `engines`, …) never prints or calls `sys.exit`; it uses `logging`, an optional progress callback and exceptions derived from `AudioCleanupError`. Only `cli.py` turns those into terminal output and exit codes.

## Modules

| Module | Responsibility |
|---|---|
| `cli.py` | `argparse` sub-commands (`clean`, `fix-chapters`, `diagnose`, `doctor`). Builds a `CleanConfig`, calls the library, prints progress. |
| `config.py` | `CleanConfig` dataclass: every option of a run, plus the default output path. |
| `pipeline.py` | The cleanup stages and `clean()`, which runs them in order. |
| `engines/base.py` | `DenoiseEngine` interface, `EngineSettings`, and the engine registry (`register_engine`, `create_engine`). |
| `engines/spectral_gating.py` | `nr` engine (noisereduce). |
| `engines/deepfilternet.py` | `df` engine (DeepFilterNet 3). Imports PyTorch lazily. |
| `filters.py` | Mains-hum frequency detection and the high-pass + notch filter cascade. |
| `noise_profile.py` | Finds the quietest windows of a recording to use as a noise sample. |
| `postprocess.py` | Clarity EQ chain, two-pass `loudnorm`, and the final ffmpeg commands. |
| `chapters.py` | Reads OBS chapters, clamps them to the video length, renders ffmetadata. |
| `fix_duration.py` | `fix-chapters` command: stream-copy remux with repaired chapters. |
| `diagnose.py` | `diagnose` command: stream durations and timestamp gap analysis. |
| `ffmpeg.py` | `ffmpeg`/`ffprobe` subprocess wrappers and probing helpers. |
| `errors.py` | Exception hierarchy. |
| `constants.py`, `timecode.py` | Shared constants and timestamp parsing. |

## The cleanup pipeline

`pipeline.clean(config)` runs four stages:

1. **`estimate_noise`**: obtains a noise-only stretch (`--noise`, or the quietest windows of the first 10 minutes), detects the hum fundamental with a Welch periodogram in 45–55 Hz, builds the hum filter (`filters.build_hum_filter`) and applies it to the noise sample.
2. **`select_engine`**: `create_engine(config.engine, EngineSettings(...))`. If the engine reports `EngineUnavailableError` (for example PyTorch is not installed) the `nr` engine is used instead, with a warning.
3. **`denoise_to_flac`**: the streaming core. ffmpeg decodes to raw mono float32 on a pipe; the hum filter runs continuously with its state carried across reads; audio is cut into blocks of `--chunk` seconds, each given 1 s of context on both sides, denoised by the engine, and only the central part is written to a second ffmpeg process that encodes 24-bit FLAC. Memory use is `O(chunk)`.
4. **`finalize`**: pass 1 measures loudness (`postprocess.measure_loudness`); pass 2 applies clarity EQ + linear `loudnorm` and either encodes an `.m4a` or remuxes with the original video (`-c:v copy`) and the repaired chapters.

Intermediate files live in a private temporary directory (`audio-cleanup-*`) next to the output, or in `--workdir`. It is removed even when something fails, unless `--keep` is used.

### Why shell out to ffmpeg?

ffmpeg already handles every container and codec, the `loudnorm` filter is the reference EBU R128 implementation, and `-c:v copy` is what keeps the video untouched. Wrapping it in `ffmpeg.py` keeps command construction in one place and turns failures into readable errors.

### Why the overlap?

Denoisers such as DeepFilterNet need context to be accurate at a block's edges. Each block is processed with 1 s of audio before and after the part that is kept, so the seams are inaudible.

## Dependencies and the optional extra

`pyproject.toml` declares a lean core (`numpy`, `scipy`, `soundfile`, `noisereduce`) and an optional extra:

```toml
[project.optional-dependencies]
deepfilternet = ["deepfilternet==0.5.6", "torch==2.0.1", "torchaudio==2.0.2"]
```

This keeps CI fast (no 3 GB download to run the tests) and lets people who only want `--engine nr` install very little. The pins come from DeepFilterNet 0.5.x, which needs `torch<2.1` and `numpy<2`; that in turn limits Python to 3.11.

`[tool.uv] environments` restricts the lockfile to Windows and Linux. On Windows, `[tool.uv.sources]` redirects `torch`/`torchaudio` to the CUDA 11.8 index.

## Adding a denoising engine

1. Create `src/audio_cleanup/engines/my_engine.py`:

   ```python
   import numpy as np
   from numpy.typing import NDArray

   from audio_cleanup.engines.base import DenoiseEngine, EngineSettings, register_engine
   from audio_cleanup.errors import EngineUnavailableError


   class MyEngine(DenoiseEngine):
       name = "my"

       def __init__(self, strength: float) -> None:
           try:
               import my_library  # heavy imports go here, not at module level
           except ImportError as exc:
               raise EngineUnavailableError(f"my_library is not installed ({exc})") from exc
           self._lib = my_library
           self._strength = strength

       def process(self, block: NDArray[np.float32]) -> NDArray[np.float32]:
           # `block` is mono float32 at 48 kHz; return an array of the same length.
           return self._lib.denoise(block, self._strength).astype(np.float32)

       def describe(self) -> str:
           return "My engine"


   @register_engine("my")
   def _create(settings: EngineSettings) -> DenoiseEngine:
       return MyEngine(settings.strength)
   ```

2. Import the module in `engines/__init__.py` so the decorator runs:
   `from audio_cleanup.engines import deepfilternet, my_engine, spectral_gating  # noqa: F401`
3. If it needs a new option, add a field to `EngineSettings`, to `CleanConfig`, and a flag in `cli.py` (`pipeline.select_engine` copies the fields over).
4. If it needs a third-party package, add it as another optional extra in `pyproject.toml` and run `uv lock`.
5. Add a test in `tests/test_engines.py` (see `test_third_party_engines_can_be_registered`).

`--engine` choices and `audio-cleanup doctor` pick the new engine up automatically.

## Adding a command

Add a sub-parser and a `_cmd_<name>(args) -> int` handler in `cli.py`, and put the real logic in its own module so it can be used as a library and tested without the CLI. Raise `AudioCleanupError` subclasses for expected failures.

## Error handling

| Exception | Meaning |
|---|---|
| `AudioCleanupError` | Base class for everything the CLI reports as `Error: …` with exit code 1. |
| `ToolNotFoundError` | ffmpeg/ffprobe missing. |
| `FFmpegError` | An ffmpeg/ffprobe call failed (stderr tail is included). |
| `EngineUnavailableError` | The engine cannot load; triggers the fallback to `nr`. |
| `UnknownEngineError` | Engine name not registered. |

## Testing strategy

| Test file | What it covers | Needs ffmpeg |
|---|---|---|
| `test_timecode.py`, `test_chapters.py`, `test_diagnose.py`, `test_postprocess_and_config.py` | Pure functions | no |
| `test_filters.py` | Hum detection and notch attenuation on synthetic tones | no |
| `test_engines.py` | Registry, `nr` engine, clean failure of `df` when PyTorch is missing | no |
| `test_cli.py` | Parser and error exit codes | no |
| `test_integration.py` | Whole pipeline on a 12 s synthetic video (hum + tone + noise) with the `nr` engine, `--audio-only`, the `df` → `nr` fallback, and `fix-chapters` | yes (skipped if absent) |

The integration tests never use PyTorch, so CI runs them on Linux and Windows without the 3 GB extra. Run them alone with `uv run pytest -m integration`.

## Platform notes

- Windows launchers are `.bat` files so they work by double-click and drag-and-drop. `_common.bat` detects that case (to keep the window open at the end) with delayed expansion, so file names containing `&`, `(`, `)` or `^` are safe.
- Linux launchers are POSIX-friendly bash scripts sharing `_common.sh`.
- `.gitattributes` forces CRLF for `.bat` and LF for `.sh`.

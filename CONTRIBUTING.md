# Contributing

Thanks for helping! The project uses [uv](https://docs.astral.sh/uv/) for everything.

## Set up

```bash
git clone https://github.com/<your-user>/audio-cleanup.git
cd audio-cleanup
uv sync                          # lean install + dev tools (pytest, ruff)
uv sync --extra deepfilternet    # also PyTorch + DeepFilterNet (about 3 GB), only if you need the `df` engine
```

You also need `ffmpeg` and `ffprobe` on `PATH` for the integration tests (see the README).

## Everyday commands

| Task | Command |
|---|---|
| Run all tests | `uv run pytest` |
| Skip the ffmpeg-based tests | `uv run pytest -m "not integration"` |
| Lint | `uv run ruff check .` |
| Auto-fix lint issues | `uv run ruff check --fix .` |
| Format | `uv run ruff format .` |
| Try the CLI | `uv run audio-cleanup --help` |
| Check your setup | `uv run audio-cleanup doctor` |
| Add a dependency | `uv add <package>` (or `uv add --optional deepfilternet <package>`) |
| Update the lockfile | `uv lock` |

CI runs `ruff check`, `ruff format --check` and `pytest` on Ubuntu and Windows; please run them before opening a pull request.

## Guidelines

- **Keep the layers.** Library code (`pipeline`, `engines`, `filters`, …) must not print or exit; use `logging`, the progress callback and `AudioCleanupError` subclasses. Only `cli.py` talks to the terminal. See [docs/architecture.md](docs/architecture.md).
- **All ffmpeg calls go through `ffmpeg.py`.**
- **Add tests** for new behavior. Prefer small pure functions that can be tested without ffmpeg; use the `noisy_video` fixture for end-to-end checks.
- **Do not commit recordings.** `.gitignore` blocks `*.mp4`, `*.wav`, etc. everywhere except `docs/samples/`.
- **Commit `uv.lock`** whenever dependencies change.
- **Everything user-facing is in English** (code, comments, docs, messages).
- Windows launchers must stay CRLF and Linux launchers LF (enforced by `.gitattributes`). If you edit a launcher, test it by dragging a file with spaces and `&` in its name onto the `.bat`.

## Adding a denoising engine

It takes one module and a decorator. A complete example is in [docs/architecture.md](docs/architecture.md#adding-a-denoising-engine).

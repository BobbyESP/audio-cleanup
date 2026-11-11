# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0]

First public version. The original scripts were reorganized into an installable package.

### Added
- `audio-cleanup` command with `clean`, `fix-chapters`, `diagnose` and `doctor` sub-commands.
- Pluggable denoising engines (`df` = DeepFilterNet 3, `nr` = noisereduce) behind a registry.
- `--workdir` for intermediate files; intermediate files are removed even if a run fails.
- Windows (`.bat`, drag-and-drop) and Linux (`.sh`) launchers in `scripts/`.
- Test suite (unit and end-to-end) and GitHub Actions CI on Ubuntu and Windows.
- PyTorch / DeepFilterNet is now an optional extra: `uv sync --extra deepfilternet`.

### Changed
- Code moved to a `src/` layout (`audio_cleanup` package); the old standalone scripts were removed.
- With `--audio-only`, `-o` is now used as given instead of getting a `_clean` suffix appended.
- The package logs through `logging` (to stderr) instead of printing.

### Fixed
- ffmpeg failures now stop the run with a clear error instead of being ignored.

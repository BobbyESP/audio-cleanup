---
name: audio-cleanup
description: Remove mains hum (50/60 Hz ground loop) and background noise/hiss from long video or audio recordings, then normalize loudness (EBU R128), without re-encoding the video. Use this skill whenever the user wants to clean up, denoise, de-hum or "fix the sound" of a recording — conference talks, podcasts, OBS captures, lectures, interviews, webinars — or wants a talk ready for YouTube loudness, even if they don't mention hum or LUFS explicitly. Also use it when an OBS/remuxed MP4 shows a wrong (too long) duration in players, or to inspect stream durations and timestamp gaps of MP4 files.
license: MIT
compatibility: Needs a shell, uv (https://docs.astral.sh/uv/) and ffmpeg/ffprobe on PATH; network access on the first run. Linux and Windows (macOS untested).
---

# audio-cleanup

This skill drives the [`audio-cleanup`](https://github.com/BobbyESP/audio-cleanup) command line
tool. The tool does the heavy lifting; your job is to pick the right options for what the user
wants, make sure the environment is ready, run it safely on files that may be hours long, and check
the result.

Pipeline of `clean` (for reference when explaining results):

```
decode (mono 48 kHz, streamed) -> 70 Hz high-pass + notch on every hum harmonic (auto-detected)
  -> denoise in 30 s blocks (engine df = DeepFilterNet 3, or nr = noisereduce)
  -> clarity EQ + gentle compression + de-esser -> two-pass loudnorm (-16 LUFS, -1.5 dBTP)
  -> remux with the original video stream copied (-c:v copy) -> <input>_clean.mp4
```

## 1. Decide how to run the tool

The skill works in two modes. Pick one once per session; in the rest of this skill,
`audio-cleanup …` means "the command of the chosen mode".

**Local mode: the skill sits inside a clone of the repository.** This is the case when it was
installed as a Claude Code plugin or the agent was started in the repository. Check it with:

```bash
SKILL_DIR="<this skill's base directory>"
ROOT="$(cd "$(dirname "$(realpath "$SKILL_DIR/SKILL.md")")/../.." && pwd)"
grep -qs '^name = "audio-cleanup"' "$ROOT/pyproject.toml" && echo local || echo remote
```

If it prints `local`, run the tool as `audio-cleanup …`. This uses the
locked versions in `uv.lock` and the scripts and docs of the clone.

**Remote mode: the skill folder was copied on its own** into an agent's skills directory. Run
the tool straight from GitHub; uv downloads and caches it on the first call (about 15 s):

```bash
uvx --python 3.11 --from git+https://github.com/BobbyESP/audio-cleanup audio-cleanup …
```

Either way, keep the user's files where they are and pass absolute paths. Quote them, because
recordings often have spaces or `&` in their names.

## 2. Check the environment (once per session)

```bash
audio-cleanup doctor
```

It reports ffmpeg/ffprobe and which engines work. It exits with 1 when the recommended `df`
engine is missing; that is fine if the user is happy with `--engine nr`. Fix what is missing:

| Missing | What to do |
| --- | --- |
| `uv` not found | Install it: `curl -LsSf https://astral.sh/uv/install.sh \| sh` (Linux/macOS) or `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` (Windows). It may land in `~/.local/bin`, which might not be on `PATH` yet. |
| ffmpeg / ffprobe | Tell the user the command for their system (`sudo apt-get install ffmpeg`, `sudo pacman -S ffmpeg`, `sudo dnf install ffmpeg-free`, `winget install -e --id Gyan.FFmpeg`). It needs sudo/admin, so let the user run it unless they ask you to. |
| engine `df` unavailable | It needs the `deepfilternet` extra, which downloads **about 3 GB** (PyTorch), so ask before installing it. Local mode: `uv sync --project "$ROOT" --extra deepfilternet`. Remote mode: from then on use `--from "audio-cleanup[deepfilternet] @ git+https://github.com/BobbyESP/audio-cleanup"` in the `uvx` command (doctor's hint about `uv sync` only applies to local mode). If the user doesn't want the download, use `--engine nr`, which works with the base install. |

uv also downloads Python 3.11 when needed, so there is no separate install step. In local mode the
repository also ships `scripts/linux/setup.sh` and `scripts/windows/setup.bat`, which do all of
the above for a human at a terminal.

## 3. Choose the options

Map what the user says to flags; the defaults are good for speech, so only add what is needed.

| The user wants… | Flags |
| --- | --- |
| Default clean-up of a talk/podcast | *(none)* — `df` engine, 30 dB max attenuation, -16 LUFS |
| Upload to YouTube / "as loud as YouTube" | `--lufs -14` |
| More natural, keep some room tone | `--atten 18` … `--atten 24` |
| Remove as much noise as possible | `--atten 100` (unlimited) |
| Lightweight, no GPU, no 3 GB install | `--engine nr` (optionally `--strength 0.6`–`1.0`, default 0.9) |
| Only the audio (e.g. for a podcast feed) | `--audio-only` → writes `<name>_clean.m4a` |
| Specific output path | `-o /path/out.mp4` |
| Hum still audible after a first pass | `--noise HH:MM:SS-HH:MM:SS` on a stretch with only noise, and/or `--atten 100` |
| Little free space next to the file | `--workdir /other/disk` |

Notes that help you choose:

- `df` (DeepFilterNet) gives clearly better results on speech and also removes hiss and clicks. It
  is built for speech, so music (intros, breaks) can come out slightly muffled; mention this when
  the recording has a lot of music, and offer `nr` as the alternative.
- `--noise` with `df` is only used to detect the hum frequency; the noise profile matters for `nr`.
- The video stream is never re-encoded, so quality and size of the picture are unchanged. Audio
  comes out as AAC stereo 192 kbps. OBS chapter markers are kept and repaired automatically.

## 4. Run it

```bash
audio-cleanup clean "/abs/path/talk.mp4" [flags]
```

Before a long file, check its length and the free disk space, because both shape what you do next:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "/abs/path/talk.mp4"   # seconds
df -h "/abs/path/"                                                               # free space
```

- **Speed:** roughly 20–25× real time on a modest 2-core CPU (≈25–30 min for 10 h), faster with
  more cores or an NVIDIA GPU. Anything longer than a few minutes should run as a **background
  command** with a generous timeout so you are not blocked; progress goes to stderr.
- **Disk:** needs the output (about the size of the input) plus 2–3 GB of temporary FLAC per 10 h of
  audio. Intermediate files are deleted at the end, even on failure, unless `--keep` is given.
- **Try before the full run** when the recording is hours long or the user is unsure about the
  settings: cut 10 minutes without re-encoding, clean that, and let the user listen first.

  ```bash
  ffmpeg -ss 00:30:00 -t 600 -i "/abs/path/talk.mp4" -c copy "/abs/path/talk_test.mp4"
  ```

  If the mic, room or mixer changed during the day, test a few different moments.
- **Several files:** process them one after another (not in parallel — each run already uses all
  cores and a lot of temp space), and report each result as it finishes.

Never write over the user's original: the default output is `<input>_clean.mp4` next to the input.

## 5. Check the result

After a run, confirm the output exists and is sane, then report it to the user:

```bash
audio-cleanup diagnose "/abs/path/talk_clean.mp4"
```

The durations of the video and audio streams should match the original. To confirm the loudness
target, measure it. The summary starts at the `Summary:` line; its `I:` value (integrated loudness)
should be within about 1 LU of the `--lufs` target, and `Peak:` below the -1.5 dBTP ceiling:

```bash
ffmpeg -hide_banner -nostats -i "/abs/path/talk_clean.mp4" -map 0:a:0 -af ebur128=peak=true -f null - 2>&1 \
  | sed -n '/Summary:/,$p'
```

Read the `I:` line before drawing conclusions; if it is not in the output, the command was cut short,
not the loudness wrong.

You cannot listen to audio, so be honest about that: say what was measured, and suggest the user
listen to a couple of passages on headphones (especially speech onsets and any music). The repository has
before/after samples in `docs/samples/` that show what to expect.

## Other commands

| Command | Use it when |
| --- | --- |
| `fix-chapters <video> [--drop] [-o out]` | A player shows a duration much longer than the video (OBS wrote a bogus last chapter). Rewrites the chapters in seconds, no re-encoding; `--drop` removes them. Writes `<name>_fixed.mp4`. |
| `diagnose [files…] [-o report.txt]` | Inspect stream durations, start times, timestamp gaps and backward jumps (default: every `.mp4` in the current folder). |
| `doctor` | Check ffmpeg and the engines. |

Global `-v` (before the command) enables debug logging, useful when something fails.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ffmpeg not found on PATH` | Install ffmpeg (step 2) and use a new shell. |
| `DeepFilterNet is not installed … Falling back to the 'nr' engine` | The run continued with `nr`. Install the extra (ask first, ~3 GB) and re-run if the user wants `df` quality. |
| PyTorch warning that the GPU "is not compatible" | Seen on very new GPUs; output is still fine. On CUDA errors, force the CPU with `CUDA_VISIBLE_DEVICES=` in front of the command. |
| `No space left on device` | `--workdir` on a disk with more free space. |
| Player shows the wrong duration | `fix-chapters` on the output. |
| Hum still audible | `--noise START-END` on a pure-noise stretch, and/or `--atten 100`. |

For the internals (how hum is detected, how engines are added) see `docs/architecture.md` in the
repository (on GitHub in remote mode); you only need it if the user wants to change the tool itself.

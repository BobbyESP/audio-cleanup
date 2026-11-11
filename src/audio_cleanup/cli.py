"""Command line interface: ``audio-cleanup <command> ...``."""

from __future__ import annotations

import argparse
import logging
import platform
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from audio_cleanup import __version__, ffmpeg
from audio_cleanup.config import CleanConfig
from audio_cleanup.constants import DEFAULT_ENGINE
from audio_cleanup.diagnose import diagnose
from audio_cleanup.engines import EngineSettings, available_engines, create_engine
from audio_cleanup.errors import AudioCleanupError, EngineUnavailableError
from audio_cleanup.fix_duration import fix_duration
from audio_cleanup.pipeline import ProgressCallback, clean
from audio_cleanup.timecode import parse_time_range

log = logging.getLogger("audio_cleanup")


# ------------------------------------------------------------------------------ parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio-cleanup",
        description="Hum removal, denoising and loudness normalization for long recordings.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # -- clean
    p = sub.add_parser(
        "clean",
        help="clean the audio of a video (or audio) file",
        description=(
            "Pipeline: mains-hum notch filters -> denoising engine (streamed in blocks) -> "
            "clarity EQ + compression + de-esser -> two-pass EBU R128 loudnorm -> remux with "
            "the untouched video stream."
        ),
    )
    p.add_argument("input", type=Path, help="input video/audio file")
    p.add_argument("-o", "--output", type=Path, help="output file (default: <input>_clean.mp4)")
    p.add_argument(
        "--engine", choices=available_engines(), default=DEFAULT_ENGINE,
        help="df = DeepFilterNet (recommended, needs the 'deepfilternet' extra), "
        "nr = noisereduce (CPU, lightweight)",
    )  # fmt: skip
    p.add_argument(
        "--noise", metavar="START-END",
        help="noise-only stretch, e.g. 00:12:03.2-00:12:04.8 (detected automatically by default)",
    )  # fmt: skip
    p.add_argument("--strength", type=float, default=0.9, help="nr: 0-1, how much noise to remove")
    p.add_argument(
        "--atten", type=float, default=30,
        help="df: max attenuation in dB (default 30; 18-24 sounds more natural; 100 = unlimited)",
    )  # fmt: skip
    p.add_argument(
        "--lufs", type=float, default=-16,
        help="target loudness (-16 speech/podcast, -14 YouTube)",
    )  # fmt: skip
    p.add_argument("--chunk", type=float, default=30, help="seconds per processing block")
    p.add_argument("--audio-only", action="store_true", help="only write a clean .m4a, no video")
    p.add_argument("--keep", action="store_true", help="keep intermediate files")
    p.add_argument(
        "--workdir", type=Path,
        help="directory for intermediate files; needs 2-3 GB per 10 h of audio "
        "(default: next to the output)",
    )  # fmt: skip
    p.set_defaults(handler=_cmd_clean)

    # -- fix-chapters
    p = sub.add_parser(
        "fix-chapters",
        help="fix a wrong duration caused by bogus OBS chapter markers (no re-encoding)",
    )
    p.add_argument("input", type=Path, help="already processed video")
    p.add_argument("-o", "--output", type=Path, help="output file (default: <input>_fixed.mp4)")
    p.add_argument("--drop", action="store_true", help="remove the chapters instead of fixing them")
    p.set_defaults(handler=_cmd_fix_chapters)

    # -- diagnose
    p = sub.add_parser("diagnose", help="report durations, start times and timestamp gaps")
    p.add_argument(
        "files", nargs="*", type=Path,
        help="files to analyse (default: every .mp4 in the current directory)",
    )  # fmt: skip
    p.add_argument("-o", "--output", type=Path, help="also save the report to this file")
    p.set_defaults(handler=_cmd_diagnose)

    # -- doctor
    p = sub.add_parser("doctor", help="check that ffmpeg and the denoising engines work")
    p.set_defaults(handler=_cmd_doctor)

    return parser


# ------------------------------------------------------------------------------ commands
def _progress_printer() -> ProgressCallback:
    start = time.time()

    def show(done_s: float, total_s: float) -> None:
        speed = done_s / max(time.time() - start, 1e-6)
        sys.stderr.write(
            f"\r  denoise {done_s / 60:7.1f} / {total_s / 60:.1f} min  ({speed:.0f}x real time)"
        )
        if done_s >= total_s:
            sys.stderr.write("\n")
        sys.stderr.flush()

    return show


def _cmd_clean(args: argparse.Namespace) -> int:
    config = CleanConfig(
        input=args.input,
        output=args.output,
        engine=args.engine,
        noise_range=parse_time_range(args.noise) if args.noise else None,
        strength=args.strength,
        atten_db=args.atten,
        lufs=args.lufs,
        chunk_s=args.chunk,
        audio_only=args.audio_only,
        keep_intermediate=args.keep,
        workdir=args.workdir,
    )
    clean(config, progress=_progress_printer())
    return 0


def _cmd_fix_chapters(args: argparse.Namespace) -> int:
    fix_duration(args.input, args.output, drop_chapters=args.drop)
    return 0


def _cmd_diagnose(args: argparse.Namespace) -> int:
    ffmpeg.require_tools()
    files = args.files or sorted(Path.cwd().glob("*.mp4"))
    if not files:
        raise AudioCleanupError(
            "No files to analyse: pass some files or run in a folder with .mp4s"
        )
    reports: list[str] = []
    for report in diagnose(files):
        print(report, flush=True)
        reports.append(report)
    if args.output:
        args.output.write_text("\n\n".join(reports) + "\n", encoding="utf-8")
        log.info("Report saved to %s", args.output)
    return 0


def _cmd_doctor(_args: argparse.Namespace) -> int:
    ok = True
    print(
        f"audio-cleanup {__version__} on Python {platform.python_version()} ({platform.system()})"
    )
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        print(f"  [{'ok' if path else 'MISSING'}] {tool}" + (f"  ({path})" if path else ""))
        ok &= path is not None

    # A short silent noise profile is enough to instantiate any engine.
    probe_settings = EngineSettings(noise=np.full(4800, 1e-4, np.float32))
    for name in available_engines():
        try:
            description = create_engine(name, probe_settings).describe()
            print(f"  [ok] engine {name}: {description}")
        except EngineUnavailableError as exc:
            print(f"  [--] engine {name}: unavailable ({exc})")
            ok &= name != DEFAULT_ENGINE  # the recommended engine missing is worth a failure
    return 0 if ok else 1


# ------------------------------------------------------------------------------ entry point
def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )
    try:
        return int(args.handler(args))
    except AudioCleanupError as exc:
        log.error("Error: %s", exc)
        return 1
    except KeyboardInterrupt:
        log.error("Interrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())

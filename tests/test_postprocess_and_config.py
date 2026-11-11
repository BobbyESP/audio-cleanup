from pathlib import Path

from audio_cleanup.config import CleanConfig
from audio_cleanup.postprocess import audio_only_command, build_audio_filter, mux_command

MEASURED = {
    "input_i": "-20.1",
    "input_tp": "-3.0",
    "input_lra": "5.5",
    "input_thresh": "-30.2",
    "target_offset": "0.4",
}


def test_audio_filter_uses_measurements_and_target():
    graph = build_audio_filter(-14, MEASURED)
    assert "loudnorm=I=-14" in graph
    assert "measured_I=-20.1" in graph
    assert "offset=0.4" in graph
    assert "linear=true" in graph
    assert graph.endswith("aresample=48000")


def test_mux_never_reencodes_video():
    cmd = mux_command(Path("in.mp4"), Path("a.flac"), "anull", Path("out.mp4"), None)
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert cmd[cmd.index("-map_chapters") + 1] == "-1"  # chapters dropped when there are none


def test_mux_maps_chapters_from_the_metadata_file():
    cmd = mux_command(Path("in.mp4"), Path("a.flac"), "anull", Path("o.mp4"), Path("ch.txt"))
    assert cmd[cmd.index("-map_chapters") + 1] == "2"


def test_audio_only_writes_aac():
    cmd = audio_only_command(Path("a.flac"), "anull", Path("out.m4a"))
    assert "aac" in cmd
    assert cmd[-1] == str(Path("out.m4a"))


def test_default_output_paths():
    assert CleanConfig(Path("talks/day1.mp4")).output_path == Path("talks/day1_clean.mp4")
    audio_only = CleanConfig(Path("talks/day1.mp4"), audio_only=True)
    assert audio_only.output_path == Path("talks/day1_clean.m4a")
    assert CleanConfig(Path("a.mp4"), output=Path("b.mkv")).output_path == Path("b.mkv")

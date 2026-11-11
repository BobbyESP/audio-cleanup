import pytest

from audio_cleanup import __version__
from audio_cleanup.cli import build_parser, main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_clean_defaults():
    args = build_parser().parse_args(["clean", "talk.mp4"])
    assert (args.engine, args.atten, args.lufs, args.chunk) == ("df", 30, -16, 30)
    assert not args.audio_only
    assert not args.keep


def test_clean_options():
    args = build_parser().parse_args(
        ["clean", "talk.mp4", "--engine", "nr", "--lufs", "-14", "--noise", "1:00-1:03"]
    )
    assert (args.engine, args.lufs, args.noise) == ("nr", -14, "1:00-1:03")


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_user_errors_exit_with_code_1_and_no_traceback(tmp_path, caplog):
    code = main(["clean", str(tmp_path / "missing.mp4")])
    assert code == 1
    assert "Error:" in caplog.text

from audio_cleanup.chapters import Chapter, clamp_chapters, render_ffmetadata


def raw(start, end, title=None):
    chapter = {"start_time": str(start), "end_time": str(end)}
    if title:
        chapter["tags"] = {"title": title}
    return chapter


def test_last_chapter_is_clamped_to_video_length():
    # The OBS bug: the last chapter ends long after the recording.
    chapters = clamp_chapters([raw(0, 10, "A"), raw(10, 7077, "B")], end_s=60)
    assert chapters == [Chapter(0, 10, "A"), Chapter(10, 60, "B")]


def test_chapters_starting_after_the_end_are_dropped():
    assert clamp_chapters([raw(0, 10), raw(100, 200)], end_s=50) == [Chapter(0, 10)]


def test_chapter_never_overlaps_the_next_one():
    chapters = clamp_chapters([raw(0, 50), raw(20, 60)], end_s=60)
    assert chapters[0].end_s == 20


def test_no_chapters():
    assert clamp_chapters([], end_s=60) == []


def test_ffmetadata_rendering_escapes_special_characters():
    text = render_ffmetadata([Chapter(0, 1.5, "Talk=1; #intro")])
    assert text.startswith(";FFMETADATA1\n")
    assert "START=0" in text
    assert "END=1500" in text
    assert r"title=Talk\=1\; \#intro" in text

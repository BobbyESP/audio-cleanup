from audio_cleanup.diagnose import summarize_packets


def test_regular_stream_has_no_gaps():
    pts = [i * 0.02 for i in range(500)]
    report = summarize_packets("a:0", pts)
    assert "500 packets" in report
    assert "0 gaps" in report
    assert "0 big backward jumps" in report


def test_gap_is_reported():
    pts = [i * 0.02 for i in range(100)] + [10.0 + i * 0.02 for i in range(100)]
    report = summarize_packets("v:0", pts)
    assert "1 gaps" in report
    assert "gap of" in report


def test_backward_jump_is_reported():
    pts = [0.0, 0.02, 0.04, 5.0, 2.0, 2.02]
    assert "1 big backward jumps" in summarize_packets("a:0", pts)


def test_empty_stream():
    assert "no packets" in summarize_packets("a:0", [])

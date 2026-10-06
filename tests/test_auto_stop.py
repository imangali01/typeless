from typeless.engines.streaming import NO_SPEECH_S, should_auto_stop


def test_stops_after_silence_following_speech():
    assert not should_auto_stop(2.0, heard=True, quiet=1.9)
    assert should_auto_stop(2.0, heard=True, quiet=2.0)


def test_waits_longer_when_nothing_was_said_yet():
    assert not should_auto_stop(2.0, heard=False, quiet=3.0)
    assert should_auto_stop(2.0, heard=False, quiet=NO_SPEECH_S)


def test_off_means_never():
    assert not should_auto_stop(0.0, heard=True, quiet=999)

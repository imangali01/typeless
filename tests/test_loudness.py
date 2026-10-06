from typeless.loudness import Envelope, loudness


def test_silence_and_clipping():
    assert loudness(0.0) == 0.0
    assert loudness(1e-4) == 0.0  # -80 dB: room noise
    assert loudness(1.0) == 1.0


def test_quiet_vs_normal_vs_loud_speech_are_clearly_apart():
    quiet, normal, loud = loudness(0.006), loudness(0.03), loudness(0.15)
    assert 0.15 < quiet < 0.4
    assert quiet + 0.2 < normal < loud
    assert loud > 0.8


def test_envelope_rises_fast_and_falls_slowly():
    env = Envelope()
    up = env.step(1.0)
    assert up > 0.7
    down = env.step(0.0)
    assert down > 0.6  # one quiet tick barely lowers it

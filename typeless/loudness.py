"""Microphone loudness for the on-screen waveform, on a perceptual (decibel) scale."""

from __future__ import annotations

import math

FLOOR_DB = -55.0  # room silence / breathing -> 0
CEIL_DB = -12.0  # loud speech close to the mic -> 1


def loudness(rms: float) -> float:
    """RMS of a float32 [-1, 1] block -> 0..1, linear in decibels.

    A linear RMS scale makes quiet speech look like silence and everything else
    look the same; dB matches how loud it sounds.
    """
    if rms <= 1e-9:
        return 0.0
    db = 20.0 * math.log10(rms)
    return max(0.0, min(1.0, (db - FLOOR_DB) / (CEIL_DB - FLOOR_DB)))


class Envelope:
    """Fast attack, slow release: the wave jumps up on a syllable and settles in pauses."""

    def __init__(self, attack: float = 0.75, release: float = 0.12) -> None:
        self.attack = attack
        self.release = release
        self.value = 0.0

    def step(self, target: float) -> float:
        k = self.attack if target > self.value else self.release
        self.value += (target - self.value) * k
        return self.value

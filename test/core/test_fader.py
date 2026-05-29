import time

import numpy as np
from olc.core.fader import Fade, FadeEngine
from olc.core.universe_data import NUM_CHANNELS, DMXUniverse


class TestFade:
    """Test suite for the Fade data-class computation."""

    def test_fade_at_start(self) -> None:
        """At t=0, the output should match the start frame."""
        start = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        target = np.full(NUM_CHANNELS, 200, dtype=np.uint8)
        fade = Fade(start=start, target=target, duration=1.0, t0=time.monotonic())

        # Compute immediately — should be very close to start values
        frame = fade.compute(fade.t0 + 0.001)
        assert int(frame[0]) < 5
        assert not fade.done

    def test_fade_at_end(self) -> None:
        """After duration has elapsed, the output should match the target."""
        start = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        target = np.full(NUM_CHANNELS, 200, dtype=np.uint8)
        fade = Fade(start=start, target=target, duration=1.0, t0=time.monotonic())

        frame = fade.compute(fade.t0 + 2.0)  # Past the end
        assert int(frame[0]) == 200
        assert fade.done

    def test_fade_midpoint(self) -> None:
        """At t=0.5 of duration, the output should be roughly half-way."""
        start = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        target = np.full(NUM_CHANNELS, 200, dtype=np.uint8)
        fade = Fade(start=start, target=target, duration=1.0, t0=time.monotonic())

        frame = fade.compute(fade.t0 + 0.5)
        # Allow tolerance for integer rounding: expect ~100 ± 5
        assert 95 <= int(frame[0]) <= 105

    def test_zero_duration(self) -> None:
        """A zero-duration fade should snap immediately to target."""
        start = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        target = np.full(NUM_CHANNELS, 255, dtype=np.uint8)
        fade = Fade(start=start, target=target, duration=0.0, t0=time.monotonic())

        frame = fade.compute(time.monotonic())
        assert int(frame[0]) == 255
        assert fade.done


class TestFadeEngine:
    """Test suite for the FadeEngine."""

    def test_snap(self) -> None:
        """snap() should update the universe instantly and cancel any fade."""
        univ = DMXUniverse()
        engine = FadeEngine(univ)

        target = np.full(NUM_CHANNELS, 128, dtype=np.uint8)
        engine.snap(target)

        assert univ[0] == 128
        assert not engine.is_fading
        assert not engine.tick()

    def test_go_starts_fade(self) -> None:
        """go() should start a fade and is_fading should be True."""
        univ = DMXUniverse()
        engine = FadeEngine(univ)
        target = np.full(NUM_CHANNELS, 200, dtype=np.uint8)

        engine.go(target, duration=1.0)
        assert engine.is_fading

    def test_go_snap_cancels_fade(self) -> None:
        """snap() during a fade should cancel it."""
        univ = DMXUniverse()
        engine = FadeEngine(univ)

        engine.go(np.full(NUM_CHANNELS, 200, dtype=np.uint8), duration=10.0)
        assert engine.is_fading

        engine.snap(np.zeros(NUM_CHANNELS, dtype=np.uint8))
        assert not engine.is_fading

    def test_tick_updates_universe(self) -> None:
        """tick() should move the universe values toward the target."""
        univ = DMXUniverse()
        univ.set_all(0)

        engine = FadeEngine(univ)
        target = np.full(NUM_CHANNELS, 200, dtype=np.uint8)

        engine.go(target, duration=0.1)

        # Wait for fade to complete
        time.sleep(0.15)
        still_fading = engine.tick()

        assert not still_fading
        assert not engine.is_fading
        assert univ[0] == 200

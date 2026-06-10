import time
from unittest.mock import MagicMock

import pytest
from olc.core.dmxloop import DMXLoop


class TestDMXLoop:
    """Test suite for DMXLoop."""

    def test_initial_state(self) -> None:
        """Test default metrics before starting."""
        mock_send = MagicMock()
        loop = DMXLoop(send_fn=mock_send, hz=40)

        assert not loop.is_running
        assert loop.frame_count == 0
        assert loop.late_count == 0
        assert loop.last_jitter == 0.0
        assert loop.effective_hz == 0.0
        assert loop.windowed_hz is None

        # Should not raise any error if __repr__ is called
        repr_str = repr(loop)
        assert "stopped" in repr_str

    def test_start_stop(self) -> None:
        """Test manual start and stop logic."""
        mock_send = MagicMock()
        loop = DMXLoop(send_fn=mock_send, hz=40)

        loop.start()
        assert loop.is_running is True

        loop.stop()
        assert loop.is_running is False

    def test_context_manager(self) -> None:
        """Test starting and stopping via context manager."""
        mock_send = MagicMock()

        with DMXLoop(send_fn=mock_send, hz=40) as loop:
            assert loop.is_running is True

        assert loop.is_running is False

    def test_double_start(self) -> None:
        """Test safety against starting an already running loop."""
        mock_send = MagicMock()
        loop = DMXLoop(send_fn=mock_send, hz=40)

        loop.start()
        try:
            with pytest.raises(RuntimeError, match="DMXLoop is already running."):
                loop.start()
        finally:
            loop.stop()

    def test_execution_frequency(self) -> None:
        """Test real periodic execution with a tolerance."""
        mock_send = MagicMock()
        # High Hz to get multiple frames quickly
        loop = DMXLoop(send_fn=mock_send, hz=100)

        loop.start()
        # Sleep for exactly 0.1s. At 100Hz, we expect ~10 frames.
        # Allow a tolerance [5, 15] to avoid flaky tests on CI.
        time.sleep(0.1)
        loop.stop()

        call_count = mock_send.call_count
        assert 5 <= call_count <= 15, f"Expected ~10 frames, got {call_count}"
        assert loop.frame_count == call_count

    def test_metrics_and_windowed_hz(self) -> None:
        """Test windowed_hz and metrics calculation with a short window."""
        mock_send = MagicMock()
        # Set a very small window (0.05s) to quickly fill it up
        loop = DMXLoop(send_fn=mock_send, hz=100, window_seconds=0.05)

        loop.start()
        # Sleep for 0.1s to ensure the 0.05s window is completely filled
        # and old frames are purged
        time.sleep(0.1)

        # Capture metrics before stopping
        eff_hz = loop.effective_hz
        win_hz = loop.windowed_hz

        loop.stop()

        assert eff_hz > 0
        assert win_hz is not None
        # Should be roughly 100Hz. Tolerance [50, 150] for CI stability.
        assert 50 <= win_hz <= 150, f"Expected ~100Hz, got {win_hz}"

        # Check __repr__ output with active window
        repr_str = repr(loop)
        assert "Hz total" in repr_str

    def test_restart(self) -> None:
        """Test starting, stopping, and starting again."""
        mock_send = MagicMock()
        loop = DMXLoop(send_fn=mock_send, hz=100)

        # First run
        loop.start()
        time.sleep(0.05)
        loop.stop()
        count_first = loop.frame_count
        assert count_first > 0

        # Second run
        loop.start()
        time.sleep(0.05)
        loop.stop()

        # The local counter is reset, but mock_send continues to increment
        assert loop.frame_count > 0
        assert mock_send.call_count > count_first

    def test_stop_without_start(self) -> None:
        """Test stopping a loop that was never started."""
        mock_send = MagicMock()
        loop = DMXLoop(send_fn=mock_send, hz=40)
        # Should not raise any exception
        loop.stop()
        assert not loop.is_running

    def test_late_count(self) -> None:
        """Test that slow send_fn increments late_count."""

        def slow_send() -> None:
            # Target period = 10ms (100Hz).
            # We simulate a network send that drags on (30ms).
            time.sleep(0.03)

        loop = DMXLoop(send_fn=slow_send, hz=100)
        loop.start()
        time.sleep(0.1)
        loop.stop()

        # Since the function takes 30ms for a 10ms period,
        # jitter will accumulate and late_count should explode.
        assert loop.late_count > 0

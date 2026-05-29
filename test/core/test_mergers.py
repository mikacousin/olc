import time

import numpy as np
from olc.core.mergers import HTPMerger, LTPMerger
from olc.core.universe_data import NUM_CHANNELS


class TestHTPMerger:
    """Test suite for Highest Takes Precedence merger."""

    def test_htp_merger(self) -> None:
        """Test HTP logic with multiple sources."""
        merger = HTPMerger(num_sources=3)

        merger.write(0, {10: 100, 20: 50})
        merger.write(1, {10: 50, 20: 200, 30: 255})
        merger.write(2, {10: 150})

        out = merger.get_output()

        assert out[10] == 150  # Max between 100, 50, 150
        assert out[20] == 200  # Max between 50, 200, 0
        assert out[30] == 255  # Max between 0, 255, 0
        assert out[0] == 0

    def test_htp_write_universe_and_out_buffer(self) -> None:
        """Test writing full array and outputting to an existing buffer."""
        merger = HTPMerger(num_sources=2)

        arr1 = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        arr1[5] = 100
        merger.write_universe(0, arr1)

        arr2 = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        arr2[5] = 50
        arr2[6] = 200
        merger.write_universe(1, arr2)

        out_buffer = np.zeros(NUM_CHANNELS, dtype=np.uint8)
        result = merger.get_output(out=out_buffer)

        assert result is out_buffer
        assert out_buffer[5] == 100
        assert out_buffer[6] == 200


class TestLTPMerger:
    """Test suite for Latest Takes Precedence merger."""

    def test_ltp_merger(self) -> None:
        """Test LTP logic with multiple sources and timestamps."""
        merger = LTPMerger(num_sources=2)

        merger.write(0, {10: 100, 20: 50})
        # Slight delay to ensure monotonic clock ticks
        time.sleep(0.01)

        merger.write(1, {10: 50, 30: 255})

        out = merger.get_output()

        # Channel 10: source 0 wrote 100, then source 1 wrote 50 -> 50 wins
        assert out[10] == 50
        # Channel 20: only source 0 wrote 50 -> 50 wins
        assert out[20] == 50
        # Channel 30: only source 1 wrote 255 -> 255 wins
        assert out[30] == 255

    def test_ltp_write_universe(self) -> None:
        """Test writing full array updates timestamps for all channels."""
        merger = LTPMerger(num_sources=2)

        arr0 = np.full(NUM_CHANNELS, 100, dtype=np.uint8)
        merger.write_universe(0, arr0)

        time.sleep(0.01)

        # Source 1 writes a single channel
        merger.write(1, {5: 200})

        out = merger.get_output()

        assert out[0] == 100
        assert out[5] == 200
        assert out[10] == 100

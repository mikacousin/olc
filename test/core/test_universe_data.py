import numpy as np
from olc.core.universe_data import NUM_CHANNELS, DMXUniverse


class TestDMXUniverse:
    """Test suite for DMXUniverse logic."""

    def test_init(self) -> None:
        """Test default values."""
        univ = DMXUniverse(1)
        assert univ.universe_id == 1
        assert len(univ.array) == NUM_CHANNELS
        assert univ.array.dtype == np.uint8
        assert np.all(univ.array == 0)

    def test_getitem_setitem(self) -> None:
        """Test basic access method with clipping."""
        univ = DMXUniverse()
        univ[0] = 255
        assert univ[0] == 255
        assert univ[0] == 255
        # Test clipping
        univ[1] = 300
        assert univ[1] == 255
        univ[2] = -50
        assert univ[2] == 0

    def test_set_channels(self) -> None:
        """Test batch channel update."""
        univ = DMXUniverse()
        univ.set_channels({10: 128, 20: 255})
        assert univ[10] == 128
        assert univ[20] == 255
        assert univ[0] == 0

    def test_apply_array_and_blackout(self) -> None:
        """Test bulk operations."""
        univ = DMXUniverse()
        arr = np.full(NUM_CHANNELS, 100, dtype=np.uint8)
        univ.apply_array(arr)
        assert univ[0] == 100
        assert univ[511] == 100

        univ.blackout()
        assert univ[0] == 0
        assert univ[511] == 0

    def test_snapshot_and_diff(self) -> None:
        """Test snapshot creation and difference calculation."""
        univ = DMXUniverse()
        univ[5] = 200
        snap = univ.snapshot()
        assert snap[5] == 200
        assert snap is not univ.array
        univ[5] = 0
        univ[10] = 255
        diff_indices = univ.diff(snap)
        # Channels 5 and 10 are different now
        assert len(diff_indices) == 2
        assert 5 in diff_indices
        assert 10 in diff_indices

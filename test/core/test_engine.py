import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from olc.core.engine import CoreEngine
from olc.core.universe_config import Protocol, UniverseMap


def _make_engine(num_universes: int = 4, hz: float = 100.0) -> CoreEngine:
    """Helper: create a CoreEngine with a plain UniverseMap (no senders)."""
    umap = UniverseMap(num_universes)
    return CoreEngine(umap, hz=hz)


class TestCoreEngineBuild:
    """Test construction and slot initialization."""

    def test_build_no_protocols(self) -> None:
        """Universes with no protocols have empty sender lists."""
        engine = _make_engine(4)
        for uid in range(4):
            assert engine._slots[uid].senders == []  # pylint: disable=protected-access

    def test_build_unknown_universe_raises(self) -> None:
        """Accessing a universe not in the map raises KeyError."""
        engine = _make_engine(2)
        with pytest.raises(KeyError):
            engine.universe(99)

    def test_build_artnet_creates_sender(self) -> None:
        """Enabling Art-Net on a universe creates an ArtNetSender."""
        umap = UniverseMap(4)
        umap.enable_protocol(1, Protocol.ARTNET)
        print(umap)
        engine = CoreEngine(umap)
        assert len(engine._slots[1].senders) == 1  # pylint: disable=protected-access

    def test_build_no_senders_by_default(self) -> None:
        """Universe 0 has no senders when no protocols are active."""
        umap = UniverseMap(4)
        engine = CoreEngine(umap)
        assert engine._slots[0].senders == []  # pylint: disable=protected-access


class TestCoreEngineLifecycle:
    """Test start, stop, context manager, and restart."""

    def test_start_stop(self) -> None:
        """start() and stop() control the loop properly."""
        engine = _make_engine()
        engine.start()
        assert engine.is_running
        engine.stop()
        assert not engine.is_running

    def test_context_manager(self) -> None:
        """Context manager starts and stops the loop automatically."""
        with _make_engine() as engine:
            assert engine.is_running
        assert not engine.is_running

    def test_restart(self) -> None:
        """Engine can be restarted after being stopped."""
        engine = _make_engine()
        engine.start()
        engine.stop()
        engine.start()
        assert engine.is_running
        engine.stop()


class TestCoreEngineDataOps:
    """Test DMX data operations: blackout, set_channels."""

    def test_blackout(self) -> None:
        """blackout() zeros the universe buffer."""
        engine = _make_engine()
        engine.set_channels(0, {0: 255, 100: 128})
        engine.blackout(0)
        assert engine.universe(0)[0] == 0
        assert engine.universe(0)[100] == 0

    def test_set_channels(self) -> None:
        """set_channels() writes values to the correct universe."""
        engine = _make_engine()
        engine.set_channels(1, {10: 200, 20: 50})
        assert engine.universe(1)[10] == 200
        assert engine.universe(1)[20] == 50
        # Other universes untouched
        assert engine.universe(0)[10] == 0

    def test_set_channels_wrong_universe(self) -> None:
        """set_channels() on unknown universe raises KeyError."""
        engine = _make_engine(2)
        with pytest.raises(KeyError):
            engine.set_channels(99, {0: 255})


class TestCoreEngineMergers:
    """Test optional HTP and LTP merger integration."""

    def test_htp_write_without_merger_raises(self) -> None:
        """htp_write() raises RuntimeError when no HTPMerger is attached."""
        engine = _make_engine()
        with pytest.raises(RuntimeError):
            engine._htp_write(0, 0, {10: 100})

    def test_htp_write_with_merger(self) -> None:
        """HTP merge produces the highest value in the buffer."""
        engine = _make_engine()
        engine._add_htp_merger(0, num_sources=2)
        engine._htp_write(0, 0, {10: 100})
        engine._htp_write(0, 1, {10: 200})
        assert engine.universe(0)[10] == 200

    def test_ltp_write_without_merger_raises(self) -> None:
        """ltp_write() raises RuntimeError when no LTPMerger is attached."""
        engine = _make_engine()
        with pytest.raises(RuntimeError):
            engine._ltp_write(0, 0, {10: 100})

    def test_ltp_write_with_merger(self) -> None:
        """LTP merge produces the most recently written value in the buffer."""
        engine = _make_engine()
        engine._add_ltp_merger(0, num_sources=2)
        engine._ltp_write(0, 0, {10: 100})
        time.sleep(0.01)
        engine._ltp_write(0, 1, {10: 50})
        # Source 1 wrote last -> 50 wins
        assert engine.universe(0)[10] == 50


class TestCoreEngineSenders:
    """Test that senders are called on every tick."""

    def test_senders_called_each_tick(self) -> None:
        """Mock senders receive send() calls on each loop tick."""
        umap = UniverseMap(2)
        engine = CoreEngine(umap, hz=100.0)

        mock_sender = MagicMock()
        engine._slots[0].senders = [mock_sender]  # pylint: disable=protected-access

        engine.start()
        time.sleep(0.05)
        engine.stop()

        assert mock_sender.send.call_count > 0

    def test_reload_universe_rebuilds_senders(self) -> None:
        """reload_universe() rebuilds senders after protocol change."""
        umap = UniverseMap(4)
        engine = CoreEngine(umap)

        # No senders initially
        assert engine._slots[1].senders == []  # pylint: disable=protected-access

        # Activate Art-Net, then reload
        umap.enable_protocol(1, Protocol.ARTNET)
        engine.reload_universe(1)

        assert len(engine._slots[1].senders) == 1  # pylint: disable=protected-access


class TestCoreEngineMetrics:
    """Test metrics delegated from DMXLoop."""

    def test_frame_count_increases(self) -> None:
        """frame_count grows while the engine is running."""
        engine = _make_engine(hz=200.0)
        engine.start()
        time.sleep(0.05)
        engine.stop()
        assert engine.frame_count > 0

    def test_effective_hz_reasonable(self) -> None:
        """effective_hz is in a reasonable range."""
        engine = _make_engine(hz=100.0)
        engine.start()
        time.sleep(0.1)
        engine.stop()
        assert 50 <= engine.effective_hz <= 150


class TestCoreEngineOSError:  # pylint: disable=too-few-public-methods
    """Test that OSError from senders does not crash the loop."""

    def test_sender_oserror_is_swallowed(self) -> None:
        """A sender that raises OSError must not stop the loop."""
        umap = UniverseMap(2)
        engine = CoreEngine(umap, hz=100.0)

        bad_sender = MagicMock()
        bad_sender.send.side_effect = OSError("Network unreachable")
        engine._slots[0].senders = [bad_sender]  # pylint: disable=protected-access

        engine.start()
        time.sleep(0.05)
        engine.stop()

        assert not engine.is_running
        assert bad_sender.send.call_count > 0


# Needed to allow patching for potential future use of socket
with patch("socket.socket"):
    pass


class TestCoreEngineZMQ:
    """Test optional ZeroMQ monitoring publisher."""

    @patch("zmq.Context")
    def test_zmq_pub_created(self, mock_zmq_context: MagicMock) -> None:
        """CoreEngine creates a ZeroMQ PUB socket if monitor_port is provided."""
        mock_ctx_instance = mock_zmq_context.return_value
        mock_socket = MagicMock()
        mock_ctx_instance.socket.return_value = mock_socket

        umap = UniverseMap(2)
        engine = CoreEngine(umap, monitor_port=5555)

        # socket created and bound
        mock_ctx_instance.socket.assert_called_once()
        mock_socket.bind.assert_called_once_with("tcp://127.0.0.1:5555")

        # Context and socket cleaned up on stop
        engine.stop()
        mock_socket.close.assert_called_once()
        mock_ctx_instance.term.assert_called_once()

    @patch("zmq.Context")
    def test_zmq_publish_throttled(self, mock_zmq_context: MagicMock) -> None:
        """ZeroMQ messages are sent at the specified fps, not on every tick."""
        mock_ctx_instance = mock_zmq_context.return_value
        mock_socket = MagicMock()
        mock_ctx_instance.socket.return_value = mock_socket

        umap = UniverseMap(1)
        # engine runs at 100hz, monitor at 10fps
        engine = CoreEngine(umap, hz=100.0, monitor_port=5555, monitor_fps=10.0)

        engine.start()
        # Sleep for ~0.2 seconds. Loop runs ~20 times. Monitor should run ~2 times.
        time.sleep(0.25)
        engine.stop()

        # Should be called around 2-3 times, definitely not 20 times.
        assert 1 <= mock_socket.send_multipart.call_count <= 4

    @patch("zmq.Context")
    def test_zmq_pub_bind_failure(self, mock_zmq_context: MagicMock) -> None:
        """CoreEngine does not crash if ZeroMQ bind fails."""
        mock_ctx_instance = mock_zmq_context.return_value
        mock_socket = MagicMock()
        mock_socket.bind.side_effect = Exception("Address already in use")
        mock_ctx_instance.socket.return_value = mock_socket

        umap = UniverseMap(2)
        # Should not raise exception
        engine = CoreEngine(umap, monitor_port=5555)

        # Publisher and context should be None
        assert engine._zmq_pub is None
        assert engine._zmq_ctx is None

        engine.stop()


class TestCoreEngineNoTransmit:
    """Test suite for the no_transmit passive (listen-only) monitor mode."""

    def test_no_transmit_senders_and_loop(self) -> None:
        """Passive engine must not build senders or start the transmit loop."""
        umap = UniverseMap(4)
        umap.enable_protocol(1, Protocol.SACN)
        umap.enable_protocol(2, Protocol.ARTNET)

        engine = CoreEngine(umap, hz=100.0, no_transmit=True)

        # Verify no senders are built in slots
        assert engine._slots[1].senders == []  # pylint: disable=protected-access
        assert engine._slots[2].senders == []  # pylint: disable=protected-access

        # Verify SacnManager got the no_transmit flag
        assert engine._sacn_manager._no_transmit  # pylint: disable=protected-access
        # Verify no sACN senders were instantiated
        assert engine._sacn_manager.senders == {}

        # Start the engine, wait, and check that no frames were transmitted
        engine.start()
        time.sleep(0.05)
        engine.stop()

        assert engine.frame_count == 0

    def test_no_transmit_reload_universe(self) -> None:
        """reload_universe() must not build senders when no_transmit is enabled."""
        umap = UniverseMap(4)
        engine = CoreEngine(umap, no_transmit=True)

        umap.enable_protocol(1, Protocol.SACN)
        engine.reload_universe(1)

        assert engine._slots[1].senders == []  # pylint: disable=protected-access
        assert engine._sacn_manager.senders == {}


class TestCoreEngineNoListen:
    """Test suite for the no_listen passive (listening disabled) mode."""

    def test_no_listen_starts_managers(self) -> None:
        """CoreEngine.start() starts backends even with no_listen=True."""
        umap = UniverseMap(4)
        umap.enable_protocol(1, Protocol.SACN)
        umap.enable_protocol(2, Protocol.ARTNET)

        engine = CoreEngine(umap, no_listen=True)

        mock_sacn_manager = MagicMock()
        mock_artnet_manager = MagicMock()
        engine._sacn_manager = mock_sacn_manager
        engine._artnet_manager = mock_artnet_manager

        engine.start()

        mock_sacn_manager.start.assert_called_once()
        mock_artnet_manager.start.assert_called_once()

        engine.stop()

    def test_no_listen_discards_incoming_dmx(self) -> None:
        """Callbacks discard incoming DMX data if no_listen=True."""
        umap = UniverseMap(4)
        umap.enable_protocol(1, Protocol.SACN)
        umap.enable_protocol(2, Protocol.ARTNET)

        engine = CoreEngine(umap, no_listen=True)

        # Trigger callbacks with dummy data
        data = [255] * 512
        engine._on_sacn_dmx_received(1, data)
        engine._on_artnet_dmx_received(2, data)

        # Universe array should remain untouched (all zeros)
        assert np.all(engine.universe(1).array == 0)
        assert np.all(engine.universe(2).array == 0)

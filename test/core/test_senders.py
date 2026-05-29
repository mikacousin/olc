import struct
import sys
from unittest.mock import MagicMock, patch

from olc.core.senders import (
    ARTNET_PORT,
    SACN_PORT,
    ArtNetSender,
    SACNSender,
    _build_artnet_header,
    _build_sacn_buffers,
    _sacn_multicast_ip,
)
from olc.core.universe_data import DMXUniverse


class TestArtNetHeader:
    """Test suite for the Art-Net header builder."""

    def test_header_length(self) -> None:
        """The ArtDmx header must be exactly 18 bytes."""
        header = _build_artnet_header(sequence=1, universe=0)
        assert len(header) == 18

    def test_header_magic(self) -> None:
        """The header must start with the Art-Net magic string."""
        header = _build_artnet_header(sequence=1, universe=0)
        assert header[:8] == b"Art-Net\x00"

    def test_sequence_wraps_at_256(self) -> None:
        """Sequence byte must be masked to 0xFF."""
        header = _build_artnet_header(sequence=256, universe=0)
        # Sequence byte is at offset 12
        assert header[12] == 0

    def test_universe_encoding(self) -> None:
        """Universe must be encoded as LE uint16 at offset 14."""
        header = _build_artnet_header(sequence=1, universe=3)
        universe_le = struct.unpack_from("<H", header, 14)[0]
        assert universe_le == 3


class TestArtNetSender:
    """Test suite for the ArtNetSender."""

    def test_send_calls_socket(self) -> None:
        """send() must transmit data via the socket."""
        with patch("socket.socket") as mock_sock_class:
            mock_sock = MagicMock()
            mock_sock_class.return_value = mock_sock
            # Disable send-msg to force the send-to fallback path (cross-platform)
            mock_sock.sendmsg = MagicMock(side_effect=AttributeError)

            sender = ArtNetSender(ip="127.0.0.1", universe=0)
            univ = DMXUniverse()
            univ[0] = 100

            # Patch _HAS_SENDMSG to force the fallback path
            with patch("olc.core.senders._HAS_SENDMSG", False):
                sender.send(univ)

            mock_sock.sendto.assert_called_once()
            args = mock_sock.sendto.call_args[0]
            # First argument is the raw bytes, second is (ip, port)
            assert args[1] == ("127.0.0.1", ARTNET_PORT)

    def test_sequence_increments(self) -> None:
        """Sequence counter must increment on each send call."""
        with patch("socket.socket"):
            with patch("olc.core.senders._HAS_SENDMSG", False):
                sender = ArtNetSender(ip="127.0.0.1")
                univ = DMXUniverse()
                sender._sock = MagicMock()  # pylint: disable=protected-access

                for i in range(1, 4):
                    sender.send(univ)
                    assert sender._sequence == i  # pylint: disable=protected-access

    def test_sequence_wraps(self) -> None:
        """Sequence counter must wrap around at 256."""
        with patch("socket.socket"):
            sender = ArtNetSender(ip="127.0.0.1")
            sender._sock = MagicMock()  # pylint: disable=protected-access
            sender._sequence = 255  # pylint: disable=protected-access

            with patch("olc.core.senders._HAS_SENDMSG", False):
                sender.send(DMXUniverse())

            assert sender._sequence == 0  # pylint: disable=protected-access


class TestSACNHelpers:
    """Test suite for sACN helper functions."""

    def test_multicast_ip_universe_1(self) -> None:
        """Universe 1 must map to 239.255.0.1."""
        assert _sacn_multicast_ip(1) == "239.255.0.1"

    def test_multicast_ip_universe_256(self) -> None:
        """Universe 256 must map to 239.255.1.0."""
        assert _sacn_multicast_ip(256) == "239.255.1.0"

    def test_sacn_buffers_payload_is_memoryview(self) -> None:
        """The last buffer must be the raw memory view (no copy)."""
        univ = DMXUniverse()
        buffers = _build_sacn_buffers(
            cid=b"\x00" * 16,
            source="test",
            universe=1,
            sequence=1,
            priority=100,
            payload=univ.view,
        )
        assert isinstance(buffers[-1], memoryview)


class TestSACNSender:  # pylint: disable=too-few-public-methods
    """Test suite for the SACNSender."""

    def test_send_calls_socket(self) -> None:
        """send() must transmit data via the socket."""
        with patch("socket.socket") as mock_sock_class:
            mock_sock = MagicMock()
            mock_sock_class.return_value = mock_sock

            sender = SACNSender(universe=1, multicast=False, ip="127.0.0.1")
            univ = DMXUniverse()

            with patch("olc.core.senders._HAS_SENDMSG", False):
                sender.send(univ)

            mock_sock.sendto.assert_called_once()
            args = mock_sock.sendto.call_args[0]
            assert args[1] == ("127.0.0.1", SACN_PORT)


# Run send-msg path only on non-Windows platforms
if sys.platform != "win32":
    class TestSendmsgPath:  # pylint: disable=too-few-public-methods
        """Test the send-msg (zero-copy) path on Linux/macOS."""

        def test_artnet_sendmsg(self) -> None:
            """send-msg must be called with two buffers: header + memory view."""
            with patch("socket.socket") as mock_sock_class:
                mock_sock = MagicMock()
                mock_sock_class.return_value = mock_sock

                sender = ArtNetSender(ip="127.0.0.1")
                sender._sock = mock_sock  # pylint: disable=protected-access
                univ = DMXUniverse()

                with patch("olc.core.senders._HAS_SENDMSG", True):
                    sender.send(univ)

                mock_sock.sendmsg.assert_called_once()
                buffers = mock_sock.sendmsg.call_args[0][0]
                assert len(buffers) == 2
                assert isinstance(buffers[1], memoryview)

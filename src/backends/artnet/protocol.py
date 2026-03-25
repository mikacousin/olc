# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
import ipaddress
import itertools
from enum import IntEnum
from struct import pack, unpack

HEADER = b"Art-Net\x00"
PORT = 6454  # 0x1936


class ArtNetDecodeError(Exception):
    """Exception raised when an Art-Net packet is corrupted or malformed."""


class ArtNetSequenceError(Exception):
    """Exception raised when an ArtDmx packet arrives in the wrong order."""


class OpCodes(IntEnum):
    """Legal OpCode values used in Art-Net packets"""

    OP_POLL = 0x2000  # ArtPoll packet, no other data is contained in this UDP packet
    OP_POLL_REPLY = 0x2100  # ArtPollReply, contains device status information
    OP_DIAG_DATA = 0x2300  # Diagnostics and data logging packet
    OP_COMMAND = 0x2400  # ArtCommand, it is used to send text based parameter command
    OP_DATA_REQUEST = 0x2700  # ArtDataRequest, to request data such as products URLs
    OP_DATA_REPLY = 0x2800  # ArtDataReply, used to reply to ArtDataRequest packets
    OP_DMX = 0x5000  # ArtDmx, it contains zero start code DMX512 information for a
    #                  single Universe
    OP_NZS = 0x5100  # ArtNzs, contains non-zero start code (except RDM) DMX512
    #                  information for a single Universe
    OP_SYNC = 0x5200  # ArtSync, used to force synchronous transfer of ArtDmx packets
    #                   to a node's output
    OP_ADDRESS = 0x6000  # ArtAdress, contains remote programming information for a node
    OP_INPUT = 0x7000  # ArtInput, contains enable - disable data for DMX inputs
    OP_TOD_REQUEST = 0x8000  # ArtTodRequest, used to request a Table of Devices (ToD)
    #                          for RDM discovery
    OP_TOD_DATA = 0x8100  # ArtTodData, used to send a Table of Devices (ToD) for
    #                       RDM discovery
    OP_TOD_CONTROL = 0x8200  # ArtTodControl, used to send RDM discovery control
    #                          messages
    OP_RDM = 0x8300  # ArtRdm, used to send all non discovery RDM messages
    OP_RDM_SUB = 0x8400  # ArtRdmSub, used to send compressed, RDM Sub-Device data
    OP_VIDEO_SETUP = 0xA010  # ArtVideoSetup, contains video screen setup information
    #                          for nodes that implement the extended video features
    OP_VIDEO_PALETTE = 0xA020  # ArtVideoPalette, contains color palette setup
    #                            information for nodes that implement the extended
    #                            video features
    OP_VIDEO_DATA = 0xA040  # ArtVideoData, contains display data for nodes that
    #                         implement extended video features
    OP_MAC_MASTER = 0xF000  # This packet is deprecated
    OP_MAC_SLAVE = 0xF100  # This packet is deprecated
    OP_FIRMWARE_MASTER = 0xF200  # ArtFirmwareMaster, used to upload new firmware or
    #                              firmware extensions to the Node
    OP_FIRMWARE_REPLY = 0xF300  # ArtFirmwareReply, returned by the node to acknowledge
    #                             receipt of an ArtFirmwareMaster packet or
    #                             ArtFileTnMaster packet
    OP_FILE_TN_MASTER = 0xF400  # Uploads user file to node
    OP_FILE_FN_MASTER = 0xF500  # Downloads user file from node
    OP_FILE_FN_REPLAY = 0xF600  # Server to Node acknowledge for download packets
    OP_IP_PROG = 0xF800  # ArtIpProg, used to reprogram the IP address and Mask of the
    #                      Node
    OP_IP_PROG_REPLY = 0xF900  # ArtIpProgReply, returned by the node to acknowledge
    #                            receipt of an ArtIpProg packet
    OP_MEDIA = 0x9000  # ArtMedia, it is Unicast by a Media Server and acted upon by
    #                    a Controller
    OP_MEDIA_PATCH = 0x9100  # ArtMediaPatch, it is Unicast by a Controller and acted
    #                          upon by a Media Server
    OP_MEDIA_CONTROL = 0x9200  # ArtMediaControl, it is Unicast by a Controller and
    #                            acted upon by a Media Server
    OP_MEDIA_CONTRL_REPLY = 0x9300  # ArtMediaControlReply, it is Unicast by a Media
    #                                 Server and acted upon by a Controller
    OP_TIMECODE = 0x9700  # ArtTimeCode, used to transport time code over the network
    OP_TIME_SYNC = 0x9800  # Used to synchronize real time date and clock
    OP_TRIGGER = 0x9900  # Used to send trigger macros
    OP_DIRECTORY = 0x9A00  # Requests a node's file list
    OP_DIRECTORY_REPLY = 0x9B00  # Replies to OpDirectory with file list


class PriorityCodes(IntEnum):
    """Diagnostics Priority Codes.
    These are used in ArtPoll and ArtDiagData.
    """

    DP_LOW = 0x10  # Low priority message
    DP_MED = 0x40  # Medium priority message
    DP_HIGH = 0x80  # High priority message
    DP_CRITICAL = 0xE0  # Critical priority message
    DP_VOLATILE = 0xF0  # Volatile message


class NodeReport(IntEnum):
    """The NodeReport code defines generic error, advisory and status messages for
    both Nodes and Controllers.
    The NodeReport is returned in ArtPollReply.
    """

    RC_DEBUG = 0x0000  # Booted in debug mode (only used in development)
    RC_POWER_OK = 0x0001  # Power On Tests successful
    RC_POWER_FAIL = 0x0002  # Hardware tests failed at Power On
    RC_SOCKET_WR1 = 0x0003  # Last UDP from Node failed due to truncated length,
    #                         Most likely caused by a collision
    RC_PARSE_FAIL = 0x0004  # Unable to identify last UDP transmission. Check
    #                         OpCode and packet length
    RC_UDP_FAIL = 0x0005  # Unable to open UDP socket in last transmission attempt
    RC_SH_NAME_OK = 0x0006  # Confirms that Port Name programming via ArtAddress
    #                         was successful
    RC_LO_NAME_OK = 0x0007  # Confirms that Long Name programming via ArtAddress was
    #                        successful
    RC_DMX_ERROR = 0x0008  # DMX512 receive errors detected
    RC_DMX_UDP_FULL = 0x0009  # Ran out of internal DMX transmit buffers
    RC_DMX_RX_FULL = 0x000A  # Ran out of internal DMX Rx buffers
    RC_SWITCH_ERR = 0x000B  # Rx Universe switches conflict
    RC_CONFIG_ERR = 0x000C  # Product configuration does not match firmware
    RC_DMX_SHORT = 0x000D  # DMX output short detected. See GoodOutput field
    RC_FIRMWARE_FAIL = 0x000E  # Last attempt to upload new firmware failed
    RC_USER_FAIL = 0x000F  # User changed switch settings when address locked by
    #                        remote programming. User changed ignored
    RC_FACTORY_RES = 0x0010  # Factory reset has occurred


class StyleCodes(IntEnum):
    """The Style code defines the general functionality of a Controller.
    The Style code is returned in ArtPollReply.
    """

    ST_NODE = 0x00  # A DMX to / from Art-Net device
    ST_CONTROLLER = 0x01  # A lighting console
    ST_MEDIA = 0x02  # A media server
    ST_ROUTE = 0x03  # A network routing device
    ST_BACKUP = 0x04  # A backup device
    ST_CONFIG = 0x05  # A configuration or diagnostic tool
    ST_VISUAL = 0x06  # A visualizer


# pylint: disable=too-few-public-methods
class PacketTracker:
    """Track ArtDmx packets order"""

    previous_seq: int | None
    lost_packets: int
    total_received: int
    total_expected: int
    alert_threshold: float
    consecutive_disordered: int

    def __init__(self, alert_threshold: float = 10.0) -> None:
        self.previous_seq = None
        self.lost_packets = 0
        self.total_received = 0
        self.total_expected = 0
        self.consecutive_disordered = 0
        self.alert_threshold = alert_threshold

    def process_packet(self, current_seq: int) -> bool:
        """Processes a packet, considering out-of-order sequence numbers,
        and calculates losses.

        Args:
            current_seq: Current packet sequence (between 1 and 255)

        Returns:
            True if the packet is used, False if it is ignored
        """
        self.total_received += 1

        if self.previous_seq is not None:
            diff = (current_seq - self.previous_seq) % 255

            if diff == 0 or diff > 127:
                # Ignore the disordered or duplicated packet
                self.consecutive_disordered += 1
                if self.consecutive_disordered > 5:
                    # Sender reset or massive drop: force resync
                    self.previous_seq = current_seq
                    self.consecutive_disordered = 0
                return False

            self.consecutive_disordered = 0

            # Calculate the number of packets lost between the two sequences
            if diff > 1:
                self.lost_packets += diff - 1

            self.total_expected += diff

        else:
            # First packet received
            self.total_expected = 1
            self.consecutive_disordered = 0

        self.previous_seq = current_seq

        # Fast decay to avoid infinite historical memory
        # (roughly 1 to 2.5 seconds history at 40fps)
        if self.total_expected >= 100:
            self.total_expected //= 2
            self.lost_packets //= 2

        self._check_alert()

        return True

    def _check_alert(self) -> None:
        """Checks whether the loss rate exceeds the defined threshold
        and triggers an alert."""
        if self.total_expected == 0:
            loss_rate = 0.0
        else:
            loss_rate = (self.lost_packets / self.total_expected) * 100
        if loss_rate > self.alert_threshold:
            print(
                f"[WARNING] High loss rate : {loss_rate:.2f}% "
                f"[(threshold : {self.alert_threshold}%)"
            )


class ArtCommon:
    """Base Art-Net packet"""

    protocol_version: int
    opcode: int | None
    min_length: int

    def __init__(self) -> None:
        self.protocol_version = 14  # 0X00E
        self.opcode = None
        self.min_length = 8

    def is_valid(self, packet: bytes) -> bool:
        """Test if it's a valid packet

        Args:
            packet: Raw data

        Returns:
            True if valid, else False
        """
        header, opcode = unpack("<8sH", packet[0:10])
        if header != HEADER or opcode != self.opcode:
            return False
        if len(packet) < self.min_length:
            return False
        return True


class ArtDmx(ArtCommon):
    """ArtDmx packet"""

    sequence: itertools.cycle
    universe: int
    data: list[int]
    tracker: PacketTracker

    def __init__(self) -> None:
        super().__init__()
        self.min_length = 20
        self.opcode = OpCodes.OP_DMX
        self.sequence = itertools.cycle(range(1, 256))
        self.universe = 0
        self.data = []
        self.tracker = PacketTracker(alert_threshold=10.0)

    def encode(self, universe: int, data: bytes) -> bytes:
        """Fill ArtDmx packet

        Args:
            universe: packet universe
            data: DMX data

        Returns:
            ArtDmx packet
        """
        packet = pack("8s", HEADER)
        packet += pack("<H", self.opcode)
        packet += pack(">H", self.protocol_version)
        packet += pack("B", next(self.sequence))
        packet += pack("B", 0)  # Physical input port
        subuni = universe & 0xFF
        net = universe >> 8
        packet += pack("B", subuni)  # SubUni
        packet += pack("B", net)  # Net
        packet += pack(">H", 512)  # Length
        packet += data
        return packet

    def decode(self, packet: bytes) -> None:
        """Interpret ArtDmx packet

        Args:
            packet: Raw data
        """
        if not self.is_valid(packet):
            raise ArtNetDecodeError("Invalid Art-Net header")

        protocol_version = unpack(">H", packet[10:12])[0]
        if protocol_version != self.protocol_version:
            raise ArtNetDecodeError(f"Bad Art-Net protocol version, {protocol_version}")

        sequence, _physical, subuni, net = unpack("4B", packet[12:16])
        self.sequence = sequence

        # Verify sequence number validity
        if not self.tracker.process_packet(sequence):
            raise ArtNetSequenceError(f"Ignored packet {self.sequence} (disordered).")

        self.universe = net << 8 | subuni
        length = unpack(">H", packet[16:18])[0]
        self.data = list(packet[18:])
        if length != len(self.data):
            raise ArtNetDecodeError(
                f"ArtDmx package corrupted, wrong length: "
                f"{len(self.data)} instead of {length}"
            )


class ArtPoll(ArtCommon):
    """ArtPoll packet"""

    flags: int
    diag_priority: PriorityCodes

    def __init__(self) -> None:
        super().__init__()
        self.min_length = 14
        self.opcode = OpCodes.OP_POLL
        self.flags = 0b00000010
        self.diag_priority = PriorityCodes.DP_LOW

    def encode(self) -> bytes:
        """Create ArtPoll packet

        Returns:
            ArtPoll packet
        """
        packet = pack("8s", HEADER)
        packet += pack("<H", self.opcode)
        packet += pack(">H", self.protocol_version)
        packet += pack(">B", self.flags)
        packet += pack(">B", self.diag_priority)
        return packet

    def decode(self, packet: bytes) -> None:
        """Interpret ArtPoll packet

        Args:
            packet: Raw data
        """
        if not self.is_valid(packet):
            raise ArtNetDecodeError("Invalid Art-Net header")

        protocol_version = unpack(">H", packet[10:12])[0]
        if protocol_version != self.protocol_version:
            raise ArtNetDecodeError(
                f"Art-Net protocol version too old: {protocol_version}"
            )


# pylint: disable=too-many-instance-attributes
class ArtPollReply(ArtCommon):
    """ArtPollReply packet"""

    ip: int
    firm_rev: int
    net_switch: int
    sub_switch: int
    oem: int
    ubea: int
    status: int
    esta: int
    port_name: str
    long_name: str
    node_report: str
    num_ports: int
    port_types: tuple[int, int, int, int]
    good_input: tuple[int, int, int, int]
    good_output_a: tuple[int, int, int, int]
    sw_in: tuple[int, ...]
    sw_out: tuple[int, int, int, int]
    acn_priority: int
    sw_macro: int
    sw_remote: int
    style: int
    mac: tuple[int, int, int, int, int, int]
    bind_ip: int
    bind_index: int
    status2: int
    good_output_b: tuple[int, int, int, int]
    status3: int
    default_resp_uid: tuple[int, int, int, int, int, int]
    user: int
    refresh_rate: int
    bg_queue_policy: int

    def __init__(self, universes: list[int]) -> None:
        super().__init__()
        self.min_length = 207
        self.opcode = OpCodes.OP_POLL_REPLY

        self.ip = 0
        self.firm_rev = 0
        self.net_switch = 0
        self.sub_switch = 0
        self.oem = 0xFFFF
        self.ubea = 0
        self.status = 0xC0
        self.esta = 0xFFFF
        self.port_name = ""
        self.long_name = ""
        self.node_report = ""
        self.num_ports = len(universes)
        self.port_types = (0x45, 0x45, 0x45, 0x45)
        self.good_input = (0, 0, 0, 0)
        self.good_output_a = (0x80, 0x80, 0x80, 0x80)
        univs = [0, 0, 0, 0]
        for index, univ in enumerate(universes[:4]):
            univs[index] = univ
        self.sw_in = tuple(univs)
        self.sw_out = (0, 0, 0, 0)
        self.acn_priority = 0
        self.sw_macro = 0
        self.sw_remote = 0
        self.style = 0
        self.mac = (0, 0, 0, 0, 0, 0)
        self.bind_ip = 0
        self.bind_index = 0
        self.status2 = 0
        self.good_output_b = (0, 0, 0, 0)
        self.status3 = 0
        self.default_resp_uid = (0, 0, 0, 0, 0, 0)
        self.user = 0
        self.refresh_rate = 0
        self.bg_queue_policy = 0

        self.counter = 0

    def encode(self, ip: str, mac: tuple[int, ...]) -> bytes:
        """Create ArtPollReply packet

        Args:
            ip: IP address
            mac: MAC address

        Returns:
            ArtPollReply packet
        """
        address = ipaddress.IPv4Address(ip)

        packet = pack("8s", HEADER)
        packet += pack("<H", self.opcode)
        packet += pack(">I", int(address))
        packet += pack("<H", PORT)
        packet += pack(">H", self.firm_rev)
        packet += pack("BB", self.net_switch, self.sub_switch)
        packet += pack(">H", self.oem)
        packet += pack("<BBH", self.ubea, self.status, self.esta)
        packet += pack("18s", b"olc")
        packet += pack("64s", b"Open Lighting Console")
        self.counter += 1
        if self.counter > 9999:
            self.counter = 0
        self.node_report = f"#0001 [{self.counter:04d}] OLC OK"
        packet += pack("64s", self.node_report.encode())
        packet += pack(">H", self.num_ports)
        self.port_types = (0x45, 0x45, 0x45, 0x45)  # 0b01000101
        packet += pack("4B", *self.port_types)
        packet += pack("4B", *self.good_input)
        packet += pack("4B", *self.good_output_a)
        packet += pack("4B", *self.sw_in)
        packet += pack("4B", *self.sw_out)
        packet += pack("3B", self.acn_priority, self.sw_macro, self.sw_remote)
        packet += pack("3B", 0, 0, 0)
        packet += pack("B", StyleCodes.ST_CONTROLLER)
        packet += pack("6B", *mac)
        packet += pack(">I", self.bind_ip)
        packet += pack("BB", self.bind_index, self.status2)
        packet += pack("4B", *self.good_output_b)
        packet += pack("B", self.status3)
        packet += pack("6B", *self.default_resp_uid)
        packet += pack(">HHB", self.user, self.refresh_rate, self.bg_queue_policy)
        packet += pack("10s", b"")

        return packet

    def decode(self, packet: bytes) -> None:
        """Interpret ArtPollReply packet

        Args:
            packet: Raw data
        """
        if not self.is_valid(packet):
            raise ArtNetDecodeError("Invalid Art-Net header")

        self.ip = unpack(">I", packet[10:14])[0]
        port = unpack("<H", packet[14:16])[0]
        self.firm_rev = unpack(">H", packet[16:18])[0]
        self.net_switch, self.sub_switch = unpack("<BB", packet[18:20])
        self.oem = unpack(">H", packet[20:22])[0]
        self.ubea, self.status, self.esta = unpack("<BBH", packet[22:26])
        self.port_name = unpack("18s", packet[26:44])[0].decode()
        if self.oem == 0x0190 and self.firm_rev == 0x0107:
            # Enttec Open DMX Ethernet sends LongName with a length of 20 instead of 64
            # And fill NodeReport with garbage...
            self.long_name = unpack("20s", packet[44:64])[0].decode()
            self.node_report = unpack("64s", packet[64:128])[0]
        else:
            self.long_name = unpack("64s", packet[44:108])[0].decode()
            self.node_report = unpack("64s", packet[108:172])[0].decode()
        self.num_ports = unpack(">H", packet[172:174])[0]
        self.port_types = unpack("4B", packet[174:178])
        self.good_input = unpack("4B", packet[178:182])
        self.good_output_a = unpack("4B", packet[182:186])
        self.sw_in = unpack("4B", packet[186:190])
        self.sw_out = unpack("4B", packet[190:194])
        self.acn_priority, self.sw_macro, self.sw_remote = unpack("3B", packet[194:197])
        # packet[197:200] : Spare, not used, set to zero
        self.style = packet[200]
        self.mac = unpack("6B", packet[201:207])

        self._decode_extended_fields(packet, len(packet))

        if port != PORT:
            print(f"ArtPollReply with Art-Net port {port}, must be {PORT}.")

    def _decode_extended_fields(self, packet: bytes, length: int) -> None:
        """Decode extended optional fields based on packet length."""
        if length >= 211:
            self.bind_ip = unpack(">I", packet[207:211])[0]
        if length >= 212:
            self.bind_index = packet[211]
        if length >= 213:
            self.status2 = packet[212]
        if length >= 217:
            self.good_output_b = unpack("4B", packet[213:217])
        if length >= 218:
            self.status3 = packet[217]
        if length >= 224:
            self.default_resp_uid = unpack("6B", packet[218:224])
        if length >= 226:
            self.user = unpack(">H", packet[224:226])[0]
        if length >= 228:
            self.refresh_rate = unpack(">H", packet[226:228])[0]
        if length >= 229:
            self.bg_queue_policy = packet[228]


def get_opcode(data: bytes) -> int:
    """Extract OpCode of Art-Net packet

    Args:
        data: Raw data

    Returns:
        OpCode
    """
    return unpack("<H", data[8:10])[0]


def get_universe(data: bytes) -> int:
    """Extract Universe of ArtDmx packet

    Args:
        data: Raw data

    Returns:
        Universe
    """
    subuni, net = unpack("2B", data[14:16])
    universe = net << 8 | subuni
    return universe

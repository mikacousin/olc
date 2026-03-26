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
from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable

from olc.backends.artnet.merge import ArtDmxMerger, MergeMode
from olc.backends.artnet.network import Network, get_ip_and_mac
from olc.backends.artnet.protocol import (
    PORT,
    ArtDmx,
    ArtNetDecodeError,
    ArtNetSequenceError,
    ArtPoll,
    ArtPollReply,
    OpCodes,
    StyleCodes,
    get_opcode,
    get_universe,
)
from olc.timer import RepeatedTimer

PORT_TYPES = {
    0: "DMX512",
    1: "Midi",
    2: "Avab",
    3: "Colortran CMX",
    4: "ADB 62.5",
    5: "Art-Net",
    6: "DALI",
}


class NodeUniverses:
    """Art-Net universes"""

    _types: tuple[int, ...]
    _net: int
    _sub: int
    _out: tuple[int, int, int, int]
    _in: tuple[int, int, int, int]

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        types: tuple[int, int, int, int] = (0, 0, 0, 0),
        net: int = 0,
        sub: int = 0,
        out_sw: tuple[int, int, int, int] = (0, 0, 0, 0),
        in_sw: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> None:
        self._types = types
        self._net = net
        self._sub = sub
        self._out = out_sw
        self._in = in_sw

    @property
    def output_universes(self) -> list[int]:
        """Gives universes the node takes from Art-Net to DMX (Outputs)."""
        universes = []
        for index, port in enumerate(self._types):
            if port:
                if port >> 7 & 1:
                    universe = (
                        ((self._net & 0x7F) << 8)
                        + ((self._sub & 0x0F) << 4)
                        + (self._out[index] & 0x0F)
                    )
                    universes.append(universe)
        return universes

    @property
    def input_universes(self) -> list[int]:
        """Gives universes the node sends from DMX to Art-Net (Inputs)."""
        universes = []
        for index, port in enumerate(self._types):
            if port:
                if port >> 6 & 1:
                    universe = (
                        ((self._net & 0x7F) << 8)
                        + ((self._sub & 0x0F) << 4)
                        + (self._in[index] & 0x0F)
                    )
                    universes.append(universe)
        return universes

    @property
    def universes(self) -> list[int]:
        """Union of all configured universes on this node."""
        return list(set(self.input_universes + self.output_universes))

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def set_universes(
        self,
        types: tuple[int, int, int, int],
        net: int,
        sub: int,
        out_sw: tuple[int, int, int, int],
        in_sw: tuple[int, int, int, int],
    ) -> None:
        """Store internal routing universes values.

        Args:
            types: Port types
            net: Net switch
            sub: Sub switch
            out: Port out switch
            in_sw: Port in switch
        """
        if self._types != types:
            self._types = types
        if self._net != net:
            self._net = net
        if self._sub != sub:
            self._sub = sub
        if self._out != out_sw:
            self._out = out_sw
        if self._in != in_sw:
            self._in = in_sw


class NodeNet:
    """Node IP and MAC addresses."""

    def __init__(
        self,
        ip: str = "",
        mac: tuple[int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0),
        notify: Callable | None = None,
    ) -> None:
        self._ip = ip
        self._mac = mac
        self.notify = notify

    @property
    def ip(self) -> str:
        """Get IP address."""
        return self._ip

    @ip.setter
    def ip(self, value: str) -> None:
        old_value = self._ip
        self._ip = value
        if old_value and old_value != value:
            if self.notify:
                self.notify("IP address", old_value, value)

    @property
    def mac(self) -> tuple[int, int, int, int, int, int]:
        """Get MAC address."""
        return self._mac

    @mac.setter
    def mac(self, value: tuple[int, int, int, int, int, int]) -> None:
        old_value = self._mac
        self._mac = value
        if old_value not in ((0, 0, 0, 0, 0, 0), value):
            print(f"MAC has changed from {old_value} to {self._mac}.")


class Node(NodeNet, NodeUniverses):
    """Art-Net Node."""

    names: dict[str, str]
    last_seen: float
    notify: Callable | None

    def __init__(
        self,
        reply: ArtPollReply | None = None,
        notify: Callable | None = None,
    ) -> None:
        self.notify = notify
        self.last_seen = 0.0
        self.bind_index = 0
        NodeNet.__init__(self, notify=self.modified)
        NodeUniverses.__init__(self)

        if reply:
            self.from_poll_reply(reply)
        else:
            self.ip = "127.0.0.1"
            self.mac = (0, 0, 0, 0, 0, 0)
            self.names = {"port": "", "long": "Not a Node"}

    def from_poll_reply(self, reply: ArtPollReply) -> None:
        """Set node from ArtPollReply packet.

        Args:
            reply: ArtPollReply object
        """
        self.mac = reply.mac
        self.ip = str(ipaddress.IPv4Address(reply.ip))
        self.names = {"port": reply.port_name, "long": reply.long_name}
        self.bind_index = reply.bind_index
        self.set_universes(
            reply.port_types,
            reply.net_switch,
            reply.sub_switch,
            reply.sw_out,
            reply.sw_in,
        )
        self.last_seen = time.time()

    def modified(self, attribute: str, old_value: int, value: int) -> None:
        """Dispatch attribute modified event to front-end."""
        if self.notify:
            self.notify(
                "node-modified", self.names["port"], attribute, old_value, value
            )

    def __repr__(self) -> str:
        last = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_seen))
        ports = "Ports\n"
        for i, t in enumerate(self._types):
            if not t:
                ports += f"\tPort {i + 1}: Not present\n"
            typ = t & 0b00111111
            tt = PORT_TYPES.get(typ, "Unknown")
            if t >> 7 & 1:
                univ = (
                    ((self._net & 0x7F) << 8)
                    + ((self._sub & 0x0F) << 4)
                    + (self._out[i] & 0x0F)
                )
                ports += f"\tPort {i + 1}: Output, Type {tt}, Universe {univ}\n"
            if t >> 6 & 1:
                univ = (
                    ((self._net & 0x7F) << 8)
                    + ((self._sub & 0x0F) << 4)
                    + (self._in[i] & 0x0F)
                )
                ports += f"\tPort {i + 1}: Input, Type {tt}, Universe {univ}\n"
        return (
            f"Art-Net Node: {ipaddress.IPv4Address(self.ip)},"
            f" {self.names['port']}, {self.names['long']}, last seen {last}"
            f"\n{ports}"
        )


class Sender:
    """Art-Net sender."""

    universe: int
    nodes: dict[tuple[tuple[int, int, int, int, int, int], int], Node]
    artdmx: ArtDmx

    def __init__(self, universe: int, notify: Callable | None) -> None:
        self.universe = universe
        self.nodes = {((0, 0, 0, 0, 0, 0), 0): Node(notify=notify)}
        self.artdmx = ArtDmx()

    def add_node(
        self, uid: tuple[tuple[int, int, int, int, int, int], int], node: Node
    ) -> None:
        """Add node.

        Args:
            uid: Node's unique identifier (MAC, BindIndex)
            node: Node to add
        """
        self.nodes[uid] = node

    def del_node(self, uid: tuple[tuple[int, int, int, int, int, int], int]) -> None:
        """Remove node.

        Args:
            uid: Node's unique identifier (MAC, BindIndex)
        """
        self.nodes.pop(uid, None)


# pylint: disable=too-many-instance-attributes
class Discovery:
    """Discover Art-Net devices."""

    network: Network
    universes: list[int]
    senders: dict[int, Sender]
    artpollreply: ArtPollReply
    monitor_thread: RepeatedTimer
    nodes: dict[tuple[tuple[int, int, int, int, int, int], int], Node]
    notify: Callable | None

    def __init__(
        self,
        network: Network,
        universes: list[int],
        senders: dict[int, Sender],
        notify: Callable | None,
    ) -> None:
        self.network = network
        self.universes = universes
        self.senders = senders
        self.artpollreply = ArtPollReply(universes)
        self.monitor_thread = RepeatedTimer(2.5, self.send_artpoll)
        self.nodes = {}
        self.consoles = {}
        self.notify = notify

    def stop(self) -> None:
        """Stop discovery of Art-Net devices."""
        self.monitor_thread.stop()

    def send_artpoll(self) -> None:
        """Broadcast ArtPoll packet to discover Controllers and Nodes
        and verify if there are alive.
        """
        packet = ArtPoll().encode()
        self.network.send_broadcast(packet)

        # Check if nodes were seen less than 8s ago
        nodes = self.nodes.copy()
        for node in nodes.values():
            if time.time() - node.last_seen > 8:
                uid = (node.mac, node.bind_index)
                for universe in node.output_universes:
                    if universe in self.senders:
                        self.senders[universe].del_node(uid)
                self.nodes.pop(uid, None)
                if self.notify:
                    self.notify("del-node", node.ip)

        # Check if consoles were seen less than 8s ago
        consoles = self.consoles.copy()
        for console in consoles.values():
            if time.time() - console.last_seen > 8:
                uid = (console.mac, console.bind_index)
                self.consoles.pop(uid, None)
                if self.notify:
                    self.notify("del-console", console.ip)

    def on_art_poll(self, data: bytes, addr: tuple[str, int]) -> None:
        """ArtPoll packet received.

        Args:
            data: Raw data
            addr: Sender's address
        """
        poll = ArtPoll()
        try:
            poll.decode(data)
        except ArtNetDecodeError:
            return
        self.send_artpollreply(addr)

    def _handle_node_reply(self, reply: ArtPollReply) -> None:
        """Process an ArtPollReply from a standard Node."""
        uid = (reply.mac, reply.bind_index)
        node = self.nodes.get(uid, None)
        if not node:
            node = Node(reply=reply, notify=self.notify)
            self.nodes[uid] = node
            for universe in node.output_universes:
                if universe in self.senders:
                    self.senders[universe].add_node(uid, node)
                    if self.notify:
                        self.notify("add-node", node.ip, universe)
        else:
            old_universes = node.output_universes.copy()
            node.from_poll_reply(reply)
            new_universes = node.output_universes

            # Remove from old universes that are no longer listened to
            removed_universes = set(old_universes) - set(new_universes)
            for u in removed_universes:
                if u in self.senders:
                    self.senders[u].del_node(uid)

            # Add to new newly listened universes
            added_universes = set(new_universes) - set(old_universes)
            for u in added_universes:
                if u in self.senders:
                    self.senders[u].add_node(uid, node)

    def _handle_console_reply(self, reply: ArtPollReply) -> None:
        """Process an ArtPollReply from a Console/Controller."""
        uid = (reply.mac, reply.bind_index)
        console = self.consoles.get(uid, None)
        if not console:
            console = Node(reply=reply, notify=self.notify)
            self.consoles[uid] = console
            if self.notify:
                self.notify("add-console", console.ip, 0)
        else:
            console.from_poll_reply(reply)

    def on_art_poll_reply(self, data: bytes) -> None:
        """ArtPollReply packet received.

        Args:
            data: Raw data
        """
        reply = ArtPollReply(self.universes)
        try:
            reply.decode(data)
        except ArtNetDecodeError:
            return

        if reply.style == StyleCodes.ST_NODE:
            self._handle_node_reply(reply)
        elif reply.style == StyleCodes.ST_CONTROLLER:
            self._handle_console_reply(reply)

    def send_artpollreply(self, addr: tuple[str, int]) -> None:
        """Send ArtPollReply in response of ArtPoll packet.

        Args:
            addr: Address to send packet
        """
        reply_ip, mac = get_ip_and_mac(addr)
        if reply_ip and mac:
            packet = self.artpollreply.encode(reply_ip, mac)
            self.network.send(packet, addr)


class Listener:
    """Art-Net listener."""

    universes: list[int]
    artdmx: dict[int, ArtDmx]

    def __init__(self, universes: list[int]) -> None:
        self.universes = universes
        # One ArtDmx by universe to follow sequence number
        self.artdmx = {}

    def is_handled_universe(self, universe: int) -> bool:
        """Verify if an universe is one we used.

        Args:
            universe: Universe number

        Returns:
            True if universe is one of ours, otherwise False
        """
        return universe in self.universes

    def get_artdmx(self, universe: int) -> ArtDmx | None:
        """Return ArtDmx corresponding to universe (create it if doesn't exist).

        Args:
            universe: Universe number

        Returns:
            ArtDmx
        """
        if not self.is_handled_universe(universe):
            return None
        if (artdmx := self.artdmx.get(universe, None)) is None:
            self.artdmx[universe] = ArtDmx()
            return self.artdmx[universe]
        return artdmx


class Listeners:
    """ArtDmx listeners."""

    universes: list[int]
    callback: Callable | None
    listeners: dict[tuple[str, int], Listener]
    merger: ArtDmxMerger

    def __init__(self, universes: list[int], callback: Callable | None) -> None:
        self.universes = universes
        self.callback = callback
        self.listeners = {}
        self.merger = ArtDmxMerger(mode=MergeMode.HTP, callback=callback)

    def get_listener(self, addr: tuple[str, int]) -> Listener:
        """Return existing listener or a new one.

        Args:
            addr: Listener IP/port

        Returns:
            Listener
        """
        if (listener := self.listeners.get(addr, None)) is None:
            self.listeners[addr] = Listener(self.universes)
            return self.listeners[addr]
        return listener

    def on_artdmx(self, data: bytes, addr: tuple[str, int]) -> None:
        """On ArtDmx reception.

        Args:
            data: Raw data
            addr: Sender IP/port
        """
        univ = get_universe(data)
        listener = self.get_listener(addr)
        if artdmx := listener.get_artdmx(univ):
            try:
                artdmx.decode(data)
            except ArtNetDecodeError, ArtNetSequenceError:
                return

            self.merger.update(artdmx.universe, addr[0], artdmx.data)


class Artnet:
    """Art-Net protocol."""

    listeners: Listeners
    senders: dict[int, Sender]
    network: Network
    discovery: Discovery

    def __init__(
        self,
        universes: list[int] | None = None,
        notify: Callable | None = None,
        on_artdmx_cb: Callable | None = None,
    ) -> None:
        if universes is None:
            universes = []
        self.listeners = Listeners(universes, on_artdmx_cb)
        self.senders = {}
        for universe in universes:
            self.senders[universe] = Sender(universe, notify)
        self.network = Network(self)
        self.discovery = Discovery(self.network, universes, self.senders, notify)

    def stop(self) -> None:
        """Stop Art-Net backend"""
        self.network.stop()
        self.discovery.stop()

    def read_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        """Dispatch packet treatment.

        Args:
            data: Raw data
            addr: (IP, port)
        """
        opcode = get_opcode(data)
        if opcode == OpCodes.OP_POLL_REPLY:
            self.discovery.on_art_poll_reply(data)
        elif opcode == OpCodes.OP_POLL:
            self.discovery.on_art_poll(data, addr)
        elif opcode == OpCodes.OP_DMX:
            self.listeners.on_artdmx(data, addr)

    def send(self, universe: int, packet: bytearray) -> None:
        """Send Art-Net universe to nodes.

        Args:
            universe: one in UNIVERSES
            packet: DMX data
        """
        if self.senders.get(universe, None):
            data = self.senders[universe].artdmx.encode(universe, packet)
            # Copy nodes to not iterate on changed dict
            nodes = self.senders[universe].nodes.copy()
            # Send dmx packet
            for node in nodes.values():
                addr = (node.ip, PORT)
                self.network.send(data, addr)

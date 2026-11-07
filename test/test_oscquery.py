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
"""Tests for the OSCQuery protocol implementation and HTTP server."""

from __future__ import annotations

import asyncio
import json
import socket

from olc.core.backends.osc.oscquery import (
    ACCESS_CONTAINER,
    ACCESS_READ_ONLY,
    ACCESS_READ_WRITE,
    ACCESS_WRITE_ONLY,
    OSCQueryServer,
    build_oscquery_tree,
    find_node_by_path,
)


def _get_free_port() -> int:
    """Find an available TCP port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def test_build_oscquery_tree_structure() -> None:
    """Test OSCQuery tree contains all standard nodes, ranges, and types."""
    tree = build_oscquery_tree(osc_port=8000)
    assert tree["OSC_PORT"] == 8000
    assert tree["OSC_TRANSPORT"] == "UDP"
    assert tree["FULL_PATH"] == "/"
    assert tree["ACCESS"] == ACCESS_CONTAINER
    assert "TEMPLATES" in tree
    assert "TABLET" in tree["TEMPLATES"]
    assert "PHONE" in tree["TEMPLATES"]
    assert "olc" in tree["CONTENTS"]

    olc = tree["CONTENTS"]["olc"]["CONTENTS"]

    # Main fader
    mainfader = olc["mainfader"]
    assert mainfader["FULL_PATH"] == "/olc/mainfader"
    assert mainfader["ACCESS"] == ACCESS_READ_WRITE
    assert mainfader["TYPE"] == "f"
    assert mainfader["RANGE"] == [{"MIN": 0.0, "MAX": 1.0}]

    # Blackout
    blackout = olc["blackout"]
    assert blackout["FULL_PATH"] == "/olc/blackout"
    assert blackout["ACCESS"] == ACCESS_READ_WRITE
    assert blackout["TYPE"] == "i"
    assert blackout["RANGE"] == [{"MIN": 0, "MAX": 1}]

    # Playback nodes
    pb = olc["playback"]["CONTENTS"]
    assert pb["active"]["CONTENTS"]["cue"]["ACCESS"] == ACCESS_READ_ONLY
    assert pb["active"]["CONTENTS"]["cue"]["TYPE"] == "f"
    assert pb["goto_cue"]["ACCESS"] == ACCESS_WRITE_ONLY
    assert pb["progress"]["RANGE"] == [{"MIN": 0.0, "MAX": 1.0}]

    # Faders
    faders_p1 = olc["fader"]["CONTENTS"]["1"]["CONTENTS"]
    assert "1" in faders_p1
    fader1 = faders_p1["1"]["CONTENTS"]
    assert fader1["level"]["ACCESS"] == ACCESS_READ_WRITE
    assert fader1["flash"]["ACCESS"] == ACCESS_WRITE_ONLY

    # Paged channels cells
    cells = olc["cell"]["CONTENTS"]
    assert len(cells) == 24
    assert cells["1"]["CONTENTS"]["level"]["RANGE"] == [{"MIN": 0.0, "MAX": 1.0}]

    # Selected color
    color = olc["selected"]["CONTENTS"]["color"]["CONTENTS"]
    assert color["rgb"]["TYPE"] == "fff"
    assert color["hsv"]["TYPE"] == "fff"
    assert color["kelvin"]["RANGE"] == [{"MIN": 1000.0, "MAX": 20000.0}]

    # Additional moving head wheels & selected nodes
    wheel = olc["wheel"]["CONTENTS"]
    assert wheel["zoom"]["ACCESS"] == ACCESS_WRITE_ONLY
    assert wheel["frost"]["ACCESS"] == ACCESS_WRITE_ONLY
    assert wheel["strobe"]["ACCESS"] == ACCESS_WRITE_ONLY

    selected = olc["selected"]["CONTENTS"]
    assert selected["zoom"]["RANGE"] == [{"MIN": 0.0, "MAX": 1.0}]
    assert selected["frost"]["RANGE"] == [{"MIN": 0.0, "MAX": 1.0}]
    assert selected["gobo"]["RANGE"] == [{"MIN": 0.0, "MAX": 1.0}]

    # Device container
    assert "device" in olc
    assert olc["device"]["ACCESS"] == ACCESS_CONTAINER


def test_find_node_by_path() -> None:
    """Test path matching and lookup inside OSCQuery tree."""
    tree = build_oscquery_tree(osc_port=9000)

    # Root
    assert find_node_by_path(tree, "/") is tree
    assert find_node_by_path(tree, "") is tree

    # Sub-nodes
    mf = find_node_by_path(tree, "/olc/mainfader")
    assert mf is not None
    assert mf["FULL_PATH"] == "/olc/mainfader"

    cell1 = find_node_by_path(tree, "/olc/cell/1/level")
    assert cell1 is not None
    assert cell1["TYPE"] == "f"

    # Nonexistent
    assert find_node_by_path(tree, "/invalid/path") is None
    assert find_node_by_path(tree, "/olc/nonexistent") is None


async def _read_http_response(
    reader: asyncio.StreamReader,
) -> tuple[str, dict[str, str], bytes]:
    """Read full HTTP response parsing status line, headers and body."""
    header_data = bytearray()
    while b"\r\n\r\n" not in header_data:
        chunk = await reader.read(512)
        if not chunk:
            break
        header_data.extend(chunk)

    idx = header_data.find(b"\r\n\r\n")
    headers_text = header_data[:idx].decode("utf-8")
    body_start = header_data[idx + 4 :]

    lines = headers_text.split("\r\n")
    status_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    content_len = int(headers.get("content-length", "0"))
    needed = content_len - len(body_start)
    body = bytes(body_start)
    if needed > 0:
        rest = await reader.readexactly(needed)
        body += rest
    return status_line, headers, body


def test_oscquery_server_http_lifecycle_and_requests() -> None:
    """Test starting the server, requesting root JSON, CORS, and subnodes."""

    async def _run() -> None:
        test_port = _get_free_port()
        server = OSCQueryServer(host="127.0.0.1", http_port=test_port)
        assert not server.is_running

        started = await server.start(http_port=test_port, osc_port=9005)
        assert started is True
        assert server.is_running is True

        # 1. Request Root Tree 'GET /'
        reader, writer = await asyncio.open_connection("127.0.0.1", test_port)
        writer.write(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()

        status, headers, body = await _read_http_response(reader)
        writer.close()
        await writer.wait_closed()

        assert "200 OK" in status
        assert "application/json" in headers.get("content-type", "")
        assert headers.get("access-control-allow-origin") == "*"

        body_json = json.loads(body.decode("utf-8"))
        assert body_json["OSC_PORT"] == 9005
        assert body_json["CONTENTS"]["olc"]["CONTENTS"]["mainfader"]["TYPE"] == "f"

        # 2. Request Subnode 'GET /olc/mainfader'
        reader, writer = await asyncio.open_connection("127.0.0.1", test_port)
        writer.write(b"GET /olc/mainfader HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()
        status, _headers, body = await _read_http_response(reader)
        writer.close()
        await writer.wait_closed()

        assert "200 OK" in status
        sub_json = json.loads(body.decode("utf-8"))
        assert sub_json["FULL_PATH"] == "/olc/mainfader"

        # 3. Test CORS pre-flight 'OPTIONS /'
        reader, writer = await asyncio.open_connection("127.0.0.1", test_port)
        writer.write(b"OPTIONS / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()
        status, headers, _body = await _read_http_response(reader)
        writer.close()
        await writer.wait_closed()
        assert "200 OK" in status
        assert "access-control-allow-methods" in headers

        # 4. Request 404
        reader, writer = await asyncio.open_connection("127.0.0.1", test_port)
        writer.write(b"GET /not_found HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()
        status, _headers, _body = await _read_http_response(reader)
        writer.close()
        await writer.wait_closed()
        assert "404 Not Found" in status

        # 5. Request TouchOSC Template Download
        reader, writer = await asyncio.open_connection("127.0.0.1", test_port)
        writer.write(
            b"GET /templates/OpenLightingConsole_Tablet.tosc HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n\r\n"
        )
        await writer.drain()
        status, headers, body = await _read_http_response(reader)
        writer.close()
        await writer.wait_closed()
        assert "200 OK" in status
        assert "application/vnd.touchosc.layout" in headers.get("content-type", "")
        assert "attachment" in headers.get("content-disposition", "")
        assert len(body) > 1000

        # 6. Request non-existent template
        reader, writer = await asyncio.open_connection("127.0.0.1", test_port)
        writer.write(b"GET /templates/unknown.tosc HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()
        status, _headers, _body = await _read_http_response(reader)
        writer.close()
        await writer.wait_closed()
        assert "404 Not Found" in status

        # 7. Stop Server
        await server.stop()
        assert server.is_running is False

    asyncio.run(_run())

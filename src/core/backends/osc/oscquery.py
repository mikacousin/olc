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
"""OSCQuery Protocol implementation (RFC IETF / Vidvox / HEXLER).

Exposes the Open Lighting Console OSC command tree over an asynchronous
HTTP JSON endpoint, allowing automatic discovery and introspection by
TouchOSC, Chataigne, Unreal Engine, and other modern controllers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import typing
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("olc.osc.oscquery")

# OSCQuery Access flags (RFC standard)
ACCESS_CONTAINER = 0  # No value, container folder
ACCESS_READ_ONLY = 1  # Read-only (telemetry / output only)
ACCESS_WRITE_ONLY = 2  # Write-only (command input only)
ACCESS_READ_WRITE = 3  # Read-Write (bidirectional telemetry & command)


def build_oscquery_tree(osc_port: int = 9000) -> dict[str, typing.Any]:
    """Construct the complete OSCQuery node tree for Open Lighting Console.

    Args:
        osc_port: The UDP listening port of the OLC OSC server.

    Returns:
        A dictionary representing the root OSCQuery node hierarchy.
    """
    fader_contents: dict[str, typing.Any] = {}
    for i in range(1, 11):
        fader_contents[str(i)] = {
            "DESCRIPTION": f"Fader {i} container",
            "FULL_PATH": f"/olc/fader/1/{i}",
            "ACCESS": ACCESS_CONTAINER,
            "CONTENTS": {
                "level": {
                    "DESCRIPTION": f"Normalized level for fader {i} (0.0 to 1.0)",
                    "FULL_PATH": f"/olc/fader/1/{i}/level",
                    "ACCESS": ACCESS_READ_WRITE,
                    "TYPE": "f",
                    "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                },
                "flash": {
                    "DESCRIPTION": f"Flash button for fader {i} (1=down, 0=up)",
                    "FULL_PATH": f"/olc/fader/1/{i}/flash",
                    "ACCESS": ACCESS_READ_WRITE,
                    "TYPE": "i",
                    "RANGE": [{"MIN": 0, "MAX": 1}],
                },
                "label": {
                    "DESCRIPTION": f"Label/caption for fader {i}",
                    "FULL_PATH": f"/olc/fader/1/{i}/label",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "s",
                },
            },
        }

    independent_contents: dict[str, typing.Any] = {}
    for i in range(1, 10):
        independent_contents[str(i)] = {
            "DESCRIPTION": f"Independent {i} container",
            "FULL_PATH": f"/olc/independent/{i}",
            "ACCESS": ACCESS_CONTAINER,
            "CONTENTS": {
                "level": {
                    "DESCRIPTION": f"Normalized level for independent {i} (0.0 to 1.0)",
                    "FULL_PATH": f"/olc/independent/{i}/level",
                    "ACCESS": ACCESS_READ_WRITE,
                    "TYPE": "f",
                    "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                },
                "button": {
                    "DESCRIPTION": f"Button trigger for independent {i} (1/0)",
                    "FULL_PATH": f"/olc/independent/{i}/button",
                    "ACCESS": ACCESS_WRITE_ONLY,
                    "TYPE": "i",
                    "RANGE": [{"MIN": 0, "MAX": 1}],
                },
                "label": {
                    "DESCRIPTION": f"Label for independent {i}",
                    "FULL_PATH": f"/olc/independent/{i}/label",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "s",
                },
                "type": {
                    "DESCRIPTION": f"Type of independent {i} (knob or button)",
                    "FULL_PATH": f"/olc/independent/{i}/type",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "s",
                },
            },
        }

    cell_contents: dict[str, typing.Any] = {}
    for i in range(1, 25):
        cell_contents[str(i)] = {
            "DESCRIPTION": f"Paged channels grid cell {i}",
            "FULL_PATH": f"/olc/cell/{i}",
            "ACCESS": ACCESS_CONTAINER,
            "CONTENTS": {
                "level": {
                    "DESCRIPTION": f"Normalized level for cell {i} (0.0 to 1.0)",
                    "FULL_PATH": f"/olc/cell/{i}/level",
                    "ACCESS": ACCESS_READ_WRITE,
                    "TYPE": "f",
                    "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                },
                "touch": {
                    "DESCRIPTION": f"Touch toggle selection for cell {i} (1=touch)",
                    "FULL_PATH": f"/olc/cell/{i}/touch",
                    "ACCESS": ACCESS_WRITE_ONLY,
                    "TYPE": "i",
                    "RANGE": [{"MIN": 0, "MAX": 1}],
                },
                "channel": {
                    "DESCRIPTION": f"Channel number mapped to cell {i}",
                    "FULL_PATH": f"/olc/cell/{i}/channel",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "i",
                },
                "label": {
                    "DESCRIPTION": f"Fixture name for cell {i}",
                    "FULL_PATH": f"/olc/cell/{i}/label",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "s",
                },
                "selected": {
                    "DESCRIPTION": f"Selection backlight for cell {i} (1/0)",
                    "FULL_PATH": f"/olc/cell/{i}/selected",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "i",
                    "RANGE": [{"MIN": 0, "MAX": 1}],
                },
                "color": {
                    "DESCRIPTION": f"Cell status color category for cell {i}",
                    "FULL_PATH": f"/olc/cell/{i}/color",
                    "ACCESS": ACCESS_READ_ONLY,
                    "TYPE": "s",
                },
            },
        }

    return {
        "NAME": "Open Lighting Console",
        "DESCRIPTION": "Open Lighting Console OSCQuery Protocol Endpoint",
        "FULL_PATH": "/",
        "ACCESS": ACCESS_CONTAINER,
        "OSC_PORT": osc_port,
        "OSC_TRANSPORT": "UDP",
        "EXTENSIONS": {
            "TEMPLATES": {
                "tablet": "/templates/OpenLightingConsole_Tablet.tosc",
                "phone": "/templates/OpenLightingConsole_Phone.tosc",
            }
        },
        "TEMPLATES": {
            "TABLET": "/templates/OpenLightingConsole_Tablet.tosc",
            "PHONE": "/templates/OpenLightingConsole_Phone.tosc",
        },
        "CONTENTS": {
            "olc": {
                "DESCRIPTION": "Open Lighting Console root namespace",
                "FULL_PATH": "/olc",
                "ACCESS": ACCESS_CONTAINER,
                "CONTENTS": {
                    "mainfader": {
                        "DESCRIPTION": "Main Fader intensity level (0.0 to 1.0)",
                        "FULL_PATH": "/olc/mainfader",
                        "ACCESS": ACCESS_READ_WRITE,
                        "TYPE": "f",
                        "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                    },
                    "blackout": {
                        "DESCRIPTION": "Scenic blackout state (0=inactive, 1=active)",
                        "FULL_PATH": "/olc/blackout",
                        "ACCESS": ACCESS_READ_WRITE,
                        "TYPE": "i",
                        "RANGE": [{"MIN": 0, "MAX": 1}],
                    },
                    "command_line": {
                        "DESCRIPTION": "Active logical command-line keystring",
                        "FULL_PATH": "/olc/command_line",
                        "ACCESS": ACCESS_READ_ONLY,
                        "TYPE": "s",
                    },
                    "key": {
                        "DESCRIPTION": "Keypad and playback impulse keys",
                        "FULL_PATH": "/olc/key",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            "go": {
                                "DESCRIPTION": "Trigger playback Go transition",
                                "FULL_PATH": "/olc/key/go",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "pause": {
                                "DESCRIPTION": "Pause or resume current playback fade",
                                "FULL_PATH": "/olc/key/pause",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "goback": {
                                "DESCRIPTION": "Return to previous cue",
                                "FULL_PATH": "/olc/key/goback",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "clear": {
                                "DESCRIPTION": "Clear logical command line",
                                "FULL_PATH": "/olc/key/clear",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "enter": {
                                "DESCRIPTION": "Execute command on command line",
                                "FULL_PATH": "/olc/key/enter",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "backspace": {
                                "DESCRIPTION": "Backspace on command line",
                                "FULL_PATH": "/olc/key/backspace",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                        },
                    },
                    "playback": {
                        "DESCRIPTION": "Main sequence playback telemetry & controls",
                        "FULL_PATH": "/olc/playback",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            "active": {
                                "DESCRIPTION": "Active cue container",
                                "FULL_PATH": "/olc/playback/active",
                                "ACCESS": ACCESS_CONTAINER,
                                "CONTENTS": {
                                    "cue": {
                                        "DESCRIPTION": "Active cue number (e.g. 1.0)",
                                        "FULL_PATH": "/olc/playback/active/cue",
                                        "ACCESS": ACCESS_READ_ONLY,
                                        "TYPE": "f",
                                    },
                                    "text": {
                                        "DESCRIPTION": "Active cue label/description",
                                        "FULL_PATH": "/olc/playback/active/text",
                                        "ACCESS": ACCESS_READ_ONLY,
                                        "TYPE": "s",
                                    },
                                },
                            },
                            "next": {
                                "DESCRIPTION": "Next cue container",
                                "FULL_PATH": "/olc/playback/next",
                                "ACCESS": ACCESS_CONTAINER,
                                "CONTENTS": {
                                    "cue": {
                                        "DESCRIPTION": "Next cue number in sequence",
                                        "FULL_PATH": "/olc/playback/next/cue",
                                        "ACCESS": ACCESS_READ_ONLY,
                                        "TYPE": "f",
                                    },
                                    "text": {
                                        "DESCRIPTION": "Next cue label/description",
                                        "FULL_PATH": "/olc/playback/next/text",
                                        "ACCESS": ACCESS_READ_ONLY,
                                        "TYPE": "s",
                                    },
                                },
                            },
                            "progress": {
                                "DESCRIPTION": "Crossfade progress (0.0 to 1.0)",
                                "FULL_PATH": "/olc/playback/progress",
                                "ACCESS": ACCESS_READ_ONLY,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "state": {
                                "DESCRIPTION": "Playback state",
                                "FULL_PATH": "/olc/playback/state",
                                "ACCESS": ACCESS_READ_ONLY,
                                "TYPE": "s",
                            },
                            "goto_cue": {
                                "DESCRIPTION": "Jump directly to specified cue number",
                                "FULL_PATH": "/olc/playback/goto_cue",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "dump": {
                                "DESCRIPTION": "JSON snapshot of all sequence cues",
                                "FULL_PATH": "/olc/playback/dump",
                                "ACCESS": ACCESS_READ_ONLY,
                                "TYPE": "s",
                            },
                            "xfade": {
                                "DESCRIPTION": "Unified manual crossfade (0.0 to 1.0)",
                                "FULL_PATH": "/olc/playback/xfade",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "xfade_a": {
                                "DESCRIPTION": "Manual crossfade scale A (0.0 to 1.0)",
                                "FULL_PATH": "/olc/playback/xfade/a",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "xfade_b": {
                                "DESCRIPTION": "Manual crossfade scale B (0.0 to 1.0)",
                                "FULL_PATH": "/olc/playback/xfade/b",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                        },
                    },
                    "independent": {
                        "DESCRIPTION": "Independents (1 to 9) container",
                        "FULL_PATH": "/olc/independent",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            **independent_contents,
                            "dump": {
                                "DESCRIPTION": "JSON snapshot of all independents",
                                "FULL_PATH": "/olc/independent/dump",
                                "ACCESS": ACCESS_READ_ONLY,
                                "TYPE": "s",
                            },
                        },
                    },
                    "fader": {
                        "DESCRIPTION": "Fader banks and controls",
                        "FULL_PATH": "/olc/fader",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            "page": {
                                "DESCRIPTION": "Active fader page number",
                                "FULL_PATH": "/olc/fader/page",
                                "ACCESS": ACCESS_READ_ONLY,
                                "TYPE": "i",
                            },
                            "page_plus": {
                                "DESCRIPTION": "Increment fader page",
                                "FULL_PATH": "/olc/fader/page/+",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "page_minus": {
                                "DESCRIPTION": "Decrement fader page",
                                "FULL_PATH": "/olc/fader/page/-",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "1": {
                                "DESCRIPTION": "Page 1 faders container",
                                "FULL_PATH": "/olc/fader/1",
                                "ACCESS": ACCESS_CONTAINER,
                                "CONTENTS": fader_contents,
                            },
                        },
                    },
                    "channels": {
                        "DESCRIPTION": "Channels grid navigation and subscriptions",
                        "FULL_PATH": "/olc/channels",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            "subscribe": {
                                "DESCRIPTION": "Subscribe to grid with custom size",
                                "FULL_PATH": "/olc/channels/subscribe",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "ii",
                            },
                            "start": {
                                "DESCRIPTION": "Jump grid start to channel number",
                                "FULL_PATH": "/olc/channels/start",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "i",
                            },
                            "page_plus": {
                                "DESCRIPTION": "Advance grid window by one page",
                                "FULL_PATH": "/olc/channels/page/+",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "page_minus": {
                                "DESCRIPTION": "Step back grid window by one page",
                                "FULL_PATH": "/olc/channels/page/-",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "",
                            },
                            "dump": {
                                "DESCRIPTION": "JSON matrix snapshot of channels block",
                                "FULL_PATH": "/olc/channels/dump",
                                "ACCESS": ACCESS_READ_ONLY,
                                "TYPE": "s",
                            },
                        },
                    },
                    "cell": {
                        "DESCRIPTION": "Paged channel grid cells (1 to 24)",
                        "FULL_PATH": "/olc/cell",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": cell_contents,
                    },
                    "wheel": {
                        "DESCRIPTION": "Encoder wheels for selected fixtures",
                        "FULL_PATH": "/olc/wheel",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            "pan": {
                                "DESCRIPTION": "Relative Pan delta angle in degrees",
                                "FULL_PATH": "/olc/wheel/pan",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "tilt": {
                                "DESCRIPTION": "Relative Tilt delta angle in degrees",
                                "FULL_PATH": "/olc/wheel/tilt",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "intensity": {
                                "DESCRIPTION": "Relative intensity adjustment delta",
                                "FULL_PATH": "/olc/wheel/intensity",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "zoom": {
                                "DESCRIPTION": "Relative Zoom adjustment delta",
                                "FULL_PATH": "/olc/wheel/zoom",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "focus": {
                                "DESCRIPTION": "Relative Focus adjustment delta",
                                "FULL_PATH": "/olc/wheel/focus",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "iris": {
                                "DESCRIPTION": "Relative Iris adjustment delta",
                                "FULL_PATH": "/olc/wheel/iris",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "strobe": {
                                "DESCRIPTION": "Relative Strobe adjustment delta",
                                "FULL_PATH": "/olc/wheel/strobe",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "frost": {
                                "DESCRIPTION": "Relative Frost adjustment delta",
                                "FULL_PATH": "/olc/wheel/frost",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "gobo": {
                                "DESCRIPTION": "Relative Gobo wheel adjustment delta",
                                "FULL_PATH": "/olc/wheel/gobo",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "prism": {
                                "DESCRIPTION": "Relative Prism adjustment delta",
                                "FULL_PATH": "/olc/wheel/prism",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "cct": {
                                "DESCRIPTION": "Relative CCT adjustment delta",
                                "FULL_PATH": "/olc/wheel/cct",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                        },
                    },
                    "selected": {
                        "DESCRIPTION": "Absolute controls for selected fixtures",
                        "FULL_PATH": "/olc/selected",
                        "ACCESS": ACCESS_CONTAINER,
                        "CONTENTS": {
                            "pan": {
                                "DESCRIPTION": "Set absolute Pan angle in degrees",
                                "FULL_PATH": "/olc/selected/pan",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "tilt": {
                                "DESCRIPTION": "Set absolute Tilt angle in degrees",
                                "FULL_PATH": "/olc/selected/tilt",
                                "ACCESS": ACCESS_WRITE_ONLY,
                                "TYPE": "f",
                            },
                            "zoom": {
                                "DESCRIPTION": "Normalized Zoom level (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/zoom",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "focus": {
                                "DESCRIPTION": "Normalized Focus level (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/focus",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "iris": {
                                "DESCRIPTION": "Normalized Iris aperture (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/iris",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "strobe": {
                                "DESCRIPTION": "Normalized Strobe freq (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/strobe",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "frost": {
                                "DESCRIPTION": "Normalized Frost filter (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/frost",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "gobo": {
                                "DESCRIPTION": "Gobo wheel normalized pos (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/gobo",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "prism": {
                                "DESCRIPTION": "Prism normalized level (0.0 to 1.0)",
                                "FULL_PATH": "/olc/selected/prism",
                                "ACCESS": ACCESS_READ_WRITE,
                                "TYPE": "f",
                                "RANGE": [{"MIN": 0.0, "MAX": 1.0}],
                            },
                            "color": {
                                "DESCRIPTION": "Color controls for selected fixtures",
                                "FULL_PATH": "/olc/selected/color",
                                "ACCESS": ACCESS_CONTAINER,
                                "CONTENTS": {
                                    "rgb": {
                                        "DESCRIPTION": (
                                            "Set RGB [red, green, blue] 0.0..1.0"
                                        ),
                                        "FULL_PATH": "/olc/selected/color/rgb",
                                        "ACCESS": ACCESS_WRITE_ONLY,
                                        "TYPE": "fff",
                                        "RANGE": [
                                            {"MIN": 0.0, "MAX": 1.0},
                                            {"MIN": 0.0, "MAX": 1.0},
                                            {"MIN": 0.0, "MAX": 1.0},
                                        ],
                                    },
                                    "hsv": {
                                        "DESCRIPTION": (
                                            "Set HSV [hue, sat, val] 0.0..1.0"
                                        ),
                                        "FULL_PATH": "/olc/selected/color/hsv",
                                        "ACCESS": ACCESS_WRITE_ONLY,
                                        "TYPE": "fff",
                                        "RANGE": [
                                            {"MIN": 0.0, "MAX": 1.0},
                                            {"MIN": 0.0, "MAX": 1.0},
                                            {"MIN": 0.0, "MAX": 1.0},
                                        ],
                                    },
                                    "kelvin": {
                                        "DESCRIPTION": (
                                            "Set correlated color temp in Kelvin"
                                        ),
                                        "FULL_PATH": "/olc/selected/color/kelvin",
                                        "ACCESS": ACCESS_WRITE_ONLY,
                                        "TYPE": "f",
                                        "RANGE": [{"MIN": 1000.0, "MAX": 20000.0}],
                                    },
                                },
                            },
                        },
                    },
                    "device": {
                        "DESCRIPTION": "Individual fixture controls by channel ID",
                        "FULL_PATH": "/olc/device",
                        "ACCESS": ACCESS_CONTAINER,
                    },
                },
            }
        },
    }


def find_node_by_path(
    root: dict[str, typing.Any], path: str
) -> dict[str, typing.Any] | None:
    """Find an OSCQuery node matching the specified slash-separated path.

    Args:
        root: The root dictionary tree.
        path: Path string (e.g. '/' or '/olc/mainfader').

    Returns:
        The matched dictionary node, or None if not found.
    """
    clean_path = path.strip("/")
    if not clean_path:
        return root

    parts = clean_path.split("/")
    curr: dict[str, typing.Any] = root
    for part in parts:
        contents = curr.get("CONTENTS")
        if not isinstance(contents, dict) or part not in contents:
            return None
        curr = contents[part]
    return curr


class OSCQueryServer:
    """Asynchronous HTTP JSON server implementing the OSCQuery protocol."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        http_port: int = 9001,
        on_client_connected: typing.Callable[[str], None] | None = None,
    ) -> None:
        self.host = host
        self.http_port = http_port
        self.osc_port = 9000
        self.on_client_connected = on_client_connected
        self._server: typing.Optional[asyncio.Server] = None
        self._loop: typing.Optional[asyncio.AbstractEventLoop] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the OSCQuery HTTP server is actively running."""
        return self._running

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming HTTP request for OSCQuery JSON introspection."""
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            req_line = line.decode("utf-8", errors="ignore").strip()
            parts = req_line.split()
            if len(parts) < 2:
                writer.close()
                await writer.wait_closed()
                return

            method, target_url = parts[0].upper(), parts[1]
            parsed = urlparse(target_url)
            req_path = parsed.path

            # Drain remainder of headers
            while True:
                header_line = await reader.readline()
                if not header_line or header_line in (b"\r\n", b"\n"):
                    break

            # Handle CORS pre-flight
            if method == "OPTIONS":
                resp_headers = (
                    "HTTP/1.1 200 OK\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "Access-Control-Allow-Methods: GET, OPTIONS\r\n"
                    "Access-Control-Allow-Headers: Content-Type, Accept\r\n"
                    "Content-Length: 0\r\n\r\n"
                )
                writer.write(resp_headers.encode("utf-8"))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            if method != "GET":
                resp = "HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n"
                writer.write(resp.encode("utf-8"))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            if self.on_client_connected is not None:
                peername = writer.get_extra_info("peername")
                if isinstance(peername, tuple) and len(peername) >= 1:
                    try:
                        self.on_client_connected(str(peername[0]))
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

            # Template download handling
            if req_path.startswith("/templates/"):
                raw_filename = req_path[len("/templates/") :].strip("/")
                filename = Path(raw_filename).name
                templates_dir = (
                    Path(__file__).resolve().parents[4]
                    / "data"
                    / "templates"
                    / "touchosc"
                )
                file_path = templates_dir / filename
                if not file_path.exists() and filename in (
                    "OpenLightingConsole_Tablet.tosc",
                    "OpenLightingConsole_Phone.tosc",
                ):
                    try:
                        from src.core.backends.osc.touchosc import (
                            generate_all_templates,
                        )

                        generate_all_templates(str(templates_dir))
                    except Exception as gen_err:
                        logger.error(
                            "Failed to auto-generate TouchOSC templates: %s",
                            gen_err,
                        )

                if file_path.is_file():
                    content = file_path.read_bytes()
                    header = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/vnd.touchosc.layout\r\n"
                        f'Content-Disposition: attachment; filename="{filename}"\r\n'
                        "Access-Control-Allow-Origin: *\r\n"
                        f"Content-Length: {len(content)}\r\n\r\n"
                    )
                    writer.write(header.encode("utf-8") + content)
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    return

                body = b'{"error": "Template not found"}'
                resp = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: application/json; charset=utf-8\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n"
                ).encode("utf-8") + body
                writer.write(resp)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

            tree = build_oscquery_tree(osc_port=self.osc_port)
            node = find_node_by_path(tree, req_path)
            if node is None:
                body = b'{"error": "Node not found"}'
                resp = (
                    f"HTTP/1.1 404 Not Found\r\n"
                    f"Content-Type: application/json; charset=utf-8\r\n"
                    f"Access-Control-Allow-Origin: *\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n"
                ).encode("utf-8") + body
            else:
                body = json.dumps(node, indent=2).encode("utf-8")
                resp = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: application/json; charset=utf-8\r\n"
                    f"Access-Control-Allow-Origin: *\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n"
                ).encode("utf-8") + body

            writer.write(resp)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.CancelledError, ConnectionResetError) as err:
            logger.debug("OSCQuery client handling error: %s", err)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    async def start(self, http_port: int | None = None, osc_port: int = 9000) -> bool:
        """Start the asynchronous HTTP server on the given loop.

        Args:
            http_port: TCP port for the HTTP server (defaults to self.http_port).
            osc_port: UDP port where OSC server is listening.

        Returns:
            True if started successfully, False otherwise.
        """
        if self._running:
            await self.stop()

        if http_port is not None:
            self.http_port = http_port
        self.osc_port = osc_port
        self._loop = asyncio.get_running_loop()

        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                host=self.host,
                port=self.http_port,
            )
            self._running = True
            logger.info(
                "OSCQuery HTTP server listening on http://%s:%d/ (OSC port %d)",
                self.host,
                self.http_port,
                self.osc_port,
            )
            return True
        except OSError as err:
            logger.info(
                "Could not start OSCQuery HTTP server on port %d: %s",
                self.http_port,
                err,
            )
            self._running = False
            return False

    async def stop(self) -> None:
        """Stop the OSCQuery HTTP server and close all active sockets."""
        if not self._running or self._server is None:
            return
        self._running = False
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        logger.info("OSCQuery HTTP server stopped.")

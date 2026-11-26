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
"""Serve the current patch to external viewers (e.g. olc-viz) over ZeroMQ.

The DMX monitor stream announces the current ``patch_version`` in the metadata
of every frame. A viewer that sees a new version asks for a full snapshot on a
REQ/REP socket. A patch is a few kB and changes rarely, so a full snapshot is
simpler and more robust than a stream of deltas.

Wire format (reply to a request ``b"patch"``)::

    {"version": 12,
     "devices": [{"id": 101, "label": "...", "manufacturer": "...",
                  "model": "...", "mode": "...", "gdtf": "...",
                  "universe": 2, "address": 17, "footprint": 24}]}

This module only depends on the standard library and (lazily) on pyzmq.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Callable, Iterable

SNAPSHOT_REQUEST = b"patch"
_POLL_MS = 200
_DEFAULT_STAGE: dict[str, Any] = {
    "width": 12.0,
    "depth": 10.0,
    "color": "#222226",
    "grid_spacing": 1.0,
    "fog_density": 0.35,
}


def _enum_value(val: object, default: str = "generic") -> str:
    enum_val = getattr(val, "value", None)
    if enum_val is not None:
        return str(enum_val)
    return str(val) if val else default


def _vec3_list(val: object, default: tuple[float, float, float]) -> list[float]:
    if isinstance(val, (list, tuple)) and len(val) == 3:
        return [float(val[0]), float(val[1]), float(val[2])]
    return [default[0], default[1], default[2]]


def _channel_row(ch: Any) -> dict[str, Any]:  # noqa: ANN401
    row: dict[str, Any] = {
        "type": _enum_value(getattr(ch, "channel_type", None), "generic"),
        "universe": int(ch.universe),
        "address": int(ch.address),
    }
    lbl = getattr(ch, "label", "")
    if lbl:
        row["label"] = str(lbl)
    if getattr(ch, "fine", False):
        row["fine"] = True
    if getattr(ch, "ultra_fine", False):
        row["ultra_fine"] = True
    pmin = getattr(ch, "physical_min", None)
    pmax = getattr(ch, "physical_max", None)
    if pmin is not None and pmax is not None and (pmin, pmax) != (0.0, 1.0):
        row["physical_min"] = float(pmin)
        row["physical_max"] = float(pmax)
    ranges = getattr(ch, "ranges", None)
    if ranges:
        row["ranges"] = [
            {
                "label": str(r.label),
                "min": int(r.value_min),
                "max": int(r.value_max),
                **({"gobo_id": str(r.gobo_id)} if getattr(r, "gobo_id", "") else {}),
            }
            for r in ranges
        ]
    return row


def _device_row(device: Any) -> dict[str, Any]:  # noqa: ANN401
    """Describe one LightingDevice for the snapshot."""
    universe = device.universe
    addresses = [ch.address for ch in device.channels if ch.universe == universe]
    footprint = (max(addresses) - min(addresses) + 1) if addresses else 0
    return {
        "id": device.fixture_id,
        "label": device.label,
        "manufacturer": device.manufacturer,
        "model": device.model,
        "mode": device.mode_name,
        "gdtf": device.gdtf_id,
        "fixture_type": _enum_value(getattr(device, "fixture_type", None), "generic"),
        "universe": universe,
        "address": device.address,
        "footprint": footprint,
        "position": _vec3_list(getattr(device, "position", None), (0.0, 0.0, 4.0)),
        "focus_point": _vec3_list(
            getattr(device, "focus_point", None), (0.0, 0.0, 0.0)
        ),
        "orientation": _vec3_list(
            getattr(device, "orientation", None), (0.0, 0.0, 0.0)
        ),
        "beam_angle": float(getattr(device, "beam_angle", 25.0)),
        "static_gobo": str(getattr(device, "static_gobo", "")),
        "gel": str(getattr(device, "gel", "")),
        "gel_color": str(
            getattr(device, "effective_gel_color", "")
            or getattr(device, "gel_color", "")
        ),
        "channels": [_channel_row(ch) for ch in getattr(device, "channels", [])],
    }


def _stage_dict(stage: object) -> dict[str, Any]:
    to_dict = getattr(stage, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    if isinstance(stage, dict):
        return {**_DEFAULT_STAGE, **stage}
    return dict(_DEFAULT_STAGE)


def build_snapshot(devices: Iterable[Any], version: int, stage: object = None) -> bytes:
    """Serialize patched devices and stage config into snapshot JSON (UTF-8 bytes)."""
    rows = sorted((_device_row(d) for d in devices), key=lambda r: r["id"])
    return json.dumps(
        {"version": version, "stage": _stage_dict(stage), "devices": rows}
    ).encode("utf-8")


class PatchSnapshotServer:
    """Answer patch snapshot requests from a background thread.

    ``update()`` is called from the thread that owns the PatchManager: it
    builds the snapshot there and swaps it atomically. The serving thread
    only reads the cached bytes, so it never touches the live patch.
    """

    def __init__(
        self,
        port: int,
        host: str = "127.0.0.1",
        on_command: Callable[[dict[str, Any]], dict[str, Any] | bytes] | None = None,
    ) -> None:
        self._endpoint = f"tcp://{host}:{port}"
        self._snapshot: tuple[int, bytes] = (0, build_snapshot([], 0))
        self._next_version = 1
        self._on_command = on_command
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None

    def set_command_handler(
        self, handler: Callable[[dict[str, Any]], dict[str, Any] | bytes] | None
    ) -> None:
        """Register or clear the callback invoked for JSON commands."""
        self._on_command = handler

    @property
    def version(self) -> int:
        """Version of the snapshot currently served (0 = nothing published)."""
        return self._snapshot[0]

    def update(self, devices: Iterable[Any], stage: object = None) -> int:
        """Rebuild the snapshot from current devices and stage; return version."""
        version = self._next_version
        self._next_version += 1
        self._snapshot = (version, build_snapshot(devices, version, stage=stage))
        return version

    def start(self, timeout: float = 2.0) -> None:
        """Bind the REP socket and start serving. Raises if the bind fails."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._serve, name="PatchSnapshot", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("patch snapshot server did not start")
        if self._error is not None:
            self._thread = None
            raise self._error

    def stop(self) -> None:
        """Stop serving and release the port."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _handle_request(self, request: bytes) -> bytes:
        if request == SNAPSHOT_REQUEST:
            return self._snapshot[1]
        try:
            payload = json.loads(request.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return b"{}"
        if not isinstance(payload, dict):
            return b"{}"
        if payload.get("cmd") == "patch":
            return self._snapshot[1]
        handler = self._on_command
        if handler is None:
            return b"{}"
        try:
            reply = handler(payload)
        except Exception as err:  # pylint: disable=broad-exception-caught
            reply = {"ok": False, "error": str(err)}
        if isinstance(reply, bytes):
            return reply
        return json.dumps(reply).encode("utf-8")

    def _serve(self) -> None:
        import zmq  # pylint: disable=import-outside-toplevel

        ctx = zmq.Context()
        sock = ctx.socket(zmq.REP)
        sock.setsockopt(zmq.LINGER, 0)
        try:
            sock.bind(self._endpoint)
        except zmq.ZMQError as err:
            self._error = err
            self._ready.set()
            sock.close()
            ctx.term()
            return
        self._ready.set()
        try:
            while not self._stop.is_set():
                if not sock.poll(_POLL_MS):
                    continue
                request = sock.recv()
                sock.send(self._handle_request(request))
        finally:
            sock.close()
            ctx.term()

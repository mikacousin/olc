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
"""Augment3d (``working.a3d``) 3D patch transform fallback extractor."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any


def eos_euler_to_olc(rx: float, ry: float, rz: float) -> tuple[float, float, float]:
    """Convert Eos Augment3d XYZ Euler degrees to OLC ``(rz, ry, -rx)``."""
    return (float(rz), float(ry), -float(rx))


def parse_working_a3d_patch(
    a3d_bytes: bytes,
) -> dict[int, dict[str, tuple[float, float, float]]]:
    """Extract per-channel 3D ``position`` and ``orientation`` from ``working.a3d``."""
    result: dict[int, dict[str, tuple[float, float, float]]] = {}
    if not a3d_bytes:
        return result

    try:
        with zipfile.ZipFile(io.BytesIO(a3d_bytes)) as azf:
            if "Scene/Patch.json" not in azf.namelist():
                return result
            raw_json = azf.read("Scene/Patch.json")
            payload: Any = json.loads(raw_json.decode("utf-8"))
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
        return result

    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return result

    for entry in items:
        if not isinstance(entry, dict):
            continue
        obj = entry.get("obj")
        if not isinstance(obj, dict):
            continue
        console_data = obj.get("console_data")
        try:
            channel = int(console_data)
        except (TypeError, ValueError):
            continue
        if channel <= 0:
            continue

        local = obj.get("local")
        if not isinstance(local, dict):
            continue

        meta: dict[str, tuple[float, float, float]] = {}
        pos = local.get("pos")
        if isinstance(pos, dict):
            meta["position"] = (
                float(pos.get("x", 0.0)),
                float(pos.get("y", 0.0)),
                float(pos.get("z", 0.0)),
            )
        eulers = local.get("eulers")
        if isinstance(eulers, dict):
            meta["orientation"] = eos_euler_to_olc(
                float(eulers.get("x", 0.0)),
                float(eulers.get("y", 0.0)),
                float(eulers.get("z", 0.0)),
            )
        if meta:
            result[channel] = meta

    return result

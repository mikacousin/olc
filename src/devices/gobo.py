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
"""Gobo image library, built-in patterns, and Eos resource decoding."""

from __future__ import annotations

import base64
import zlib
from dataclasses import dataclass
from typing import Any, Optional

BUILTIN_GOBO_IDS: tuple[str, ...] = (
    "builtin:open",
    "builtin:stars",
    "builtin:breakup",
    "builtin:bars",
    "builtin:radial",
    "builtin:ring",
    "builtin:grid",
    "builtin:triangle",
    "builtin:cross",
    "builtin:spiral",
)

BUILTIN_GOBO_LABELS: dict[str, str] = {
    "builtin:open": "Open",
    "builtin:stars": "Stars",
    "builtin:breakup": "Breakup",
    "builtin:bars": "Bars",
    "builtin:radial": "Radial",
    "builtin:ring": "Ring",
    "builtin:grid": "Grid",
    "builtin:triangle": "Triangle",
    "builtin:cross": "Cross",
    "builtin:spiral": "Spiral",
}

_KEYWORD_TO_BUILTIN: tuple[tuple[tuple[str, ...], str], ...] = (
    (("open", "clear", "no gobo", "empty"), "builtin:open"),
    (("star", "dot", "circle", "bubble", "shower"), "builtin:stars"),
    (
        ("break", "leaf", "leaves", "foliage", "forest", "tree", "cloud"),
        "builtin:breakup",
    ),
    (("bar", "line", "stripe", "blind", "slit", "venetian"), "builtin:bars"),
    (("rad", "sun", "burst", "ray", "spoke", "cone", "fan"), "builtin:radial"),
    (("ring", "iris", "donut", "halo", "target"), "builtin:ring"),
    (("grid", "window", "square", "check", "brick", "matrix"), "builtin:grid"),
    (("tri", "delta", "pyramid"), "builtin:triangle"),
    (("cross", "plus", "x-ray"), "builtin:cross"),
    (("spiral", "vortex", "swirl", "tunnel"), "builtin:spiral"),
)


def resolve_builtin_gobo(label: str, slot_index: int = 0) -> str:
    """Resolve a gobo label or slot index to a built-in gobo ID."""
    low = label.strip().lower()
    if low.startswith("builtin:") and low in BUILTIN_GOBO_LABELS:
        return low
    for keywords, gobo_id in _KEYWORD_TO_BUILTIN:
        if any(kw in low for kw in keywords):
            return gobo_id
    if slot_index <= 0:
        return "builtin:open"
    non_open = BUILTIN_GOBO_IDS[1:]
    return non_open[(slot_index - 1) % len(non_open)]


def decode_eos_resource_hex(hex_str: str) -> Optional[bytes]:
    """Decode Eos $$HD resource payload (4-byte Qt qCompress header + zlib stream)."""
    cleaned = "".join(hex_str.split())
    if len(cleaned) < 10:
        return None
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError:
        return None
    if len(raw) <= 4:
        return None
    try:
        return zlib.decompress(raw[4:])
    except zlib.error:
        return None


@dataclass
class GoboAsset:
    """Stored gobo image asset (PNG/SVG/JPG bytes)."""

    gobo_id: str
    name: str
    data: bytes
    ext: str = "png"

    def to_dict(self) -> dict[str, Any]:
        """Serialize gobo asset to dictionary with base64 image data."""
        return {
            "gobo_id": self.gobo_id,
            "name": self.name,
            "ext": self.ext,
            "data_b64": base64.b64encode(self.data).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Optional[GoboAsset]:
        """Deserialize gobo asset from dictionary."""
        raw_b64 = data.get("data_b64")
        gobo_id = str(data.get("gobo_id", "")).strip()
        if not raw_b64 or not gobo_id:
            return None
        try:
            img_bytes = base64.b64decode(str(raw_b64))
        except (ValueError, TypeError):
            return None
        return cls(
            gobo_id=gobo_id,
            name=str(data.get("name", gobo_id)),
            data=img_bytes,
            ext=str(data.get("ext", "png")),
        )


class GoboLibrary:
    """Show-level registry of custom gobo images keyed by gobo_id."""

    def __init__(self) -> None:
        self._assets: dict[str, GoboAsset] = {}

    def add(self, asset: GoboAsset) -> None:
        """Register or replace a gobo asset."""
        if asset.gobo_id and asset.data:
            self._assets[asset.gobo_id] = asset

    def get(self, gobo_id: str) -> Optional[GoboAsset]:
        """Return GoboAsset for *gobo_id*, or None."""
        return self._assets.get(gobo_id)

    def all(self) -> list[GoboAsset]:
        """Return all stored gobo assets."""
        return list(self._assets.values())

    def clear(self) -> None:
        """Remove all stored gobo assets."""
        self._assets.clear()

    def __len__(self) -> int:
        return len(self._assets)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialize all gobo assets."""
        return {gid: asset.to_dict() for gid, asset in self._assets.items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoboLibrary:
        """Deserialize GoboLibrary from dictionary."""
        lib = cls()
        for gid, item in data.items():
            if not isinstance(item, dict):
                continue
            payload = dict(item)
            payload.setdefault("gobo_id", str(gid))
            asset = GoboAsset.from_dict(payload)
            if asset is not None:
                lib.add(asset)
        return lib

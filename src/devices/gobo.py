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
import hashlib
import os
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import platformdirs

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


_VALID_GOBO_EXTS: tuple[str, ...] = ("png", "svg", "jpg", "jpeg")


def get_user_gobos_dir() -> Path:
    """Return the directory path for cached user gobo images (XDG data dir)."""
    env_dir = os.environ.get("OLC_USER_GOBOS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(platformdirs.user_data_dir("olc")) / "gobos"


def _gobo_cache_stem(gobo_id: str) -> str:
    """Return a filesystem-safe deterministic filename stem for *gobo_id*."""
    return hashlib.sha256(gobo_id.encode("utf-8")).hexdigest()[:24]


def save_user_gobo(asset: GoboAsset) -> Optional[Path]:
    """Persist a gobo image asset to the user gobo cache directory."""
    if not asset.gobo_id or not asset.data:
        return None
    ext = (asset.ext or "png").strip().lower().lstrip(".")
    if ext not in _VALID_GOBO_EXTS:
        ext = "png"
    try:
        gobos_dir = get_user_gobos_dir()
        gobos_dir.mkdir(parents=True, exist_ok=True)
        file_path = gobos_dir / f"{_gobo_cache_stem(asset.gobo_id)}.{ext}"
        file_path.write_bytes(asset.data)
        return file_path
    except OSError:
        return None


def load_user_gobo(gobo_id: str) -> Optional[GoboAsset]:
    """Load a cached gobo image asset from disk by *gobo_id*, or None."""
    if not gobo_id or gobo_id.startswith("builtin:"):
        return None
    try:
        gobos_dir = get_user_gobos_dir()
        if not gobos_dir.is_dir():
            return None
        stem = _gobo_cache_stem(gobo_id)
        for ext in _VALID_GOBO_EXTS:
            cand = gobos_dir / f"{stem}.{ext}"
            if cand.is_file():
                return GoboAsset(
                    gobo_id=gobo_id,
                    name=gobo_id,
                    data=cand.read_bytes(),
                    ext=ext,
                )
    except OSError:
        return None
    return None


class GoboLibrary:
    """Show-level registry of custom gobo images keyed by gobo_id."""

    def __init__(self) -> None:
        self._assets: dict[str, GoboAsset] = {}

    def add(self, asset: GoboAsset) -> None:
        """Register or replace a gobo asset."""
        if asset.gobo_id and asset.data:
            self._assets[asset.gobo_id] = asset

    def get(self, gobo_id: str) -> Optional[GoboAsset]:
        """Return GoboAsset for *gobo_id* (checking user disk cache on miss)."""
        asset = self._assets.get(gobo_id)
        if asset is not None:
            return asset
        cached = load_user_gobo(gobo_id)
        if cached is not None:
            self._assets[gobo_id] = cached
        return cached

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

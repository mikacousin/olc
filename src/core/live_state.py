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
"""Thread-safe live parameter state and palette reference tracking."""

from __future__ import annotations

import threading
import typing
from collections.abc import Iterable, Mapping

from olc.show.step import get_parameter_family

if typing.TYPE_CHECKING:
    from olc.show.palette import PaletteRef

ChannelLiveSnapshot = tuple[dict[str, "PaletteRef"], set[str]]

_FAMILY_ALIASES: dict[str, str] = {
    "focus": "position",
    "pos": "position",
    "position": "position",
    "f": "position",
    "color": "color",
    "colour": "color",
    "c": "color",
    "intensity": "intensity",
    "intens": "intensity",
    "int": "intensity",
    "i": "intensity",
    "beam": "beam",
    "b": "beam",
}

_COLOR_EMITTER_KEYS: frozenset[str] = frozenset(
    {
        "red",
        "green",
        "blue",
        "white",
        "amber",
        "lime",
        "cyan",
        "indigo",
        "magenta",
        "yellow",
    }
)
_COLOR_KEYS: frozenset[str] = frozenset({"color", "colour"})
_COLOR_ALL_KEYS: frozenset[str] = _COLOR_KEYS | _COLOR_EMITTER_KEYS

_PARAM_ALIASES: dict[str, frozenset[str]] = {
    "color": _COLOR_KEYS,
    "colour": _COLOR_KEYS,
    "cct": frozenset({"cct", "color_temp", "colortemp"}),
    "color_temp": frozenset({"cct", "color_temp", "colortemp"}),
    "colortemp": frozenset({"cct", "color_temp", "colortemp"}),
    "strobe": frozenset({"strobe", "shutter"}),
    "shutter": frozenset({"strobe", "shutter"}),
    "gobo": frozenset({"gobo", "gobo_wheel"}),
    "gobo_wheel": frozenset({"gobo", "gobo_wheel"}),
}


def _normalize_param_name(param_name: str) -> str:
    """Normalize parameter name to lowercase canonical form."""
    low = str(param_name).strip().lower()
    if low == "colour":
        return "color"
    return low


class LiveParameterState:
    """Tracks live manual parameter overrides and active palette/preset references."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._palette_refs: dict[int, dict[str, PaletteRef]] = {}
        self._manual_params: dict[int, set[str]] = {}

    @staticmethod
    def normalize_family(family: str) -> str:
        """Normalize IFCB family alias to canonical tracking family name."""
        low = str(family).strip().lower()
        return _FAMILY_ALIASES.get(low, low)

    @staticmethod
    def _expand_break_keys(param_norm: str) -> set[str]:
        """Return all palette ref keys that should break when *param_norm* is edited."""
        keys: set[str] = {param_norm, "*"}
        if param_norm in _COLOR_KEYS:
            keys.update(_COLOR_ALL_KEYS)
        elif param_norm in _COLOR_EMITTER_KEYS:
            keys.add("color")
            keys.add("colour")
        elif param_norm in _PARAM_ALIASES:
            keys.update(_PARAM_ALIASES[param_norm])
        return keys

    def get_palette_refs(self, channel: int) -> dict[str, PaletteRef]:
        """Return a shallow copy of active live palette references for *channel*."""
        with self._lock:
            return dict(self._palette_refs.get(int(channel), {}))

    def get_palette_ref(self, channel: int, param_name: str) -> PaletteRef | None:
        """Return active live palette reference for *(channel, param_name)* or None."""
        p_norm = _normalize_param_name(param_name)
        candidates = (p_norm, *_PARAM_ALIASES.get(p_norm, ()), "*")
        with self._lock:
            refs = self._palette_refs.get(int(channel))
            if not refs:
                return None
            for key in candidates:
                if key in refs:
                    return refs[key]
            return None

    def set_palette_ref(
        self,
        channel: int,
        param_name: str,
        ref: PaletteRef,
        *,
        mark_manual: bool = True,
    ) -> None:
        """Record an active live palette reference for a single parameter."""
        self.set_palette_refs(channel, {param_name: ref}, mark_manual=mark_manual)

    def set_palette_refs(
        self,
        channel: int,
        refs: Mapping[str, PaletteRef],
        *,
        mark_manual: bool = True,
    ) -> None:
        """Record multiple active live palette references for *channel*."""
        if not refs:
            return
        ch = int(channel)
        with self._lock:
            ch_refs = self._palette_refs.setdefault(ch, {})
            ch_manual = (
                self._manual_params.setdefault(ch, set()) if mark_manual else None
            )
            for param_name, ref in refs.items():
                p_norm = _normalize_param_name(param_name)
                if not p_norm:
                    continue
                ch_refs[p_norm] = (str(ref[0]), float(ref[1]))
                if ch_manual is not None:
                    ch_manual.add(p_norm)

    def mark_manual_params(
        self,
        channel: int,
        params: Iterable[str],
        *,
        break_refs: bool = True,
    ) -> None:
        """Mark parameters as manually modified in live and optionally break refs."""
        ch = int(channel)
        with self._lock:
            ch_manual = self._manual_params.setdefault(ch, set())
            ch_refs = self._palette_refs.get(ch)
            for raw_param in params:
                p_norm = _normalize_param_name(raw_param)
                if not p_norm:
                    continue
                ch_manual.add(p_norm)
                if break_refs and ch_refs:
                    for key in self._expand_break_keys(p_norm):
                        ch_refs.pop(key, None)
            if ch_refs is not None and not ch_refs:
                self._palette_refs.pop(ch, None)
            if not ch_manual:
                self._manual_params.pop(ch, None)

    def break_family_refs(self, channel: int, family: str | None) -> None:
        """Break live palette references belonging to *family* on *channel*.

        Args:
            channel: 1-based channel number.
            family: Canonical or aliased family name, ``"all"`` for everything,
                or ``None`` for all non-intensity families (position, color, beam).
        """
        ch = int(channel)
        if family is None:
            target_families = frozenset({"position", "color", "beam"})
        else:
            norm = self.normalize_family(family)
            if norm == "all":
                target_families = frozenset({"intensity", "position", "color", "beam"})
            else:
                target_families = frozenset({norm})

        with self._lock:
            ch_refs = self._palette_refs.get(ch)
            if not ch_refs:
                return
            to_remove = [
                key
                for key in ch_refs
                if key == "*"
                or self.normalize_family(get_parameter_family(key)) in target_families
            ]
            for key in to_remove:
                ch_refs.pop(key, None)
            if not ch_refs:
                self._palette_refs.pop(ch, None)

    def clear_params(
        self,
        channel: int,
        params: Iterable[str] | None = None,
    ) -> None:
        """Clear manual flags and palette references for selected or all parameters."""
        ch = int(channel)
        with self._lock:
            if params is None:
                self._palette_refs.pop(ch, None)
                self._manual_params.pop(ch, None)
                return

            keys_to_clear: set[str] = set()
            for raw_param in params:
                p_norm = _normalize_param_name(raw_param)
                if not p_norm:
                    continue
                keys_to_clear.add(p_norm)
                keys_to_clear.update(self._expand_break_keys(p_norm) - {"*"})

            ch_refs = self._palette_refs.get(ch)
            if ch_refs is not None:
                for key in keys_to_clear:
                    ch_refs.pop(key, None)
                if not ch_refs:
                    self._palette_refs.pop(ch, None)

            ch_manual = self._manual_params.get(ch)
            if ch_manual is not None:
                ch_manual.difference_update(keys_to_clear)
                if not ch_manual:
                    self._manual_params.pop(ch, None)

    def clear_channel(self, channel: int) -> None:
        """Clear all live manual states and palette references for *channel*."""
        self.clear_params(channel, None)

    def clear_all(self) -> None:
        """Reset all live manual states and palette references across all channels."""
        with self._lock:
            self._palette_refs.clear()
            self._manual_params.clear()

    def is_param_manual(self, channel: int, param_name: str) -> bool:
        """Return True if *param_name* (or its alias) is marked manual on *channel*."""
        p_norm = _normalize_param_name(param_name)
        candidates = (p_norm, *_PARAM_ALIASES.get(p_norm, ()))
        with self._lock:
            ch_manual = self._manual_params.get(int(channel))
            if not ch_manual:
                return False
            if p_norm in _COLOR_EMITTER_KEYS and any(
                k in ch_manual for k in _COLOR_KEYS
            ):
                return True
            if p_norm in _COLOR_KEYS and any(k in ch_manual for k in _COLOR_ALL_KEYS):
                return True
            return any(k in ch_manual for k in candidates)

    def is_family_manual(self, channel: int, family: str) -> bool:
        """Return True if any manual parameter on *channel* belongs to *family*."""
        target = self.normalize_family(family)
        with self._lock:
            ch_manual = self._manual_params.get(int(channel))
            if not ch_manual:
                return False
            return any(
                self.normalize_family(get_parameter_family(p)) == target
                for p in ch_manual
            )

    def is_channel_manual(self, channel: int) -> bool:
        """Return True if *channel* has any manual parameter or live palette ref."""
        ch = int(channel)
        with self._lock:
            return bool(self._manual_params.get(ch) or self._palette_refs.get(ch))

    def get_manual_params(self, channel: int) -> set[str]:
        """Return a copy of manually modified parameter names for *channel*."""
        with self._lock:
            return set(self._manual_params.get(int(channel), set()))

    def get_manual_channels(self) -> set[int]:
        """Return channels currently carrying any manual parameter or palette ref."""
        with self._lock:
            return {ch for ch, params in self._manual_params.items() if params} | {
                ch for ch, refs in self._palette_refs.items() if refs
            }

    def snapshot_channel(self, channel: int) -> ChannelLiveSnapshot:
        """Capture an undoable snapshot of live refs and manual params for *channel*."""
        ch = int(channel)
        with self._lock:
            return (
                dict(self._palette_refs.get(ch, {})),
                set(self._manual_params.get(ch, set())),
            )

    def restore_channel(self, channel: int, snap: ChannelLiveSnapshot) -> None:
        """Restore *channel* live refs and manual params from *snap*."""
        ch = int(channel)
        refs, manual = snap
        with self._lock:
            if refs:
                self._palette_refs[ch] = dict(refs)
            else:
                self._palette_refs.pop(ch, None)
            if manual:
                self._manual_params[ch] = set(manual)
            else:
                self._manual_params.pop(ch, None)

    def snapshot_all(self) -> dict[int, ChannelLiveSnapshot]:
        """Capture a snapshot across all channels with active live state."""
        with self._lock:
            all_ch = set(self._palette_refs.keys()) | set(self._manual_params.keys())
            return {ch: self.snapshot_channel(ch) for ch in all_ch}

    def restore_all(self, snap: Mapping[int, ChannelLiveSnapshot]) -> None:
        """Replace all live state with *snap*."""
        with self._lock:
            self._palette_refs.clear()
            self._manual_params.clear()
            for ch, ch_snap in snap.items():
                self.restore_channel(ch, ch_snap)

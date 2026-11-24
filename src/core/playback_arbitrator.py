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
"""Multi-sequence playback arbitration engine (HTP/LTP + priority stack)."""

from __future__ import annotations

import copy
import threading
import typing
from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np

from olc.define import MAX_CHANNELS


class PlaybackPriority(IntEnum):
    """Priority tiers for concurrent sequence playbacks."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    SUPER = 40


def parse_playback_priority(
    value: PlaybackPriority | int | str | None,
) -> PlaybackPriority:
    """Parse an enum, integer, or string name into a PlaybackPriority."""
    if isinstance(value, PlaybackPriority):
        return value
    if isinstance(value, int):
        try:
            return PlaybackPriority(value)
        except ValueError:
            return PlaybackPriority.NORMAL
    if isinstance(value, str):
        key = value.strip().upper()
        if key in PlaybackPriority.__members__:
            return PlaybackPriority[key]
        try:
            return PlaybackPriority(int(value))
        except ValueError:
            return PlaybackPriority.NORMAL
    return PlaybackPriority.NORMAL


@dataclass
class SequencePlaybackState:
    """Output buffer and arbitration metadata for one Sequence."""

    sequence_index: float
    priority: PlaybackPriority = PlaybackPriority.NORMAL
    htp_intensity: bool = True
    active: bool = False
    fader_level: float = 1.0
    cue_number: float | None = None
    off_on_overwritten: bool = False
    intensities: np.ndarray = field(
        default_factory=lambda: np.zeros(MAX_CHANNELS, dtype=np.float64)
    )
    intensity_timestamps: dict[int, int] = field(default_factory=dict)
    device_values: dict[int, dict[str, typing.Any]] = field(default_factory=dict)
    ltp_timestamps: dict[tuple[int, str], int] = field(default_factory=dict)


@dataclass
class ArbitratedOutput:
    """Composed DMX/device output and ownership map across all active sequences."""

    intensities: np.ndarray = field(
        default_factory=lambda: np.zeros(MAX_CHANNELS, dtype=np.float64)
    )
    device_values: dict[int, dict[str, typing.Any]] = field(default_factory=dict)
    owners: dict[int, tuple[float, float | None]] = field(default_factory=dict)
    param_owners: dict[tuple[int, str], tuple[float, float | None]] = field(
        default_factory=dict
    )


class PlaybackArbitrator:
    """Thread-safe arbitrator merging multiple concurrent sequence playbacks."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ltp_clock: int = 0
        self._states: dict[float, SequencePlaybackState] = {}

    def _next_tick(self) -> int:
        self._ltp_clock += 1
        return self._ltp_clock

    def clear(self) -> None:
        """Reset all sequence playback states and LTP clock."""
        with self._lock:
            self._states.clear()
            self._ltp_clock = 0

    def get_state(self, seq_index: float) -> SequencePlaybackState | None:
        """Return the playback state for *seq_index*, if any."""
        with self._lock:
            return self._states.get(float(seq_index))

    def active_sequences(self) -> list[float]:
        """Return sorted list of currently active sequence indices."""
        with self._lock:
            return sorted(idx for idx, state in self._states.items() if state.active)

    def _get_or_create_state(self, seq_index: float) -> SequencePlaybackState:
        key = float(seq_index)
        state = self._states.get(key)
        if state is None:
            state = SequencePlaybackState(sequence_index=key)
            self._states[key] = state
        return state

    def set_sequence_output(  # pylint: disable=too-many-arguments,too-many-branches,too-many-locals
        self,
        seq_index: float,
        intensities: np.ndarray | dict[int, float] | None = None,
        device_values: dict[int, dict[str, typing.Any]] | None = None,
        *,
        priority: PlaybackPriority | int | str | None = None,
        htp_intensity: bool | None = None,
        fader_level: float | None = None,
        cue_number: float | None = None,
        off_on_overwritten: bool | None = None,
        assert_all: bool = False,
    ) -> ArbitratedOutput:
        """Update output buffer for *seq_index* and return composed arbitration."""
        with self._lock:
            state = self._get_or_create_state(seq_index)
            state.active = True
            if priority is not None:
                state.priority = parse_playback_priority(priority)
            if htp_intensity is not None:
                state.htp_intensity = bool(htp_intensity)
            if fader_level is not None:
                state.fader_level = max(0.0, min(1.0, float(fader_level)))
            if cue_number is not None:
                state.cue_number = float(cue_number)
            if off_on_overwritten is not None:
                state.off_on_overwritten = bool(off_on_overwritten)

            tick = self._next_tick()

            if intensities is not None:
                new_arr = np.zeros(MAX_CHANNELS, dtype=np.float64)
                if isinstance(intensities, dict):
                    for ch, val in intensities.items():
                        ch_int = int(ch)
                        if 1 <= ch_int <= MAX_CHANNELS:
                            new_arr[ch_int - 1] = max(0.0, min(1.0, float(val)))
                else:
                    n_ch = min(MAX_CHANNELS, len(intensities))
                    new_arr[:n_ch] = np.clip(intensities[:n_ch], 0.0, 1.0)

                old_arr = state.intensities
                changed_mask = new_arr != old_arr
                if assert_all:
                    for ch_idx in np.flatnonzero(new_arr > 0.0):
                        state.intensity_timestamps[int(ch_idx) + 1] = tick
                else:
                    for ch_idx in np.flatnonzero(changed_mask):
                        ch = int(ch_idx) + 1
                        if new_arr[ch_idx] > 0.0 or not state.htp_intensity:
                            state.intensity_timestamps[ch] = tick
                        else:
                            state.intensity_timestamps.pop(ch, None)
                state.intensities = new_arr

            if device_values is not None:
                new_devs: dict[int, dict[str, typing.Any]] = {}
                new_ltp: dict[tuple[int, str], int] = {}
                for ch, params in device_values.items():
                    if not isinstance(params, dict) or not params:
                        continue
                    ch_int = int(ch)
                    old_params = state.device_values.get(ch_int, {})
                    copied_params: dict[str, typing.Any] = {}
                    for pk, pv in params.items():
                        p_key = str(pk).strip().lower()
                        if not p_key:
                            continue
                        copied_val = copy.deepcopy(pv)
                        copied_params[p_key] = copied_val
                        prev_ts = state.ltp_timestamps.get((ch_int, p_key))
                        if (
                            assert_all
                            or prev_ts is None
                            or old_params.get(p_key) != copied_val
                        ):
                            new_ltp[(ch_int, p_key)] = tick
                        else:
                            new_ltp[(ch_int, p_key)] = prev_ts
                    if copied_params:
                        new_devs[ch_int] = copied_params
                state.device_values = new_devs
                state.ltp_timestamps = new_ltp

            if any(
                s.active
                and s.off_on_overwritten
                and s.sequence_index != state.sequence_index
                for s in self._states.values()
            ):
                self.check_off_on_overwritten()

            return self.compose()

    def set_fader_level(self, seq_index: float, level: float) -> ArbitratedOutput:
        """Update fader multiplier for *seq_index* and recompose."""
        with self._lock:
            state = self._get_or_create_state(seq_index)
            state.fader_level = max(0.0, min(1.0, float(level)))
            return self.compose()

    def assert_sequence(self, seq_index: float) -> ArbitratedOutput:
        """Refresh all LTP timestamps for *seq_index* so it reclaims ownership."""
        with self._lock:
            state = self._states.get(float(seq_index))
            if state is None or not state.active:
                return self.compose()
            tick = self._next_tick()
            for ch_idx in np.flatnonzero(state.intensities > 0.0):
                state.intensity_timestamps[int(ch_idx) + 1] = tick
            for ch, params in state.device_values.items():
                for p_key in params:
                    state.ltp_timestamps[(ch, p_key)] = tick
            return self.compose()

    def release_sequence(
        self, seq_index: float
    ) -> tuple[ArbitratedOutput, dict[int, set[str]]]:
        """Deactivate *seq_index* and report parameters with no remaining owner."""
        with self._lock:
            key = float(seq_index)
            state = self._states.get(key)
            released_to_home: dict[int, set[str]] = {}
            if state is None or not state.active:
                return self.compose(), released_to_home

            prev_params: dict[int, set[str]] = {
                ch: set(params.keys())
                for ch, params in state.device_values.items()
                if params
            }
            state.active = False
            state.intensities.fill(0.0)
            state.intensity_timestamps.clear()
            state.device_values.clear()
            state.ltp_timestamps.clear()

            composed = self.compose()
            for ch, p_set in prev_params.items():
                remaining = set(composed.device_values.get(ch, {}).keys())
                orphan = p_set - remaining
                if orphan:
                    released_to_home[ch] = orphan
            return composed, released_to_home

    def release_all(self) -> ArbitratedOutput:
        """Deactivate all concurrent sequence playbacks."""
        with self._lock:
            for state in self._states.values():
                state.active = False
                state.intensities.fill(0.0)
                state.intensity_timestamps.clear()
                state.device_values.clear()
                state.ltp_timestamps.clear()
            return self.compose()

    def check_off_on_overwritten(self) -> list[float]:
        """Release active sequences with ``off_on_overwritten`` that own nothing."""
        with self._lock:
            composed = self.compose()
            owned_seqs: set[float] = {seq for seq, _cue in composed.owners.values()}
            owned_seqs.update(seq for seq, _cue in composed.param_owners.values())

            released: list[float] = []
            for idx, state in self._states.items():
                if not state.active or not state.off_on_overwritten:
                    continue
                if idx not in owned_seqs:
                    state.active = False
                    state.intensities.fill(0.0)
                    state.intensity_timestamps.clear()
                    state.device_values.clear()
                    state.ltp_timestamps.clear()
                    released.append(idx)
            return released

    def compose(self) -> ArbitratedOutput:
        """Compose intensities, device_values, and owners across active sequences."""
        with self._lock:
            out = ArbitratedOutput()
            active_states = [s for s in self._states.values() if s.active]
            if not active_states:
                return out

            # Sort ascending by sequence_index for deterministic tie-breaking
            active_states.sort(key=lambda s: s.sequence_index)

            # 1. Intensities per channel: highest priority band wins; within band
            #    compare HTP vs LTP-intensity timestamps.
            for ch_idx in range(MAX_CHANNELS):
                ch = ch_idx + 1
                best_prio = -1
                band_entries: list[tuple[SequencePlaybackState, float, int]] = []
                for s in active_states:
                    raw_lvl = float(s.intensities[ch_idx])
                    scaled = raw_lvl * s.fader_level
                    has_contrib = scaled > 0.0 or (
                        not s.htp_intensity and ch in s.intensity_timestamps
                    )
                    if not has_contrib:
                        continue
                    prio = int(s.priority)
                    ts = s.intensity_timestamps.get(ch, 0)
                    if prio > best_prio:
                        best_prio = prio
                        band_entries = [(s, scaled, ts)]
                    elif prio == best_prio:
                        band_entries.append((s, scaled, ts))

                if not band_entries:
                    continue

                # Check if an LTP-intensity sequence is latest in the winning band
                latest_ltp_entry: tuple[SequencePlaybackState, float, int] | None = None
                max_htp_ts = -1
                for s, scaled, ts in band_entries:
                    if not s.htp_intensity:
                        if latest_ltp_entry is None or ts > latest_ltp_entry[2]:
                            latest_ltp_entry = (s, scaled, ts)
                    elif ts > max_htp_ts:
                        max_htp_ts = ts

                if latest_ltp_entry is not None and latest_ltp_entry[2] >= max_htp_ts:
                    win_s, win_lvl, _ts = latest_ltp_entry
                else:
                    win_s, win_lvl, _ts = max(
                        band_entries, key=lambda item: (item[1], item[2])
                    )

                clamped = max(0.0, min(1.0, win_lvl))
                out.intensities[ch_idx] = clamped
                if clamped > 0.0 or not win_s.htp_intensity:
                    out.owners[ch] = (win_s.sequence_index, win_s.cue_number)

            # 2. Non-intensity device attributes: (priority, ltp_timestamp) wins
            best_param_rank: dict[tuple[int, str], tuple[int, int]] = {}
            for s in active_states:
                prio = int(s.priority)
                for ch, params in s.device_values.items():
                    for p_key, p_val in params.items():
                        ts = s.ltp_timestamps.get((ch, p_key), 0)
                        rank = (prio, ts)
                        key = (ch, p_key)
                        prev = best_param_rank.get(key)
                        if prev is None or rank > prev:
                            best_param_rank[key] = rank
                            out.device_values.setdefault(ch, {})[p_key] = copy.deepcopy(
                                p_val
                            )
                            out.param_owners[key] = (s.sequence_index, s.cue_number)
                            out.owners.setdefault(ch, (s.sequence_index, s.cue_number))

            return out

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
"""Real-time 40 Hz vectorized parametric Effects Engine for OLC."""

from __future__ import annotations

import colorsys
import math
import threading
import time
import typing
from typing import Any

import numpy as np

from olc.core.scheduler import ThreadingScheduler, TimerScheduler
from olc.define import MAX_CHANNELS
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType
from olc.show.effect import (
    ActiveEffectInstance,
    DistributeDirection,
    EffectDefinition,
    EffectEnvelopeMode,
    EffectLayer,
    EffectMode,
    WaveformType,
)
from olc.show.palette import PaletteCategory

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.devices.device import LightingDevice
    from olc.show.lightshow import LightShow
    from olc.show.palette import PaletteRef


def _det_hash_float(seed_a: int, seed_b: int) -> float:
    """Return deterministic pseudo-random float in [0.0, 1.0[ from two integer seeds."""
    x = ((seed_a * 73856093) ^ (seed_b * 19349663) ^ 0x9E3779B9) & 0xFFFFFFFF
    x = ((x >> 16) ^ x) * 0x45D9F3B & 0xFFFFFFFF
    x = ((x >> 16) ^ x) & 0xFFFFFFFF
    return (x & 0xFFFFFF) / float(0x1000000)


def _parse_hex_or_rgb(
    val: Any,  # noqa: ANN401
) -> tuple[float, float, float] | None:
    """Parse a '#RRGGBB' hex string or (r, g, b) sequence into normalized floats."""
    if isinstance(val, str):
        s = val.strip().lstrip("#")
        if len(s) == 6:
            try:
                return (
                    int(s[0:2], 16) / 255.0,
                    int(s[2:4], 16) / 255.0,
                    int(s[4:6], 16) / 255.0,
                )
            except ValueError:
                return None
    if isinstance(val, (list, tuple)) and len(val) >= 3:
        try:
            r, g, b = float(val[0]), float(val[1]), float(val[2])
            if max(r, g, b) > 1.0:
                return (
                    max(0.0, min(1.0, r / 255.0)),
                    max(0.0, min(1.0, g / 255.0)),
                    max(0.0, min(1.0, b / 255.0)),
                )
            return (
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
            )
        except (TypeError, ValueError):
            return None
    return None


def compute_channel_phase_offsets(
    channels: list[int],
    *,
    groups: int = 0,
    blocks: int = 1,
    wings: int = 1,
    direction: DistributeDirection = DistributeDirection.FORWARD,
    phase_start_deg: float = 0.0,
    phase_end_deg: float = 360.0,
    effect_seed: int = 1,
) -> np.ndarray:
    """Compute normalized phase offset theta_i in [0.0, 1.0[ for each channel.

    Implements the pipeline: Blocks (Buddying) -> Wings (Symmetry) -> Groups (Spread)
    -> Direction -> Phase range [phase_start_deg, phase_end_deg].
    """
    n_total = len(channels)
    if n_total == 0:
        return np.zeros(0, dtype=np.float64)

    b_size = max(1, int(blocks))
    w_count = max(1, int(wings))
    g_count = max(0, int(groups))

    # 1. Blocks (Buddying)
    indices = np.arange(n_total, dtype=np.int64)
    block_idx = indices // b_size
    n_blocks = int(math.ceil(n_total / float(b_size)))

    # 2. Wings (Mirror symmetry)
    if w_count <= 1 or n_blocks <= 1:
        wing_idx = block_idx
        n_eff = n_blocks
    elif w_count == 2:
        # Exact center-symmetric mirroring for 2 wings (both even and odd counts)
        mirror = (n_blocks - 1) - block_idx
        wing_idx = np.minimum(block_idx, mirror)
        n_eff = int(math.ceil(n_blocks / 2.0))
    else:
        seg_len = max(1, int(math.ceil(n_blocks / float(w_count))))
        w_num = block_idx // seg_len
        local = block_idx % seg_len
        wing_idx = np.where((w_num % 2) == 1, (seg_len - 1) - local, local)
        wing_idx = np.clip(wing_idx, 0, seg_len - 1)
        n_eff = seg_len

    # 3. Groups (0 = Full Spread across n_eff, 1 = Unison, k > 1 = modulo k)
    if g_count == 1 or n_eff <= 1:
        spread_count = 1
        slot_idx = np.zeros(n_total, dtype=np.int64)
    elif g_count == 0:
        spread_count = n_eff
        slot_idx = wing_idx
    else:
        spread_count = g_count
        slot_idx = wing_idx % g_count

    # 4. Direction
    if spread_count <= 1 and direction != DistributeDirection.RANDOM:
        frac = np.zeros(n_total, dtype=np.float64)
    elif direction == DistributeDirection.FORWARD:
        frac = slot_idx.astype(np.float64) / float(spread_count)
    elif direction == DistributeDirection.BACKWARD:
        frac = ((spread_count - 1 - slot_idx) % spread_count).astype(
            np.float64
        ) / float(spread_count)
    elif direction == DistributeDirection.BOUNCE:
        if spread_count <= 2:
            frac = slot_idx.astype(np.float64) / float(max(1, spread_count))
        else:
            norm_pos = slot_idx.astype(np.float64) / float(spread_count - 1)
            frac = 0.5 * (1.0 - np.abs(2.0 * norm_pos - 1.0))
    elif direction == DistributeDirection.RANDOM:
        frac = np.array(
            [_det_hash_float(effect_seed, int(ch)) for ch in channels],
            dtype=np.float64,
        )
    else:
        frac = slot_idx.astype(np.float64) / float(spread_count)

    # 5. Map to [phase_start_deg, phase_end_deg] in turns [0.0, 1.0[
    span_deg = float(phase_end_deg) - float(phase_start_deg)
    deg = float(phase_start_deg) + frac * span_deg
    return np.mod(deg / 360.0, 1.0)


def evaluate_waveform(
    waveform: WaveformType,
    phases: np.ndarray,
    *,
    mode: EffectMode = EffectMode.RELATIVE,
    duty_cycle: float = 0.5,
    softness: float = 1.0,
    cycle_index: np.ndarray | None = None,
    channels: list[int] | None = None,
    curve_evaluator: typing.Callable[[np.ndarray], float | np.ndarray] | None = None,
) -> np.ndarray:
    """Evaluate *waveform* at normalized *phases* in [0.0, 1.0[.

    In RELATIVE mode:
      - Bipolar waveforms (SINE, COSINE, TRIANGLE, SQUARE, SAW_UP, SAW_DOWN, RANDOM)
        return values in [-1.0, +1.0].
      - PULSE returns values in [0.0, +1.0].
      - CURVE maps [0.0, 1.0] curve output to [-1.0, +1.0].
    In ABSOLUTE mode:
      - All waveforms return unipolar interpolation factors in [0.0, +1.0].
    """
    phi = np.mod(phases, 1.0)
    duty = max(0.01, min(1.0, float(duty_cycle)))
    soft = max(0.0, min(1.0, float(softness)))

    if waveform == WaveformType.SINE:
        bipolar = np.sin(2.0 * math.pi * phi)
        return bipolar if mode == EffectMode.RELATIVE else 0.5 * (bipolar + 1.0)

    if waveform == WaveformType.COSINE:
        bipolar = np.cos(2.0 * math.pi * phi)
        return bipolar if mode == EffectMode.RELATIVE else 0.5 * (bipolar + 1.0)

    if waveform == WaveformType.TRIANGLE:
        # 0 -> 0, 0.25 -> +1, 0.5 -> 0, 0.75 -> -1, 1.0 -> 0
        bipolar = np.where(
            phi < 0.25,
            4.0 * phi,
            np.where(phi < 0.75, 2.0 - 4.0 * phi, 4.0 * phi - 4.0),
        )
        return bipolar if mode == EffectMode.RELATIVE else 0.5 * (bipolar + 1.0)

    if waveform == WaveformType.SQUARE:
        bipolar = np.where(phi < duty, 1.0, -1.0)
        return (
            bipolar if mode == EffectMode.RELATIVE else np.where(phi < duty, 1.0, 0.0)
        )

    if waveform == WaveformType.SAW_UP:
        bipolar = 2.0 * phi - 1.0
        return bipolar if mode == EffectMode.RELATIVE else phi

    if waveform == WaveformType.SAW_DOWN:
        bipolar = 1.0 - 2.0 * phi
        return bipolar if mode == EffectMode.RELATIVE else 1.0 - phi

    if waveform == WaveformType.PULSE:
        # Unipolar [0.0, 1.0] pulse of width `duty` and cosine edge `soft`
        out = np.zeros_like(phi, dtype=np.float64)
        active = phi < duty
        if not np.any(active):
            return out
        if soft <= 1e-5:
            out[active] = 1.0
            return out
        edge = max(1e-5, 0.5 * soft * duty)
        p_act = phi[active]
        val = np.ones_like(p_act, dtype=np.float64)
        rise = p_act < edge
        if np.any(rise):
            val[rise] = 0.5 - 0.5 * np.cos(math.pi * (p_act[rise] / edge))
        fall = p_act > (duty - edge)
        if np.any(fall):
            rem = np.maximum(0.0, duty - p_act[fall])
            val[fall] = 0.5 - 0.5 * np.cos(math.pi * (rem / edge))
        out[active] = np.clip(val, 0.0, 1.0)
        return out

    if waveform == WaveformType.RAINBOW:
        # Normalized hue angle in [0.0, 1.0[
        return phi

    if waveform == WaveformType.CURVE:
        if curve_evaluator is not None:
            unipolar = np.clip(
                np.asarray(curve_evaluator(phi), dtype=np.float64), 0.0, 1.0
            )
        else:
            unipolar = phi
        return (2.0 * unipolar - 1.0) if mode == EffectMode.RELATIVE else unipolar

    if waveform == WaveformType.RANDOM:
        n_items = len(phi)
        ch_list = channels if channels is not None else list(range(1, n_items + 1))
        cyc = (
            cycle_index
            if cycle_index is not None
            else np.zeros(n_items, dtype=np.int64)
        )
        v0 = np.array(
            [_det_hash_float(int(cyc[i]), int(ch_list[i])) for i in range(n_items)],
            dtype=np.float64,
        )
        v1 = np.array(
            [_det_hash_float(int(cyc[i]) + 1, int(ch_list[i])) for i in range(n_items)],
            dtype=np.float64,
        )
        if soft <= 1e-5:
            unipolar = v0
        else:
            blend = 0.5 - 0.5 * np.cos(math.pi * phi)
            unipolar = v0 + (v1 - v0) * (soft * blend)
        return (2.0 * unipolar - 1.0) if mode == EffectMode.RELATIVE else unipolar

    return np.zeros_like(phi, dtype=np.float64)


NUM_SPEED_MASTERS = 8
NUM_RATE_MASTERS = 4
NUM_SIZE_MASTERS = 4
SPEED_MASTER_MAX_BPM = 240.0


# pylint: disable=too-many-instance-attributes
class EffectsEngine:
    """Real-time 40 Hz non-destructive parametric Effects Engine."""

    def __init__(
        self,
        app: CoreApplication | None = None,
        lightshow: LightShow | None = None,
        scheduler: TimerScheduler | None = None,
        interval_ms: int = 25,
    ) -> None:
        self._lock = threading.RLock()
        self.app = app
        self._lightshow = lightshow
        self.scheduler: TimerScheduler = (
            scheduler if scheduler is not None else ThreadingScheduler()
        )
        self.interval_ms = max(5, int(interval_ms))
        self._timer_handle: Any = None
        self._instances: list[ActiveEffectInstance] = []
        # Base unmodulated device values per channel: {channel: {param: base_val}}
        self._base_device_state: dict[int, dict[str, Any]] = {}
        # Last value written by the engine on previous tick: {channel: {param: val}}
        self._last_modulated_state: dict[int, dict[str, Any]] = {}
        # Tap-tempo history timestamps
        self._tap_timestamps: list[float] = []
        # Decoupled FX Master buses
        self._speed_masters_bpm: dict[int, float] = {
            i: 120.0 for i in range(1, NUM_SPEED_MASTERS + 1)
        }
        self._rate_masters: dict[int, float] = {
            i: 1.0 for i in range(1, NUM_RATE_MASTERS + 1)
        }
        self._size_masters: dict[int, float] = {
            i: 1.0 for i in range(1, NUM_SIZE_MASTERS + 1)
        }
        self._speed_master_frozen: dict[int, bool] = {
            i: False for i in range(1, NUM_SPEED_MASTERS + 1)
        }
        self._rate_master_frozen: dict[int, bool] = {
            i: False for i in range(1, NUM_RATE_MASTERS + 1)
        }
        self._speed_master_taps: dict[int, list[float]] = {}

    @property
    def lightshow(self) -> LightShow | None:
        """Return active LightShow instance."""
        if self._lightshow is not None:
            return self._lightshow
        if self.app is not None:
            return self.app.lightshow
        return None

    @property
    def has_active_effects(self) -> bool:
        """Return True if at least one effect instance is currently running."""
        with self._lock:
            return bool(self._instances)

    def get_active_instances(self) -> list[ActiveEffectInstance]:
        """Return a shallow copy of active effect instances."""
        with self._lock:
            return list(self._instances)

    def get_channel_effects(self, channel: int) -> list[ActiveEffectInstance]:
        """Return all active effect instances currently modulating *channel*."""
        ch_int = int(channel)
        with self._lock:
            return [inst for inst in self._instances if ch_int in inst.channels]

    # -- Decoupled Speed / Rate / Size Master buses ---------------------------

    def _resolve_effect_masters_locked(
        self, eff: EffectDefinition
    ) -> tuple[float | None, float, float, float]:
        """Return (speed_bpm, speed_multiplier, rate_master, size_master)."""
        sm_id = getattr(eff, "speed_master", None)
        if sm_id is None:
            speed_bpm: float | None = None
        elif self._speed_master_frozen.get(sm_id, False):
            speed_bpm = 0.0
        else:
            speed_bpm = float(self._speed_masters_bpm.get(sm_id, 120.0))

        speed_mult = float(getattr(eff, "speed_multiplier", 1.0))

        rm_id = getattr(eff, "rate_master", None)
        if rm_id is None:
            rate_master = 1.0
        elif self._rate_master_frozen.get(rm_id, False):
            rate_master = 0.0
        else:
            rate_master = float(self._rate_masters.get(rm_id, 1.0))

        sz_id = getattr(eff, "size_master", None)
        size_master = (
            1.0 if sz_id is None else float(self._size_masters.get(sz_id, 1.0))
        )
        return speed_bpm, speed_mult, rate_master, size_master

    def _advance_all_phases_locked(self, t_now: float) -> None:
        """Integrate phases of all active instances up to *t_now*."""
        show = self.lightshow
        if show is None:
            return
        for inst in self._instances:
            eff = show.effects.get(inst.effect_number)
            if eff is None:
                continue
            speed_bpm, speed_mult, rate_m, _size_m = (
                self._resolve_effect_masters_locked(eff)
            )
            inst.advance_phase(
                t_now,
                eff.cycle_time,
                master_rate=rate_m,
                speed_bpm=speed_bpm,
                speed_multiplier=speed_mult,
            )

    def _emit_master_changed(self, kind: str, master_id: int, value: float) -> None:
        if self.app is not None and hasattr(self.app, "emit"):
            self.app.emit("effect.master_changed", kind, int(master_id), float(value))

    def get_speed_master_bpm(self, master_id: int) -> float:
        """Return current BPM of Speed Master *master_id*."""
        with self._lock:
            return float(self._speed_masters_bpm.get(int(master_id), 120.0))

    def set_speed_master_bpm(
        self, master_id: int, bpm: float, *, now: float | None = None
    ) -> float:
        """Set Speed Master *master_id* BPM (0.0 .. SPEED_MASTER_MAX_BPM)."""
        t_now = time.monotonic() if now is None else float(now)
        mid = max(1, min(NUM_SPEED_MASTERS, int(master_id)))
        clamped = max(0.0, min(SPEED_MASTER_MAX_BPM, float(bpm)))
        with self._lock:
            self._advance_all_phases_locked(t_now)
            self._speed_masters_bpm[mid] = clamped
        self._emit_master_changed("speed", mid, clamped)
        return clamped

    def scale_speed_master(
        self, master_id: int, factor: float, *, now: float | None = None
    ) -> float:
        """Multiply Speed Master *master_id* BPM by *factor* (e.g. 0.5 or 2.0)."""
        t_now = time.monotonic() if now is None else float(now)
        mid = max(1, min(NUM_SPEED_MASTERS, int(master_id)))
        with self._lock:
            self._advance_all_phases_locked(t_now)
            cur = self._speed_masters_bpm.get(mid, 120.0)
            new_bpm = max(1.0, min(SPEED_MASTER_MAX_BPM, cur * float(factor)))
            self._speed_masters_bpm[mid] = new_bpm
        self._emit_master_changed("speed", mid, new_bpm)
        return new_bpm

    def tap_speed_master(
        self, master_id: int, *, now: float | None = None
    ) -> float | None:
        """Record a tap timestamp for Speed Master *master_id* and return BPM."""
        t_now = time.monotonic() if now is None else float(now)
        mid = max(1, min(NUM_SPEED_MASTERS, int(master_id)))
        new_bpm: float | None = None
        with self._lock:
            taps = self._speed_master_taps.setdefault(mid, [])
            if taps and (t_now - taps[-1]) > 3.0:
                taps.clear()
            taps.append(t_now)
            if len(taps) > 5:
                del taps[:-5]
            if len(taps) >= 2:
                intervals = [
                    b - a for a, b in zip(taps, taps[1:], strict=False) if b > a
                ]
                if intervals:
                    mean_dt = sum(intervals) / len(intervals)
                    new_bpm = max(
                        1.0, min(SPEED_MASTER_MAX_BPM, 60.0 / max(0.05, mean_dt))
                    )
                    self._advance_all_phases_locked(t_now)
                    self._speed_masters_bpm[mid] = new_bpm
        if new_bpm is not None:
            self._emit_master_changed("speed", mid, new_bpm)
        return new_bpm

    def get_rate_master(self, master_id: int) -> float:
        """Return current multiplier of Rate Master *master_id*."""
        with self._lock:
            return float(self._rate_masters.get(int(master_id), 1.0))

    def set_rate_master(
        self, master_id: int, rate: float, *, now: float | None = None
    ) -> float:
        """Set Rate Master *master_id* multiplier (>= 0.0)."""
        t_now = time.monotonic() if now is None else float(now)
        mid = max(1, min(NUM_RATE_MASTERS, int(master_id)))
        clamped = max(0.0, float(rate))
        with self._lock:
            self._advance_all_phases_locked(t_now)
            self._rate_masters[mid] = clamped
        self._emit_master_changed("rate", mid, clamped)
        return clamped

    def get_size_master(self, master_id: int) -> float:
        """Return current scale [0.0..1.0] of Size Master *master_id*."""
        with self._lock:
            return float(self._size_masters.get(int(master_id), 1.0))

    def set_size_master(
        self, master_id: int, size: float, *, now: float | None = None
    ) -> float:
        """Set Size Master *master_id* scale [0.0..1.0]."""
        t_now = time.monotonic() if now is None else float(now)
        mid = max(1, min(NUM_SIZE_MASTERS, int(master_id)))
        clamped = max(0.0, min(1.0, float(size)))
        with self._lock:
            self._advance_all_phases_locked(t_now)
            self._size_masters[mid] = clamped
        self._emit_master_changed("size", mid, clamped)
        return clamped

    def is_master_frozen(self, kind: str, master_id: int) -> bool:
        """Return True if Speed or Rate Master *master_id* is frozen."""
        mid = int(master_id)
        with self._lock:
            if kind == "speed":
                return bool(self._speed_master_frozen.get(mid, False))
            if kind == "rate":
                return bool(self._rate_master_frozen.get(mid, False))
            return False

    def toggle_master_freeze(
        self, kind: str, master_id: int, *, now: float | None = None
    ) -> bool:
        """Toggle freeze state on a Speed or Rate Master; return new freeze state."""
        t_now = time.monotonic() if now is None else float(now)
        mid = int(master_id)
        frozen = False
        with self._lock:
            self._advance_all_phases_locked(t_now)
            if kind == "speed":
                frozen = not self._speed_master_frozen.get(mid, False)
                self._speed_master_frozen[mid] = frozen
            elif kind == "rate":
                frozen = not self._rate_master_frozen.get(mid, False)
                self._rate_master_frozen[mid] = frozen
        self._emit_master_changed(kind, mid, 0.0 if frozen else 1.0)
        return frozen

    def is_channel_intensity_modulated(self, channel: int) -> bool:
        """Return True if *channel* has an active intensity layer."""
        show = self.lightshow
        if show is None:
            return False
        ch_int = int(channel)
        with self._lock:
            for inst in self._instances:
                if ch_int not in inst.channels:
                    continue
                eff = show.effects.get(inst.effect_number)
                if eff is None:
                    continue
                if any(layer.parameter == "intensity" for layer in eff.layers):
                    return True
        return False

    def get_base_device_value(self, channel: int, parameter: str) -> Any:  # noqa: ANN401
        """Return unmodulated base device value for *(channel, parameter)*."""
        p_norm = str(parameter).strip().lower()
        with self._lock:
            ch_base = self._base_device_state.get(int(channel))
            if ch_base is not None and p_norm in ch_base:
                return ch_base[p_norm]
        return None

    def notify_base_parameter_changed(
        self,
        channels: list[int],
        parameter: str | None = None,
    ) -> None:
        """Refresh stored base device state after an external manual or cue edit."""
        show = self.lightshow
        if show is None:
            return
        with self._lock:
            for ch in channels:
                ch_int = int(ch)
                dev = show.patch.devices.get(ch_int)
                if dev is None:
                    continue
                ch_base = self._base_device_state.get(ch_int)
                if ch_base is None:
                    continue
                params = (
                    [str(parameter).strip().lower()]
                    if parameter is not None
                    else list(ch_base.keys())
                )
                for p_name in params:
                    if p_name in ch_base:
                        curr = self._read_device_parameter(dev, p_name)
                        if curr is not None:
                            ch_base[p_name] = curr
                            if ch_int in self._last_modulated_state:
                                self._last_modulated_state[ch_int][p_name] = curr

    @staticmethod
    def _configure_entry_envelope(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        inst: ActiveEffectInstance,
        eff: EffectDefinition,
        target_size: float,
        target_rate: float,
        fade_in: float,
        t_now: float,
        *,
        is_existing: bool,
        master_rate: float = 1.0,
        speed_bpm: float | None = None,
        speed_multiplier: float = 1.0,
    ) -> None:
        """Configure entry size/rate ramps on *inst* according to *eff.entry_mode*."""
        mode = getattr(eff, "entry_mode", EffectEnvelopeMode.FADE_BY_SIZE)
        tgt_size = max(0.0, float(target_size))
        tgt_rate = max(0.0, float(target_rate))
        inst.remove_on_fade_end = False
        if is_existing:
            inst.advance_phase(
                t_now,
                eff.cycle_time,
                master_rate=master_rate,
                speed_bpm=speed_bpm,
                speed_multiplier=speed_multiplier,
            )

        if fade_in <= 0.0 or mode == EffectEnvelopeMode.IMMEDIATE:
            inst.size_scale = tgt_size
            inst.fade_duration = 0.0
            inst.cascade_fade = False
            inst.rate_scale = tgt_rate
            inst.rate_fade_duration = 0.0
            return

        dur = float(fade_in)
        if mode in (
            EffectEnvelopeMode.FADE_BY_SIZE,
            EffectEnvelopeMode.FADE_BY_SIZE_AND_RATE,
        ):
            start_sz = inst.effective_size_scale(t_now) if is_existing else 0.0
            inst.size_scale = start_sz
            inst.fade_start_size = start_sz
            inst.fade_target_size = tgt_size
            inst.fade_start_time = t_now
            inst.fade_duration = dur
            inst.cascade_fade = bool(getattr(eff, "cascade", False))
        else:
            inst.size_scale = tgt_size
            inst.fade_duration = 0.0
            inst.cascade_fade = False

        if mode in (
            EffectEnvelopeMode.FADE_BY_RATE,
            EffectEnvelopeMode.FADE_BY_SIZE_AND_RATE,
        ):
            start_rt = inst.effective_rate_scale(t_now) if is_existing else 0.05
            inst.rate_scale = start_rt
            inst.fade_start_rate = start_rt
            inst.fade_target_rate = tgt_rate
            inst.rate_fade_start_time = t_now
            inst.rate_fade_duration = dur
        else:
            inst.rate_scale = tgt_rate
            inst.rate_fade_duration = 0.0

    @staticmethod
    def _configure_exit_envelope(
        inst: ActiveEffectInstance,
        eff: EffectDefinition | None,
        fade_out: float,
        t_now: float,
    ) -> bool:
        """Configure exit ramps on *inst*; return True if faded out."""
        mode = (
            getattr(eff, "exit_mode", EffectEnvelopeMode.FADE_BY_SIZE)
            if eff is not None
            else EffectEnvelopeMode.FADE_BY_SIZE
        )
        if fade_out <= 0.0 or mode == EffectEnvelopeMode.IMMEDIATE:
            return False

        dur = float(fade_out)
        if mode in (
            EffectEnvelopeMode.FADE_BY_SIZE,
            EffectEnvelopeMode.FADE_BY_SIZE_AND_RATE,
        ):
            cur_sz = inst.effective_size_scale(t_now)
            inst.fade_start_size = cur_sz
            inst.fade_target_size = 0.0
            inst.fade_start_time = t_now
            inst.fade_duration = dur
            inst.cascade_fade = bool(getattr(eff, "cascade", False)) if eff else False
        else:
            inst.fade_duration = 0.0
            inst.cascade_fade = False

        if mode in (
            EffectEnvelopeMode.FADE_BY_RATE,
            EffectEnvelopeMode.FADE_BY_SIZE_AND_RATE,
        ):
            cur_rt = inst.effective_rate_scale(t_now)
            inst.fade_start_rate = cur_rt
            inst.fade_target_rate = 0.01
            inst.rate_fade_start_time = t_now
            inst.rate_fade_duration = dur
        else:
            inst.rate_fade_duration = 0.0

        inst.remove_on_fade_end = True
        return True

    # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
    def start_effect(
        self,
        effect_number: float,
        channels: list[int],
        *,
        rate_scale: float = 1.0,
        size_scale: float = 1.0,
        groups_override: int | None = None,
        blocks_override: int | None = None,
        wings_override: int | None = None,
        direction_override: DistributeDirection | None = None,
        fade_in: float = 0.0,
        now: float | None = None,
    ) -> ActiveEffectInstance | None:
        """Start or update an Effect on an ordered *channels* selection."""
        show = self.lightshow
        if show is None:
            return None
        eff = show.effects.get(effect_number)
        if eff is None or not channels:
            return None

        t_now = time.monotonic() if now is None else float(now)
        eff_num = round(float(effect_number), 3)
        target_params = {layer.parameter for layer in eff.layers}

        with self._lock:
            # If the same effect is already running on the same channels, update it
            # smoothly without resetting start_timestamp (phase continuity!)
            for existing in self._instances:
                if existing.effect_number == eff_num and existing.channels == list(
                    dict.fromkeys(int(c) for c in channels)
                ):
                    existing.groups_override = groups_override
                    existing.blocks_override = blocks_override
                    existing.wings_override = wings_override
                    existing.direction_override = direction_override
                    speed_bpm, speed_mult, rate_m, _size_m = (
                        self._resolve_effect_masters_locked(eff)
                    )
                    self._configure_entry_envelope(
                        existing,
                        eff,
                        size_scale,
                        rate_scale,
                        fade_in,
                        t_now,
                        is_existing=True,
                        master_rate=rate_m,
                        speed_bpm=speed_bpm,
                        speed_multiplier=speed_mult,
                    )
                    self._ensure_timer_locked()
                    return existing

            # Stomp overlapping channels from instances touching the same parameters
            self._stomp_overlapping_channels_locked(
                channels, target_params, exclude_effect=eff_num
            )

            inst = ActiveEffectInstance(
                effect_number=eff_num,
                channels=channels,
                rate_scale=rate_scale,
                size_scale=size_scale,
                groups_override=groups_override,
                blocks_override=blocks_override,
                wings_override=wings_override,
                direction_override=direction_override,
                start_timestamp=t_now,
                last_phase_time=t_now,
            )
            self._configure_entry_envelope(
                inst, eff, size_scale, rate_scale, fade_in, t_now, is_existing=False
            )
            self._capture_initial_base_state_locked(inst.channels, eff)
            self._instances.append(inst)
            self._ensure_timer_locked()
        return inst

    # pylint: disable=too-many-branches
    def stop_effect(
        self,
        effect_number: float | None = None,
        channels: list[int] | None = None,
        *,
        fade_out: float = 0.0,
        now: float | None = None,
    ) -> int:
        """Stop running effect(s) matching *effect_number* and/or *channels*.

        If *fade_out* > 0 and exit mode is not IMMEDIATE, applies the effect's exit
        envelope over *fade_out* seconds before removing and restoring base state.
        """
        t_now = time.monotonic() if now is None else float(now)
        eff_key = round(float(effect_number), 3) if effect_number is not None else None
        ch_set = {int(c) for c in channels} if channels is not None else None
        affected = 0
        restored_channels: set[int] = set()
        show = self.lightshow

        with self._lock:
            remaining: list[ActiveEffectInstance] = []
            for inst in self._instances:
                eff_match = eff_key is None or inst.effect_number == eff_key
                ch_match = ch_set is None or bool(ch_set.intersection(inst.channels))
                if not (eff_match and ch_match):
                    remaining.append(inst)
                    continue

                affected += 1
                eff = show.effects.get(inst.effect_number) if show is not None else None
                partial = ch_set is not None and not ch_set.issuperset(inst.channels)
                exit_mode = (
                    getattr(eff, "exit_mode", EffectEnvelopeMode.FADE_BY_SIZE)
                    if eff is not None
                    else EffectEnvelopeMode.FADE_BY_SIZE
                )
                if fade_out > 0.0 and exit_mode != EffectEnvelopeMode.IMMEDIATE:
                    if partial and ch_set is not None:
                        stay_chs = [c for c in inst.channels if c not in ch_set]
                        fade_chs = [c for c in inst.channels if c in ch_set]
                        inst.channels = stay_chs
                        remaining.append(inst)
                        if eff is not None:
                            speed_bpm, speed_mult, rate_m, _size_m = (
                                self._resolve_effect_masters_locked(eff)
                            )
                            inst.advance_phase(
                                t_now,
                                eff.cycle_time,
                                master_rate=rate_m,
                                speed_bpm=speed_bpm,
                                speed_multiplier=speed_mult,
                            )
                        fading_copy = ActiveEffectInstance(
                            effect_number=inst.effect_number,
                            channels=fade_chs,
                            rate_scale=inst.effective_rate_scale(t_now),
                            size_scale=inst.effective_size_scale(t_now),
                            groups_override=inst.groups_override,
                            blocks_override=inst.blocks_override,
                            wings_override=inst.wings_override,
                            direction_override=inst.direction_override,
                            start_timestamp=inst.start_timestamp,
                            accumulated_cycles=inst.accumulated_cycles,
                            last_phase_time=inst.last_phase_time,
                        )
                        if self._configure_exit_envelope(
                            fading_copy, eff, fade_out, t_now
                        ):
                            remaining.append(fading_copy)
                        else:
                            restored_channels.update(fade_chs)
                    elif self._configure_exit_envelope(inst, eff, fade_out, t_now):
                        remaining.append(inst)
                    else:
                        restored_channels.update(inst.channels)
                elif partial and ch_set is not None:
                    removed = [c for c in inst.channels if c in ch_set]
                    inst.channels = [c for c in inst.channels if c not in ch_set]
                    remaining.append(inst)
                    restored_channels.update(removed)
                else:
                    restored_channels.update(inst.channels)

            self._instances = [i for i in remaining if i.channels]
            for ch in restored_channels:
                self._restore_channel_base_state_locked(ch)
            if not self._instances:
                self._stop_timer_locked()

        if restored_channels:
            self._notify_dmx_and_ui(restored_channels)
        return affected

    def stop_all(self) -> None:
        """Stop all running effects immediately and restore base device states."""
        self.stop_effect(effect_number=None, channels=None, fade_out=0.0)

    def tap_tempo(
        self,
        effect_number: float | None = None,
        *,
        now: float | None = None,
    ) -> float | None:
        """Record a Tap Tempo beat and update BPM/cycle_time; return computed BPM."""
        t_now = time.monotonic() if now is None else float(now)
        with self._lock:
            if self._tap_timestamps and (t_now - self._tap_timestamps[-1]) > 3.0:
                self._tap_timestamps.clear()
            self._tap_timestamps.append(t_now)
            if len(self._tap_timestamps) > 4:
                self._tap_timestamps = self._tap_timestamps[-4:]
            if len(self._tap_timestamps) < 2:
                return None
            intervals = [
                self._tap_timestamps[i + 1] - self._tap_timestamps[i]
                for i in range(len(self._tap_timestamps) - 1)
            ]
            avg_period = sum(intervals) / float(len(intervals))
            if avg_period <= 0.05:
                return None
            bpm = round(60.0 / avg_period, 1)
            show = self.lightshow
            if show is not None:
                if effect_number is not None:
                    eff = show.effects.get(effect_number)
                    if eff is not None:
                        eff.set_bpm(bpm)
                else:
                    for inst in self._instances:
                        eff = show.effects.get(inst.effect_number)
                        if eff is not None:
                            eff.set_bpm(bpm)
            return bpm

    def apply_intensity_modulation(
        self,
        base_composite: np.ndarray,
        *,
        now: float | None = None,
    ) -> np.ndarray:
        """Return a new composite intensity array [0.0..1.0] with active effects."""
        show = self.lightshow
        if show is None:
            return base_composite
        with self._lock:
            if not self._instances:
                return base_composite
            t_now = time.monotonic() if now is None else float(now)
            result = base_composite.copy()
            for inst in self._instances:
                eff = show.effects.get(inst.effect_number)
                if eff is None or not inst.channels:
                    continue
                int_layers = [
                    layer for layer in eff.layers if layer.parameter == "intensity"
                ]
                if not int_layers:
                    continue
                speed_bpm, speed_mult, rate_m, size_m = (
                    self._resolve_effect_masters_locked(eff)
                )
                theta_all = self._compute_instance_thetas(eff, inst)
                size_all = inst.effective_channel_size_scales(t_now, theta_all) * size_m
                if not np.any(size_all > 0.0):
                    continue
                valid_pairs = [
                    (idx, ch)
                    for idx, ch in enumerate(inst.channels)
                    if 1 <= ch <= len(result)
                ]
                if not valid_pairs:
                    continue
                sel_indices = np.array([idx for idx, _ in valid_pairs], dtype=np.int64)
                ch_indices = np.array([ch - 1 for _, ch in valid_pairs], dtype=np.int64)
                theta = theta_all[sel_indices]
                size_mult = size_all[sel_indices]
                cycles = inst.phase_cycles_at(
                    t_now,
                    eff.cycle_time,
                    master_rate=rate_m,
                    speed_bpm=speed_bpm,
                    speed_multiplier=speed_mult,
                )

                for layer in int_layers:
                    phi_raw = (
                        cycles * layer.freq_mult
                        - theta
                        + (layer.phase_offset_deg + inst.phase_offset_deg) / 360.0
                    )
                    cyc_idx = np.floor(phi_raw).astype(np.int64)
                    phi = np.mod(phi_raw, 1.0)
                    wave = self._eval_layer_waveform(
                        show,
                        layer,
                        phi,
                        cyc_idx,
                        [ch for _, ch in valid_pairs],
                    )
                    if layer.mode == EffectMode.RELATIVE:
                        delta = (layer.size / 100.0) * size_mult * wave
                        result[ch_indices] = np.clip(
                            result[ch_indices] + delta, 0.0, 1.0
                        )
                    else:
                        low_norm, high_norm = self._resolve_intensity_bounds(
                            show,
                            layer,
                            [ch for _, ch in valid_pairs],
                            result[ch_indices],
                        )
                        target = low_norm + (high_norm - low_norm) * wave
                        blended = result[ch_indices] + (
                            target - result[ch_indices]
                        ) * np.clip(size_mult, 0.0, 1.0)
                        result[ch_indices] = np.clip(blended, 0.0, 1.0)
            return result

    def apply_channel_intensity(
        self,
        channel: int,
        base_level: float,
        *,
        now: float | None = None,
    ) -> float:
        """Compute modulated intensity [0.0..1.0] for a single 1-based *channel*."""
        if not self.is_channel_intensity_modulated(channel):
            return base_level
        arr = np.zeros(MAX_CHANNELS, dtype=np.float64)
        ch_int = int(channel)
        if 1 <= ch_int <= MAX_CHANNELS:
            arr[ch_int - 1] = float(base_level)
            mod = self.apply_intensity_modulation(arr, now=now)
            return float(mod[ch_int - 1])
        return base_level

    def tick(self, now: float | None = None) -> bool:
        """Advance all active effects to timestamp *now* and update DMX & UI."""
        t_now = time.monotonic() if now is None else float(now)
        show = self.lightshow
        if show is None:
            return False

        changed_devices: set[int] = set()
        color_changed: set[int] = set()
        restored_channels: set[int] = set()
        has_intensity_effect = False

        with self._lock:
            if not self._instances:
                self._stop_timer_locked()
                return False

            # 1. Check completed fade-outs first
            active_list: list[ActiveEffectInstance] = []
            for inst in self._instances:
                inst.effective_size_scale(t_now)
                inst.effective_rate_scale(t_now)
                if inst.remove_on_fade_end and inst.is_fade_finished(t_now):
                    restored_channels.update(inst.channels)
                else:
                    active_list.append(inst)
            self._instances = active_list
            for ch in restored_channels:
                self._restore_channel_base_state_locked(ch)

            # 2. Evaluate all active instances
            for inst in self._instances:
                eff = show.effects.get(inst.effect_number)
                if eff is None or not inst.channels:
                    continue
                speed_bpm, speed_mult, rate_m, _size_m = (
                    self._resolve_effect_masters_locked(eff)
                )
                inst.advance_phase(
                    t_now,
                    eff.cycle_time,
                    master_rate=rate_m,
                    speed_bpm=speed_bpm,
                    speed_multiplier=speed_mult,
                )
                if any(layer.parameter == "intensity" for layer in eff.layers):
                    has_intensity_effect = True
                dev_changed, col_changed = self._evaluate_device_layers_locked(
                    show, eff, inst, t_now
                )
                changed_devices.update(dev_changed)
                color_changed.update(col_changed)

            still_running = bool(self._instances)
            if not still_running:
                self._stop_timer_locked()

        # 3. Push DMX frame and emit UI refresh events outside lock
        if has_intensity_effect or changed_devices or restored_channels:
            if (
                self.app is not None
                and self.app.backend is not None
                and getattr(self.app.backend, "dmx", None) is not None
            ):
                self.app.backend.dmx.set_levels()

        if self.app is not None:
            if color_changed:
                self.app.emit("device.color_changed", sorted(color_changed), None)
            non_color = (changed_devices | restored_channels) - color_changed
            if non_color:
                self.app.emit(
                    "device.parameter_changed", sorted(non_color), "effect", None
                )

        return still_running

    def _on_timer_tick(self) -> bool:
        try:
            return self.tick()
        except Exception:
            with self._lock:
                self._timer_handle = None
            raise

    def _ensure_timer_locked(self) -> None:
        if self._timer_handle is None and self._instances:
            self._timer_handle = self.scheduler.timeout_add(
                self.interval_ms, self._on_timer_tick
            )

    def _stop_timer_locked(self) -> None:
        if self._timer_handle is not None:
            self.scheduler.source_remove(self._timer_handle)
            self._timer_handle = None

    def _stomp_overlapping_channels_locked(
        self,
        new_channels: list[int],
        target_params: set[str],
        *,
        exclude_effect: float,
    ) -> None:
        show = self.lightshow
        if show is None:
            return
        new_set = {int(c) for c in new_channels}
        kept: list[ActiveEffectInstance] = []
        for inst in self._instances:
            if inst.effect_number == exclude_effect:
                kept.append(inst)
                continue
            eff = show.effects.get(inst.effect_number)
            if eff is None:
                continue
            inst_params = {layer.parameter for layer in eff.layers}
            if inst_params.intersection(target_params):
                inst.channels = [c for c in inst.channels if c not in new_set]
            if inst.channels:
                kept.append(inst)
        self._instances = kept

    def _compute_instance_thetas(
        self,
        eff: EffectDefinition,
        inst: ActiveEffectInstance,
    ) -> np.ndarray:
        groups = (
            inst.groups_override if inst.groups_override is not None else eff.groups
        )
        blocks = (
            inst.blocks_override if inst.blocks_override is not None else eff.blocks
        )
        wings = inst.wings_override if inst.wings_override is not None else eff.wings
        direction = (
            inst.direction_override
            if inst.direction_override is not None
            else eff.direction
        )
        return compute_channel_phase_offsets(
            inst.channels,
            groups=groups,
            blocks=blocks,
            wings=wings,
            direction=direction,
            phase_start_deg=eff.phase_start_deg,
            phase_end_deg=eff.phase_end_deg,
            effect_seed=int(round(eff.number * 1000)),
        )

    def _eval_layer_waveform(
        self,
        show: LightShow,
        layer: EffectLayer,
        phi: np.ndarray,
        cyc_idx: np.ndarray,
        channels: list[int],
    ) -> np.ndarray:
        curve_fn: typing.Callable[[np.ndarray], float | np.ndarray] | None = None
        if layer.waveform == WaveformType.CURVE and layer.curve_id is not None:
            curve = show.curves.get_curve(layer.curve_id)
            if curve is not None:
                curve_fn = curve.evaluate_normalized
        return evaluate_waveform(
            layer.waveform,
            phi,
            mode=layer.mode,
            duty_cycle=layer.duty_cycle,
            softness=layer.softness,
            cycle_index=cyc_idx,
            channels=channels,
            curve_evaluator=curve_fn,
        )

    def _resolve_intensity_bounds(
        self,
        show: LightShow,
        layer: EffectLayer,
        channels: list[int],
        base_vals: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        low = np.zeros(len(channels), dtype=np.float64)
        high = np.ones(len(channels), dtype=np.float64)
        if (
            isinstance(layer.low_value, str)
            and layer.low_value.strip().lower() == "bkgrd"
        ):
            low = base_vals.copy()
        elif isinstance(layer.low_value, (int, float)):
            val = float(layer.low_value)
            low.fill(val / 100.0 if val > 1.0 else val)
        elif layer.low_palette is not None:
            low = self._resolve_palette_intensities(
                show, layer.low_palette, channels, base_vals
            )
        if (
            isinstance(layer.high_value, str)
            and layer.high_value.strip().lower() == "bkgrd"
        ):
            high = base_vals.copy()
        elif isinstance(layer.high_value, (int, float)):
            val = float(layer.high_value)
            high.fill(val / 100.0 if val > 1.0 else val)
        elif layer.high_palette is not None:
            high = self._resolve_palette_intensities(
                show, layer.high_palette, channels, high
            )
        return np.clip(low, 0.0, 1.0), np.clip(high, 0.0, 1.0)

    @staticmethod
    def _resolve_palette_intensities(
        show: LightShow,
        pal_ref: PaletteRef,
        channels: list[int],
        fallback: np.ndarray,
    ) -> np.ndarray:
        out = fallback.copy()
        pal = show.palettes.get(pal_ref[0], pal_ref[1])
        if pal is None:
            return out
        for i, ch in enumerate(channels):
            if ch in pal.channels:
                v = float(pal.channels[ch])
                out[i] = v / 255.0 if v > 1.0 else v
            elif ch in pal.device_values and "intensity" in pal.device_values[ch]:
                v = float(pal.device_values[ch]["intensity"])
                out[i] = v / 255.0 if v > 1.0 else v
        return out

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def _evaluate_device_layers_locked(
        self,
        show: LightShow,
        eff: EffectDefinition,
        inst: ActiveEffectInstance,
        t_now: float,
    ) -> tuple[set[int], set[int]]:
        dev_layers = [layer for layer in eff.layers if layer.parameter != "intensity"]
        if not dev_layers:
            return set(), set()

        speed_bpm, speed_mult, rate_m, size_m = self._resolve_effect_masters_locked(eff)
        theta = self._compute_instance_thetas(eff, inst)
        size_all = inst.effective_channel_size_scales(t_now, theta) * size_m
        cycles = inst.advance_phase(
            t_now,
            eff.cycle_time,
            master_rate=rate_m,
            speed_bpm=speed_bpm,
            speed_multiplier=speed_mult,
        )

        # Precompute waveform array per device layer
        layer_waves: list[tuple[EffectLayer, np.ndarray]] = []
        for layer in dev_layers:
            phi_raw = (
                cycles * layer.freq_mult
                - theta
                + (layer.phase_offset_deg + inst.phase_offset_deg) / 360.0
            )
            cyc_idx = np.floor(phi_raw).astype(np.int64)
            phi = np.mod(phi_raw, 1.0)
            wave = self._eval_layer_waveform(show, layer, phi, cyc_idx, inst.channels)
            layer_waves.append((layer, wave))

        changed_devs: set[int] = set()
        color_devs: set[int] = set()
        axis_rad = math.radians(eff.axis_deg) if eff.axis_deg != 0.0 else 0.0
        cos_a = math.cos(axis_rad)
        sin_a = math.sin(axis_rad)

        for idx, ch in enumerate(inst.channels):
            dev = show.patch.devices.get(ch)
            if dev is None:
                continue

            size_mult = float(size_all[idx])
            self._sync_external_base_updates_locked(ch, dev, dev_layers)
            ch_base = self._base_device_state.setdefault(ch, {})
            ch_last = self._last_modulated_state.setdefault(ch, {})

            d_pan = 0.0
            d_tilt = 0.0
            has_rel_pan = False
            has_rel_tilt = False

            for layer, wave_arr in layer_waves:
                w_val = float(wave_arr[idx])
                p_name = layer.parameter

                if p_name == "pan" and layer.mode == EffectMode.RELATIVE:
                    d_pan += layer.size * size_mult * w_val
                    has_rel_pan = True
                elif p_name == "tilt" and layer.mode == EffectMode.RELATIVE:
                    d_tilt += layer.size * size_mult * w_val
                    has_rel_tilt = True
                elif p_name in ("pan", "tilt") and layer.mode == EffectMode.ABSOLUTE:
                    base_ang = float(
                        ch_base.get(
                            p_name,
                            dev.pan_degrees if p_name == "pan" else dev.tilt_degrees,
                        )
                    )
                    low_a, high_a = self._resolve_angle_bounds(
                        show, layer, ch, p_name, base_ang
                    )
                    target_a = low_a + (high_a - low_a) * w_val
                    final_a = base_ang + (target_a - base_ang) * min(1.0, size_mult)
                    if p_name == "pan" and dev.get_channel(ChannelType.PAN) is not None:
                        dev.set_pan_degrees(final_a)
                        ch_last["pan"] = dev.pan_degrees
                        changed_devs.add(ch)
                    elif (
                        p_name == "tilt"
                        and dev.get_channel(ChannelType.TILT) is not None
                    ):
                        dev.set_tilt_degrees(final_a)
                        ch_last["tilt"] = dev.tilt_degrees
                        changed_devs.add(ch)
                elif p_name == "color":
                    if self._apply_color_layer_locked(
                        show, dev, ch, layer, w_val, size_mult, ch_base, ch_last
                    ):
                        changed_devs.add(ch)
                        color_devs.add(ch)
                else:
                    if self._apply_scalar_device_layer_locked(
                        dev, ch, layer, w_val, size_mult, ch_base, ch_last
                    ):
                        changed_devs.add(ch)

            if has_rel_pan or has_rel_tilt:
                if axis_rad != 0.0:
                    rot_pan = d_pan * cos_a - d_tilt * sin_a
                    rot_tilt = d_pan * sin_a + d_tilt * cos_a
                    d_pan, d_tilt = rot_pan, rot_tilt
                if has_rel_pan or (axis_rad != 0.0 and has_rel_tilt):
                    if dev.get_channel(ChannelType.PAN) is not None:
                        base_p = float(ch_base.get("pan", dev.pan_degrees))
                        dev.set_pan_degrees(base_p + d_pan)
                        ch_last["pan"] = dev.pan_degrees
                        changed_devs.add(ch)
                if has_rel_tilt or (axis_rad != 0.0 and has_rel_pan):
                    if dev.get_channel(ChannelType.TILT) is not None:
                        base_t = float(ch_base.get("tilt", dev.tilt_degrees))
                        dev.set_tilt_degrees(base_t + d_tilt)
                        ch_last["tilt"] = dev.tilt_degrees
                        changed_devs.add(ch)

        return changed_devs, color_devs

    def _resolve_angle_bounds(
        self,
        show: LightShow,
        layer: EffectLayer,
        channel: int,
        param: str,
        default_angle: float,
    ) -> tuple[float, float]:
        low_a = (
            float(layer.low_value)
            if isinstance(layer.low_value, (int, float))
            else (default_angle - layer.size * 0.5)
        )
        high_a = (
            float(layer.high_value)
            if isinstance(layer.high_value, (int, float))
            else (default_angle + layer.size * 0.5)
        )
        if layer.low_palette is not None:
            pal = show.palettes.get(layer.low_palette[0], layer.low_palette[1])
            if (
                pal is not None
                and channel in pal.device_values
                and param in pal.device_values[channel]
            ):
                low_a = float(pal.device_values[channel][param])
        if layer.high_palette is not None:
            pal = show.palettes.get(layer.high_palette[0], layer.high_palette[1])
            if (
                pal is not None
                and channel in pal.device_values
                and param in pal.device_values[channel]
            ):
                high_a = float(pal.device_values[channel][param])
        return low_a, high_a

    def _apply_color_layer_locked(
        self,
        show: LightShow,
        dev: LightingDevice,
        channel: int,
        layer: EffectLayer,
        w_val: float,
        size_mult: float,
        ch_base: dict[str, Any],
        ch_last: dict[str, Any],
    ) -> bool:
        if not dev.has_color_capability:
            return False
        base_rgb = ch_base.get("color")
        if not isinstance(base_rgb, tuple):
            base_rgb = dev.get_preview_rgb() or (1.0, 1.0, 1.0)
            ch_base["color"] = base_rgb

        if layer.waveform == WaveformType.RAINBOW:
            hue = w_val % 1.0
            r_t, g_t, b_t = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        else:
            low_rgb = self._resolve_color_bound(
                show, layer.low_palette, layer.low_value, channel, base_rgb
            )
            high_rgb = self._resolve_color_bound(
                show, layer.high_palette, layer.high_value, channel, (1.0, 1.0, 1.0)
            )
            u = max(
                0.0,
                min(
                    1.0,
                    (0.5 * (w_val + 1.0))
                    if layer.mode == EffectMode.RELATIVE
                    else w_val,
                ),
            )
            r_t = low_rgb[0] + (high_rgb[0] - low_rgb[0]) * u
            g_t = low_rgb[1] + (high_rgb[1] - low_rgb[1]) * u
            b_t = low_rgb[2] + (high_rgb[2] - low_rgb[2]) * u

        blend = min(1.0, max(0.0, size_mult))
        r = max(0.0, min(1.0, base_rgb[0] + (r_t - base_rgb[0]) * blend))
        g = max(0.0, min(1.0, base_rgb[1] + (g_t - base_rgb[1]) * blend))
        b = max(0.0, min(1.0, base_rgb[2] + (b_t - base_rgb[2]) * blend))
        self._write_device_rgb(dev, (r, g, b))
        ch_last["color"] = dev.get_preview_rgb() or (r, g, b)
        return True

    @staticmethod
    def _write_device_rgb(
        dev: LightingDevice,
        rgb: tuple[float, float, float],
    ) -> None:
        r, g, b = rgb
        c_ch = dev.get_channel(ChannelType.CYAN)
        m_ch = dev.get_channel(ChannelType.MAGENTA)
        y_ch = dev.get_channel(ChannelType.YELLOW)
        r_ch = dev.get_channel(ChannelType.RED)
        if c_ch is not None and m_ch is not None and y_ch is not None and r_ch is None:
            dev.set_parameter_normalized(ChannelType.CYAN, 1.0 - r)
            dev.set_parameter_normalized(ChannelType.MAGENTA, 1.0 - g)
            dev.set_parameter_normalized(ChannelType.YELLOW, 1.0 - b)
        else:
            dev.set_color_srgb(r, g, b)

    def _resolve_color_bound(
        self,
        show: LightShow,
        pal_ref: PaletteRef | None,
        raw_val: Any,  # noqa: ANN401
        channel: int,
        fallback: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        if pal_ref is not None:
            cat = pal_ref[0] if pal_ref[0] else PaletteCategory.COLOR.value
            pal = show.palettes.get(cat, pal_ref[1])
            if pal is not None:
                dev_vals = pal.device_values.get(channel)
                if dev_vals is None and pal.device_values:
                    dev_vals = next(iter(pal.device_values.values()))
                if isinstance(dev_vals, dict):
                    if "color" in dev_vals:
                        parsed = _parse_hex_or_rgb(dev_vals["color"])
                        if parsed is not None:
                            return parsed
                    if any(k in dev_vals for k in ("red", "green", "blue")):
                        return (
                            float(dev_vals.get("red", 0.0)),
                            float(dev_vals.get("green", 0.0)),
                            float(dev_vals.get("blue", 0.0)),
                        )
                    if any(k in dev_vals for k in ("cyan", "magenta", "yellow")):
                        return (
                            1.0 - float(dev_vals.get("cyan", 0.0)),
                            1.0 - float(dev_vals.get("magenta", 0.0)),
                            1.0 - float(dev_vals.get("yellow", 0.0)),
                        )
        parsed_raw = _parse_hex_or_rgb(raw_val)
        if parsed_raw is not None:
            return parsed_raw
        return fallback

    @staticmethod
    def _resolve_palette_device_value(
        show: LightShow | None,
        pal_ref: PaletteRef | None,
        channel: int,
        param_key: str,
    ) -> float | None:
        if show is None or pal_ref is None:
            return None
        pal = show.palettes.get(pal_ref[0], pal_ref[1])
        if pal is None:
            return None
        dev_vals = pal.device_values.get(channel)
        if dev_vals is None and pal.device_values:
            dev_vals = next(iter(pal.device_values.values()))
        if isinstance(dev_vals, dict):
            raw = dev_vals.get(param_key)
            if isinstance(raw, (int, float)):
                return float(raw)
        return None

    def _apply_scalar_device_layer_locked(
        self,
        dev: LightingDevice,
        channel: int,
        layer: EffectLayer,
        w_val: float,
        size_mult: float,
        ch_base: dict[str, Any],
        ch_last: dict[str, Any],
    ) -> bool:
        p_name = layer.parameter
        if p_name == "zoom" and dev.get_channel(ChannelType.ZOOM) is not None:
            base_z = float(ch_base.get("zoom", dev.zoom_degrees or 20.0))
            if layer.mode == EffectMode.RELATIVE:
                target_z = base_z + layer.size * size_mult * w_val
            else:
                if (
                    isinstance(layer.low_value, str)
                    and layer.low_value.strip().lower() == "bkgrd"
                ):
                    low_z = base_z
                elif isinstance(layer.low_value, (int, float)):
                    low_z = float(layer.low_value)
                else:
                    pal_low = self._resolve_palette_device_value(
                        self.lightshow, layer.low_palette, channel, "zoom"
                    )
                    low_z = pal_low if pal_low is not None else 5.0

                if (
                    isinstance(layer.high_value, str)
                    and layer.high_value.strip().lower() == "bkgrd"
                ):
                    high_z = base_z
                elif isinstance(layer.high_value, (int, float)):
                    high_z = float(layer.high_value)
                else:
                    pal_high = self._resolve_palette_device_value(
                        self.lightshow, layer.high_palette, channel, "zoom"
                    )
                    high_z = pal_high if pal_high is not None else 50.0

                target_z = base_z + ((low_z + (high_z - low_z) * w_val) - base_z) * min(
                    1.0, size_mult
                )
            dev.set_zoom_degrees(target_z)
            ch_last["zoom"] = dev.zoom_degrees
            return True

        if p_name == "focus" and dev.get_channel(ChannelType.FOCUS) is not None:
            base_f = float(ch_base.get("focus", dev.focus_meters or 5.0))
            target_f = base_f + layer.size * size_mult * w_val
            dev.set_focus_meters(target_f)
            ch_last["focus"] = dev.focus_meters
            return True

        if p_name == "iris" and dev.get_channel(ChannelType.IRIS) is not None:
            base_i = float(
                ch_base.get(
                    "iris",
                    dev.get_parameter_normalized(ChannelType.IRIS) or 0.5,
                )
            )
            delta_i = (layer.size / 100.0) * size_mult * w_val
            target_i = max(0.0, min(1.0, base_i + delta_i))
            dev.set_parameter_normalized(ChannelType.IRIS, target_i)
            ch_last["iris"] = dev.get_parameter_normalized(ChannelType.IRIS)
            return True

        if (
            p_name in ("strobe", "shutter")
            and dev.get_channel(ChannelType.STROBE) is not None
        ):
            base_s = float(ch_base.get("strobe", dev.strobe_hz or 0.0))
            target_s = max(0.0, base_s + layer.size * size_mult * w_val)
            dev.set_strobe_hz(target_s)
            ch_last["strobe"] = dev.strobe_hz
            return True

        if (
            p_name in ("cct", "color_temp")
            and dev.get_channel(ChannelType.COLOR_TEMP) is not None
        ):
            base_c = float(ch_base.get("cct", dev.color_temp_kelvin or 3200.0))
            target_c = base_c + layer.size * size_mult * w_val
            dev.set_color_temp_kelvin(target_c)
            ch_last["cct"] = dev.color_temp_kelvin
            return True

        return False

    def _capture_initial_base_state_locked(
        self,
        channels: list[int],
        eff: EffectDefinition,
    ) -> None:
        show = self.lightshow
        if show is None:
            return
        params = {
            layer.parameter for layer in eff.layers if layer.parameter != "intensity"
        }
        if eff.axis_deg != 0.0 and params.intersection({"pan", "tilt"}):
            params.update({"pan", "tilt"})
        if not params:
            return
        for ch in channels:
            dev = show.patch.devices.get(ch)
            if dev is None:
                continue
            ch_base = self._base_device_state.setdefault(ch, {})
            ch_last = self._last_modulated_state.setdefault(ch, {})
            for p_name in params:
                if p_name not in ch_base:
                    val = self._read_device_parameter(dev, p_name)
                    if val is not None:
                        ch_base[p_name] = val
                        ch_last[p_name] = val

    def _sync_external_base_updates_locked(
        self,
        channel: int,
        dev: LightingDevice,
        layers: list[EffectLayer],
    ) -> None:
        ch_base = self._base_device_state.setdefault(channel, {})
        ch_last = self._last_modulated_state.setdefault(channel, {})
        params = {layer.parameter for layer in layers}
        if params.intersection({"pan", "tilt"}):
            params.update({"pan", "tilt"})
        for p_name in params:
            curr = self._read_device_parameter(dev, p_name)
            if curr is None:
                continue
            if p_name not in ch_base or p_name not in ch_last:
                ch_base[p_name] = curr
                ch_last[p_name] = curr
                continue
            prev_mod = ch_last[p_name]
            if isinstance(curr, tuple) and isinstance(prev_mod, tuple):
                if any(
                    abs(float(a) - float(b)) > 1e-2
                    for a, b in zip(curr, prev_mod, strict=False)
                ):
                    ch_base[p_name] = curr
            elif isinstance(curr, (int, float)) and isinstance(prev_mod, (int, float)):
                if abs(float(curr) - float(prev_mod)) > 1e-2:
                    ch_base[p_name] = curr

    @staticmethod
    def _read_device_parameter(
        dev: LightingDevice,
        parameter: str,
    ) -> Any:  # noqa: ANN401
        p_norm = str(parameter).strip().lower()
        if p_norm == "pan":
            return (
                dev.pan_degrees
                if dev.get_channel(ChannelType.PAN) is not None
                else None
            )
        if p_norm == "tilt":
            return (
                dev.tilt_degrees
                if dev.get_channel(ChannelType.TILT) is not None
                else None
            )
        if p_norm == "color":
            return dev.get_preview_rgb() if dev.has_color_capability else None
        if p_norm == "zoom":
            return dev.zoom_degrees
        if p_norm == "focus":
            return dev.focus_meters
        if p_norm == "iris":
            return dev.get_parameter_normalized(ChannelType.IRIS)
        if p_norm in ("strobe", "shutter"):
            return dev.strobe_hz
        if p_norm in ("cct", "color_temp"):
            return dev.color_temp_kelvin
        return None

    def _restore_channel_base_state_locked(self, channel: int) -> None:
        show = self.lightshow
        ch_base = self._base_device_state.pop(channel, None)
        self._last_modulated_state.pop(channel, None)
        if show is None or not ch_base:
            return
        dev = show.patch.devices.get(channel)
        if dev is None:
            return
        for p_name, base_val in ch_base.items():
            if p_name == "pan" and isinstance(base_val, (int, float)):
                dev.set_pan_degrees(float(base_val))
            elif p_name == "tilt" and isinstance(base_val, (int, float)):
                dev.set_tilt_degrees(float(base_val))
            elif p_name == "color" and isinstance(base_val, tuple):
                self._write_device_rgb(dev, base_val)
            elif p_name == "zoom" and isinstance(base_val, (int, float)):
                dev.set_zoom_degrees(float(base_val))
            elif p_name == "focus" and isinstance(base_val, (int, float)):
                dev.set_focus_meters(float(base_val))
            elif p_name == "iris" and isinstance(base_val, (int, float)):
                dev.set_parameter_normalized(ChannelType.IRIS, float(base_val))
            elif p_name == "strobe" and isinstance(base_val, (int, float)):
                dev.set_strobe_hz(float(base_val))
            elif p_name == "cct" and isinstance(base_val, (int, float)):
                dev.set_color_temp_kelvin(float(base_val))
            else:
                for ctype in COLOR_CHANNEL_TYPES:
                    if ctype.value == p_name and isinstance(base_val, (int, float)):
                        dev.set_parameter_normalized(ctype, float(base_val))

    def _notify_dmx_and_ui(self, channels: set[int]) -> None:
        if not channels:
            return
        if (
            self.app is not None
            and self.app.backend is not None
            and getattr(self.app.backend, "dmx", None) is not None
        ):
            self.app.backend.dmx.set_levels()
        if self.app is not None:
            sorted_chs = sorted(channels)
            self.app.emit("device.color_changed", sorted_chs, None)
            self.app.emit("device.parameter_changed", sorted_chs, "effect", None)

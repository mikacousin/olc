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
"""Parametric Effect definitions, layers, templates, and show-level EffectManager."""

from __future__ import annotations

import copy
import typing
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

if typing.TYPE_CHECKING:
    from olc.show.lightshow import LightShow
    from olc.show.palette import PaletteRef


class EffectMode(str, Enum):
    """Composition mode for an effect layer."""

    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class WaveformType(str, Enum):
    """Periodic waveform shape evaluated by an effect layer."""

    SINE = "sine"
    COSINE = "cosine"
    TRIANGLE = "triangle"
    SQUARE = "square"
    SAW_UP = "saw_up"
    SAW_DOWN = "saw_down"
    PULSE = "pulse"
    RAINBOW = "rainbow"
    RANDOM = "random"
    CURVE = "curve"


class DistributeDirection(str, Enum):
    """Phase propagation direction across an ordered channel selection."""

    FORWARD = "forward"
    BACKWARD = "backward"
    BOUNCE = "bounce"
    RANDOM = "random"


class EffectEnvelopeMode(str, Enum):
    """Entry/exit transition behavior mapped from Eos ``$$Entry`` / ``$$Exit``."""

    IMMEDIATE = "immediate"
    FADE_BY_SIZE = "fade_by_size"
    FADE_BY_RATE = "fade_by_rate"
    FADE_BY_SIZE_AND_RATE = "fade_by_size_and_rate"


def _parse_palette_ref(
    raw: typing.Any,  # noqa: ANN401
) -> tuple[str, float] | None:
    """Parse an optional (category, number) palette reference tuple."""
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return (str(raw[0]).strip().lower(), float(raw[1]))
        except (TypeError, ValueError):
            return None
    return None


# pylint: disable=too-many-instance-attributes
@dataclass
class EffectLayer:
    """Single parameter modulation line inside an EffectDefinition."""

    parameter: str
    waveform: WaveformType = WaveformType.SINE
    mode: EffectMode = EffectMode.RELATIVE
    size: float = 20.0
    phase_offset_deg: float = 0.0
    freq_mult: float = 1.0
    duty_cycle: float = 0.5
    softness: float = 1.0
    low_value: float | str | None = None
    high_value: float | str | None = None
    low_palette: PaletteRef | None = None
    high_palette: PaletteRef | None = None
    curve_id: int | None = None

    def __post_init__(self) -> None:
        self.parameter = str(self.parameter).strip().lower()
        if not isinstance(self.waveform, WaveformType):
            self.waveform = WaveformType(str(self.waveform).strip().lower())
        if not isinstance(self.mode, EffectMode):
            self.mode = EffectMode(str(self.mode).strip().lower())
        self.size = float(self.size)
        self.phase_offset_deg = float(self.phase_offset_deg)
        self.freq_mult = max(0.01, float(self.freq_mult))
        self.duty_cycle = max(0.01, min(1.0, float(self.duty_cycle)))
        self.softness = max(0.0, min(1.0, float(self.softness)))
        if self.low_palette is not None:
            self.low_palette = _parse_palette_ref(self.low_palette)
        if self.high_palette is not None:
            self.high_palette = _parse_palette_ref(self.high_palette)
        if self.curve_id is not None:
            self.curve_id = int(self.curve_id)

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize layer into a JSON-compatible dictionary."""
        data: dict[str, typing.Any] = {
            "parameter": self.parameter,
            "waveform": self.waveform.value,
            "mode": self.mode.value,
            "size": self.size,
            "phase_offset_deg": self.phase_offset_deg,
            "freq_mult": self.freq_mult,
            "duty_cycle": self.duty_cycle,
            "softness": self.softness,
        }
        if self.low_value is not None:
            data["low_value"] = self.low_value
        if self.high_value is not None:
            data["high_value"] = self.high_value
        if self.low_palette is not None:
            data["low_palette"] = [self.low_palette[0], float(self.low_palette[1])]
        if self.high_palette is not None:
            data["high_palette"] = [self.high_palette[0], float(self.high_palette[1])]
        if self.curve_id is not None:
            data["curve_id"] = int(self.curve_id)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> EffectLayer:
        """Deserialize layer from a dictionary."""
        return cls(
            parameter=str(data.get("parameter", "intensity")),
            waveform=WaveformType(
                str(data.get("waveform", WaveformType.SINE.value)).lower()
            ),
            mode=EffectMode(str(data.get("mode", EffectMode.RELATIVE.value)).lower()),
            size=float(data.get("size", 20.0)),
            phase_offset_deg=float(data.get("phase_offset_deg", 0.0)),
            freq_mult=float(data.get("freq_mult", 1.0)),
            duty_cycle=float(data.get("duty_cycle", 0.5)),
            softness=float(data.get("softness", 1.0)),
            low_value=data.get("low_value"),
            high_value=data.get("high_value"),
            low_palette=_parse_palette_ref(data.get("low_palette")),
            high_palette=_parse_palette_ref(data.get("high_palette")),
            curve_id=(
                int(data["curve_id"]) if data.get("curve_id") is not None else None
            ),
        )


# pylint: disable=too-many-instance-attributes
@dataclass
class EffectDefinition:
    """Reusable Effect template stored in LightShow.effects (Effect 1..999)."""

    number: float
    label: str = ""
    layers: list[EffectLayer] = field(default_factory=list)
    cycle_time: float = 2.0
    bpm: float | None = None
    direction: DistributeDirection = DistributeDirection.FORWARD
    groups: int = 0
    blocks: int = 1
    wings: int = 1
    axis_deg: float = 0.0
    phase_start_deg: float = 0.0
    phase_end_deg: float = 360.0
    template_id: str | None = None
    entry_mode: EffectEnvelopeMode = EffectEnvelopeMode.FADE_BY_SIZE
    exit_mode: EffectEnvelopeMode = EffectEnvelopeMode.FADE_BY_SIZE
    cascade: bool = False
    speed_master: int | None = None
    speed_multiplier: float = 1.0
    rate_master: int | None = None
    size_master: int | None = None

    def __post_init__(self) -> None:
        self.number = round(float(self.number), 3)
        self.label = str(self.label)
        self.cycle_time = max(0.05, float(self.cycle_time))
        if self.bpm is not None:
            self.bpm = max(1.0, float(self.bpm))
            self.cycle_time = max(0.05, 60.0 / self.bpm)
        if not isinstance(self.direction, DistributeDirection):
            self.direction = DistributeDirection(str(self.direction).strip().lower())
        if not isinstance(self.entry_mode, EffectEnvelopeMode):
            self.entry_mode = EffectEnvelopeMode(str(self.entry_mode).strip().lower())
        if not isinstance(self.exit_mode, EffectEnvelopeMode):
            self.exit_mode = EffectEnvelopeMode(str(self.exit_mode).strip().lower())
        self.cascade = bool(self.cascade)
        self.groups = max(0, int(self.groups))
        self.blocks = max(1, int(self.blocks))
        self.wings = max(1, int(self.wings))
        self.axis_deg = float(self.axis_deg)
        self.phase_start_deg = float(self.phase_start_deg)
        self.phase_end_deg = float(self.phase_end_deg)
        self.speed_master = (
            int(self.speed_master) if self.speed_master is not None else None
        )
        self.speed_multiplier = max(0.0625, float(self.speed_multiplier))
        self.rate_master = (
            int(self.rate_master) if self.rate_master is not None else None
        )
        self.size_master = (
            int(self.size_master) if self.size_master is not None else None
        )

    def set_bpm(self, bpm: float | None) -> None:
        """Set musical tempo in BPM and synchronize cycle_time (60 / BPM)."""
        if bpm is None:
            self.bpm = None
            return
        self.bpm = max(1.0, float(bpm))
        self.cycle_time = max(0.05, 60.0 / self.bpm)

    def set_cycle_time(self, seconds: float) -> None:
        """Set period in seconds and update BPM if previously linked."""
        self.cycle_time = max(0.05, float(seconds))
        if self.bpm is not None:
            self.bpm = 60.0 / self.cycle_time

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize EffectDefinition into a JSON-compatible dictionary."""
        data: dict[str, typing.Any] = {
            "number": float(self.number),
            "label": self.label,
            "cycle_time": self.cycle_time,
            "direction": self.direction.value,
            "groups": self.groups,
            "blocks": self.blocks,
            "wings": self.wings,
            "axis_deg": self.axis_deg,
            "phase_start_deg": self.phase_start_deg,
            "phase_end_deg": self.phase_end_deg,
            "layers": [layer.to_dict() for layer in self.layers],
        }
        if self.bpm is not None:
            data["bpm"] = self.bpm
        if self.template_id is not None:
            data["template_id"] = self.template_id
        if self.entry_mode != EffectEnvelopeMode.FADE_BY_SIZE:
            data["entry_mode"] = self.entry_mode.value
        if self.exit_mode != EffectEnvelopeMode.FADE_BY_SIZE:
            data["exit_mode"] = self.exit_mode.value
        if self.cascade:
            data["cascade"] = True
        if self.speed_master is not None:
            data["speed_master"] = self.speed_master
        if self.speed_multiplier != 1.0:
            data["speed_multiplier"] = self.speed_multiplier
        if self.rate_master is not None:
            data["rate_master"] = self.rate_master
        if self.size_master is not None:
            data["size_master"] = self.size_master
        return data

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> EffectDefinition:
        """Deserialize EffectDefinition from a dictionary."""
        raw_layers = data.get("layers", [])
        layers = [
            EffectLayer.from_dict(item) for item in raw_layers if isinstance(item, dict)
        ]
        bpm_raw = data.get("bpm")
        entry_raw = data.get("entry_mode", EffectEnvelopeMode.FADE_BY_SIZE.value)
        exit_raw = data.get("exit_mode", EffectEnvelopeMode.FADE_BY_SIZE.value)
        return cls(
            number=float(data.get("number", 1.0)),
            label=str(data.get("label", "")),
            layers=layers,
            cycle_time=float(data.get("cycle_time", 2.0)),
            bpm=float(bpm_raw) if bpm_raw is not None else None,
            direction=DistributeDirection(
                str(data.get("direction", DistributeDirection.FORWARD.value)).lower()
            ),
            groups=int(data.get("groups", 0)),
            blocks=int(data.get("blocks", 1)),
            wings=int(data.get("wings", 1)),
            axis_deg=float(data.get("axis_deg", 0.0)),
            phase_start_deg=float(data.get("phase_start_deg", 0.0)),
            phase_end_deg=float(data.get("phase_end_deg", 360.0)),
            template_id=(
                str(data["template_id"])
                if data.get("template_id") is not None
                else None
            ),
            entry_mode=EffectEnvelopeMode(str(entry_raw).lower()),
            exit_mode=EffectEnvelopeMode(str(exit_raw).lower()),
            cascade=bool(data.get("cascade", False)),
            speed_master=(
                int(data["speed_master"])
                if data.get("speed_master") is not None
                else None
            ),
            speed_multiplier=float(data.get("speed_multiplier", 1.0)),
            rate_master=(
                int(data["rate_master"])
                if data.get("rate_master") is not None
                else None
            ),
            size_master=(
                int(data["size_master"])
                if data.get("size_master") is not None
                else None
            ),
        )


# pylint: disable=too-many-instance-attributes
@dataclass
class ActiveEffectInstance:
    """Running or recorded instance of an Effect applied to an ordered channel list."""

    effect_number: float
    channels: list[int]
    rate_scale: float = 1.0
    size_scale: float = 1.0
    groups_override: int | None = None
    blocks_override: int | None = None
    wings_override: int | None = None
    direction_override: DistributeDirection | None = None
    phase_offset_deg: float = 0.0
    start_timestamp: float = 0.0
    fade_start_size: float = 1.0
    fade_target_size: float = 1.0
    fade_start_time: float = 0.0
    fade_duration: float = 0.0
    fade_start_rate: float = 1.0
    fade_target_rate: float = 1.0
    rate_fade_start_time: float = 0.0
    rate_fade_duration: float = 0.0
    cascade_fade: bool = False
    remove_on_fade_end: bool = False
    accumulated_cycles: float = 0.0
    last_phase_time: float | None = None

    def __post_init__(self) -> None:
        self.effect_number = round(float(self.effect_number), 3)
        seen: set[int] = set()
        ordered: list[int] = []
        for ch in self.channels:
            ch_int = int(ch)
            if ch_int not in seen:
                seen.add(ch_int)
                ordered.append(ch_int)
        self.channels = ordered
        self.rate_scale = max(0.0, float(self.rate_scale))
        self.size_scale = max(0.0, float(self.size_scale))
        if self.direction_override is not None and not isinstance(
            self.direction_override, DistributeDirection
        ):
            self.direction_override = DistributeDirection(
                str(self.direction_override).strip().lower()
            )

    def effective_size_scale(self, now: float) -> float:
        """Compute current size_scale including any active size fade envelope."""
        if self.fade_duration <= 0.0:
            return self.size_scale
        elapsed = max(0.0, now - self.fade_start_time)
        if elapsed >= self.fade_duration:
            self.size_scale = self.fade_target_size
            self.fade_duration = 0.0
            self.cascade_fade = False
            return self.size_scale
        progress = elapsed / self.fade_duration
        self.size_scale = (
            self.fade_start_size
            + (self.fade_target_size - self.fade_start_size) * progress
        )
        return max(0.0, self.size_scale)

    def effective_rate_scale(self, now: float) -> float:
        """Compute current rate_scale including any active rate fade envelope."""
        if self.rate_fade_duration <= 0.0:
            return max(0.0, self.rate_scale)
        elapsed = max(0.0, now - self.rate_fade_start_time)
        if elapsed >= self.rate_fade_duration:
            self.rate_scale = max(0.0, self.fade_target_rate)
            self.rate_fade_duration = 0.0
            return self.rate_scale
        progress = elapsed / self.rate_fade_duration
        self.rate_scale = max(
            0.0,
            self.fade_start_rate
            + (self.fade_target_rate - self.fade_start_rate) * progress,
        )
        return self.rate_scale

    def _compute_freq(
        self,
        now: float,
        cycle_time: float,
        *,
        master_rate: float = 1.0,
        speed_bpm: float | None = None,
        speed_multiplier: float = 1.0,
    ) -> float:
        """Compute instantaneous frequency in Hz combining instance and master rates."""
        combined_rate = self.effective_rate_scale(now) * max(0.0, float(master_rate))
        if combined_rate <= 0.0:
            return 0.0
        if speed_bpm is not None:
            if speed_bpm <= 0.0:
                return 0.0
            return (
                (float(speed_bpm) / 60.0)
                * max(0.0625, float(speed_multiplier))
                * combined_rate
            )
        period = max(0.05, float(cycle_time) / combined_rate)
        return 1.0 / period

    def advance_phase(
        self,
        now: float,
        cycle_time: float,
        *,
        master_rate: float = 1.0,
        speed_bpm: float | None = None,
        speed_multiplier: float = 1.0,
    ) -> float:
        """Integrate and return accumulated cycles up to timestamp *now*."""
        if self.last_phase_time is None:
            self.last_phase_time = (
                self.start_timestamp if self.start_timestamp > 0.0 else now
            )
        dt = now - self.last_phase_time
        if dt > 0.0:
            freq = self._compute_freq(
                now,
                cycle_time,
                master_rate=master_rate,
                speed_bpm=speed_bpm,
                speed_multiplier=speed_multiplier,
            )
            if freq > 0.0:
                self.accumulated_cycles += dt * freq
            self.last_phase_time = now
        return self.accumulated_cycles

    def phase_cycles_at(
        self,
        now: float,
        cycle_time: float,
        *,
        master_rate: float = 1.0,
        speed_bpm: float | None = None,
        speed_multiplier: float = 1.0,
    ) -> float:
        """Project accumulated cycles to timestamp *now* without mutating state."""
        ref_t = (
            self.start_timestamp
            if self.last_phase_time is None
            else self.last_phase_time
        )
        dt = max(0.0, now - ref_t)
        if dt <= 0.0:
            return self.accumulated_cycles
        freq = self._compute_freq(
            now,
            cycle_time,
            master_rate=master_rate,
            speed_bpm=speed_bpm,
            speed_multiplier=speed_multiplier,
        )
        if freq > 0.0:
            return self.accumulated_cycles + dt * freq
        return self.accumulated_cycles

    def effective_channel_size_scales(
        self, now: float, thetas: np.ndarray
    ) -> np.ndarray:
        """Return per-channel size multipliers, staggered for cascade fade."""
        if self.fade_duration <= 0.0 or not self.cascade_fade or len(thetas) <= 1:
            return np.full(
                len(thetas), max(0.0, self.effective_size_scale(now)), dtype=np.float64
            )
        elapsed = max(0.0, now - self.fade_start_time)
        if elapsed >= self.fade_duration:
            self.size_scale = self.fade_target_size
            self.fade_duration = 0.0
            self.cascade_fade = False
            return np.full(len(thetas), max(0.0, self.size_scale), dtype=np.float64)
        max_t = float(np.max(thetas))
        order_norm = (
            thetas / max_t if max_t > 1e-9 else np.linspace(0.0, 1.0, len(thetas))
        )
        win = 0.5 * self.fade_duration
        start_offsets = 0.5 * self.fade_duration * order_norm
        progress = np.clip((elapsed - start_offsets) / max(1e-6, win), 0.0, 1.0)
        return np.maximum(
            0.0,
            self.fade_start_size
            + (self.fade_target_size - self.fade_start_size) * progress,
        )

    def is_fade_finished(self, now: float) -> bool:
        """Return True if all scheduled size/rate fades have completed at *now*."""
        size_done = (
            self.fade_duration <= 0.0
            or (now - self.fade_start_time) >= self.fade_duration
        )
        rate_done = (
            self.rate_fade_duration <= 0.0
            or (now - self.rate_fade_start_time) >= self.rate_fade_duration
        )
        return size_done and rate_done

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize instance configuration into a JSON-compatible dictionary."""
        data: dict[str, typing.Any] = {
            "effect_number": float(self.effect_number),
            "channels": list(self.channels),
            "rate_scale": float(self.rate_scale),
            "size_scale": float(self.size_scale),
        }
        if self.groups_override is not None:
            data["groups_override"] = int(self.groups_override)
        if self.blocks_override is not None:
            data["blocks_override"] = int(self.blocks_override)
        if self.wings_override is not None:
            data["wings_override"] = int(self.wings_override)
        if self.direction_override is not None:
            data["direction_override"] = self.direction_override.value
        if self.phase_offset_deg != 0.0:
            data["phase_offset_deg"] = float(self.phase_offset_deg)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> ActiveEffectInstance:
        """Deserialize instance configuration from a dictionary."""
        dir_raw = data.get("direction_override")
        return cls(
            effect_number=float(data.get("effect_number", 1.0)),
            channels=[int(c) for c in data.get("channels", [])],
            rate_scale=float(data.get("rate_scale", 1.0)),
            size_scale=float(data.get("size_scale", 1.0)),
            groups_override=(
                int(data["groups_override"])
                if data.get("groups_override") is not None
                else None
            ),
            blocks_override=(
                int(data["blocks_override"])
                if data.get("blocks_override") is not None
                else None
            ),
            wings_override=(
                int(data["wings_override"])
                if data.get("wings_override") is not None
                else None
            ),
            direction_override=(
                DistributeDirection(str(dir_raw).lower())
                if dir_raw is not None
                else None
            ),
            phase_offset_deg=float(data.get("phase_offset_deg", 0.0)),
        )


@dataclass(frozen=True)
class EffectTemplateSpec:
    """Specification of a built-in effect template."""

    template_id: str
    default_label: str
    category: str
    description: str
    factory: typing.Callable[[float, str], EffectDefinition]


def _make_sine_dimmer(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Sine Dimmer",
        cycle_time=3.0,
        groups=0,
        blocks=1,
        wings=1,
        template_id="sine_dimmer",
        layers=[
            EffectLayer(
                parameter="intensity",
                waveform=WaveformType.SINE,
                mode=EffectMode.RELATIVE,
                size=50.0,
            )
        ],
    )


def _make_chase_cancan(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Chase Can-Can",
        cycle_time=1.5,
        groups=4,
        blocks=1,
        wings=1,
        template_id="chase_cancan",
        layers=[
            EffectLayer(
                parameter="intensity",
                waveform=WaveformType.PULSE,
                mode=EffectMode.ABSOLUTE,
                size=100.0,
                duty_cycle=0.25,
                softness=0.2,
                low_value=0.0,
                high_value=100.0,
            )
        ],
    )


def _make_candle_flicker(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Candle Flicker",
        cycle_time=0.4,
        direction=DistributeDirection.RANDOM,
        groups=0,
        blocks=1,
        wings=1,
        template_id="candle_flicker",
        layers=[
            EffectLayer(
                parameter="intensity",
                waveform=WaveformType.RANDOM,
                mode=EffectMode.RELATIVE,
                size=25.0,
                softness=0.8,
            )
        ],
    )


def _make_circle(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Circle",
        cycle_time=4.0,
        groups=0,
        blocks=1,
        wings=1,
        template_id="circle",
        layers=[
            EffectLayer(
                parameter="pan",
                waveform=WaveformType.SINE,
                mode=EffectMode.RELATIVE,
                size=15.0,
                phase_offset_deg=0.0,
            ),
            EffectLayer(
                parameter="tilt",
                waveform=WaveformType.COSINE,
                mode=EffectMode.RELATIVE,
                size=15.0,
                phase_offset_deg=0.0,
            ),
        ],
    )


def _make_figure_8(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Figure 8",
        cycle_time=5.0,
        groups=0,
        blocks=1,
        wings=1,
        template_id="figure_8",
        layers=[
            EffectLayer(
                parameter="pan",
                waveform=WaveformType.SINE,
                mode=EffectMode.RELATIVE,
                size=20.0,
                freq_mult=1.0,
            ),
            EffectLayer(
                parameter="tilt",
                waveform=WaveformType.SINE,
                mode=EffectMode.RELATIVE,
                size=15.0,
                freq_mult=2.0,
            ),
        ],
    )


def _make_tilt_wave(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Tilt Wave",
        cycle_time=3.0,
        groups=0,
        blocks=1,
        wings=2,
        template_id="tilt_wave",
        layers=[
            EffectLayer(
                parameter="tilt",
                waveform=WaveformType.SINE,
                mode=EffectMode.RELATIVE,
                size=25.0,
            )
        ],
    )


def _make_fly_in_out(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Fly-In / Fly-Out",
        cycle_time=4.0,
        groups=0,
        blocks=1,
        wings=1,
        template_id="fly_in_out",
        layers=[
            EffectLayer(
                parameter="tilt",
                waveform=WaveformType.SAW_UP,
                mode=EffectMode.RELATIVE,
                size=30.0,
                phase_offset_deg=0.0,
            ),
            EffectLayer(
                parameter="intensity",
                waveform=WaveformType.PULSE,
                mode=EffectMode.ABSOLUTE,
                size=100.0,
                phase_offset_deg=90.0,
                duty_cycle=0.5,
                softness=0.5,
                low_value=0.0,
                high_value=100.0,
            ),
        ],
    )


def _make_two_color_chase(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Two-Color Chase",
        cycle_time=2.0,
        groups=2,
        blocks=1,
        wings=1,
        template_id="two_color_chase",
        layers=[
            EffectLayer(
                parameter="color",
                waveform=WaveformType.PULSE,
                mode=EffectMode.ABSOLUTE,
                size=100.0,
                duty_cycle=0.5,
                softness=0.25,
                low_palette=("color", 1.0),
                high_palette=("color", 2.0),
            )
        ],
    )


def _make_rainbow(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Rainbow Cycle",
        cycle_time=6.0,
        groups=0,
        blocks=1,
        wings=1,
        template_id="rainbow",
        layers=[
            EffectLayer(
                parameter="color",
                waveform=WaveformType.RAINBOW,
                mode=EffectMode.ABSOLUTE,
                size=100.0,
            )
        ],
    )


def _make_zoom_pulse(number: float, label: str) -> EffectDefinition:
    return EffectDefinition(
        number=number,
        label=label or "Zoom Pulse",
        cycle_time=2.5,
        groups=0,
        blocks=1,
        wings=2,
        template_id="zoom_pulse",
        layers=[
            EffectLayer(
                parameter="zoom",
                waveform=WaveformType.SINE,
                mode=EffectMode.RELATIVE,
                size=15.0,
            )
        ],
    )


BUILTIN_EFFECT_TEMPLATES: dict[str, EffectTemplateSpec] = {
    "sine_dimmer": EffectTemplateSpec(
        template_id="sine_dimmer",
        default_label="Sine Dimmer",
        category="intensity",
        description="Smooth relative sinusoidal intensity wave across channels.",
        factory=_make_sine_dimmer,
    ),
    "chase_cancan": EffectTemplateSpec(
        template_id="chase_cancan",
        default_label="Chase Can-Can",
        category="intensity",
        description="4-part pulse intensity chase with adjustable duty cycle.",
        factory=_make_chase_cancan,
    ),
    "candle_flicker": EffectTemplateSpec(
        template_id="candle_flicker",
        default_label="Candle Flicker",
        category="intensity",
        description="Organic random intensity flicker around the base level.",
        factory=_make_candle_flicker,
    ),
    "circle": EffectTemplateSpec(
        template_id="circle",
        default_label="Circle",
        category="focus",
        description="Relative 2D Pan/Tilt circle around the active focus position.",
        factory=_make_circle,
    ),
    "figure_8": EffectTemplateSpec(
        template_id="figure_8",
        default_label="Figure 8",
        category="focus",
        description="Relative 2D Lissajous Figure-8 (Ballyhoo) Pan/Tilt movement.",
        factory=_make_figure_8,
    ),
    "tilt_wave": EffectTemplateSpec(
        template_id="tilt_wave",
        default_label="Tilt Wave",
        category="focus",
        description="Symmetric 2-wing Tilt wave across the rig.",
        factory=_make_tilt_wave,
    ),
    "fly_in_out": EffectTemplateSpec(
        template_id="fly_in_out",
        default_label="Fly-In / Fly-Out",
        category="focus",
        description="Coordinated Tilt sweep that blacks out during the return stroke.",
        factory=_make_fly_in_out,
    ),
    "two_color_chase": EffectTemplateSpec(
        template_id="two_color_chase",
        default_label="Two-Color Chase",
        category="color",
        description="Alternates between Color Palette 1 and Color Palette 2.",
        factory=_make_two_color_chase,
    ),
    "rainbow": EffectTemplateSpec(
        template_id="rainbow",
        default_label="Rainbow Cycle",
        category="color",
        description="Continuous 360-degree Hue rainbow across fixtures.",
        factory=_make_rainbow,
    ),
    "zoom_pulse": EffectTemplateSpec(
        template_id="zoom_pulse",
        default_label="Zoom Pulse",
        category="beam",
        description="Symmetric 2-wing Zoom breathing oscillation.",
        factory=_make_zoom_pulse,
    ),
}


class EffectManager:
    """Container and registry for all EffectDefinition objects in a LightShow."""

    def __init__(self, lightshow: LightShow | None = None) -> None:
        self.lightshow = lightshow
        self._effects: dict[float, EffectDefinition] = {}

    def __len__(self) -> int:
        return len(self._effects)

    def __iter__(self) -> typing.Iterator[EffectDefinition]:
        for num in sorted(self._effects):
            yield self._effects[num]

    @staticmethod
    def _norm_num(number: float | int) -> float:
        return round(float(number), 3)

    def add(self, effect: EffectDefinition) -> EffectDefinition:
        """Insert or replace an EffectDefinition in the pool."""
        key = self._norm_num(effect.number)
        effect.number = key
        self._effects[key] = effect
        return effect

    def get(self, number: float | int) -> EffectDefinition | None:
        """Retrieve an EffectDefinition by number, or None if not found."""
        return self._effects.get(self._norm_num(number))

    def delete(self, number: float | int) -> EffectDefinition | None:
        """Remove and return an EffectDefinition by number, or None."""
        return self._effects.pop(self._norm_num(number), None)

    def rename(self, number: float | int, new_label: str) -> bool:
        """Rename an existing EffectDefinition; return True if found."""
        eff = self.get(number)
        if eff is None:
            return False
        eff.label = str(new_label)
        return True

    def all(self) -> list[EffectDefinition]:
        """Return all EffectDefinitions sorted by number."""
        return [self._effects[k] for k in sorted(self._effects)]

    def clear(self) -> None:
        """Remove all EffectDefinitions from the show."""
        self._effects.clear()

    def next_available_number(self) -> float:
        """Return the next free integer effect number starting at 1.0."""
        if not self._effects:
            return 1.0
        highest = max(int(num) for num in self._effects)
        return float(highest + 1)

    def create_from_template(
        self,
        template_id: str,
        number: float | int | None = None,
        label: str = "",
    ) -> EffectDefinition:
        """Instantiate one of the 10 built-in effect templates and register it."""
        key = str(template_id).strip().lower()
        spec = BUILTIN_EFFECT_TEMPLATES.get(key)
        if spec is None:
            valid = ", ".join(sorted(BUILTIN_EFFECT_TEMPLATES))
            raise ValueError(
                f"Unknown effect template '{template_id}'. Valid templates: {valid}"
            )
        target_num = (
            self.next_available_number() if number is None else self._norm_num(number)
        )
        eff = spec.factory(target_num, label)
        return self.add(eff)

    @staticmethod
    def list_templates() -> list[EffectTemplateSpec]:
        """Return all 10 built-in effect template specifications in catalog order."""
        return list(BUILTIN_EFFECT_TEMPLATES.values())

    def to_list(self) -> list[dict[str, typing.Any]]:
        """Serialize all effects in sorted order."""
        return [copy.deepcopy(eff.to_dict()) for eff in self.all()]

    def from_list(self, items: list[dict[str, typing.Any]]) -> None:
        """Replace current pool from a list of serialized effect dictionaries."""
        self.clear()
        for item in items:
            if isinstance(item, dict):
                self.add(EffectDefinition.from_dict(item))


def serialize_effect_refs(
    refs: dict[int, dict[str, typing.Any]],
) -> dict[int, dict[str, typing.Any]]:
    """Serialize cue effect_refs mapping to JSON-friendly dictionaries."""
    result: dict[int, dict[str, typing.Any]] = {}
    for ch, entry in refs.items():
        if not isinstance(entry, dict) or not entry:
            continue
        result[int(ch)] = copy.deepcopy(entry)
    return result


def deserialize_effect_refs(
    raw: typing.Any,  # noqa: ANN401
) -> dict[int, dict[str, typing.Any]]:
    """Deserialize JSON effect_refs payload into integer-keyed mappings."""
    if not isinstance(raw, dict):
        return {}
    result: dict[int, dict[str, typing.Any]] = {}
    for ch_key, entry in raw.items():
        if not isinstance(entry, dict) or not entry:
            continue
        try:
            ch = int(ch_key)
        except (TypeError, ValueError):
            continue
        result[ch] = copy.deepcopy(entry)
    return result

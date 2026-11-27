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
"""DMX primitives: address, channel, channel range, and patched lighting device."""

# pylint: disable=too-many-lines

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, Callable, Optional

from .channel import (
    BEAM_CHANNEL_TYPES,
    CATEGORY_CHANNEL_TYPES,
    COLOR_CHANNEL_TYPES,
    POSITION_CHANNEL_TYPES,
    Channel,
    ChannelRange,
    ChannelType,
    DmxAddress,
    FixtureType,
    MergeMode,
    get_default_merge_mode,
)
from .color import CIEXYZ, CIExyY, ColorMatcher, FixtureColorProfile, MatchResult, sRGB

if TYPE_CHECKING:
    from olc.show.curve import Curve


_SUBTRACTIVE_CMY_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.CYAN,
        ChannelType.MAGENTA,
        ChannelType.YELLOW,
    }
)
_ADDITIVE_RGB_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.RED,
        ChannelType.GREEN,
        ChannelType.BLUE,
    }
)


def _parse_vec3(
    value: object, default: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Parse a 3-element sequence into a float 3-tuple, falling back to default."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return default
    return default


def _rotate_inv_zyx(
    dx: float, dy: float, dz: float, orientation: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Rotate world vector into fixture-local frame (inverse Z-Y-X Euler degrees)."""
    yaw, pitch, roll = (math.radians(a) for a in orientation)
    # Rz(-yaw)
    cy, sy = math.cos(yaw), math.sin(yaw)
    x1 = cy * dx + sy * dy
    y1 = -sy * dx + cy * dy
    z1 = dz
    # Ry(-pitch)
    cp, sp = math.cos(pitch), math.sin(pitch)
    x2 = cp * x1 - sp * z1
    y2 = y1
    z2 = sp * x1 + cp * z1
    # Rx(-roll)
    cr, sr = math.cos(roll), math.sin(roll)
    lx = x2
    ly = cr * y2 + sr * z2
    lz = -sr * y2 + cr * z2
    return (lx, ly, lz)


def compute_pan_tilt_for_target(
    position: tuple[float, float, float],
    orientation: tuple[float, float, float],
    target: tuple[float, float, float],
    pan_bounds: tuple[float, float] | None = None,
    tilt_bounds: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    """Compute (pan_deg, tilt_deg) aiming fixture at *target* (Z-up, beam -Z at 0,0)."""
    dx = target[0] - position[0]
    dy = target[1] - position[1]
    dz = target[2] - position[2]
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if norm < 1e-6:
        return None
    lx, ly, lz = _rotate_inv_zyx(dx, dy, dz, orientation)
    cos_tilt = max(-1.0, min(1.0, -lz / norm))
    tilt = math.degrees(math.acos(cos_tilt))
    horiz = math.hypot(lx, ly)
    pan = math.degrees(math.atan2(lx, ly)) if horiz > 1e-6 else 0.0

    def _in_bounds(p: float, t: float) -> bool:
        p_ok = pan_bounds is None or pan_bounds[0] <= p <= pan_bounds[1]
        t_ok = tilt_bounds is None or tilt_bounds[0] <= t <= tilt_bounds[1]
        return p_ok and t_ok

    if not _in_bounds(pan, tilt):
        alt_pan = pan - 180.0 if pan >= 0.0 else pan + 180.0
        alt_tilt = -tilt
        if _in_bounds(alt_pan, alt_tilt):
            pan, tilt = alt_pan, alt_tilt
        else:
            if pan_bounds is not None:
                pan = max(pan_bounds[0], min(pan_bounds[1], pan))
            if tilt_bounds is not None:
                tilt = max(tilt_bounds[0], min(tilt_bounds[1], tilt))

    return (pan, tilt)


def compute_focus_point_from_orientation(
    position: tuple[float, float, float],
    orientation: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Project local beam (0, 0, -1) rotated by Z-Y-X Euler degrees to floor or 5m."""
    yaw, pitch, roll = (math.radians(a) for a in orientation)
    # Rx(roll) * [0, 0, -1]
    y1 = math.sin(roll)
    z1 = -math.cos(roll)
    # Ry(pitch) * [0, y1, z1]
    x2 = math.sin(pitch) * z1
    y2 = y1
    z2 = math.cos(pitch) * z1
    # Rz(yaw) * [x2, y2, z2]
    cy, sy = math.cos(yaw), math.sin(yaw)
    dx = cy * x2 - sy * y2
    dy = sy * x2 + cy * y2
    dz = z2

    px, py, pz = (float(position[0]), float(position[1]), float(position[2]))
    t = pz / -dz if (dz < -1e-4 and pz > 0.01) else 5.0
    return (
        round(px + dx * t, 4),
        round(py + dy * t, 4),
        0.0 if (dz < -1e-4 and pz > 0.01) else round(pz + dz * t, 4),
    )


class LightingDevice:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Patched lighting fixture in the show."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        fixture_id: int,
        label: str,
        fixture_type: FixtureType,
        channels: Optional[list[Channel]] = None,
        group: str = "",
        notes: str = "",
        color_profile: Optional[FixtureColorProfile] = None,
        manufacturer: str = "",
        model: str = "",
        mode_name: str = "",
        gdtf_id: str = "",
        position: tuple[float, float, float] = (0.0, 0.0, 4.0),
        focus_point: tuple[float, float, float] = (0.0, 0.0, 0.0),
        orientation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        beam_angle: float = 25.0,
        static_gobo: str = "",
        gel: str = "",
        gel_color: str = "",
        swap_pan_tilt: bool = False,
    ) -> None:
        self.fixture_id = fixture_id
        self.label = label
        self.fixture_type = fixture_type
        self.channels: list[Channel] = channels or []
        self.group = group
        self.notes = notes
        self.color_profile = color_profile
        self.manufacturer = manufacturer
        self.model = model
        self.mode_name = mode_name
        self.gdtf_id = gdtf_id
        self.position: tuple[float, float, float] = (
            float(position[0]),
            float(position[1]),
            float(position[2]),
        )
        self.focus_point: tuple[float, float, float] = (
            float(focus_point[0]),
            float(focus_point[1]),
            float(focus_point[2]),
        )
        self.orientation: tuple[float, float, float] = (
            float(orientation[0]),
            float(orientation[1]),
            float(orientation[2]),
        )
        self.beam_angle: float = max(1.0, min(180.0, float(beam_angle)))
        self.static_gobo: str = str(static_gobo)
        self.gel: str = str(gel)
        self.gel_color: str = str(gel_color)
        self.swap_pan_tilt: bool = bool(swap_pan_tilt)
        self._enabled = True
        self._locked = False
        self._created_at = time.time()

        # Virtual controls and normalized states
        self.curve_id: int = 0
        self._curve: Optional[Curve] = None
        self._curve_provider: Optional[Callable[[int], Optional[Curve]]] = None
        self._intensity: float = 0.0 if self.has_physical_dimmer else 1.0
        self._target_intensity: Optional[float] = None
        self._target_color: sRGB = sRGB(1.0, 1.0, 1.0)
        self._target_cie: CIExyY = CIExyY(0.3127, 0.3290, 100.0)
        self._base_emitters: dict[ChannelType, float] = {}
        self._param_normalized: dict[ChannelType, float] = {}
        self._param_last_raw: dict[ChannelType, int] = {}
        self._init_base_emitters()

    @property
    def effective_gel_color(self) -> str:
        """Return '#rrggbb' gel color from gel_color or resolved gel code."""
        if self.gel_color:
            return self.gel_color
        if self.gel:
            from .color_pick.gels import resolve_gel_hex  # pylint: disable=import-outside-toplevel

            return resolve_gel_hex(self.gel)
        return ""

    @property
    def universe(self) -> int:
        """Primary starting DMX universe of this device."""
        if not self.channels:
            return 1
        return min(ch.universe for ch in self.channels)

    @property
    def address(self) -> int:
        """Primary starting DMX address of this device."""
        if not self.channels:
            return 1
        u = self.universe
        return min(ch.address for ch in self.channels if ch.universe == u)

    @property
    def fixture_name(self) -> str:
        """Human-readable fixture profile name (e.g. 'Moving Head Spot', 'LED RGB')."""
        if self.model:
            if self.manufacturer and self.manufacturer.lower() != "generic":
                return f"{self.manufacturer} {self.model}"
            return self.model
        return self.fixture_type.value.replace("_", " ").title()

    @property
    def type_key(self) -> str:
        """Canonical fixture model + DMX mode key for By-Type palettes."""
        mode = self.mode_name.strip().lower()
        gdtf = self.gdtf_id.strip().lower()
        if gdtf:
            return f"gdtf:{gdtf}::{mode}" if mode else f"gdtf:{gdtf}"
        model = self.model.strip().lower()
        if model:
            mfr = self.manufacturer.strip().lower()
            base = f"{mfr}:{model}" if mfr else model
            return f"{base}::{mode}" if mode else base
        return f"type:{self.fixture_type.value.lower()}"

    def _addresses_by_universe(self) -> dict[int, list[int]]:
        by_univ: dict[int, set[int]] = {}
        for ch in self.channels:
            by_univ.setdefault(ch.universe, set()).add(ch.address)
        return {u: sorted(addrs) for u, addrs in sorted(by_univ.items())}

    @staticmethod
    def _format_contiguous_ranges(sorted_addrs: list[int], prefix: str = "") -> str:
        ranges: list[str] = []
        start = prev = sorted_addrs[0]
        for addr in sorted_addrs[1:]:
            if addr == prev + 1:
                prev = addr
            else:
                ranges.append(
                    f"{prefix}{start}" if start == prev else f"{prefix}{start}-{prev}"
                )
                start = prev = addr
        ranges.append(
            f"{prefix}{start}" if start == prev else f"{prefix}{start}-{prev}"
        )
        return ", ".join(ranges)

    @property
    def universe_display_str(self) -> str:
        """Return human-readable universe list (e.g. '1' or '1, 2')."""
        if not self.channels:
            return "-"
        by_univ = self._addresses_by_universe()
        return ", ".join(str(u) for u in by_univ)

    @property
    def address_range_str(self) -> str:
        """Return human-readable address range string (e.g. '10-17', '10, 25')."""
        if not self.channels:
            return "-"
        by_univ = self._addresses_by_universe()
        if len(by_univ) == 1:
            addrs = next(iter(by_univ.values()))
            return self._format_contiguous_ranges(addrs)
        return ", ".join(
            self._format_contiguous_ranges(addrs, prefix=f"{u}/")
            for u, addrs in by_univ.items()
        )

    def set_curve_id(self, curve_id: int) -> None:
        """Set curve ID for the device intensity transfer function."""
        self.curve_id = max(0, int(curve_id))

    def set_curve(self, curve: Optional[Curve]) -> None:
        """Directly assign a Curve instance."""
        self._curve = curve
        if curve is not None and hasattr(curve, "number"):
            self.curve_id = getattr(curve, "number", 0)

    def set_curve_provider(
        self, provider: Optional[Callable[[int], Optional[Curve]]]
    ) -> None:
        """Set a callable (curve_id -> Curve) to resolve curves dynamically."""
        self._curve_provider = provider
        if provider is not None and self.curve_id != 0 and self.uses_virtual_dimmer:
            self._apply_virtual_dimmer()

    def get_effective_curve(self) -> Optional[Curve]:
        """Resolve effective Curve instance if assigned."""
        if self._curve is not None:
            return self._curve
        if self.curve_id != 0 and self._curve_provider is not None:
            return self._curve_provider(self.curve_id)
        return None

    def _init_base_emitters(self) -> None:
        """Initialize emitter defaults (CMY default fraction or open white)."""
        if self.is_subtractive_cmy:
            for ch in self.channels:
                if ch.channel_type in COLOR_CHANNEL_TYPES:
                    self._base_emitters[ch.channel_type] = ch.default_value / 255.0
            self._update_target_from_emitters()
        else:
            for ch in self.channels:
                if ch.channel_type in COLOR_CHANNEL_TYPES:
                    self._base_emitters[ch.channel_type] = 1.0

    def add_channel(self, channel: Channel) -> LightingDevice:
        """Add a Channel to this device."""
        self.channels.append(channel)
        if channel.channel_type in COLOR_CHANNEL_TYPES:
            if self.is_subtractive_cmy:
                for ch in self.channels:
                    if ch.channel_type in COLOR_CHANNEL_TYPES and (
                        ch is channel or ch.channel_type not in self._base_emitters
                    ):
                        self._base_emitters[ch.channel_type] = ch.default_value / 255.0
                self._update_target_from_emitters()
            elif channel.channel_type not in self._base_emitters:
                self._base_emitters[channel.channel_type] = 1.0
        if channel.channel_type == ChannelType.INTENSITY:
            self._intensity = 0.0
        return self

    def get_channel(self, channel_type: ChannelType) -> Optional[Channel]:
        """Get first coarse channel matching the given ChannelType."""
        for ch in self.channels:
            if ch.channel_type == channel_type and not ch.fine and not ch.ultra_fine:
                return ch
        for ch in self.channels:
            if ch.channel_type == channel_type:
                return ch
        return None

    def get_channels(self, channel_type: ChannelType) -> list[Channel]:
        """Get all channels matching the given ChannelType."""
        return [ch for ch in self.channels if ch.channel_type == channel_type]

    def channel_count(self) -> int:
        """Total number of channels in this device."""
        return len(self.channels)

    def universes(self) -> list[int]:
        """List of universes spanned by this device."""
        return sorted({ch.universe for ch in self.channels})

    def channels_by_universe(self) -> dict[int, list[Channel]]:
        """Group channels by universe index."""
        result: dict[int, list[Channel]] = {}
        for ch in self.channels:
            result.setdefault(ch.universe, []).append(ch)
        return {
            u: sorted(chs, key=lambda c: c.address) for u, chs in sorted(result.items())
        }

    def footprint(self) -> dict[int, tuple[int, int]]:
        """Return {universe: (start_address, end_address)}."""
        return {
            u: (chs[0].address, chs[-1].address)
            for u, chs in self.channels_by_universe().items()
        }

    def patch_summary(self) -> str:
        """Human-readable summary of universe and address footprints."""
        fp = self.footprint()
        if not fp:
            return "unpatched"
        return " | ".join(f"U{u}:{s}-{e}" for u, (s, e) in fp.items())

    # Resolution channel helpers
    def _get_resolution_channels(
        self, channel_type: ChannelType
    ) -> tuple[Optional[Channel], Optional[Channel], Optional[Channel]]:
        """Get (coarse_channel, fine_channel, ultra_fine_channel) for ChannelType."""
        coarse_ch = None
        fine_ch = None
        ultra_fine_ch = None
        for ch in self.channels:
            if ch.channel_type == channel_type:
                if ch.ultra_fine:
                    ultra_fine_ch = ch
                elif ch.fine:
                    fine_ch = ch
                elif coarse_ch is None:
                    coarse_ch = ch
        return coarse_ch, fine_ch, ultra_fine_ch

    def _get_resolution_channels_by_label(
        self, label: str
    ) -> tuple[Optional[Channel], Optional[Channel], Optional[Channel]]:
        """Get (coarse_channel, fine_channel, ultra_fine_channel) matched by label."""
        target = label.strip().lower()
        if not target:
            return None, None, None
        coarse_ch = None
        for ch in self.channels:
            if not ch.fine and not ch.ultra_fine and ch.label.strip().lower() == target:
                coarse_ch = ch
                break
        if coarse_ch is None:
            return None, None, None
        fine_target = f"{target}_fine"
        ultra_target = f"{target}_ultra_fine"
        fine_ch = None
        ultra_fine_ch = None
        for ch in self.channels:
            ch_low = ch.label.strip().lower()
            if ch.fine and ch_low == fine_target and fine_ch is None:
                fine_ch = ch
            elif ch.ultra_fine and ch_low == ultra_target and ultra_fine_ch is None:
                ultra_fine_ch = ch
        return coarse_ch, fine_ch, ultra_fine_ch

    def _get_coarse_fine_channels(
        self, channel_type: ChannelType
    ) -> tuple[Optional[Channel], Optional[Channel]]:
        """Get (coarse_channel, fine_channel) for the specified ChannelType."""
        coarse_ch, fine_ch, _ = self._get_resolution_channels(channel_type)
        return coarse_ch, fine_ch

    # Dimmer and virtual dimmer properties
    @property
    def has_physical_dimmer(self) -> bool:
        """True if the device has at least one physical INTENSITY channel."""
        return any(
            ch.channel_type == ChannelType.INTENSITY
            and not ch.fine
            and not ch.ultra_fine
            for ch in self.channels
        )

    @property
    def has_16bit_dimmer(self) -> bool:
        """True if the physical dimmer is 16-bit (coarse + fine)."""
        return any(
            ch.channel_type == ChannelType.INTENSITY and ch.fine for ch in self.channels
        )

    @property
    def has_24bit_dimmer(self) -> bool:
        """True if the physical dimmer is 24-bit (coarse + fine + ultra-fine)."""
        return any(
            ch.channel_type == ChannelType.INTENSITY and ch.ultra_fine
            for ch in self.channels
        )

    @property
    def is_subtractive_cmy(self) -> bool:
        """True if fixture uses subtractive CMY mixing without additive RGB."""
        ctypes = {ch.channel_type for ch in self.channels}
        return bool(ctypes & _SUBTRACTIVE_CMY_TYPES) and not bool(
            ctypes & _ADDITIVE_RGB_TYPES
        )

    @property
    def has_color_capability(self) -> bool:
        """True if fixture has at least one color mixing channel."""
        return any(ch.channel_type in COLOR_CHANNEL_TYPES for ch in self.channels)

    @property
    def uses_virtual_dimmer(self) -> bool:
        """True if fixture has additive color emitters without physical INTENSITY."""
        return (
            not self.has_physical_dimmer
            and not self.is_subtractive_cmy
            and any(ch.channel_type in COLOR_CHANNEL_TYPES for ch in self.channels)
        )

    # Intensity controls [0.0, 1.0]
    @property
    def intensity(self) -> float:
        """Normalized intensity level in range [0.0, 1.0]."""
        return self._intensity

    @property
    def intensity_8bit(self) -> int:
        """Intensity level as an 8-bit integer in range [0..255]."""
        return round(self._intensity * 255.0)

    @property
    def intensity_16bit(self) -> int:
        """Intensity level as a 16-bit integer in range [0..65535]."""
        return round(self._intensity * 65535.0)

    @property
    def intensity_24bit(self) -> int:
        """Intensity level as a 24-bit integer in range [0..16777215]."""
        return round(self._intensity * 16777215.0)

    @property
    def intensity_percent(self) -> float:
        """Intensity level as a percentage in range [0.0..100.0]."""
        return round(self._intensity * 100.0, 1)

    def set_intensity(self, value: float | int) -> None:
        """Set intensity level.

        Accepts normalized float [0.0, 1.0] or 8-bit int [0..255].
        Values > 1.0 are treated as 8-bit integers and normalized.
        """
        if isinstance(value, (int, float)) and value > 1.0:
            norm_val = max(0.0, min(1.0, float(value) / 255.0))
        else:
            norm_val = max(0.0, min(1.0, float(value)))
        self._intensity = norm_val
        self._target_intensity = norm_val
        self._apply_intensity()

    def set_intensity_8bit(self, value: int) -> None:
        """Set intensity from 8-bit integer [0..255]."""
        self.set_intensity(max(0, min(255, value)) / 255.0)

    def set_intensity_16bit(self, value: int) -> None:
        """Set intensity from 16-bit integer [0..65535]."""
        clamped = max(0, min(65535, value))
        self._intensity = clamped / 65535.0
        self._target_intensity = self._intensity
        self._apply_intensity()

    def set_intensity_24bit(self, value: int) -> None:
        """Set intensity from 24-bit integer [0..16777215]."""
        clamped = max(0, min(16777215, value))
        self._intensity = clamped / 16777215.0
        self._target_intensity = self._intensity
        self._apply_intensity()

    def set_intensity_percent(self, percent: float) -> None:
        """Set intensity from percentage [0.0..100.0]."""
        self.set_intensity(max(0.0, min(100.0, percent)) / 100.0)

    def _apply_intensity(self) -> None:
        """Propagate intensity to DMX channels, applying effective curve if any."""
        curve = self.get_effective_curve()
        if self.has_physical_dimmer:
            coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
                ChannelType.INTENSITY
            )
            if (
                ultra_fine_ch is not None
                and fine_ch is not None
                and coarse_ch is not None
            ):
                raw_24 = round(self._intensity * 16777215.0)
                val_24 = curve.get_level_24bit(raw_24) if curve else raw_24
                c_b, f_b, u_b = (
                    (val_24 >> 16) & 0xFF,
                    (val_24 >> 8) & 0xFF,
                    val_24 & 0xFF,
                )
                for ch in self.channels:
                    if ch.channel_type is ChannelType.INTENSITY:
                        if ch.ultra_fine:
                            ch.set_value(u_b)
                        elif ch.fine:
                            ch.set_value(f_b)
                        else:
                            ch.set_value(c_b)
            elif fine_ch is not None and coarse_ch is not None:
                raw_16 = round(self._intensity * 65535.0)
                val_16 = curve.get_level_16bit(raw_16) if curve else raw_16
                c_b, f_b = (val_16 >> 8) & 0xFF, val_16 & 0xFF
                for ch in self.channels:
                    if ch.channel_type is ChannelType.INTENSITY:
                        if ch.fine:
                            ch.set_value(f_b)
                        elif not ch.ultra_fine:
                            ch.set_value(c_b)
            elif coarse_ch is not None:
                raw_8 = round(self._intensity * 255.0)
                val_8 = curve.get_level(raw_8) if curve else raw_8
                for ch in self.channels:
                    if (
                        ch.channel_type is ChannelType.INTENSITY
                        and not ch.fine
                        and not ch.ultra_fine
                    ):
                        ch.set_value(val_8)
        elif self.uses_virtual_dimmer:
            self._apply_virtual_dimmer(curve=curve)

    def _set_color_emitter_channels(
        self, channel_type: ChannelType, level: float
    ) -> None:
        """Write normalized [0.0, 1.0] color emitter level to 8/16/24-bit channels."""
        clamped = max(0.0, min(1.0, float(level)))
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(channel_type)
        if coarse_ch is None:
            return
        if ultra_fine_ch is not None and fine_ch is not None:
            val_24 = round(clamped * 16777215.0)
            c_byte, f_byte, u_byte = (
                (val_24 >> 16) & 0xFF,
                (val_24 >> 8) & 0xFF,
                val_24 & 0xFF,
            )
        elif fine_ch is not None:
            val_16 = round(clamped * 65535.0)
            c_byte, f_byte, u_byte = (val_16 >> 8) & 0xFF, val_16 & 0xFF, None
        else:
            c_byte, f_byte, u_byte = round(clamped * 255.0), None, None

        for ch in self.channels:
            if ch.channel_type != channel_type:
                continue
            if ch.ultra_fine and u_byte is not None:
                ch.set_value(u_byte)
            elif ch.fine and f_byte is not None:
                ch.set_value(f_byte)
            elif not ch.fine and not ch.ultra_fine:
                ch.set_value(c_byte)
        self._param_normalized.pop(channel_type, None)
        self._param_last_raw.pop(channel_type, None)

    def _apply_virtual_dimmer(self, curve: Optional[Curve] = None) -> None:
        """Scale base emitter levels by current intensity (curved if assigned)."""
        active_curve = curve if curve is not None else self.get_effective_curve()
        if active_curve is not None:
            try:
                eff_intensity = float(active_curve.evaluate_normalized(self._intensity))
            except NotImplementedError:
                idx = max(0, min(255, round(self._intensity * 255.0)))
                eff_intensity = float(active_curve.values_array[idx]) / 255.0
        else:
            eff_intensity = self._intensity
        for ctype in COLOR_CHANNEL_TYPES:
            base_val = self._base_emitters.get(ctype, 0.0)
            self._set_color_emitter_channels(ctype, base_val * eff_intensity)

    # Color controls
    @property
    def color_rgb(self) -> tuple[int, int, int]:
        """Return (r, g, b) tuple [0..255] of base target color."""
        return self._target_color.to_255()

    @property
    def color_srgb(self) -> sRGB:
        """Return target color as normalized sRGB instance."""
        return self._target_color

    @property
    def color_cie(self) -> CIExyY:
        """Return target color as CIE xyY chromaticity."""
        return self._target_cie

    def get_preview_rgb(self) -> Optional[tuple[float, float, float]]:
        """Return normalized (r, g, b) preview color for color-capable devices."""
        if not self.has_color_capability:
            return None
        if self.is_subtractive_cmy:
            c = self.get_parameter_normalized(ChannelType.CYAN)
            m = self.get_parameter_normalized(ChannelType.MAGENTA)
            y = self.get_parameter_normalized(ChannelType.YELLOW)
            c_val = c if c is not None else 0.0
            m_val = m if m is not None else 0.0
            y_val = y if y is not None else 0.0
            if (
                self.color_profile is not None
                and self.color_profile.mixing_mode == "subtractive"
            ):
                cto_val = (
                    self.get_parameter_normalized(ChannelType.COLOR_TEMP) or 0.0
                    if self.color_profile.has_cto_filter
                    else 0.0
                )
                rgb = self.color_profile.evaluate_subtractive(
                    c_val, m_val, y_val, cto=cto_val
                ).to_srgb()
                return (rgb.r, rgb.g, rgb.b)
            return (
                max(0.0, min(1.0, 1.0 - c_val)),
                max(0.0, min(1.0, 1.0 - m_val)),
                max(0.0, min(1.0, 1.0 - y_val)),
            )
        return (self._target_color.r, self._target_color.g, self._target_color.b)

    def set_color_srgb(
        self,
        r: float,
        g: float,
        b: float,
        solved: Optional[MatchResult] = None,
    ) -> None:
        """Set color from normalized sRGB components [0.0, 1.0].

        Args:
            r: Red, 0.0 to 1.0.
            g: Green, 0.0 to 1.0.
            b: Blue, 0.0 to 1.0.
            solved: Optional pre-computed NNLS result for this device's color
                profile and this color. It lets a caller that drives many
                identical fixtures solve once and share the result.
        """
        r_norm = max(0.0, min(1.0, float(r)))
        g_norm = max(0.0, min(1.0, float(g)))
        b_norm = max(0.0, min(1.0, float(b)))
        self._target_color = sRGB(r_norm, g_norm, b_norm)
        self._target_cie = self._target_color.to_XYZ().to_xyY()

        if self.color_profile is not None:
            if solved is not None:
                self._apply_match_result(solved)
            else:
                self._solve_emitters_from_cie(self._target_cie)
        elif self.is_subtractive_cmy:
            self._base_emitters[ChannelType.CYAN] = 1.0 - r_norm
            self._base_emitters[ChannelType.MAGENTA] = 1.0 - g_norm
            self._base_emitters[ChannelType.YELLOW] = 1.0 - b_norm
        else:
            self._base_emitters[ChannelType.RED] = r_norm
            self._base_emitters[ChannelType.GREEN] = g_norm
            self._base_emitters[ChannelType.BLUE] = b_norm
        self._apply_color()

    def set_color_cie(
        self,
        x: float,
        y: float,
        Y: Optional[float] = None,  # pylint: disable=invalid-name
        solved: Optional[MatchResult] = None,
    ) -> None:
        """Set target color from CIE xyY chromaticity coordinates."""
        if Y is not None:
            eff_y = max(0.0, float(Y))
        else:
            eff_y = max(
                0.0,
                min(
                    100.0,
                    CIExyY(float(x), float(y), 100.0).to_XYZ().to_srgb().to_XYZ().Y,
                ),
            )
        self._target_cie = CIExyY(float(x), float(y), eff_y)
        self._target_color = self._target_cie.to_XYZ().to_srgb()
        if self.color_profile is not None:
            if solved is not None:
                self._apply_match_result(solved)
            else:
                self._solve_emitters_from_cie(self._target_cie)
        elif self.is_subtractive_cmy:
            self._base_emitters[ChannelType.CYAN] = max(
                0.0, min(1.0, 1.0 - self._target_color.r)
            )
            self._base_emitters[ChannelType.MAGENTA] = max(
                0.0, min(1.0, 1.0 - self._target_color.g)
            )
            self._base_emitters[ChannelType.YELLOW] = max(
                0.0, min(1.0, 1.0 - self._target_color.b)
            )
        else:
            self._base_emitters[ChannelType.RED] = self._target_color.r
            self._base_emitters[ChannelType.GREEN] = self._target_color.g
            self._base_emitters[ChannelType.BLUE] = self._target_color.b
        self._apply_color()

    def set_color_rgb(self, r: int, g: int, b: int) -> None:
        """Set color from 8-bit integer RGB components [0..255]."""
        self.set_color_srgb(r / 255.0, g / 255.0, b / 255.0)

    def set_color_hex(self, hex_str: str) -> None:
        """Set color from HTML hex string (#RRGGBB)."""
        c = sRGB.from_hex(hex_str)
        self.set_color_srgb(c.r, c.g, c.b)

    def set_color(self, r: int, g: int, b: int, w: int = 0, a: int = 0) -> None:
        """Set color emitter channel values directly [0..255]."""
        r_norm = max(0, min(255, r)) / 255.0
        g_norm = max(0, min(255, g)) / 255.0
        b_norm = max(0, min(255, b)) / 255.0
        w_norm = max(0, min(255, w)) / 255.0
        a_norm = max(0, min(255, a)) / 255.0

        if self.is_subtractive_cmy:
            self._base_emitters[ChannelType.CYAN] = 1.0 - r_norm
            self._base_emitters[ChannelType.MAGENTA] = 1.0 - g_norm
            self._base_emitters[ChannelType.YELLOW] = 1.0 - b_norm
        else:
            self._base_emitters[ChannelType.RED] = r_norm
            self._base_emitters[ChannelType.GREEN] = g_norm
            self._base_emitters[ChannelType.BLUE] = b_norm
            self._base_emitters[ChannelType.WHITE] = w_norm
            self._base_emitters[ChannelType.AMBER] = a_norm

        self._target_color = sRGB(r_norm, g_norm, b_norm)
        self._target_cie = self._target_color.to_XYZ().to_xyY()
        self._apply_color()

    def get_emitter_level(self, channel_type: ChannelType) -> float:
        """Return normalized [0.0, 1.0] emitter level for a color ChannelType."""
        if channel_type == ChannelType.COLOR_TEMP:
            return float(self.get_parameter_normalized(ChannelType.COLOR_TEMP) or 0.0)
        return float(self._base_emitters.get(channel_type, 0.0))

    def set_emitter_level(self, channel_type: ChannelType, level: float) -> None:
        """Set a single color emitter level [0.0, 1.0] and update CIE/sRGB state."""
        if channel_type == ChannelType.COLOR_TEMP:
            if self.get_channel(ChannelType.COLOR_TEMP) is None:
                return
            clamped = max(0.0, min(1.0, float(level)))
            self._set_color_emitter_channels(ChannelType.COLOR_TEMP, clamped)
            self._update_target_from_emitters()
            return
        if channel_type not in COLOR_CHANNEL_TYPES:
            return
        self._base_emitters[channel_type] = max(0.0, min(1.0, float(level)))
        self._update_target_from_emitters()
        self._apply_color()

    def _update_target_from_emitters(self) -> None:  # pylint: disable=too-many-locals
        """Synthesize target CIE xyY and sRGB from current _base_emitters levels."""
        if self.is_subtractive_cmy:
            c_val = float(self._base_emitters.get(ChannelType.CYAN, 0.0))
            m_val = float(self._base_emitters.get(ChannelType.MAGENTA, 0.0))
            y_val = float(self._base_emitters.get(ChannelType.YELLOW, 0.0))
            if (
                self.color_profile is not None
                and self.color_profile.mixing_mode == "subtractive"
            ):
                cto_val = (
                    self.get_parameter_normalized(ChannelType.COLOR_TEMP) or 0.0
                    if self.color_profile.has_cto_filter
                    else 0.0
                )
                xyz = self.color_profile.evaluate_subtractive(
                    c_val, m_val, y_val, cto=cto_val
                )
                self._target_cie = xyz.to_xyY()
                self._target_color = xyz.to_srgb()
            else:
                self._target_color = sRGB(
                    max(0.0, min(1.0, 1.0 - c_val)),
                    max(0.0, min(1.0, 1.0 - m_val)),
                    max(0.0, min(1.0, 1.0 - y_val)),
                )
                self._target_cie = self._target_color.to_XYZ().to_xyY()
            return
        default_cie: dict[ChannelType, CIExyY] = {
            ChannelType.RED: CIExyY(0.6400, 0.3300, 21.26),
            ChannelType.GREEN: CIExyY(0.3000, 0.6000, 71.52),
            ChannelType.BLUE: CIExyY(0.1500, 0.0600, 7.22),
            ChannelType.WHITE: CIExyY(0.3127, 0.3290, 100.0),
            ChannelType.AMBER: CIExyY(0.5900, 0.4000, 50.0),
            ChannelType.LIME: CIExyY(0.3225, 0.3870, 80.0),
            ChannelType.CYAN: CIExyY(0.0454, 0.2950, 25.0),
            ChannelType.INDIGO: CIExyY(0.1689, 0.0069, 5.0),
            ChannelType.MAGENTA: CIExyY(0.3800, 0.1500, 20.0),
            ChannelType.YELLOW: CIExyY(0.4800, 0.4800, 60.0),
        }
        name_map = {
            "red": ChannelType.RED,
            "green": ChannelType.GREEN,
            "blue": ChannelType.BLUE,
            "white": ChannelType.WHITE,
            "amber": ChannelType.AMBER,
            "lime": ChannelType.LIME,
            "green-yellow": ChannelType.LIME,
            "coloradd_gy": ChannelType.LIME,
            "cyan": ChannelType.CYAN,
            "coloradd_c": ChannelType.CYAN,
            "colorsub_c": ChannelType.CYAN,
            "indigo": ChannelType.INDIGO,
            "royal blue": ChannelType.INDIGO,
            "blue-cyan": ChannelType.INDIGO,
            "coloradd_bc": ChannelType.INDIGO,
            "magenta": ChannelType.MAGENTA,
            "coloradd_m": ChannelType.MAGENTA,
            "colorsub_m": ChannelType.MAGENTA,
            "yellow": ChannelType.YELLOW,
            "coloradd_y": ChannelType.YELLOW,
            "colorsub_y": ChannelType.YELLOW,
            "red-orange": ChannelType.RED,
            "coloradd_ry": ChannelType.RED,
        }
        if self.color_profile is not None:
            for em in self.color_profile.emitters:
                ct = name_map.get(em.name.lower())
                if ct is not None:
                    default_cie[ct] = em.cie

        tot_x = tot_y = tot_z = 0.0
        for ctype in COLOR_CHANNEL_TYPES:
            lvl = self._base_emitters.get(ctype, 0.0)
            if lvl <= 0.0:
                continue
            xyz = default_cie[ctype].to_XYZ()
            tot_x += lvl * xyz.X
            tot_y += lvl * xyz.Y
            tot_z += lvl * xyz.Z

        if tot_y <= 1e-6 and (tot_x + tot_y + tot_z) <= 1e-6:
            self._target_color = sRGB(0.0, 0.0, 0.0)
            self._target_cie = CIExyY(0.3127, 0.3290, 0.0)
            return

        total_xyz = CIEXYZ(tot_x, tot_y, tot_z)
        xyy = total_xyz.to_xyY()
        self._target_cie = CIExyY(xyy.x, xyy.y, min(100.0, xyy.Y))

        # Scale XYZ down if linear RGB exceeds 1.0 to preserve chromaticity/hue
        x_n, y_n, z_n = tot_x / 100.0, tot_y / 100.0, tot_z / 100.0
        r_lin = 3.2404542 * x_n - 1.5371385 * y_n - 0.4985314 * z_n
        g_lin = -0.9692660 * x_n + 1.8760108 * y_n + 0.0415560 * z_n
        b_lin = 0.0556434 * x_n - 0.2040259 * y_n + 1.0572252 * z_n
        max_lin = max(r_lin, g_lin, b_lin, 1.0)
        scaled_xyz = CIEXYZ(tot_x / max_lin, tot_y / max_lin, tot_z / max_lin)
        self._target_color = scaled_xyz.to_srgb()

    def _solve_emitters_from_cie(self, cie: CIExyY) -> None:
        """Calculate emitter fractions using NNLS ColorMatcher."""
        if self.color_profile is None:
            return
        matcher = ColorMatcher([self.color_profile])
        matches = matcher.match_cie(cie.x, cie.y, cie.Y)
        result = matches.get(self.color_profile.fixture_name)
        if result:
            self._apply_match_result(result)

    def _apply_match_result(self, result: MatchResult) -> None:
        """Store the emitter levels of an NNLS match result in float precision."""
        name_map = {
            "red": ChannelType.RED,
            "green": ChannelType.GREEN,
            "blue": ChannelType.BLUE,
            "white": ChannelType.WHITE,
            "amber": ChannelType.AMBER,
            "lime": ChannelType.LIME,
            "green-yellow": ChannelType.LIME,
            "coloradd_gy": ChannelType.LIME,
            "cyan": ChannelType.CYAN,
            "coloradd_c": ChannelType.CYAN,
            "colorsub_c": ChannelType.CYAN,
            "indigo": ChannelType.INDIGO,
            "royal blue": ChannelType.INDIGO,
            "blue-cyan": ChannelType.INDIGO,
            "coloradd_bc": ChannelType.INDIGO,
            "magenta": ChannelType.MAGENTA,
            "coloradd_m": ChannelType.MAGENTA,
            "colorsub_m": ChannelType.MAGENTA,
            "yellow": ChannelType.YELLOW,
            "coloradd_y": ChannelType.YELLOW,
            "colorsub_y": ChannelType.YELLOW,
            "red-orange": ChannelType.RED,
            "coloradd_ry": ChannelType.RED,
        }
        for emitter_name, ratio in result.as_normalized_dict().items():
            key = emitter_name.lower()
            if key in {"cto", "cto1", "ctc"}:
                self._set_color_emitter_channels(
                    ChannelType.COLOR_TEMP, max(0.0, min(1.0, float(ratio)))
                )
                continue
            ctype = name_map.get(key)
            if ctype:
                self._base_emitters[ctype] = max(0.0, min(1.0, float(ratio)))

    def _apply_color(self) -> None:
        """Apply base emitters to DMX channels (8, 16, or 24-bit)."""
        if self.uses_virtual_dimmer:
            self._apply_virtual_dimmer()
        else:
            for ctype in COLOR_CHANNEL_TYPES:
                base_val = self._base_emitters.get(ctype, 0.0)
                self._set_color_emitter_channels(ctype, base_val)

    # Physical, normalized and multi-resolution helpers
    @staticmethod
    def _channels_raw_and_max(
        coarse_ch: Optional[Channel],
        fine_ch: Optional[Channel],
        ultra_fine_ch: Optional[Channel],
    ) -> Optional[tuple[int, int, Channel, Optional[Channel], Optional[Channel]]]:
        """Compute (raw_value, max_raw_value, coarse_ch, fine_ch, ultra_fine_ch)."""
        if coarse_ch is None:
            return None
        if ultra_fine_ch is not None and fine_ch is not None:
            raw = (coarse_ch.value << 16) | (fine_ch.value << 8) | ultra_fine_ch.value
            max_raw = 16777215
        elif fine_ch is not None:
            raw = (coarse_ch.value << 8) | fine_ch.value
            max_raw = 65535
        else:
            raw = coarse_ch.value
            max_raw = 255
        return (raw, max_raw, coarse_ch, fine_ch, ultra_fine_ch)

    @staticmethod
    def _write_resolution_channels(
        coarse_ch: Channel,
        fine_ch: Optional[Channel],
        ultra_fine_ch: Optional[Channel],
        clamped_norm: float,
    ) -> int:
        """Write normalized value [0.0..1.0] across 8/16/24-bit channels; return raw."""
        if ultra_fine_ch is not None and fine_ch is not None:
            val_24 = round(clamped_norm * 16777215.0)
            coarse_ch.set_value((val_24 >> 16) & 0xFF)
            fine_ch.set_value((val_24 >> 8) & 0xFF)
            ultra_fine_ch.set_value(val_24 & 0xFF)
            return val_24
        if fine_ch is not None:
            val_16 = round(clamped_norm * 65535.0)
            coarse_ch.set_value((val_16 >> 8) & 0xFF)
            fine_ch.set_value(val_16 & 0xFF)
            return val_16
        coarse_ch.set_normalized(clamped_norm)
        return coarse_ch.value

    def _get_raw_and_max(
        self, channel_type: ChannelType
    ) -> Optional[tuple[int, int, Channel, Optional[Channel], Optional[Channel]]]:
        """Return (raw_value, max_raw_value, coarse_ch, fine_ch, ultra_fine_ch)."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(channel_type)
        return self._channels_raw_and_max(coarse_ch, fine_ch, ultra_fine_ch)

    def get_channel_normalized_by_label(self, label: str) -> Optional[float]:
        """Return normalized [0.0..1.0] value for a channel matched by label."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels_by_label(
            label
        )
        res = self._channels_raw_and_max(coarse_ch, fine_ch, ultra_fine_ch)
        if res is None:
            return None
        raw, max_raw, _, _, _ = res
        return raw / float(max_raw) if max_raw > 0 else 0.0

    def set_channel_normalized_by_label(self, label: str, norm: float) -> bool:
        """Set normalized [0.0..1.0] value across 8/16/24-bit channels by label."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels_by_label(
            label
        )
        if coarse_ch is None:
            return False
        clamped_norm = max(0.0, min(1.0, float(norm)))
        self._write_resolution_channels(coarse_ch, fine_ch, ultra_fine_ch, clamped_norm)
        return True

    def _sync_param_after_raw_write(self, channel_type: ChannelType) -> None:
        """Synchronize _param_normalized and _param_last_raw from DMX channels."""
        res = self._get_raw_and_max(channel_type)
        if res is not None:
            raw, max_raw, _, _, _ = res
            self._param_last_raw[channel_type] = raw
            self._param_normalized[channel_type] = (
                raw / float(max_raw) if max_raw > 0 else 0.0
            )

    def get_parameter_normalized(self, channel_type: ChannelType) -> Optional[float]:
        """Return normalized parameter value in continuous range [0.0..1.0]."""
        res = self._get_raw_and_max(channel_type)
        if res is None:
            return None
        raw, max_raw, _, _, _ = res
        if (
            channel_type not in self._param_normalized
            or self._param_last_raw.get(channel_type) != raw
        ):
            norm = raw / float(max_raw) if max_raw > 0 else 0.0
            self._param_normalized[channel_type] = norm
            self._param_last_raw[channel_type] = raw
        return self._param_normalized[channel_type]

    def set_parameter_normalized(self, channel_type: ChannelType, norm: float) -> None:
        """Set normalized parameter [0.0..1.0] and distribute across 8/16/24 bits."""
        res = self._get_raw_and_max(channel_type)
        if res is None:
            return
        _, _, coarse_ch, fine_ch, ultra_fine_ch = res
        clamped_norm = max(0.0, min(1.0, float(norm)))
        self._param_normalized[channel_type] = clamped_norm

        self._param_last_raw[channel_type] = self._write_resolution_channels(
            coarse_ch, fine_ch, ultra_fine_ch, clamped_norm
        )
        for ch in self.channels:
            if ch.channel_type == channel_type:
                if (
                    ch.ultra_fine
                    and ultra_fine_ch is not None
                    and ch.label == ultra_fine_ch.label
                ):
                    ch.set_value(ultra_fine_ch.value)
                elif ch.fine and fine_ch is not None and ch.label == fine_ch.label:
                    ch.set_value(fine_ch.value)
                elif not ch.fine and not ch.ultra_fine and ch.label == coarse_ch.label:
                    ch.set_value(coarse_ch.value)
        if channel_type in COLOR_CHANNEL_TYPES:
            self._base_emitters[channel_type] = clamped_norm
            self._update_target_from_emitters()

    def set_parameter_percent(self, channel_type: ChannelType, percent: float) -> None:
        """Set parameter percent [0.0..100.0] across 8/16/24-bit channels."""
        norm = max(0.0, min(100.0, float(percent))) / 100.0
        self.set_parameter_normalized(channel_type, norm)

    def get_parameter_percent(self, channel_type: ChannelType) -> Optional[float]:
        """Get parameter percent [0.0..100.0] reconstructed across channels."""
        norm = self.get_parameter_normalized(channel_type)
        return round(norm * 100.0, 2) if norm is not None else None

    def _set_physical_parameter(self, channel_type: ChannelType, value: float) -> None:
        """Set a parameter value using physical range (supports 8/16/24-bit)."""
        coarse_ch, _, _ = self._get_resolution_channels(channel_type)
        if coarse_ch is None:
            return

        p_min = coarse_ch.physical_min
        p_max = coarse_ch.physical_max
        if p_max == p_min:
            norm = 0.0
        else:
            clamped = max(min(p_min, p_max), min(max(p_min, p_max), float(value)))
            norm = (clamped - p_min) / (p_max - p_min)

        self.set_parameter_normalized(channel_type, norm)

    def _get_physical_parameter(self, channel_type: ChannelType) -> Optional[float]:
        """Get parameter value in physical units, preserving continuous float."""
        coarse_ch, _, _ = self._get_resolution_channels(channel_type)
        if coarse_ch is None:
            return None
        norm = self.get_parameter_normalized(channel_type)
        if norm is None:
            return None
        p_min = coarse_ch.physical_min
        p_max = coarse_ch.physical_max
        return p_min + norm * (p_max - p_min)

    # Position controls (8-bit, 16-bit, 24-bit and physical degrees)
    def set_position(self, pan: int, tilt: int) -> None:
        """Set pan and tilt coordinates (8-bit) [0..255]."""
        self.set_pan(pan)
        self.set_tilt(tilt)

    def set_position_16bit(self, pan: int, tilt: int) -> None:
        """Set pan and tilt coordinates (16-bit) [0..65535]."""
        self.set_pan_16bit(pan)
        self.set_tilt_16bit(tilt)

    def set_position_24bit(self, pan: int, tilt: int) -> None:
        """Set pan and tilt coordinates (24-bit) [0..16777215]."""
        self.set_pan_24bit(pan)
        self.set_tilt_24bit(tilt)

    def set_position_degrees(self, pan: float, tilt: float) -> None:
        """Set pan and tilt coordinates in physical degrees."""
        self.set_pan_degrees(pan)
        self.set_tilt_degrees(tilt)

    def set_pan(self, pan: int) -> None:
        """Set pan coordinate (8-bit) [0..255]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        if coarse_ch:
            coarse_ch.set_value(pan)
        if fine_ch:
            fine_ch.set_value(0)
        if ultra_fine_ch:
            ultra_fine_ch.set_value(0)
        self._sync_param_after_raw_write(ChannelType.PAN)

    def set_pan_16bit(self, pan: int) -> None:
        """Set pan coordinate (16-bit) [0..65535]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        clamped = max(0, min(65535, int(pan)))
        if fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 8) & 0xFF)
            fine_ch.set_value(clamped & 0xFF)
            if ultra_fine_ch:
                ultra_fine_ch.set_value(0)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 65535.0 * 255.0))
        self._sync_param_after_raw_write(ChannelType.PAN)

    def set_pan_24bit(self, pan: int) -> None:
        """Set pan coordinate (24-bit) [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        clamped = max(0, min(16777215, int(pan)))
        if ultra_fine_ch and fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 16) & 0xFF)
            fine_ch.set_value((clamped >> 8) & 0xFF)
            ultra_fine_ch.set_value(clamped & 0xFF)
        elif fine_ch and coarse_ch:
            val_16 = round(clamped / 16777215.0 * 65535.0)
            coarse_ch.set_value((val_16 >> 8) & 0xFF)
            fine_ch.set_value(val_16 & 0xFF)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 16777215.0 * 255.0))
        self._sync_param_after_raw_write(ChannelType.PAN)

    def set_tilt(self, tilt: int) -> None:
        """Set tilt coordinate (8-bit) [0..255]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        if coarse_ch:
            coarse_ch.set_value(tilt)
        if fine_ch:
            fine_ch.set_value(0)
        if ultra_fine_ch:
            ultra_fine_ch.set_value(0)
        self._sync_param_after_raw_write(ChannelType.TILT)

    def set_tilt_16bit(self, tilt: int) -> None:
        """Set tilt coordinate (16-bit) [0..65535]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        clamped = max(0, min(65535, int(tilt)))
        if fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 8) & 0xFF)
            fine_ch.set_value(clamped & 0xFF)
            if ultra_fine_ch:
                ultra_fine_ch.set_value(0)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 65535.0 * 255.0))
        self._sync_param_after_raw_write(ChannelType.TILT)

    def set_tilt_24bit(self, tilt: int) -> None:
        """Set tilt coordinate (24-bit) [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        clamped = max(0, min(16777215, int(tilt)))
        if ultra_fine_ch and fine_ch and coarse_ch:
            coarse_ch.set_value((clamped >> 16) & 0xFF)
            fine_ch.set_value((clamped >> 8) & 0xFF)
            ultra_fine_ch.set_value(clamped & 0xFF)
        elif fine_ch and coarse_ch:
            val_16 = round(clamped / 16777215.0 * 65535.0)
            coarse_ch.set_value((val_16 >> 8) & 0xFF)
            fine_ch.set_value(val_16 & 0xFF)
        elif coarse_ch:
            coarse_ch.set_value(round(clamped / 16777215.0 * 255.0))
        self._sync_param_after_raw_write(ChannelType.TILT)

    def set_pan_degrees(self, angle: float) -> None:
        """Set pan coordinate in physical degrees."""
        self._set_physical_parameter(ChannelType.PAN, angle)

    def set_tilt_degrees(self, angle: float) -> None:
        """Set tilt coordinate in physical degrees."""
        self._set_physical_parameter(ChannelType.TILT, angle)

    @property
    def pan_16bit(self) -> int:
        """Return pan coordinate as 16-bit integer [0..65535]."""
        coarse_ch, fine_ch = self._get_coarse_fine_channels(ChannelType.PAN)
        if not coarse_ch:
            return 0
        if fine_ch:
            return (coarse_ch.value << 8) | fine_ch.value
        return coarse_ch.value * 257

    @property
    def pan_24bit(self) -> int:
        """Return pan coordinate as 24-bit integer [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.PAN
        )
        if not coarse_ch:
            return 0
        if ultra_fine_ch and fine_ch:
            return (coarse_ch.value << 16) | (fine_ch.value << 8) | ultra_fine_ch.value
        if fine_ch:
            raw_16 = (coarse_ch.value << 8) | fine_ch.value
            return round(raw_16 / 65535.0 * 16777215.0)
        return round(coarse_ch.value / 255.0 * 16777215.0)

    @property
    def tilt_16bit(self) -> int:
        """Return tilt coordinate as 16-bit integer [0..65535]."""
        coarse_ch, fine_ch = self._get_coarse_fine_channels(ChannelType.TILT)
        if not coarse_ch:
            return 0
        if fine_ch:
            return (coarse_ch.value << 8) | fine_ch.value
        return coarse_ch.value * 257

    @property
    def tilt_24bit(self) -> int:
        """Return tilt coordinate as 24-bit integer [0..16777215]."""
        coarse_ch, fine_ch, ultra_fine_ch = self._get_resolution_channels(
            ChannelType.TILT
        )
        if not coarse_ch:
            return 0
        if ultra_fine_ch and fine_ch:
            return (coarse_ch.value << 16) | (fine_ch.value << 8) | ultra_fine_ch.value
        if fine_ch:
            raw_16 = (coarse_ch.value << 8) | fine_ch.value
            return round(raw_16 / 65535.0 * 16777215.0)
        return round(coarse_ch.value / 255.0 * 16777215.0)

    @property
    def position_24bit(self) -> tuple[int, int]:
        """Return (pan_24bit, tilt_24bit) tuple [0..16777215]."""
        return (self.pan_24bit, self.tilt_24bit)

    @property
    def pan_degrees(self) -> float:
        """Return pan coordinate in physical degrees."""
        val = self._get_physical_parameter(ChannelType.PAN)
        return val if val is not None else 0.0

    @property
    def tilt_degrees(self) -> float:
        """Return tilt coordinate in physical degrees."""
        val = self._get_physical_parameter(ChannelType.TILT)
        return val if val is not None else 0.0

    @property
    def position_degrees(self) -> tuple[float, float]:
        """Return (pan_degrees, tilt_degrees) tuple."""
        return (self.pan_degrees, self.tilt_degrees)

    @property
    def pan_tilt(self) -> tuple[int, int]:
        """Return (pan, tilt) tuple [0..255]."""
        pan_ch = self.get_channel(ChannelType.PAN)
        tilt_ch = self.get_channel(ChannelType.TILT)
        return (pan_ch.value if pan_ch else 0, tilt_ch.value if tilt_ch else 0)

    # Optical controls (Zoom, Focus)
    def set_zoom_degrees(self, angle: float) -> None:
        """Set beam zoom angle in degrees."""
        self._set_physical_parameter(ChannelType.ZOOM, angle)

    @property
    def zoom_degrees(self) -> Optional[float]:
        """Return beam zoom angle in degrees, or None if no ZOOM channel."""
        return self._get_physical_parameter(ChannelType.ZOOM)

    def set_focus_meters(self, distance: float) -> None:
        """Set focus distance in meters."""
        self._set_physical_parameter(ChannelType.FOCUS, distance)

    @property
    def focus_meters(self) -> Optional[float]:
        """Return focus distance in meters, or None if no FOCUS channel."""
        return self._get_physical_parameter(ChannelType.FOCUS)

    # Strobe frequency control
    def set_strobe_hz(self, freq: float) -> None:
        """Set strobe flash frequency in Hertz."""
        self._set_physical_parameter(ChannelType.STROBE, freq)

    @property
    def strobe_hz(self) -> Optional[float]:
        """Return strobe frequency in Hertz, or None if no STROBE channel."""
        return self._get_physical_parameter(ChannelType.STROBE)

    # Color temperature control (CCT)
    def set_color_temp_kelvin(self, kelvin: float) -> None:
        """Set correlated color temperature in Kelvin."""
        self._set_physical_parameter(ChannelType.COLOR_TEMP, kelvin)

    @property
    def color_temp_kelvin(self) -> Optional[float]:
        """Return color temperature in Kelvin, or None if no COLOR_TEMP channel."""
        return self._get_physical_parameter(ChannelType.COLOR_TEMP)

    # Iris aperture control
    def set_iris(self, value: float) -> None:
        """Set iris aperture value in physical units."""
        self._set_physical_parameter(ChannelType.IRIS, value)

    @property
    def iris(self) -> Optional[float]:
        """Return iris aperture in physical units, or None if no IRIS channel."""
        return self._get_physical_parameter(ChannelType.IRIS)

    # Frost filter control
    def set_frost(self, norm: float) -> None:
        """Set frost filter level normalized [0.0..1.0]."""
        self.set_parameter_normalized(ChannelType.FROST, norm)

    @property
    def frost(self) -> Optional[float]:
        """Return frost filter level normalized [0.0..1.0], or None if no FROST."""
        return self.get_parameter_normalized(ChannelType.FROST)

    @property
    def gobo(self) -> Optional[str | int]:
        """Return active gobo range label or DMX value if modified, else None."""
        gobo_ch = self.get_channel(ChannelType.GOBO_WHEEL)
        if gobo_ch is None or gobo_ch.value == gobo_ch.default_value:
            return None
        if gobo_ch.active_range is not None:
            return gobo_ch.active_range.label
        return gobo_ch.value

    def blackout(self) -> None:
        """Set intensity to zero (blackout)."""
        self.set_intensity(0.0)

    def reset(self) -> None:
        """Reset device to initial state."""
        self.reset_all()

    def reset_all(self) -> None:
        """Reset all channels to default values."""
        for ch in self.channels:
            ch.reset()
        self._param_normalized.clear()
        self._param_last_raw.clear()
        self._intensity = 0.0 if self.has_physical_dimmer else 1.0
        self._target_color = sRGB(0.0, 0.0, 0.0)
        self._target_cie = CIExyY(0.3127, 0.3290, 0.0)
        for k in self._base_emitters:
            self._base_emitters[k] = 0.0

    def home(
        self,
        categories: Optional[set[str] | str | set[ChannelType]] = None,
    ) -> None:
        """Reset parameters to defaults, leaving intensity untouched unless specified.

        Args:
            categories: Category name(s) ("position", "color", "beam", "intensity")
                        or specific ChannelType(s) to home.
                        If None, resets all non-intensity parameters.
        """
        target_types: set[ChannelType] = set()
        if categories is not None:
            cats = (
                {categories}
                if isinstance(categories, (str, ChannelType))
                else set(categories)
            )
            for c in cats:
                if isinstance(c, ChannelType):
                    target_types.add(c)
                elif isinstance(c, str):
                    c_lower = c.lower()
                    if c_lower in CATEGORY_CHANNEL_TYPES:
                        target_types.update(CATEGORY_CHANNEL_TYPES[c_lower])
        else:
            # All non-intensity channels
            target_types = {
                ch.channel_type
                for ch in self.channels
                if ch.channel_type != ChannelType.INTENSITY
            }

        for ch in self.channels:
            if ch.channel_type in target_types:
                ch.reset()

        # Invalidate/update internal state caches
        if any(t in POSITION_CHANNEL_TYPES for t in target_types):
            self._param_normalized.pop(ChannelType.PAN, None)
            self._param_normalized.pop(ChannelType.TILT, None)
            self._param_last_raw.pop(ChannelType.PAN, None)
            self._param_last_raw.pop(ChannelType.TILT, None)

        if any(t in COLOR_CHANNEL_TYPES for t in target_types):
            if self.is_subtractive_cmy:
                for ch in self.channels:
                    if ch.channel_type in COLOR_CHANNEL_TYPES:
                        self._base_emitters[ch.channel_type] = ch.default_value / 255.0
                self._update_target_from_emitters()
            else:
                any_color_def_255 = any(
                    ch.channel_type in COLOR_CHANNEL_TYPES and ch.default_value > 0
                    for ch in self.channels
                )
                col_level = 1.0 if any_color_def_255 else 0.0
                self._target_color = sRGB(col_level, col_level, col_level)
                self._target_cie = CIExyY(0.3127, 0.3290, col_level)
                for k in self._base_emitters:
                    self._base_emitters[k] = col_level

        for t in target_types:
            self._param_normalized.pop(t, None)
            self._param_last_raw.pop(t, None)

    def locate(self) -> None:
        """Reset fixture to home values and bring intensity to full / open."""
        self.home()
        if self.has_physical_dimmer:
            self.set_intensity(1.0)
            shutter_ch = self.get_channel(ChannelType.STROBE)
            if shutter_ch is not None:
                shutter_ch.reset()
        else:
            self.set_color_srgb(1.0, 1.0, 1.0)
            self.set_intensity(1.0)

    def _apply_color_param(self, value: Any) -> None:  # noqa: ANN401
        """Apply color parameter from hex string or RGB tuple."""
        if isinstance(value, str):
            self.set_color_hex(value)
        elif isinstance(value, (tuple, list)) and len(value) >= 3:
            c0, c1, c2 = value[0], value[1], value[2]
            if (
                all(isinstance(c, (float, int)) for c in (c0, c1, c2))
                and all(0.0 <= c <= 1.0 for c in (c0, c1, c2))
                and any(isinstance(c, float) for c in (c0, c1, c2))
            ):
                self.set_color_srgb(float(c0), float(c1), float(c2))
            else:
                self.set_color_rgb(int(c0), int(c1), int(c2))

    def _apply_gobo_param(self, value: Any) -> None:  # noqa: ANN401
        """Apply gobo parameter from normalized float, slot index, DMX, or label."""
        gobo_ch = self.get_channel(ChannelType.GOBO_WHEEL)
        if gobo_ch is None:
            return
        if isinstance(value, float) and 0.0 <= value <= 1.0:
            self.set_parameter_normalized(ChannelType.GOBO_WHEEL, value)
        elif isinstance(value, (int, float)):
            int_val = int(round(value))
            if (
                gobo_ch.ranges
                and 1 <= int_val <= len(gobo_ch.ranges)
                and (len(gobo_ch.ranges) == 1 or int_val < gobo_ch.ranges[1].value_min)
            ):
                gobo_ch.activate_range(gobo_ch.ranges[int_val - 1].label)
            else:
                gobo_ch.set_value(int_val)
        elif isinstance(value, str):
            for r in gobo_ch.ranges:
                if r.label.lower() == value.lower():
                    gobo_ch.activate_range(r.label)
                    break

    def apply_device_parameter(  # pylint: disable=too-many-branches
        self,
        param_name: str,
        value: Any,  # noqa: ANN401
    ) -> None:
        """Apply a named parameter value (physical units or normalized).

        Args:
            param_name: Parameter name (intensity, pan, tilt, color, zoom, focus, etc.)
            value: Target value.
        """
        p_lower = param_name.lower()
        if p_lower == "intensity":
            self.set_intensity(value)
        elif p_lower == "pan":
            self.set_pan_degrees(float(value))
        elif p_lower == "tilt":
            self.set_tilt_degrees(float(value))
        elif p_lower in ("color", "colour"):
            self._apply_color_param(value)
        elif p_lower == "zoom":
            self.set_zoom_degrees(float(value))
        elif p_lower == "focus":
            self.set_focus_meters(float(value))
        elif p_lower == "strobe":
            self.set_strobe_hz(float(value))
        elif p_lower in ("color_temp", "colortemp", "cct"):
            self.set_color_temp_kelvin(float(value))
        elif p_lower == "iris":
            self.set_iris(float(value))
        elif p_lower in ("gobo", "gobo_wheel"):
            self._apply_gobo_param(value)
        else:
            ctype: Optional[ChannelType] = None
            try:
                ctype = ChannelType(p_lower)
            except ValueError:
                ctype = None
            if ctype is not None and self.get_channel(ctype) is not None:
                self.set_parameter_normalized(ctype, max(0.0, min(1.0, float(value))))
            elif isinstance(value, (int, float)):
                self.set_channel_normalized_by_label(p_lower, float(value))

    def apply_device_values(self, values: dict[str, Any]) -> None:
        """Apply a batch of parameter values to this device."""
        lower_keys = {str(k).lower() for k in values}
        has_explicit_rgb = {"red", "green", "blue"}.issubset(lower_keys)
        has_explicit_cmy = {"cyan", "magenta", "yellow"}.issubset(lower_keys)
        color_items: list[tuple[str, Any]] = []
        other_items: list[tuple[str, Any]] = []
        for name, val in values.items():
            if str(name).lower() in ("color", "colour"):
                if not (has_explicit_rgb or has_explicit_cmy):
                    color_items.append((name, val))
            else:
                other_items.append((name, val))
        for name, val in color_items:
            self.apply_device_parameter(name, val)
        for name, val in other_items:
            self.apply_device_parameter(name, val)

    def activate_range(self, channel_label: str, range_label: str) -> None:
        """Activate range on channel specified by label."""
        self._channel_by_label(channel_label).activate_range(range_label)

    def set_range_percent(
        self, channel_label: str, range_label: str, percent: float
    ) -> None:
        """Set relative range percentage on channel specified by label."""
        self._channel_by_label(channel_label).set_range_percent(range_label, percent)

    def _channel_by_label(self, label: str) -> Channel:
        for ch in self.channels:
            if ch.label == label:
                return ch
        raise KeyError(f"Channel '{label}' not found on device '{self.label}'")

    def dmx_values(self) -> dict[tuple[int, int], int]:
        """Return snapshot dictionary {(universe, address): value}."""
        return {(ch.universe, ch.address): ch.value for ch in self.channels}

    def dmx_values_for_universe(self, universe: int) -> dict[int, int]:
        """Return snapshot dictionary {address: value} for a given universe."""
        return {ch.address: ch.value for ch in self.channels if ch.universe == universe}

    def osc_address(self, sub_path: str = "") -> str:
        """Build OSC address path for this fixture."""
        base = f"/fixture/{self.fixture_id}"
        return f"{base}/{sub_path.lstrip('/')}" if sub_path else base

    def to_osc_bundle(self) -> list[tuple[str, int]]:
        """Generate OSC address/value pairs for all channels and intensity."""
        bundle: list[tuple[str, int]] = [
            (self.osc_address("intensity"), round(self.intensity_percent))
        ]
        bundle.extend((self.osc_address(ch.label), ch.value) for ch in self.channels)
        return bundle

    def describe_channels(self) -> str:
        """Return textual description of all channels and ranges."""
        lines = [f"Fixture '{self.label}' — {self.patch_summary()}"]
        for ch in self.channels:
            line = f"  {ch.label:20s} {str(ch.dmx_address):10s}  val={ch.value:3d}"
            if ch.is_multi_function:
                ar = ch.active_range
                mode = ar.label if ar else "out of range"
                line += f"  [{mode}]"
                for r in ch.ranges:
                    marker = " ◀" if r is ar else ""
                    line += (
                        f"\n    {'':20s} {r.value_min:3d}-{r.value_max:3d}  "
                        f"{r.label}{marker}"
                    )
            lines.append(line)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize device to a dictionary."""
        result: dict[str, Any] = {
            "fixture_id": self.fixture_id,
            "label": self.label,
            "fixture_type": self.fixture_type.value,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "mode_name": self.mode_name,
            "gdtf_id": self.gdtf_id,
            "group": self.group,
            "notes": self.notes,
            "enabled": self._enabled,
            "locked": self._locked,
            "curve_id": self.curve_id,
            "position": list(self.position),
            "focus_point": list(self.focus_point),
            "orientation": list(self.orientation),
            "beam_angle": self.beam_angle,
            "static_gobo": self.static_gobo,
            "gel": self.gel,
            "gel_color": self.gel_color,
            "intensity": self._intensity,
            "target_color": self._target_color.to_hex(),
            "base_emitters": {
                ch_type.value: val for ch_type, val in self._base_emitters.items()
            },
            "channels": [
                {
                    "channel_type": ch.channel_type.value,
                    "universe": ch.universe,
                    "address": ch.address,
                    "value": ch.value,
                    "default_value": ch.default_value,
                    "fine": ch.fine,
                    "ultra_fine": ch.ultra_fine,
                    "label": ch.label,
                    "merge_mode": ch.merge_mode.value if ch.merge_mode else "htp",
                    "physical_min": ch.physical_min,
                    "physical_max": ch.physical_max,
                    "physical_unit": ch.physical_unit,
                    "ranges": [r.to_dict() for r in ch.ranges],
                }
                for ch in self.channels
            ],
        }
        if self.color_profile is not None:
            result["color_profile"] = self.color_profile.to_dict()
        if self.swap_pan_tilt:
            result["swap_pan_tilt"] = True
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LightingDevice:
        """Instantiate device from a dictionary."""
        channels = []
        for cd in data.get("channels", []):
            ranges = [ChannelRange.from_dict(r) for r in cd.get("ranges", [])]
            ctype = ChannelType(cd["channel_type"])
            mm = (
                MergeMode(cd["merge_mode"])
                if "merge_mode" in cd
                else get_default_merge_mode(ctype)
            )
            channels.append(
                Channel(
                    channel_type=ctype,
                    universe=int(cd["universe"]),
                    address=int(cd["address"]),
                    value=int(cd.get("value", 0)),
                    default_value=int(cd.get("default_value", 0)),
                    fine=bool(cd.get("fine", False)),
                    ultra_fine=bool(cd.get("ultra_fine", False)),
                    label=str(cd.get("label", "")),
                    ranges=ranges,
                    physical_min=float(cd.get("physical_min", 0.0)),
                    physical_max=float(cd.get("physical_max", 1.0)),
                    physical_unit=str(cd.get("physical_unit", "")),
                    merge_mode=mm,
                )
            )
        color_prof_data = data.get("color_profile")
        color_profile = (
            FixtureColorProfile.from_dict(color_prof_data)
            if isinstance(color_prof_data, dict)
            else None
        )
        device = cls(
            fixture_id=int(data["fixture_id"]),
            label=str(data["label"]),
            fixture_type=FixtureType(data["fixture_type"]),
            channels=channels,
            group=str(data.get("group", "")),
            notes=str(data.get("notes", "")),
            color_profile=color_profile,
            manufacturer=str(data.get("manufacturer", "")),
            model=str(data.get("model", "")),
            mode_name=str(data.get("mode_name", "")),
            gdtf_id=str(data.get("gdtf_id", "")),
            position=_parse_vec3(data.get("position"), (0.0, 0.0, 4.0)),
            focus_point=_parse_vec3(data.get("focus_point"), (0.0, 0.0, 0.0)),
            orientation=_parse_vec3(data.get("orientation"), (0.0, 0.0, 0.0)),
            beam_angle=float(data.get("beam_angle", 25.0)),
            static_gobo=str(data.get("static_gobo", "")),
            gel=str(data.get("gel", "")),
            gel_color=str(data.get("gel_color", "")),
            swap_pan_tilt=bool(data.get("swap_pan_tilt", False)),
        )
        device._enabled = bool(data.get("enabled", True))
        device._locked = bool(data.get("locked", False))
        device.curve_id = int(data.get("curve_id", 0))
        if "intensity" in data:
            device.set_intensity(data["intensity"])
        if "target_color" in data:
            device.set_color_hex(str(data["target_color"]))
        if "base_emitters" in data:
            device._base_emitters = {
                ChannelType(k): float(v) for k, v in data["base_emitters"].items()
            }
            if device.uses_virtual_dimmer:
                device._apply_virtual_dimmer()
        return device

    @property
    def enabled(self) -> bool:
        """True if device output is enabled."""
        return self._enabled

    @property
    def has_pan_tilt(self) -> bool:
        """True if device has a Pan or Tilt channel."""
        return (
            self.get_channel(ChannelType.PAN) is not None
            or self.get_channel(ChannelType.TILT) is not None
        )

    @property
    def is_pan_inverted(self) -> bool:
        """True if Pan physical_min > physical_max."""
        pan = self.get_channel(ChannelType.PAN)
        return pan is not None and pan.physical_min > pan.physical_max

    @property
    def is_tilt_inverted(self) -> bool:
        """True if Tilt physical_min > physical_max."""
        tilt = self.get_channel(ChannelType.TILT)
        return tilt is not None and tilt.physical_min > tilt.physical_max

    def set_pan_tilt_options(
        self,
        *,
        invert_pan: bool | None = None,
        invert_tilt: bool | None = None,
        swap_pan_tilt: bool | None = None,
    ) -> None:
        """Apply Pan/Tilt invert and swap patch options on device channels."""
        if invert_pan is not None and bool(invert_pan) != self.is_pan_inverted:
            for ch in self.channels:
                if ch.channel_type is ChannelType.PAN:
                    ch.physical_min, ch.physical_max = ch.physical_max, ch.physical_min
        if invert_tilt is not None and bool(invert_tilt) != self.is_tilt_inverted:
            for ch in self.channels:
                if ch.channel_type is ChannelType.TILT:
                    ch.physical_min, ch.physical_max = ch.physical_max, ch.physical_min
        if swap_pan_tilt is not None and bool(swap_pan_tilt) != self.swap_pan_tilt:
            pan_chs = {
                (ch.fine, ch.ultra_fine): ch
                for ch in self.channels
                if ch.channel_type is ChannelType.PAN
            }
            tilt_chs = {
                (ch.fine, ch.ultra_fine): ch
                for ch in self.channels
                if ch.channel_type is ChannelType.TILT
            }
            for res_key, p_ch in pan_chs.items():
                if (t_ch := tilt_chs.get(res_key)) is not None:
                    p_ch.universe, t_ch.universe = t_ch.universe, p_ch.universe
                    p_ch.address, t_ch.address = t_ch.address, p_ch.address
            self.swap_pan_tilt = bool(swap_pan_tilt)
        if self.get_channel(ChannelType.PAN) is not None:
            self.set_pan_degrees(self.pan_degrees)
        if self.get_channel(ChannelType.TILT) is not None:
            self.set_tilt_degrees(self.tilt_degrees)

    def enable(self) -> None:
        """Enable device output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable device output."""
        self._enabled = False

    @property
    def locked(self) -> bool:
        """True if device parameters are locked against modifications."""
        return self._locked

    def lock(self) -> None:
        """Lock device parameters."""
        self._locked = True

    def unlock(self) -> None:
        """Unlock device parameters."""
        self._locked = False

    def __repr__(self) -> str:
        return (
            f"<LightingDevice id={self.fixture_id} '{self.label}' "
            f"type={self.fixture_type.value} "
            f"patch=[{self.patch_summary()}] ch={self.channel_count()}>"
        )


__all__ = [
    "BEAM_CHANNEL_TYPES",
    "CATEGORY_CHANNEL_TYPES",
    "COLOR_CHANNEL_TYPES",
    "Channel",
    "ChannelRange",
    "ChannelType",
    "DmxAddress",
    "FixtureType",
    "LightingDevice",
    "MergeMode",
    "POSITION_CHANNEL_TYPES",
    "get_default_merge_mode",
]

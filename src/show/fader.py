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
from __future__ import annotations

import math
import typing
from collections.abc import Mapping
from enum import IntEnum

import numpy as np

from olc.define import MAX_CHANNELS
from olc.show.effect import EffectDefinition

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.cue import Cue
    from olc.show.fader_bank import FaderBank
    from olc.show.main_fader import MainFader
    from olc.show.palette import Palette
    from olc.show.sequence import Sequence


LEGACY_FADER_TYPE_GROUP = 13


class FaderType(IntEnum):
    """Fader types"""

    NONE = 0
    PRESET = 1
    CHANNELS = 2
    SEQUENCE = 3
    EFFECT = 4
    FX_MASTER = 5
    MAIN = 99


FADER_OPTION_FLAGS: tuple[str, ...] = (
    "exempt_grand_master",
    "exclude_record",
    "inhibitive",
    "solo_mode",
    "swop_protect",
    "locked",
    "intensity_master",
)


class Fader:
    """Abstraction for physical fader"""

    index: int
    text: str
    level: float
    old_level: float
    contents: typing.Any
    exempt_grand_master: bool
    exclude_record: bool
    inhibitive: bool
    solo_mode: bool
    swop_protect: bool
    locked: bool

    def __init__(self, index: int, fader_bank: FaderBank) -> None:
        self.index = index
        self.fader_bank = fader_bank
        self.text = ""
        # Fader level (0.0 - 1.0)
        self.level = 0.0
        self.old_level = 0.0
        self.contents = None
        self.exempt_grand_master = False
        self.exclude_record = False
        self.inhibitive = False
        self.solo_mode = False
        self.swop_protect = False
        self.locked = False

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.fader_bank.app

    def set_level(self, level: float) -> None:
        """Set fader level

        Args:
            level: New level
        """
        # Set level
        self.level = level
        self.level_changed()

    def flash_on(self) -> None:
        """Flash fader at full"""
        self.old_level = self.level
        self.set_level(1.0)

    def flash_off(self) -> None:
        """Stop flash"""
        self.set_level(self.old_level)

    def level_changed(self) -> None:
        """Fader level has changed"""


class FaderMain(Fader):
    """Fader with MainFader"""

    contents: MainFader | None

    def __init__(self, index: int, fader_bank: FaderBank) -> None:
        super().__init__(index, fader_bank)
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            self.contents = self.app.backend.dmx.main_fader
        else:
            self.contents = None
        self.text = "Main Fader"
        self.level = self.contents.get_level() if self.contents else 0.0

    def level_changed(self) -> None:
        """Fader level has changed"""
        if self.contents:
            self.contents.set_level(self.level)
        if self.app:
            self.app.main_fader_level = self.level
            self.app.emit("main_fader.level_changed", self.level)
            if self.app.backend:
                self.app.backend.dmx.set_levels()


class FaderPreset(Fader):
    """Fader with preset (Palette Preset or Cue)."""

    contents: Palette | Cue | None
    dmx: np.ndarray
    channels: set
    intensity_master: bool
    _ltp_base_states: dict[int, dict[str, typing.Any]]
    _ltp_active: bool

    def __init__(
        self,
        index: int,
        fader_bank: FaderBank,
        preset: Palette | Cue | None = None,
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = preset
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.float64)
        # Channels used by fader
        self.channels = set()
        self.intensity_master = False
        self._ltp_base_states = {}
        self._ltp_active = False
        if preset:
            self.text = preset.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        if self.contents is None:
            return
        for channel in self.contents.channels:
            self.channels.add(channel)
        self.fader_bank.update_active_faders()

    def _get_non_intensity_device_values(self) -> dict[int, dict[str, typing.Any]]:
        """Return target non-intensity device_values when LTP driving applies."""
        if self.contents is None:
            return {}
        if self.intensity_master and bool(getattr(self.contents, "channels", None)):
            return {}
        raw = getattr(self.contents, "device_values", None)
        if not isinstance(raw, dict) or not raw:
            return {}
        targets: dict[int, dict[str, typing.Any]] = {}
        for dev_id, params in raw.items():
            if not isinstance(params, dict):
                continue
            ltp_params = {
                k: v for k, v in params.items() if str(k).lower() != "intensity"
            }
            if ltp_params:
                targets[int(dev_id)] = ltp_params
        return targets

    def _restore_ltp_base_states(self) -> tuple[set[int], set[int]]:
        """Restore device attributes captured before this fader was raised."""
        if not self._ltp_active:
            return set(), set()
        lightshow = self.fader_bank.lightshow
        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        changed_devs: set[int] = set()
        color_changed: set[int] = set()
        if patch is not None and self._ltp_base_states:
            # pylint: disable=import-outside-toplevel
            from olc.devices.channel import ChannelType
            from olc.show.sequence_threads import (
                _COLOR_PARAM_NAMES,
                _has_device_changed,
                _snapshot_dev_diff_state,
            )

            scalar_map = {
                "pan": "pan",
                "tilt": "tilt",
                "zoom": "zoom",
                "focus": "focus",
                "strobe": "strobe",
                "cct": "cct",
                "color_temp": "cct",
                "colortemp": "cct",
                "iris": "iris",
            }
            for dev_id, base in self._ltp_base_states.items():
                dev = patch.get_device(dev_id)
                if dev is None:
                    continue
                before = _snapshot_dev_diff_state(dev)
                touched_color = False
                norm_params = base.get("norm_params", {})
                touched_raw = list(base.get("_touched_params", ()))
                touched_set = set(touched_raw)
                has_explicit_rgb = {"red", "green", "blue"}.issubset(touched_set)
                has_explicit_cmy = {"cyan", "magenta", "yellow"}.issubset(touched_set)
                ordered_touched = [
                    p for p in touched_raw if p in ("color", "colour")
                ] + [p for p in touched_raw if p not in ("color", "colour")]
                for p_lower in ordered_touched:
                    if p_lower in ("color", "colour") and (
                        has_explicit_rgb or has_explicit_cmy
                    ):
                        continue
                    if p_lower in _COLOR_PARAM_NAMES:
                        touched_color = True
                    if p_lower in scalar_map:
                        s_val = base.get(scalar_map[p_lower])
                        if s_val is not None:
                            dev.apply_device_parameter(p_lower, float(s_val))
                    elif p_lower in ("color", "colour"):
                        if getattr(dev, "is_subtractive_cmy", False) and all(
                            c in norm_params for c in ("cyan", "magenta", "yellow")
                        ):
                            for c_name, c_type in (
                                ("cyan", ChannelType.CYAN),
                                ("magenta", ChannelType.MAGENTA),
                                ("yellow", ChannelType.YELLOW),
                            ):
                                dev.set_parameter_normalized(
                                    c_type, float(norm_params[c_name])
                                )
                        elif "color_rgb" in base and hasattr(dev, "set_color_srgb"):
                            r0, g0, b0 = base["color_rgb"]
                            dev.set_color_srgb(float(r0), float(g0), float(b0))
                    elif p_lower in norm_params:
                        ctype: ChannelType | None = None
                        try:
                            ctype = ChannelType(p_lower)
                        except ValueError:
                            ctype = None
                        if ctype is not None and dev.get_channel(ctype) is not None:
                            dev.set_parameter_normalized(
                                ctype, float(norm_params[p_lower])
                            )
                        else:
                            dev.set_channel_normalized_by_label(
                                p_lower, float(norm_params[p_lower])
                            )

                any_moved, col_moved = _has_device_changed(
                    before, dev, touched_color_param=touched_color
                )
                if any_moved:
                    changed_devs.add(dev_id)
                    if col_moved:
                        color_changed.add(dev_id)

        self._ltp_base_states.clear()
        self._ltp_active = False
        return changed_devs, color_changed

    def _emit_ltp_updates(
        self, changed_devs: set[int], color_changed: set[int]
    ) -> None:
        """Emit UI parameter/color updates for modified devices."""
        if not self.app or not changed_devs:
            return
        if color_changed:
            self.app.emit("device.color_changed", sorted(color_changed), None)
        non_color = changed_devs - color_changed
        if non_color:
            self.app.emit("device.parameter_changed", sorted(non_color), "fader", None)

    def set_contents(self, preset: Palette | Cue | None) -> None:
        """Set Preset or Cue.

        Args:
            preset: Preset palette or Cue to put in fader.
        """
        if self._ltp_active:
            changed_devs, color_changed = self._restore_ltp_base_states()
            self._emit_ltp_updates(changed_devs, color_changed)
            if (
                changed_devs
                and self.app
                and hasattr(self.app, "backend")
                and self.app.backend
            ):
                self.app.backend.dmx.set_levels()
        self.contents = preset
        if preset is not None:
            self.text = preset.text
            self.update_channels()
        else:
            self.text = ""
            self.channels.clear()
            self.dmx.fill(0.0)
            self.fader_bank.update_active_faders()

    def level_changed(self) -> None:
        """Fader level has changed"""
        self.dmx.fill(0.0)
        changed_devs: set[int] = set()
        color_changed: set[int] = set()
        lightshow = self.fader_bank.lightshow
        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        target_ltp = self._get_non_intensity_device_values()

        if patch is not None:
            if self.level > 0.0 and target_ltp:
                # pylint: disable=import-outside-toplevel
                from olc.show.sequence_threads import (
                    _capture_device_states,
                    _interpolate_device_states,
                )

                if not self._ltp_active:
                    captured = _capture_device_states(patch)
                    self._ltp_base_states = {}
                    for dev_id, params in target_ltp.items():
                        if dev_id in captured:
                            entry = dict(captured[dev_id])
                            entry["_touched_params"] = {str(k).lower() for k in params}
                            self._ltp_base_states[dev_id] = entry
                    self._ltp_active = True

                factor = max(0.0, min(1.0, float(self.level)))
                changed_devs = _interpolate_device_states(
                    patch,
                    self._ltp_base_states,
                    target_ltp,
                    factor=factor,
                    color_changed_out=color_changed,
                )
            elif self._ltp_active:
                changed_devs, color_changed = self._restore_ltp_base_states()

        if self.contents:
            for channel, lvl in self.contents.channels.items():
                if 1 <= channel <= MAX_CHANNELS:
                    self.dmx[channel - 1] = float(lvl) * self.level
            self.fader_bank.update_levels()
            self._emit_ltp_updates(changed_devs, color_changed)
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()
        elif changed_devs:
            self._emit_ltp_updates(changed_devs, color_changed)
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()


class FaderChannels(Fader):
    """Fader with channels"""

    contents: dict[int, int] | None
    dmx: np.ndarray
    channels: set

    def __init__(
        self, index: int, fader_bank: FaderBank, channels: dict[int, int] | None = None
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = channels
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.float64)
        # Channels used by fader
        self.channels = set()
        if self.contents:
            self.text = "Ch"
            for channel in self.contents:
                self.text += f" {channel}"
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        self.channels.clear()
        if self.contents:
            for channel in self.contents:
                self.channels.add(channel)
        self.fader_bank.update_active_faders()

    def set_contents(self, channels: dict[int, int]) -> None:
        """Set cue

        Args:
            channels: Channels with level to put in fader
        """
        self.contents = channels
        if self.contents:
            self.text = "Ch"
            for channel in self.contents:
                self.text += f" {channel}"
        self.update_channels()

    def level_changed(self) -> None:
        """Fader level has changed"""
        if self.contents:
            for channel, lvl in self.contents.items():
                self.dmx[channel - 1] = float(lvl) * self.level
            self.fader_bank.update_levels()
            if self.app and hasattr(self.app, "backend") and self.app.backend:
                self.app.backend.dmx.set_levels()


class FaderSequence(Fader):
    """Fader with sequence"""

    contents: Sequence | None
    dmx: np.ndarray
    channels: set

    def __init__(
        self, index: int, fader_bank: FaderBank, sequence: Sequence | None = None
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = sequence
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.float64)
        self._prev_level: float = 0.0
        # Channels used by fader
        self.channels = set()
        if sequence:
            self.text = sequence.text
            self.update_channels()

    def update_channels(self) -> None:
        """Update channels used by fader"""
        if self.contents is None:
            return
        self.channels = self.contents.channels
        self.fader_bank.update_active_faders()

    def set_contents(self, sequence: Sequence | None) -> None:
        """Set sequence assigned to fader.

        Args:
            sequence: Sequence to assign to fader
        """
        self.contents = sequence
        if sequence is not None:
            self.text = sequence.text
            self.update_channels()
        else:
            self.text = ""
            self.channels.clear()
            self.fader_bank.update_active_faders()

    def level_changed(self) -> None:
        """Fader level has changed."""
        self.dmx.fill(0.0)
        if self.contents is None:
            self.fader_bank.update_levels()
            return
        sequence = self.contents
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            from olc.show.sequence_threads import apply_arbitrated_output

            state = arb.get_state(sequence.index)
            is_active = state is not None and state.active
            valid_steps = max(0, len(sequence.steps) - 2)
            if (
                self._prev_level <= 0.0 < self.level
                and getattr(sequence, "auto_start", False)
                and not is_active
                and valid_steps > 0
            ):
                pos = max(1, min(sequence.position or 1, len(sequence.steps) - 2))
                sequence.load_step(pos, fader_level=self.level)
            elif self._prev_level > 0.0 >= self.level and getattr(
                sequence, "auto_stop", False
            ):
                sequence.release()
            elif is_active:
                composed = arb.set_fader_level(sequence.index, self.level)
                apply_arbitrated_output(
                    self.app,
                    getattr(self.app, "backend", None),
                    sequence.patch,
                    composed,
                )
            elif self.level > 0.0 and valid_steps > 0:
                pos = max(1, min(sequence.position or 1, len(sequence.steps) - 2))
                sequence.load_step(pos, fader_level=self.level)
            self._prev_level = self.level
            self.fader_bank.update_levels()
            return

        if self.level > 0.0:
            pos = max(1, min(sequence.position or 1, len(sequence.steps) - 1))
            if 0 <= pos < len(sequence.steps):
                cue = sequence.steps[pos].cue
                if cue is not None:
                    for channel, lvl in cue.channels.items():
                        if 1 <= channel <= MAX_CHANNELS:
                            self.dmx[channel - 1] = float(lvl) * self.level
        self._prev_level = self.level
        self.fader_bank.update_levels()
        if self.app and hasattr(self.app, "backend") and self.app.backend:
            self.app.backend.dmx.set_levels()

    def go(self) -> None:
        """Advance the linked sequence by one step, keeping fader level in sync."""
        if self.contents is None:
            return
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            arb.set_fader_level(self.contents.index, self.level)
        self.contents.do_go(None)

    def go_back(self) -> bool:
        """Step the linked sequence backward by one step."""
        if self.contents is None:
            return False
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            arb.set_fader_level(self.contents.index, self.level)
        return self.contents.go_back(None, None)

    def pause(self) -> None:
        """Pause any active transition on the linked sequence."""
        if self.contents is not None:
            self.contents.pause(None, None)

    def release(self) -> None:
        """Release the linked sequence and restore lower layers."""
        if self.contents is not None:
            self.contents.release()


VALID_EFFECT_CONTROL_MODES: tuple[str, ...] = ("size", "rate", "both")


def fader_level_to_rate_scale(level: float) -> float:
    """Map fader level [0.0..1.0] to musical rate multiplier.

    0.0 -> 0.0 (Freeze), 0.25 -> 0.5x, 0.5 -> 1.0x, 0.75 -> 2.0x, 1.0 -> 4.0x.
    """
    lvl = max(0.0, min(1.0, float(level)))
    if lvl <= 0.0:
        return 0.0
    return float(2.0 ** (4.0 * (lvl - 0.5)))


def fader_level_to_centered_scale(
    level: float, min_scale: float = 0.0, max_scale: float = 4.0
) -> float:
    """Map fader level [0.0..1.0] with 0.5 as nominal 1.0x scale."""
    lvl = max(0.0, min(1.0, float(level)))
    lo = max(0.0, float(min_scale))
    hi = max(1.0, float(max_scale))
    if lvl <= 0.5:
        return lo + (1.0 - lo) * (lvl / 0.5)
    return 1.0 + (hi - 1.0) * ((lvl - 0.5) / 0.5)


class FaderEffect(Fader):
    """Fader controlling a procedural EffectDefinition (Size, Rate, or Both)."""

    contents: EffectDefinition | None
    dmx: np.ndarray
    channels: set[int]
    effect_channels: list[int]
    base_channels: dict[int, float]
    control_mode: str
    modifier_only: bool
    min_scale: float
    max_scale: float
    base_size_scale: float
    base_rate_scale: float

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        index: int,
        fader_bank: FaderBank,
        effect: EffectDefinition | None = None,
        effect_channels: list[int] | None = None,
        control_mode: str = "size",
        base_channels: Mapping[int, float] | None = None,
        *,
        modifier_only: bool = False,
        min_scale: float = 0.0,
        max_scale: float = 4.0,
        base_size_scale: float = 1.0,
        base_rate_scale: float = 1.0,
    ) -> None:
        super().__init__(index, fader_bank)
        self.contents = effect
        self.dmx = np.zeros(MAX_CHANNELS, dtype=np.float64)
        self.channels = set()
        self.effect_channels = list(effect_channels or [])
        self.base_channels = (
            {
                int(ch): max(0.0, min(1.0, float(lvl)))
                for ch, lvl in base_channels.items()
                if 1 <= int(ch) <= MAX_CHANNELS and float(lvl) > 0.0
            }
            if base_channels
            else {}
        )
        self.control_mode = (
            control_mode if control_mode in VALID_EFFECT_CONTROL_MODES else "size"
        )
        self.modifier_only = bool(modifier_only)
        self.min_scale = max(0.0, float(min_scale))
        self.max_scale = max(1.0, float(max_scale))
        self.base_size_scale = max(0.0, float(base_size_scale))
        self.base_rate_scale = max(0.0, float(base_rate_scale))
        if self.modifier_only:
            self.level = 0.5
        if effect is not None:
            self.text = effect.label or f"Effect {effect.number:g}"
        if effect is not None or self.base_channels:
            self.update_channels()

    def format_target_channels(self) -> str:
        """Return a concise human-readable summary of bound target channels."""
        chs = self.effect_channels
        if not chs:
            return "Auto (Sel)"
        if len(chs) == 1:
            return f"Ch {chs[0]}"
        if all(b == a + 1 for a, b in zip(chs, chs[1:], strict=False)) or all(
            b == a - 1 for a, b in zip(chs, chs[1:], strict=False)
        ):
            return f"Ch {chs[0]}..{chs[-1]}"
        if len(chs) <= 3:
            return "Ch " + ",".join(str(c) for c in chs)
        return f"Ch {chs[0]},{chs[1]}… ({len(chs)})"

    def set_control_mode(self, mode: str) -> None:
        """Set fader control mode ('size', 'rate', or 'both') and refresh if live."""
        if mode not in VALID_EFFECT_CONTROL_MODES:
            return
        self.control_mode = mode
        if self.level > 0.0:
            self.level_changed()

    def set_base_scales(
        self,
        *,
        size_scale: float | None = None,
        rate_scale: float | None = None,
    ) -> None:
        """Set nominal base size/rate multipliers and refresh if live."""
        if size_scale is not None:
            self.base_size_scale = max(0.0, float(size_scale))
        if rate_scale is not None:
            self.base_rate_scale = max(0.0, float(rate_scale))
        if self.level > 0.0:
            self.level_changed()

    def set_effect_channels(self, channels: list[int]) -> None:
        """Update ordered target channels for this effect fader."""
        ordered = list(dict.fromkeys(int(c) for c in channels))
        if (
            self.level > 0.0
            and self.contents is not None
            and self.app is not None
            and hasattr(self.app, "effects_engine")
        ):
            self.app.effects_engine.stop_effect(effect_number=self.contents.number)
        self.effect_channels = ordered
        self.update_channels()
        if self.level > 0.0 and self.contents is not None:
            self.level_changed()

    def set_base_channels(self, channels: Mapping[int, float]) -> None:
        """Set static base intensity levels scaled proportionally with fader level."""
        self.base_channels = {
            int(ch): max(0.0, min(1.0, float(lvl)))
            for ch, lvl in channels.items()
            if 1 <= int(ch) <= MAX_CHANNELS and float(lvl) > 0.0
        }
        self.update_channels()
        if self.level > 0.0 or self.dmx.any():
            self.level_changed()

    def get_target_channels(self) -> list[int]:
        """Resolve target channels for this effect fader."""
        if self.effect_channels:
            return list(self.effect_channels)
        if self.app is not None:
            selected = list(getattr(self.app, "selected_channels", []))
            if selected:
                return selected
        lightshow = self.fader_bank.lightshow
        if lightshow is not None and hasattr(lightshow, "patch"):
            patch = lightshow.patch
            patched = set(patch.devices.keys())
            if patched:
                return sorted(patched)
        return [1]

    def update_channels(self) -> None:
        """Update channels tracked by this fader."""
        self.channels.clear()
        if self.contents is not None:
            for ch in self.get_target_channels():
                self.channels.add(int(ch))
        for ch in self.base_channels:
            self.channels.add(int(ch))
        self.fader_bank.update_active_faders()

    def set_contents(
        self,
        effect: EffectDefinition | None,
        effect_channels: list[int] | None = None,
    ) -> None:
        """Assign an EffectDefinition to this fader."""
        if (
            self.contents is not None
            and self.app is not None
            and hasattr(self.app, "effects_engine")
        ):
            self.app.effects_engine.stop_effect(effect_number=self.contents.number)
        self.contents = effect
        if effect_channels is not None:
            self.effect_channels = list(effect_channels)
        elif not self.effect_channels and self.app is not None:
            selected = list(getattr(self.app, "selected_channels", []))
            if selected:
                self.effect_channels = selected
        if effect is not None:
            self.text = effect.label or f"Effect {effect.number:g}"
            self.update_channels()
        else:
            self.text = ""
            self.channels.clear()
            self.dmx.fill(0.0)
            self.fader_bank.update_active_faders()

    def _linked_faders(self) -> list[FaderEffect]:
        """Return FaderEffect instances sharing this effect number and channel list."""
        if self.contents is None:
            return []
        eff_num = round(float(self.contents.number), 3)
        target_chs = self.get_target_channels()
        linked: list[FaderEffect] = []
        for page_faders in self.fader_bank.faders.values():
            for fader in page_faders.values():
                if (
                    isinstance(fader, FaderEffect)
                    and fader.contents is not None
                    and round(float(fader.contents.number), 3) == eff_num
                    and fader.get_target_channels() == target_chs
                ):
                    linked.append(fader)
        return linked

    def _resolve_linked_scales(self) -> tuple[float, float]:
        """Compose (rate_scale, size_scale) from primary and linked modifier faders."""
        linked = self._linked_faders()
        master = next(
            (f for f in linked if not f.modifier_only),
            None if self.modifier_only else self,
        )
        if master is not None:
            size_scale = (
                1.0 if master.control_mode == "rate" else float(master.level)
            ) * master.base_size_scale
            rate_scale = (
                fader_level_to_rate_scale(master.level)
                if master.control_mode in ("rate", "both")
                else 1.0
            ) * master.base_rate_scale
        else:
            size_scale = 1.0
            rate_scale = 1.0

        for mod in linked:
            if not mod.modifier_only:
                continue
            factor = fader_level_to_centered_scale(
                mod.level, mod.min_scale, mod.max_scale
            )
            if mod.control_mode == "rate":
                rate_scale *= factor
            elif mod.control_mode == "size":
                size_scale *= factor
            else:
                rate_scale *= factor
                size_scale *= factor
        return rate_scale, size_scale

    def flash_on(self) -> None:
        """Reset modifier faders to nominal 50% (1.0x), or flash primary fader."""
        if self.modifier_only:
            self.set_level(0.5)
            return
        super().flash_on()

    def flash_off(self) -> None:
        """Release primary flash; no-op for modifier faders."""
        if self.modifier_only:
            return
        super().flash_off()

    def level_changed(self) -> None:
        """Start, modulate, or stop the assigned effect when the fader moves."""
        if not self.modifier_only and (self.base_channels or self.dmx.any()):
            self.dmx.fill(0.0)
            if self.level > 0.0:
                for ch, base_lvl in self.base_channels.items():
                    self.dmx[int(ch) - 1] = float(base_lvl) * float(self.level)
            self.fader_bank.update_levels()
        if self.contents is None or self.app is None:
            return
        engine = getattr(self.app, "effects_engine", None)
        if engine is None:
            return

        target_channels = self.get_target_channels()
        if not self.effect_channels and target_channels:
            self.effect_channels = list(target_channels)
        self.channels = set(target_channels)

        if self.modifier_only:
            eff_num = round(float(self.contents.number), 3)
            active_inst = next(
                (
                    inst
                    for inst in engine.get_active_instances()
                    if inst.effect_number == eff_num
                    and inst.channels == target_channels
                ),
                None,
            )
            if active_inst is not None:
                rate_scale, size_scale = self._resolve_linked_scales()
                engine.start_effect(
                    self.contents.number,
                    target_channels,
                    rate_scale=rate_scale,
                    size_scale=size_scale,
                )
                engine.tick()
                self.app.emit(
                    "effect.applied", self.contents.number, list(target_channels)
                )
                if hasattr(self.app, "backend") and self.app.backend:
                    self.app.backend.dmx.set_levels()
            return

        if self.level > 0.0:
            rate_scale, size_scale = self._resolve_linked_scales()
            engine.start_effect(
                self.contents.number,
                target_channels,
                rate_scale=rate_scale,
                size_scale=size_scale,
            )
            engine.tick()
            self.app.emit("effect.applied", self.contents.number, list(target_channels))
        elif self.control_mode == "rate":
            eff_num = round(float(self.contents.number), 3)
            active_inst = next(
                (
                    inst
                    for inst in engine.get_active_instances()
                    if inst.effect_number == eff_num
                ),
                None,
            )
            if active_inst is not None:
                engine.start_effect(
                    self.contents.number,
                    target_channels,
                    rate_scale=0.0,
                    size_scale=1.0,
                )
                engine.tick()
                self.app.emit(
                    "effect.applied", self.contents.number, list(target_channels)
                )
        else:
            stopped = engine.stop_effect(
                effect_number=self.contents.number, channels=target_channels
            )
            engine.tick()
            if stopped:
                self.app.emit(
                    "effect.stopped",
                    self.contents.number,
                    list(target_channels),
                )
        if hasattr(self.app, "backend") and self.app.backend:
            self.app.backend.dmx.set_levels()


VALID_FX_MASTER_KINDS: tuple[str, ...] = ("speed", "rate", "size")


def fader_level_to_speed_bpm(level: float, max_bpm: float = 240.0) -> float:
    """Map fader level [0.0..1.0] to Speed Master BPM (quadratic curve)."""
    lvl = max(0.0, min(1.0, float(level)))
    if lvl <= 0.0:
        return 0.0
    return float(max_bpm) * (lvl**2)


def speed_bpm_to_fader_level(bpm: float, max_bpm: float = 240.0) -> float:
    """Inverse of fader_level_to_speed_bpm for synchronizing fader position."""
    val = max(0.0, float(bpm))
    if val <= 0.0 or max_bpm <= 0.0:
        return 0.0
    return min(1.0, math.sqrt(val / float(max_bpm)))


def rate_scale_to_fader_level(rate: float) -> float:
    """Inverse of fader_level_to_rate_scale."""
    val = float(rate)
    if val <= 0.0:
        return 0.0
    return max(0.0, min(1.0, 0.5 + math.log2(val) / 4.0))


class FaderEffectMaster(Fader):
    """Fader controlling a decoupled Speed, Rate, or Size Master bus."""

    master_kind: str
    master_id: int

    def __init__(
        self,
        index: int,
        fader_bank: FaderBank,
        master_kind: str = "speed",
        master_id: int = 1,
    ) -> None:
        super().__init__(index, fader_bank)
        self._assign_master(master_kind, master_id)
        if self.master_kind == "speed":
            self.level = speed_bpm_to_fader_level(120.0)
        elif self.master_kind == "rate":
            self.level = 0.5
        else:
            self.level = 1.0

    def _assign_master(self, master_kind: str, master_id: int) -> None:
        kind = str(master_kind).strip().lower()
        self.master_kind = kind if kind in VALID_FX_MASTER_KINDS else "speed"
        max_id = 8 if self.master_kind == "speed" else 4
        self.master_id = max(1, min(max_id, int(master_id)))
        self.text = f"{self.master_kind.capitalize()} {self.master_id}"

    def set_contents(self, contents: typing.Any) -> None:  # noqa: ANN401
        """Update target master kind and/or ID from tuple, dict, or int."""
        if isinstance(contents, dict):
            kind = str(contents.get("master_kind", self.master_kind))
            mid = int(contents.get("master_id", self.master_id))
            self._assign_master(kind, mid)
        elif isinstance(contents, (tuple, list)) and len(contents) >= 2:
            self._assign_master(str(contents[0]), int(contents[1]))
        elif isinstance(contents, (int, float)):
            self._assign_master(self.master_kind, int(contents))
        self.level_changed()

    def level_changed(self) -> None:
        """Push fader level to the corresponding EffectsEngine master bus."""
        if self.app is None:
            return
        engine = getattr(self.app, "effects_engine", None)
        if engine is None:
            return
        if self.master_kind == "speed":
            bpm = fader_level_to_speed_bpm(self.level)
            engine.set_speed_master_bpm(self.master_id, bpm)
        elif self.master_kind == "rate":
            rate = fader_level_to_rate_scale(self.level)
            engine.set_rate_master(self.master_id, rate)
        else:
            engine.set_size_master(
                self.master_id, max(0.0, min(1.0, float(self.level)))
            )
        engine.tick()
        if hasattr(self.app, "backend") and self.app.backend:
            self.app.backend.dmx.set_levels()

    def flash_on(self) -> None:
        """Context action: Tap (Speed), Reset 1:1 (Rate), or Flash 100% (Size)."""
        if self.master_kind == "speed":
            if self.app is not None:
                engine = getattr(self.app, "effects_engine", None)
                if engine is not None:
                    bpm = engine.tap_speed_master(self.master_id)
                    if bpm is not None:
                        self.level = speed_bpm_to_fader_level(bpm)
                        engine.tick()
            return
        if self.master_kind == "rate":
            self.set_level(0.5)
            return
        super().flash_on()

    def flash_off(self) -> None:
        """Release momentary flash for Size Master; no-op for Tap/Reset."""
        if self.master_kind in ("speed", "rate"):
            return
        super().flash_off()

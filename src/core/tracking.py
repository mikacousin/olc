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
"""Universal tracking engine and cue state resolver.

Resolves sequential states for conventional channels and multi-parameter lighting
devices with LTP attribute tracking, optional intensity tracking mode, and block cues.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

from olc.define import MAX_CHANNELS
from olc.show.step import get_parameter_family

if typing.TYPE_CHECKING:
    from olc.show.palette import PaletteRef
    from olc.show.patch import PatchManager

HTP_PARAMETERS: frozenset[str] = frozenset({"intensity"})

DEFAULT_MIB_FADE_TIME: float = 2.0

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

_PARAM_ALIASES: dict[str, tuple[str, ...]] = {
    "color": ("color", "colour"),
    "colour": ("color", "colour"),
    "cct": ("cct", "color_temp", "colortemp"),
    "color_temp": ("cct", "color_temp", "colortemp"),
    "colortemp": ("cct", "color_temp", "colortemp"),
    "strobe": ("strobe", "shutter"),
    "shutter": ("strobe", "shutter"),
    "gobo": ("gobo", "gobo_wheel"),
    "gobo_wheel": ("gobo", "gobo_wheel"),
}


def _normalize_family(family: str) -> str:
    """Normalize IFCB family name or alias to canonical family key."""
    return _FAMILY_ALIASES.get(str(family).strip().lower(), str(family).strip().lower())


def _lookup_cue_palette_ref(
    cue: Any,  # noqa: ANN401
    dev_id: int,
    param_name: str,
) -> Optional[PaletteRef]:
    """Return PaletteRef tuple stored on *cue* for *(dev_id, param_name)*, if any."""
    refs_map = getattr(cue, "palette_refs", None)
    if not isinstance(refs_map, dict):
        return None
    dev_refs = refs_map.get(dev_id)
    if not isinstance(dev_refs, dict) or not dev_refs:
        return None
    p_low = str(param_name).lower()
    for cand in (param_name, p_low, *_PARAM_ALIASES.get(p_low, ()), "*"):
        if cand in dev_refs:
            raw = dev_refs[cand]
            if isinstance(raw, (tuple, list)) and len(raw) >= 2:
                return (str(raw[0]), float(raw[1]))
    return None


DEFAULT_PHYSICAL_VALUES: dict[str, Any] = {
    "intensity": 0.0,
    "pan": 0.0,
    "tilt": 0.0,
    "color": "#000000",
    "zoom": 0.0,
    "focus": 0.0,
    "strobe": 0.0,
    "color_temp": 3200.0,
}


class TrackingDisplayState(Enum):
    """Industry-standard visual classification of a parameter in a sequence step."""

    HARD_VALUE = "hard_value"
    TRACKED_VALUE = "tracked_value"
    INTENSITY_UP = "intensity_up"
    INTENSITY_DOWN = "intensity_down"
    BLOCK = "block"
    MIB = "mib"
    MANUAL = "manual"
    INACTIVE = "inactive"


TRACKING_COLORS: dict[TrackingDisplayState, dict[str, float]] = {
    TrackingDisplayState.HARD_VALUE: {"red": 0.95, "green": 0.95, "blue": 0.95},
    TrackingDisplayState.TRACKED_VALUE: {"red": 0.2, "green": 0.85, "blue": 0.95},
    TrackingDisplayState.INTENSITY_UP: {"red": 0.3, "green": 0.6, "blue": 1.0},
    TrackingDisplayState.INTENSITY_DOWN: {"red": 0.3, "green": 0.85, "blue": 0.4},
    TrackingDisplayState.BLOCK: {"red": 0.9, "green": 0.3, "blue": 0.9},
    TrackingDisplayState.MIB: {"red": 0.95, "green": 0.75, "blue": 0.2},
    TrackingDisplayState.MANUAL: {"red": 0.95, "green": 0.35, "blue": 0.35},
    TrackingDisplayState.INACTIVE: {"red": 0.6, "green": 0.6, "blue": 0.6},
}

_STATE_PRIORITY: dict[TrackingDisplayState, int] = {
    TrackingDisplayState.INACTIVE: 0,
    TrackingDisplayState.TRACKED_VALUE: 1,
    TrackingDisplayState.HARD_VALUE: 2,
    TrackingDisplayState.INTENSITY_UP: 2,
    TrackingDisplayState.INTENSITY_DOWN: 2,
    TrackingDisplayState.MIB: 3,
    TrackingDisplayState.BLOCK: 4,
    TrackingDisplayState.MANUAL: 5,
}


def get_tracking_color(state: TrackingDisplayState) -> dict[str, float]:
    """Return a copy of the RGB color dictionary for a TrackingDisplayState."""
    return dict(
        TRACKING_COLORS.get(state, TRACKING_COLORS[TrackingDisplayState.INACTIVE])
    )


def classify_channel_tracking_state(  # pylint: disable=too-many-return-statements, too-many-branches
    sequence: Any,  # noqa: ANN401
    step_index: int,
    channel: int,
    *,
    curr_resolved: ResolvedState | None = None,
    prev_resolved: ResolvedState | None = None,
) -> tuple[TrackingDisplayState, float]:
    """Classify a channel's tracking state and resolved level at a sequence step.

    Returns:
        Tuple of (TrackingDisplayState, resolved_normalized_level).
    """
    steps = getattr(sequence, "steps", None)
    if (
        not isinstance(steps, list)
        or not steps
        or step_index < 0
        or step_index >= len(steps)
        or not 1 <= channel <= MAX_CHANNELS
    ):
        return TrackingDisplayState.INACTIVE, 0.0

    cue = steps[step_index].cue
    if cue is None:
        return TrackingDisplayState.INACTIVE, 0.0

    tracking_mode = getattr(sequence, "tracking_mode", False)
    if curr_resolved is None:
        curr_resolved = TrackingEngine.resolve_step_state(
            sequence, step_index, tracking_mode=tracking_mode
        )
    curr_level = float(curr_resolved.channels[channel - 1])
    if curr_level == 0.0 and channel in curr_resolved.device_values:
        dev_int = curr_resolved.device_values[channel].get("intensity")
        if isinstance(dev_int, (int, float)):
            curr_level = max(0.0, min(1.0, float(dev_int)))

    prev_level = 0.0
    if step_index > 1:
        if prev_resolved is None:
            prev_resolved = TrackingEngine.resolve_step_state(
                sequence, step_index - 1, tracking_mode=tracking_mode
            )
        prev_level = float(prev_resolved.channels[channel - 1])
        if prev_level == 0.0 and channel in prev_resolved.device_values:
            prev_int = prev_resolved.device_values[channel].get("intensity")
            if isinstance(prev_int, (int, float)):
                prev_level = max(0.0, min(1.0, float(prev_int)))

    is_explicit_move = channel in cue.channels or (
        hasattr(cue, "device_values")
        and "intensity" in cue.device_values.get(channel, {})
    )

    if (getattr(cue, "is_block", False) or getattr(cue, "is_int_block", False)) and (
        is_explicit_move or curr_level > 0 or channel in curr_resolved.device_values
    ):
        return TrackingDisplayState.BLOCK, curr_level

    if curr_level == 0 and curr_resolved.mib_parameters.get(channel):
        return TrackingDisplayState.MIB, 0

    if is_explicit_move:
        if step_index > 1 and curr_level != prev_level:
            if curr_level > prev_level:
                return TrackingDisplayState.INTENSITY_UP, curr_level
            return TrackingDisplayState.INTENSITY_DOWN, curr_level
        return TrackingDisplayState.HARD_VALUE, curr_level

    if curr_level > 0 or channel in curr_resolved.device_values:
        return TrackingDisplayState.TRACKED_VALUE, curr_level

    return TrackingDisplayState.INACTIVE, 0


@dataclass
class ResolvedState:
    """Resolved playback state at a specific sequence step.

    Attributes:
        channels: Conventional channels levels array of length MAX_CHANNELS.
        device_values: Mapping {device_id: {param_name: physical_or_norm_value}}.
        mib_parameters: Mapping {device_id: set of LTP param names set by MIB}.
        palette_refs: Mapping {channel: {param_name: (category, number)}}.
        parameter_states: Mapping {channel: {param_name: TrackingDisplayState}}.
        family_states: Mapping {channel: {family_name: TrackingDisplayState}}.
    """

    channels: np.ndarray = field(
        default_factory=lambda: np.zeros(MAX_CHANNELS, dtype=np.float64)
    )
    device_values: dict[int, dict[str, Any]] = field(default_factory=dict)
    mib_parameters: dict[int, set[str]] = field(default_factory=dict)
    palette_refs: dict[int, dict[str, PaletteRef]] = field(default_factory=dict)
    effect_refs: dict[int, dict[str, Any]] = field(default_factory=dict)
    parameter_states: dict[int, dict[str, TrackingDisplayState]] = field(
        default_factory=dict
    )
    family_states: dict[int, dict[str, TrackingDisplayState]] = field(
        default_factory=dict
    )

    def has_move_on_family(self, channel: int, family: str) -> bool:
        """Return True if *family* on *channel* has an explicit move or block."""
        norm_fam = _normalize_family(family)
        state = self.family_states.get(int(channel), {}).get(norm_fam)
        return state in (
            TrackingDisplayState.HARD_VALUE,
            TrackingDisplayState.INTENSITY_UP,
            TrackingDisplayState.INTENSITY_DOWN,
            TrackingDisplayState.BLOCK,
        )

    def has_fcb_move(self, channel: int) -> bool:
        """Return True if Focus, Color, or Beam moved explicitly on *channel*."""
        ch_states = self.family_states.get(int(channel))
        if not ch_states:
            return False
        return any(
            ch_states.get(fam)
            in (
                TrackingDisplayState.HARD_VALUE,
                TrackingDisplayState.INTENSITY_UP,
                TrackingDisplayState.INTENSITY_DOWN,
                TrackingDisplayState.BLOCK,
            )
            for fam in ("position", "color", "beam")
        )

    def is_mib(self, channel: int) -> bool:
        """Return True if any attribute on *channel* is pre-positioned via MIB."""
        return bool(self.mib_parameters.get(int(channel)))

    def get_family_palette_ref(
        self, channel: int, family: str
    ) -> tuple[Optional[PaletteRef], bool]:
        """Return ``(palette_ref, is_partial)`` for *family* on *channel*.

        When all resolved parameters of *family* share one palette reference,
        ``is_partial`` is ``False``. If only a subset of parameters carry a
        reference or multiple distinct references coexist, ``is_partial`` is
        ``True``.
        """
        ch = int(channel)
        norm_fam = _normalize_family(family)
        ch_refs = self.palette_refs.get(ch, {})
        if not ch_refs:
            return None, False

        if norm_fam == "intensity":
            has_conv = (
                1 <= ch <= len(self.channels) and float(self.channels[ch - 1]) > 0.0
            )
            has_dev_int = "intensity" in self.device_values.get(ch, {})
            has_state = "intensity" in self.parameter_states.get(ch, {})
            if not (has_conv or has_dev_int or has_state):
                return None, False
            ref = ch_refs.get("intensity") or ch_refs.get("*")
            return (ref, False) if ref is not None else (None, False)

        dev_params = self.device_values.get(ch, {})
        param_names = [
            p
            for p in dev_params
            if p.lower() not in HTP_PARAMETERS
            and _normalize_family(get_parameter_family(p)) == norm_fam
        ]
        if not param_names:
            return None, False

        matched: list[Optional[PaletteRef]] = []
        for param_name in param_names:
            p_low = str(param_name).lower()
            found: Optional[PaletteRef] = None
            for cand in (param_name, p_low, *_PARAM_ALIASES.get(p_low, ()), "*"):
                if cand in ch_refs:
                    found = ch_refs[cand]
                    break
            matched.append(found)

        non_null = [r for r in matched if r is not None]
        if not non_null:
            return None, False

        unique_refs = list(dict.fromkeys((str(r[0]), float(r[1])) for r in non_null))
        is_partial = len(unique_refs) > 1 or len(non_null) < len(param_names)
        return unique_refs[0], is_partial


# pylint: disable=too-few-public-methods
class TrackingEngine:
    """Universal tracking engine resolving sequential playback states."""

    @staticmethod
    def is_device_dark(
        channels: np.ndarray,
        device_values: dict[int, dict[str, Any]],
        dev_id: int,
    ) -> bool:
        """Return True if device has 0 intensity in channels and device_values."""
        if 1 <= dev_id <= len(channels) and int(channels[dev_id - 1]) > 0:
            return False
        dev_params = device_values.get(dev_id)
        if dev_params is not None:
            for key, val in dev_params.items():
                if key.lower() in HTP_PARAMETERS and float(val) > 0.0:
                    return False
        return True

    @classmethod
    def resolve_step_state(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool = False,
        patch: Optional[PatchManager] = None,
        mib_enabled: Optional[bool] = None,
    ) -> ResolvedState:
        """Resolve full conventional and moving light state for a sequence step.

        Tracing back through sequence steps:
        - Non-intensity (LTP) attributes (Pan, Tilt, Color, Zoom, Gobos) are ALWAYS
          tracked backward until the last Move instruction, unless stopped by a Block.
        - Conventional & device intensity (HTP):
          - If tracking_mode is False (Cue-Only): intensities drop to 0 unless
            explicitly specified in the target cue.
          - If tracking_mode is True (Tracking): intensities propagate forward until a
            new level or an explicit 0% (Hard Zero), unless stopped by a Block Cue.
        - Move In Black (MIB):
          - When mib_enabled is True, devices that are dark (intensity == 0) at
            step_index look ahead to subsequent steps (stopping at any Block Cue).
          - If a device turns on (intensity > 0) at a future step m > step_index with
            new LTP values, those LTP values are pre-applied at step_index and listed
            in ResolvedState.mib_parameters.

        Args:
            sequence: Sequence instance.
            step_index: Target step index in sequence.steps.
            tracking_mode: True for tracked intensity, False for Cue-Only.
            patch: Optional PatchManager to query patched devices.
            mib_enabled: Optional override for MIB (defaults to sequence.mib_enabled).

        Returns:
            ResolvedState containing resolved channels, device values, and MIB flags.
        """
        if not sequence.steps or step_index < 0 or step_index >= len(sequence.steps):
            return ResolvedState()

        channels, conv_states, conv_refs = cls._resolve_conventional_channels_with_meta(
            sequence, step_index, tracking_mode
        )
        device_values, palette_refs, parameter_states = cls._resolve_devices_with_meta(
            sequence, step_index, tracking_mode, patch
        )

        for ch, state in conv_states.items():
            ch_params = parameter_states.setdefault(ch, {})
            existing = ch_params.get("intensity")
            if existing is None or (
                _STATE_PRIORITY.get(state, 0) >= _STATE_PRIORITY.get(existing, 0)
            ):
                ch_params["intensity"] = state
        for ch, ref in conv_refs.items():
            ch_refs = palette_refs.setdefault(ch, {})
            if "intensity" not in ch_refs:
                ch_refs["intensity"] = ref

        use_mib = (
            bool(getattr(sequence, "mib_enabled", True))
            if mib_enabled is None
            else mib_enabled
        )
        mib_parameters: dict[int, set[str]] = {}
        if use_mib:
            mib_parameters = cls._apply_mib_lookahead(
                sequence,
                step_index,
                channels,
                device_values,
                patch,
                palette_refs=palette_refs,
                parameter_states=parameter_states,
            )

        family_states = cls._compute_family_states(parameter_states)
        effect_refs = cls._resolve_effect_refs(sequence, step_index, tracking_mode)
        return ResolvedState(
            channels=channels,
            device_values=device_values,
            mib_parameters=mib_parameters,
            palette_refs=palette_refs,
            effect_refs=effect_refs,
            parameter_states=parameter_states,
            family_states=family_states,
        )

    @staticmethod
    def resolve_step_effects(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        *,
        tracking_mode: bool = False,
    ) -> dict[int, dict[str, Any]]:
        """Resolve active effect references at *step_index* (Cue-Only or Tracking)."""
        return TrackingEngine._resolve_effect_refs(sequence, step_index, tracking_mode)

    @staticmethod
    def _resolve_effect_refs(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
    ) -> dict[int, dict[str, Any]]:
        """Resolve active effect references at *step_index* (Cue-Only or Tracking)."""
        target_cue = sequence.steps[step_index].cue
        if target_cue is None or getattr(target_cue, "number", 0) == 0:
            return {}

        if not tracking_mode:
            raw_refs = getattr(target_cue, "effect_refs", None)
            if not isinstance(raw_refs, dict):
                return {}
            return {
                int(ch): dict(spec)
                for ch, spec in raw_refs.items()
                if isinstance(spec, dict) and not spec.get("stop")
            }

        resolved: dict[int, dict[str, Any]] = {}
        decided: set[int] = set()
        for idx in range(step_index, -1, -1):
            cue = sequence.steps[idx].cue
            if cue is None:
                continue
            raw_refs = getattr(cue, "effect_refs", None)
            if isinstance(raw_refs, dict):
                for ch_raw, spec in raw_refs.items():
                    ch = int(ch_raw)
                    if ch in decided or not isinstance(spec, dict):
                        continue
                    decided.add(ch)
                    if not spec.get("stop"):
                        resolved[ch] = dict(spec)
            if getattr(cue, "is_block", False):
                break
        return resolved

    @staticmethod
    def _compute_family_states(
        parameter_states: dict[int, dict[str, TrackingDisplayState]],
    ) -> dict[int, dict[str, TrackingDisplayState]]:
        """Aggregate per-parameter tracking states into canonical IFCB families."""
        result: dict[int, dict[str, TrackingDisplayState]] = {}
        for ch, param_map in parameter_states.items():
            fam_map: dict[str, TrackingDisplayState] = {}
            for param_name, state in param_map.items():
                fam = _normalize_family(get_parameter_family(param_name))
                prev_state = fam_map.get(fam)
                if prev_state is None or (
                    _STATE_PRIORITY.get(state, 0) > _STATE_PRIORITY.get(prev_state, 0)
                ):
                    fam_map[fam] = state
            if fam_map:
                result[ch] = fam_map
        return result

    @classmethod
    def _resolve_conventional_channels(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
    ) -> np.ndarray:
        """Resolve conventional channel levels (0-255)."""
        channels, _, _ = cls._resolve_conventional_channels_with_meta(
            sequence, step_index, tracking_mode
        )
        return channels

    @staticmethod
    def _resolve_conventional_channels_with_meta(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
    ) -> tuple[
        np.ndarray,
        dict[int, TrackingDisplayState],
        dict[int, PaletteRef],
    ]:
        """Resolve conventional levels along with tracking states and palette refs."""
        target_cue = sequence.steps[step_index].cue
        is_target_block = bool(
            target_cue is not None
            and (
                getattr(target_cue, "is_block", False)
                or getattr(target_cue, "is_int_block", False)
            )
        )
        conv_states: dict[int, TrackingDisplayState] = {}
        conv_refs: dict[int, PaletteRef] = {}

        if not tracking_mode:
            if target_cue is None:
                return np.zeros(MAX_CHANNELS, dtype=np.float64), conv_states, conv_refs
            for ch_num, level in target_cue.channels.items():
                ch_int = int(ch_num)
                if not 1 <= ch_int <= MAX_CHANNELS:
                    continue
                conv_states[ch_int] = (
                    TrackingDisplayState.BLOCK
                    if is_target_block
                    else TrackingDisplayState.HARD_VALUE
                )
                if float(level) > 0.0:
                    ref = _lookup_cue_palette_ref(target_cue, ch_int, "intensity")
                    if ref is not None:
                        conv_refs[ch_int] = ref
            return target_cue.channels_array.copy(), conv_states, conv_refs

        resolved_channels = np.zeros(MAX_CHANNELS, dtype=np.float64)
        resolved_mask = np.zeros(MAX_CHANNELS, dtype=bool)

        for idx in range(step_index, -1, -1):
            cue = sequence.steps[idx].cue
            if cue is None:
                continue

            for ch_num, level in cue.channels.items():
                ch_int = int(ch_num)
                if 1 <= ch_int <= MAX_CHANNELS and not resolved_mask[ch_int - 1]:
                    lvl_f = float(level)
                    resolved_channels[ch_int - 1] = lvl_f
                    resolved_mask[ch_int - 1] = True
                    if is_target_block:
                        conv_states[ch_int] = TrackingDisplayState.BLOCK
                    elif idx == step_index:
                        conv_states[ch_int] = TrackingDisplayState.HARD_VALUE
                    elif lvl_f > 0.0:
                        conv_states[ch_int] = TrackingDisplayState.TRACKED_VALUE
                    else:
                        conv_states[ch_int] = TrackingDisplayState.INACTIVE
                    if lvl_f > 0.0 or idx == step_index:
                        ref = _lookup_cue_palette_ref(cue, ch_int, "intensity")
                        if ref is not None:
                            conv_refs[ch_int] = ref

            if (
                getattr(cue, "is_block", False)
                or getattr(cue, "is_int_block", False)
                or np.all(resolved_mask)
            ):
                break

        return resolved_channels, conv_states, conv_refs

    @classmethod
    def _resolve_devices(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
        patch: Optional[PatchManager],
    ) -> dict[int, dict[str, Any]]:
        """Resolve all multi-parameter device states."""
        device_values, _, _ = cls._resolve_devices_with_meta(
            sequence, step_index, tracking_mode, patch
        )
        return device_values

    @classmethod
    def _resolve_devices_with_meta(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
        patch: Optional[PatchManager],
    ) -> tuple[
        dict[int, dict[str, Any]],
        dict[int, dict[str, PaletteRef]],
        dict[int, dict[str, TrackingDisplayState]],
    ]:
        """Resolve multi-parameter values, palette references, and param states."""
        all_device_ids: set[int] = set()
        if patch is not None:
            all_device_ids.update(patch.devices.keys())

        for idx in range(0, step_index + 1):
            c = sequence.steps[idx].cue
            if c is not None and hasattr(c, "device_values"):
                all_device_ids.update(c.device_values.keys())

        device_values: dict[int, dict[str, Any]] = {}
        palette_refs: dict[int, dict[str, PaletteRef]] = {}
        parameter_states: dict[int, dict[str, TrackingDisplayState]] = {}

        for dev_id in sorted(all_device_ids):
            dev_state, dev_refs, dev_pstates = cls._resolve_single_device_with_meta(
                sequence, step_index, dev_id, tracking_mode
            )
            if dev_state:
                device_values[dev_id] = dev_state
            if dev_refs:
                palette_refs[dev_id] = dev_refs
            if dev_pstates:
                parameter_states[dev_id] = dev_pstates

        return device_values, palette_refs, parameter_states

    @classmethod
    def _resolve_single_device(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        tracking_mode: bool,
    ) -> dict[str, Any]:
        """Resolve all touched parameters for a single device."""
        dev_state, _, _ = cls._resolve_single_device_with_meta(
            sequence, step_index, dev_id, tracking_mode
        )
        return dev_state

    @classmethod
    def _resolve_single_device_with_meta(  # pylint: disable=too-many-locals
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        tracking_mode: bool,
    ) -> tuple[
        dict[str, Any],
        dict[str, PaletteRef],
        dict[str, TrackingDisplayState],
    ]:
        """Resolve parameters, palette refs, and tracking states for one device."""
        touched_params: set[str] = set()
        for idx in range(0, step_index + 1):
            c = sequence.steps[idx].cue
            if c is not None and hasattr(c, "device_values"):
                touched_params.update(c.device_values.get(dev_id, {}).keys())

        target_cue = sequence.steps[step_index].cue
        is_target_block = bool(
            target_cue is not None and getattr(target_cue, "is_block", False)
        )
        is_target_int_block = bool(
            is_target_block
            or (target_cue is not None and getattr(target_cue, "is_int_block", False))
        )

        dev_state: dict[str, Any] = {}
        dev_refs: dict[str, PaletteRef] = {}
        dev_pstates: dict[str, TrackingDisplayState] = {}

        for param_name in sorted(touched_params):
            is_htp = param_name.lower() in HTP_PARAMETERS
            if is_htp:
                val, def_idx, def_cue = cls._resolve_htp_parameter_with_source(
                    sequence, step_index, dev_id, param_name, tracking_mode
                )
                dev_state[param_name] = val
                if def_cue is None:
                    dev_pstates[param_name] = TrackingDisplayState.INACTIVE
                elif is_target_int_block:
                    dev_pstates[param_name] = TrackingDisplayState.BLOCK
                elif def_idx == step_index:
                    dev_pstates[param_name] = TrackingDisplayState.HARD_VALUE
                elif float(val) > 0.0:
                    dev_pstates[param_name] = TrackingDisplayState.TRACKED_VALUE
                else:
                    dev_pstates[param_name] = TrackingDisplayState.INACTIVE

                if def_cue is not None and (float(val) > 0.0 or def_idx == step_index):
                    ref = _lookup_cue_palette_ref(def_cue, dev_id, param_name)
                    if ref is not None:
                        dev_refs[param_name] = ref
            else:
                val, def_idx, def_cue = cls._resolve_ltp_parameter_with_source(
                    sequence, step_index, dev_id, param_name
                )
                dev_state[param_name] = val
                if def_cue is None:
                    dev_pstates[param_name] = TrackingDisplayState.INACTIVE
                else:
                    dev_pstates[param_name] = (
                        TrackingDisplayState.BLOCK
                        if is_target_block
                        else (
                            TrackingDisplayState.HARD_VALUE
                            if def_idx == step_index
                            else TrackingDisplayState.TRACKED_VALUE
                        )
                    )
                    ref = _lookup_cue_palette_ref(def_cue, dev_id, param_name)
                    if ref is not None:
                        dev_refs[param_name] = ref

        return dev_state, dev_refs, dev_pstates

    @classmethod
    def _resolve_htp_parameter(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        param_name: str,
        tracking_mode: bool,
    ) -> float:
        """Resolve HTP intensity parameter (Cue-Only or Tracking)."""
        val, _, _ = cls._resolve_htp_parameter_with_source(
            sequence, step_index, dev_id, param_name, tracking_mode
        )
        return val

    @staticmethod
    def _resolve_htp_parameter_with_source(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        param_name: str,
        tracking_mode: bool,
    ) -> tuple[float, int, Any]:
        """Resolve HTP intensity along with its defining step index and Cue."""
        if not tracking_mode:
            target_cue = sequence.steps[step_index].cue
            if (
                target_cue is not None
                and hasattr(target_cue, "device_values")
                and param_name in target_cue.device_values.get(dev_id, {})
            ):
                return (
                    float(target_cue.device_values[dev_id][param_name]),
                    step_index,
                    target_cue,
                )
            return 0.0, -1, None

        for idx in range(step_index, -1, -1):
            c = sequence.steps[idx].cue
            if c is None:
                continue
            if (
                hasattr(c, "device_values")
                and dev_id in c.device_values
                and param_name in c.device_values[dev_id]
            ):
                return float(c.device_values[dev_id][param_name]), idx, c
            if getattr(c, "is_block", False) or getattr(c, "is_int_block", False):
                break
        return 0.0, -1, None

    @classmethod
    def _resolve_ltp_parameter(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        param_name: str,
    ) -> Any:  # noqa: ANN401
        """Resolve LTP parameter (tracked backward until latest Move or Block)."""
        val, _, _ = cls._resolve_ltp_parameter_with_source(
            sequence, step_index, dev_id, param_name
        )
        return val

    @staticmethod
    def _resolve_ltp_parameter_with_source(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        param_name: str,
    ) -> tuple[Any, int, Any]:
        """Resolve LTP parameter along with its defining step index and Cue."""
        for idx in range(step_index, -1, -1):
            c = sequence.steps[idx].cue
            if c is None:
                continue
            if (
                hasattr(c, "device_values")
                and dev_id in c.device_values
                and param_name in c.device_values[dev_id]
            ):
                return c.device_values[dev_id][param_name], idx, c
            if c.is_block:
                return DEFAULT_PHYSICAL_VALUES.get(param_name.lower(), 0.0), -1, None

        return DEFAULT_PHYSICAL_VALUES.get(param_name.lower(), 0.0), -1, None

    @classmethod
    def _apply_mib_lookahead(  # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        channels: np.ndarray,
        device_values: dict[int, dict[str, Any]],
        patch: Optional[PatchManager],
        *,
        palette_refs: Optional[dict[int, dict[str, PaletteRef]]] = None,
        parameter_states: Optional[dict[int, dict[str, TrackingDisplayState]]] = None,
    ) -> dict[int, set[str]]:
        """Apply Move In Black look-ahead for devices that are dark at step_index."""
        curr_cue = sequence.steps[step_index].cue
        if curr_cue is None or getattr(curr_cue, "number", 0) == 0:
            return {}

        candidate_ids: set[int] = set(device_values.keys())
        if patch is not None:
            candidate_ids.update(patch.devices.keys())
        for idx in range(step_index + 1, len(sequence.steps)):
            c = sequence.steps[idx].cue
            if c is not None and hasattr(c, "device_values"):
                candidate_ids.update(c.device_values.keys())

        mib_parameters: dict[int, set[str]] = {}
        for dev_id in sorted(candidate_ids):
            if not cls.is_device_dark(channels, device_values, dev_id):
                continue
            turn_on_idx, future_ltp, future_cues = cls._find_mib_turn_on_step_with_refs(
                sequence, step_index, dev_id
            )
            if turn_on_idx is None or not future_ltp:
                continue

            dev_state = device_values.setdefault(dev_id, {"intensity": 0.0})
            mib_set: set[str] = set()
            for param_name, target_val in future_ltp.items():
                current_val = dev_state.get(
                    param_name, DEFAULT_PHYSICAL_VALUES.get(param_name.lower(), 0.0)
                )
                if param_name not in dev_state or current_val != target_val:
                    mib_set.add(param_name)
                dev_state[param_name] = target_val
                if parameter_states is not None and (param_name in mib_set):
                    parameter_states.setdefault(dev_id, {})[param_name] = (
                        TrackingDisplayState.MIB
                    )
                if palette_refs is not None:
                    src_cue = future_cues.get(param_name)
                    fut_ref = (
                        _lookup_cue_palette_ref(src_cue, dev_id, param_name)
                        if src_cue is not None
                        else None
                    )
                    if fut_ref is not None:
                        palette_refs.setdefault(dev_id, {})[param_name] = fut_ref
                    elif param_name in mib_set and dev_id in palette_refs:
                        palette_refs[dev_id].pop(param_name, None)
            if mib_set:
                mib_parameters[dev_id] = mib_set

        return mib_parameters

    @staticmethod
    def _step_has_explicit_family(step: Any, param_name: str) -> bool:  # noqa: ANN401
        """Return True if step defines explicit timing for param_name's family."""
        fn = getattr(step, "has_explicit_family_timing", None)
        return bool(fn(get_parameter_family(param_name))) if callable(fn) else False

    @classmethod
    def _find_mib_turn_on_step(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
    ) -> tuple[Optional[int], dict[str, Any]]:
        """Find the first future step where dev_id lights up, collecting LTP moves."""
        turn_on_idx, filtered_ltp, _ = cls._find_mib_turn_on_step_with_refs(
            sequence, step_index, dev_id
        )
        return turn_on_idx, filtered_ltp

    @classmethod
    def _find_mib_turn_on_step_with_refs(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
    ) -> tuple[Optional[int], dict[str, Any], dict[str, Any]]:
        """Find future MIB turn-on step, LTP values, and defining Cue per parameter.

        Stops immediately if a Block Cue or a Cue 0 sentinel is encountered.
        Excludes any parameter whose family has explicit timing on its move step
        or on the turn-on step.
        """
        collected_ltp: dict[str, tuple[Any, bool, Any]] = {}
        for future_idx in range(step_index + 1, len(sequence.steps)):
            future_step = sequence.steps[future_idx]
            cue = future_step.cue
            if cue is None:
                continue
            if getattr(cue, "number", 0) == 0 or getattr(cue, "is_block", False):
                break

            dev_dict = (
                cue.device_values.get(dev_id, {})
                if hasattr(cue, "device_values")
                else {}
            )
            for param_name, val in dev_dict.items():
                if param_name.lower() not in HTP_PARAMETERS:
                    collected_ltp[param_name] = (
                        val,
                        cls._step_has_explicit_family(future_step, param_name),
                        cue,
                    )

            conv_level = (
                float(cue.channels.get(dev_id, 0.0))
                if hasattr(cue, "channels")
                else 0.0
            )
            dev_intensity = next(
                (
                    float(val)
                    for key, val in dev_dict.items()
                    if key.lower() in HTP_PARAMETERS
                ),
                0.0,
            )
            if conv_level > 0 or dev_intensity > 0.0:
                filtered_ltp: dict[str, Any] = {}
                filtered_cues: dict[str, Any] = {}
                for p, (val, move_exp, src_cue) in collected_ltp.items():
                    if not (move_exp or cls._step_has_explicit_family(future_step, p)):
                        filtered_ltp[p] = val
                        filtered_cues[p] = src_cue
                return future_idx, filtered_ltp, filtered_cues

        return None, {}, {}

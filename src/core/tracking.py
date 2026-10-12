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
from typing import Any, Optional

import numpy as np

from olc.define import MAX_CHANNELS

if typing.TYPE_CHECKING:
    from olc.patch import PatchManager

HTP_PARAMETERS: frozenset[str] = frozenset({"intensity"})

DEFAULT_MIB_FADE_TIME: float = 2.0

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


@dataclass
class ResolvedState:
    """Resolved playback state at a specific sequence step.

    Attributes:
        channels: Conventional channels levels array of length MAX_CHANNELS (0-255).
        device_values: Mapping {device_id: {param_name: physical_or_norm_value}}.
        mib_parameters: Mapping {device_id: set of LTP param names set by MIB}.
    """

    channels: np.ndarray = field(
        default_factory=lambda: np.zeros(MAX_CHANNELS, dtype=np.uint8)
    )
    device_values: dict[int, dict[str, Any]] = field(default_factory=dict)
    mib_parameters: dict[int, set[str]] = field(default_factory=dict)


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

        channels = cls._resolve_conventional_channels(
            sequence, step_index, tracking_mode
        )
        device_values = cls._resolve_devices(sequence, step_index, tracking_mode, patch)
        use_mib = (
            bool(getattr(sequence, "mib_enabled", True))
            if mib_enabled is None
            else mib_enabled
        )
        mib_parameters: dict[int, set[str]] = {}
        if use_mib:
            mib_parameters = cls._apply_mib_lookahead(
                sequence, step_index, channels, device_values, patch
            )
        return ResolvedState(
            channels=channels,
            device_values=device_values,
            mib_parameters=mib_parameters,
        )

    @staticmethod
    def _resolve_conventional_channels(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
    ) -> np.ndarray:
        """Resolve conventional channel levels (0-255)."""
        if not tracking_mode:
            target_cue = sequence.steps[step_index].cue
            return (
                target_cue.channels_array.copy()
                if target_cue is not None
                else np.zeros(MAX_CHANNELS, dtype=np.uint8)
            )

        resolved_channels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        resolved_mask = np.zeros(MAX_CHANNELS, dtype=bool)

        for idx in range(step_index, -1, -1):
            cue = sequence.steps[idx].cue
            if cue is None:
                continue

            for ch_num, level in cue.channels.items():
                if 1 <= ch_num <= MAX_CHANNELS and not resolved_mask[ch_num - 1]:
                    resolved_channels[ch_num - 1] = level
                    resolved_mask[ch_num - 1] = True

            if cue.is_block or np.all(resolved_mask):
                break

        return resolved_channels

    @classmethod
    def _resolve_devices(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        tracking_mode: bool,
        patch: Optional[PatchManager],
    ) -> dict[int, dict[str, Any]]:
        """Resolve all multi-parameter device states."""
        all_device_ids: set[int] = set()
        if patch is not None:
            all_device_ids.update(patch.devices.keys())

        for idx in range(0, step_index + 1):
            c = sequence.steps[idx].cue
            if c is not None and hasattr(c, "device_values"):
                all_device_ids.update(c.device_values.keys())

        device_values: dict[int, dict[str, Any]] = {}
        for dev_id in sorted(all_device_ids):
            dev_state = cls._resolve_single_device(
                sequence, step_index, dev_id, tracking_mode
            )
            if dev_state:
                device_values[dev_id] = dev_state

        return device_values

    @classmethod
    def _resolve_single_device(
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        tracking_mode: bool,
    ) -> dict[str, Any]:
        """Resolve all touched parameters for a single device."""
        touched_params: set[str] = set()
        for idx in range(0, step_index + 1):
            c = sequence.steps[idx].cue
            if c is not None and hasattr(c, "device_values"):
                touched_params.update(c.device_values.get(dev_id, {}).keys())

        dev_state: dict[str, Any] = {}
        for param_name in sorted(touched_params):
            is_htp = param_name.lower() in HTP_PARAMETERS
            if is_htp:
                dev_state[param_name] = cls._resolve_htp_parameter(
                    sequence, step_index, dev_id, param_name, tracking_mode
                )
            else:
                dev_state[param_name] = cls._resolve_ltp_parameter(
                    sequence, step_index, dev_id, param_name
                )
        return dev_state

    @staticmethod
    def _resolve_htp_parameter(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        param_name: str,
        tracking_mode: bool,
    ) -> float:
        """Resolve HTP intensity parameter (Cue-Only or Tracking)."""
        if not tracking_mode:
            target_cue = sequence.steps[step_index].cue
            if target_cue is not None and hasattr(target_cue, "device_values"):
                return float(
                    target_cue.device_values.get(dev_id, {}).get(param_name, 0.0)
                )
            return 0.0

        for idx in range(step_index, -1, -1):
            c = sequence.steps[idx].cue
            if c is None:
                continue
            if (
                hasattr(c, "device_values")
                and dev_id in c.device_values
                and param_name in c.device_values[dev_id]
            ):
                return float(c.device_values[dev_id][param_name])
            if c.is_block:
                break
        return 0.0

    @staticmethod
    def _resolve_ltp_parameter(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
        param_name: str,
    ) -> Any:  # noqa: ANN401
        """Resolve LTP parameter (tracked backward until latest Move or Block)."""
        for idx in range(step_index, -1, -1):
            c = sequence.steps[idx].cue
            if c is None:
                continue
            if (
                hasattr(c, "device_values")
                and dev_id in c.device_values
                and param_name in c.device_values[dev_id]
            ):
                return c.device_values[dev_id][param_name]
            if c.is_block:
                return DEFAULT_PHYSICAL_VALUES.get(param_name.lower(), 0.0)

        return DEFAULT_PHYSICAL_VALUES.get(param_name.lower(), 0.0)

    @classmethod
    def _apply_mib_lookahead(  # pylint: disable=too-many-locals
        cls,
        sequence: Any,  # noqa: ANN401
        step_index: int,
        channels: np.ndarray,
        device_values: dict[int, dict[str, Any]],
        patch: Optional[PatchManager],
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
            turn_on_idx, future_ltp = cls._find_mib_turn_on_step(
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
            if mib_set:
                mib_parameters[dev_id] = mib_set

        return mib_parameters

    @staticmethod
    def _find_mib_turn_on_step(
        sequence: Any,  # noqa: ANN401
        step_index: int,
        dev_id: int,
    ) -> tuple[Optional[int], dict[str, Any]]:
        """Find the first future step where dev_id lights up, collecting LTP moves.

        Stops immediately if a Block Cue or a Cue 0 sentinel is encountered.
        """
        collected_ltp: dict[str, Any] = {}
        for future_idx in range(step_index + 1, len(sequence.steps)):
            cue = sequence.steps[future_idx].cue
            if cue is None:
                continue
            if getattr(cue, "number", 0) == 0:
                break
            if getattr(cue, "is_block", False):
                break

            dev_dict = (
                cue.device_values.get(dev_id, {})
                if hasattr(cue, "device_values")
                else {}
            )
            for param_name, val in dev_dict.items():
                if param_name.lower() not in HTP_PARAMETERS:
                    collected_ltp[param_name] = val

            conv_level = (
                int(cue.channels.get(dev_id, 0)) if hasattr(cue, "channels") else 0
            )
            dev_intensity = 0.0
            for key, val in dev_dict.items():
                if key.lower() in HTP_PARAMETERS:
                    dev_intensity = float(val)
                    break

            if conv_level > 0 or dev_intensity > 0.0:
                return future_idx, collected_ltp

        return None, {}

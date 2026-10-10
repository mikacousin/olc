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
"""Execution engine for parsed lighting console command AST nodes."""

from __future__ import annotations

import dataclasses
import typing

from olc.core.parser.ast_nodes import (
    AllSelectionNode,
    AttributeCommandNode,
    BlockCueCommandNode,
    ChannelNumberNode,
    ChannelRangeNode,
    CommandNode,
    DeleteCueCommandNode,
    GotoCueCommandNode,
    GroupSelectionNode,
    IntensityCommandNode,
    RecordCueCommandNode,
    SelectionItemNode,
    SelectionNode,
    SelectOnlyCommandNode,
    UnblockCueCommandNode,
    UpdateCueCommandNode,
)
from olc.cue import Cue
from olc.define import MAX_CHANNELS
from olc.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


@dataclasses.dataclass
class CommandResult:
    """Result of command execution."""

    success: bool
    message: str
    affected_channels: list[int] = dataclasses.field(default_factory=list)


# Standard CSS/Lighting color presets mapped to hex
COLOR_PRESETS: dict[str, str] = {
    "RED": "#FF0000",
    "GREEN": "#00FF00",
    "BLUE": "#0000FF",
    "WHITE": "#FFFFFF",
    "WARM_WHITE": "#FFD1A4",
    "COOL_WHITE": "#E0EEFF",
    "AMBER": "#FFBF00",
    "YELLOW": "#FFFF00",
    "CYAN": "#00FFFF",
    "MAGENTA": "#FF00FF",
    "ORANGE": "#FFA500",
    "PINK": "#FFC0CB",
    "PURPLE": "#800080",
}


class CommandExecutor:
    """Dispatches and applies CommandNode instructions to the Core application."""

    def __init__(self, app: CoreApplication) -> None:
        self.app = app

    def execute(  # pylint: disable=too-many-return-statements
        self, node: CommandNode
    ) -> CommandResult:
        """Execute a parsed AST command node against the application state.

        Args:
            node: The root CommandNode to execute.

        Returns:
            CommandResult with success status and informative feedback message.
        """
        if isinstance(node, SelectOnlyCommandNode):
            return self._execute_select_only(node)

        if isinstance(node, IntensityCommandNode):
            return self._execute_intensity(node)

        if isinstance(node, AttributeCommandNode):
            return self._execute_attribute(node)

        if isinstance(node, RecordCueCommandNode):
            return self._execute_record_cue(node)

        if isinstance(node, UpdateCueCommandNode):
            return self._execute_update_cue(node)

        if isinstance(node, GotoCueCommandNode):
            return self._execute_goto_cue(node)

        if isinstance(node, BlockCueCommandNode):
            return self._execute_block_cue(node, is_block=True)

        if isinstance(node, UnblockCueCommandNode):
            return self._execute_block_cue(node, is_block=False)

        if isinstance(node, DeleteCueCommandNode):
            return self._execute_delete_cue(node)

        return CommandResult(False, f"Unsupported command node: {type(node).__name__}")

    # --- Selection Resolution ---

    def resolve_selection(self, selection: SelectionNode | None) -> list[int]:
        """Resolve a SelectionNode into a sorted, unique list of channel numbers."""
        if selection is None:
            return list(getattr(self.app, "selected_channels", []))

        # 1. Resolve positive items
        included: set[int] = set()
        for item in selection.items:
            included.update(self._resolve_selection_item(item))

        # 2. Resolve exclusions
        excluded: set[int] = set()
        for item in selection.exclusions:
            excluded.update(self._resolve_selection_item(item))

        final_set = included - excluded

        # 3. Apply odd/even filter
        if selection.filter_mode == "odd":
            final_set = {ch for ch in final_set if ch % 2 == 1}
        elif selection.filter_mode == "even":
            final_set = {ch for ch in final_set if ch % 2 == 0}

        return sorted(ch for ch in final_set if 1 <= ch <= MAX_CHANNELS)

    def _resolve_selection_item(  # pylint: disable=too-many-return-statements
        self, item: SelectionItemNode
    ) -> set[int]:
        if isinstance(item, ChannelNumberNode):
            return {item.channel} if 1 <= item.channel <= MAX_CHANNELS else set()

        if isinstance(item, ChannelRangeNode):
            low = min(item.start, item.end)
            high = max(item.start, item.end)
            return {ch for ch in range(low, high + 1) if 1 <= ch <= MAX_CHANNELS}

        if isinstance(item, GroupSelectionNode):
            if hasattr(self.app, "lightshow") and self.app.lightshow:
                groups = getattr(self.app.lightshow, "groups", {})
                if item.group_id in groups:
                    grp = groups[item.group_id]
                    channels = getattr(grp, "channels", [])
                    return {ch for ch in channels if 1 <= ch <= MAX_CHANNELS}
            return set()

        if isinstance(item, AllSelectionNode):
            # If patch exists, select all patched channels/devices;
            # otherwise channels with level > 0
            if (
                hasattr(self.app, "lightshow")
                and self.app.lightshow
                and hasattr(self.app.lightshow, "patch")
            ):
                patch_mgr = self.app.lightshow.patch
                patched = [
                    ch
                    for ch, outs in getattr(patch_mgr, "channels", {}).items()
                    if outs and outs != [[None, None]] and None not in outs[0]
                ]
                if patched:
                    return set(patched)
            # Fallback to all channels with level > 0 or 1..MAX_CHANNELS
            backend = getattr(self.app, "backend", None)
            if backend and getattr(backend, "dmx", None):
                levels = backend.dmx.levels.get("user", [])
                active = {i + 1 for i, lvl in enumerate(levels) if lvl > 0}
                if active:
                    return active
            return set(range(1, 101))  # Default first 100 channels

        return set()

    # --- Command Implementations ---

    def _execute_select_only(self, node: SelectOnlyCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        self.app.selected_channels = list(channels)
        self.app.last_selected_channel = channels[-1] if channels else None
        self.app.emit("channels.selected_changed", channels)
        return CommandResult(
            True, f"Selected {len(channels)} channel(s)", affected_channels=channels
        )

    def _execute_intensity(self, node: IntensityCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if node.selection is not None:
            self.app.selected_channels = list(channels)
            self.app.last_selected_channel = channels[-1] if channels else None
            self.app.emit("channels.selected_changed", channels)

        if not channels:
            return CommandResult(False, "No channels selected")

        backend = getattr(self.app, "backend", None)
        levels_dict: dict[int, int] = {}

        for ch in channels:
            if node.is_relative:
                current_raw = (
                    backend.dmx.levels["user"][ch - 1]
                    if backend and getattr(backend, "dmx", None)
                    else 0
                )
                current_pct = (current_raw / 255.0) * 100.0
                new_pct = max(0.0, min(100.0, current_pct + node.level))
                target_level = int(round((new_pct / 100.0) * 255.0))
            else:
                target_level = int(round((node.level / 100.0) * 255.0))

            target_level = max(0, min(255, target_level))
            levels_dict[ch] = target_level

            if backend and getattr(backend, "dmx", None):
                backend.dmx.levels["user"][ch - 1] = target_level

            # Update lighting device virtual dimmer or intensity if patched
            if (
                hasattr(self.app, "lightshow")
                and self.app.lightshow
                and hasattr(self.app.lightshow, "patch")
            ):
                dev = self.app.lightshow.patch.get_device(ch)
                if dev is not None and hasattr(dev, "set_intensity"):
                    dev.set_intensity(target_level / 255.0)

            self.app.emit("channel.level_changed", ch, target_level)

        if backend and getattr(backend, "dmx", None):
            if hasattr(self.app, "lightshow") and self.app.lightshow.main_playback:
                self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        return CommandResult(
            True,
            f"Set {len(channels)} channel(s) intensity to {node.level:.1f}%",
            affected_channels=channels,
        )

    def _execute_attribute(  # pylint: disable=too-many-branches
        self, node: AttributeCommandNode
    ) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if node.selection is not None:
            self.app.selected_channels = list(channels)
            self.app.last_selected_channel = channels[-1] if channels else None
            self.app.emit("channels.selected_changed", channels)

        if not channels:
            return CommandResult(False, "No channels selected")

        # Apply intensity first if specified
        if node.intensity_level is not None:
            self._execute_intensity(
                IntensityCommandNode(
                    selection=None,
                    level=node.intensity_level,
                    is_relative=node.is_intensity_relative,
                )
            )

        patch = getattr(
            getattr(self.app, "lightshow", None),
            "patch",
            None,
        )

        for ch in channels:
            dev = patch.get_device(ch) if patch is not None else None

            for attr, val in node.attributes.items():
                if dev is None:
                    continue

                if attr == "pan" and hasattr(dev, "set_pan_degrees"):
                    dev.set_pan_degrees(float(val))
                elif attr == "tilt" and hasattr(dev, "set_tilt_degrees"):
                    dev.set_tilt_degrees(float(val))
                elif attr == "zoom" and hasattr(dev, "set_zoom_degrees"):
                    dev.set_zoom_degrees(float(val))
                elif attr == "focus" and hasattr(dev, "set_focus_meters"):
                    dev.set_focus_meters(float(val))
                elif attr == "strobe" and hasattr(dev, "set_strobe_hz"):
                    dev.set_strobe_hz(float(val))
                elif attr == "cct" and hasattr(dev, "set_color_temp_kelvin"):
                    dev.set_color_temp_kelvin(float(val))
                elif attr == "color":
                    self._apply_device_color(dev, str(val))

        # Push levels to DMX backend if available
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            backend.dmx.set_levels()

        attr_names = list(node.attributes.keys())
        return CommandResult(
            True,
            f"Applied attributes {attr_names} on {len(channels)} channel(s)",
            affected_channels=channels,
        )

    def _apply_device_color(self, dev: typing.Any, color_str: str) -> None:  # noqa: ANN401
        color_hex = COLOR_PRESETS.get(color_str.upper(), color_str)
        if color_hex.startswith("#") and len(color_hex) in (7, 9):
            try:
                r = int(color_hex[1:3], 16) / 255.0
                g = int(color_hex[3:5], 16) / 255.0
                b = int(color_hex[5:7], 16) / 255.0
                if hasattr(dev, "set_color_srgb"):
                    dev.set_color_srgb(r, g, b)
                elif hasattr(dev, "set_rgb"):
                    dev.set_rgb(r, g, b)
                elif hasattr(dev, "apply_device_values"):
                    dev.apply_device_values({"color": color_hex})
            except ValueError:
                pass

    def _execute_record_cue(  # pylint: disable=too-many-locals,too-many-branches
        self, node: RecordCueCommandNode
    ) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow or not lightshow.main_playback:
            return CommandResult(False, "Main playback sequence not available")

        main_playback = lightshow.main_playback

        # Capture current channel and device levels
        channels_dict: dict[int, int] = {}
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels.get("user", [])
            limit = min(MAX_CHANNELS, len(user_levels))
            for ch in range(1, limit + 1):
                lvl = int(user_levels[ch - 1])
                if lvl > 0:
                    channels_dict[ch] = lvl

        # Capture moving light parameters
        device_values: dict[int, dict[str, typing.Any]] = {}
        patch = getattr(lightshow, "patch", None)
        if patch is not None:
            for dev_id, dev in patch.devices.items():
                vals = self._get_device_active_values(dev)
                if vals:
                    device_values[dev_id] = vals

        # Check if cue already exists in sequence
        existing_cue = lightshow.cues.get(node.cue_id, 1)
        if existing_cue is not None:
            existing_cue.channels = channels_dict
            existing_cue.device_values = device_values
            if node.is_block:
                existing_cue.is_block = True
            cue = existing_cue
        else:
            cue = Cue(
                sequence=1,
                number=node.cue_id,
                channels=channels_dict,
                device_values=device_values,
                is_block=node.is_block,
            )
            lightshow.cues.add(cue)

        # Create or update step in main_playback
        step = None
        for s in main_playback.steps:
            if s.cue and s.cue.number == node.cue_id:
                step = s
                break
        if step is None:
            time_in = node.time_in if node.time_in is not None else 5.0
            time_out = node.time_out if node.time_out is not None else time_in
            delay_in = node.delay if node.delay is not None else 0.0
            step = Step(
                sequence=main_playback.index,
                cue=cue,
                time_in=time_in,
                time_out=time_out,
                delay_in=delay_in,
            )
            main_playback.steps.append(step)
            main_playback.last = len(main_playback.steps)
        else:
            if node.time_in is not None:
                step.time_in = node.time_in
                step.time_out = (
                    node.time_out if node.time_out is not None else node.time_in
                )
            if node.delay is not None:
                step.delay_in = node.delay
            step.update_total_time()

        lightshow.set_modified()
        self.app.emit("cue.created", 1, node.cue_id)
        return CommandResult(True, f"Recorded Cue {node.cue_id}")

    def _execute_update_cue(self, node: UpdateCueCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow or not lightshow.main_playback:
            return CommandResult(False, "Main playback sequence not available")

        cue_num = node.cue_id
        if cue_num is None:
            # Use current cue from playback
            step = lightshow.main_playback.get_current_step()
            if not step or not step.cue:
                return CommandResult(False, "No active cue to update")
            cue_num = step.cue.number

        cue = lightshow.cues.get(cue_num, 1)
        if cue is None:
            return CommandResult(False, f"Cue {cue_num} does not exist")

        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels.get("user", [])
            limit = min(MAX_CHANNELS, len(user_levels))
            for ch in range(1, limit + 1):
                lvl = int(user_levels[ch - 1])
                if lvl > 0:
                    cue.channels[ch] = lvl
                elif ch in cue.channels:
                    cue.channels[ch] = 0

        lightshow.set_modified()
        self.app.emit("cue.updated", 1, cue_num)
        return CommandResult(True, f"Updated Cue {cue_num}")

    def _execute_goto_cue(self, node: GotoCueCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow or not lightshow.main_playback:
            return CommandResult(False, "Main playback sequence not available")

        lightshow.main_playback.goto(str(node.cue_id))
        return CommandResult(True, f"Jumped to Cue {node.cue_id}")

    def _execute_block_cue(
        self, node: BlockCueCommandNode | UnblockCueCommandNode, is_block: bool
    ) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow:
            return CommandResult(False, "LightShow not available")

        cue = lightshow.cues.get(node.cue_id, 1)
        if cue is None:
            return CommandResult(False, f"Cue {node.cue_id} not found")

        cue.is_block = is_block
        lightshow.set_modified()
        action_name = "Blocked" if is_block else "Unblocked"
        return CommandResult(True, f"{action_name} Cue {node.cue_id}")

    def _execute_delete_cue(self, node: DeleteCueCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow:
            return CommandResult(False, "LightShow not available")

        cue = lightshow.cues.get(node.cue_id, 1)
        if cue is None:
            return CommandResult(False, f"Cue {node.cue_id} not found")

        lightshow.cues.remove(cue)
        if lightshow.main_playback:
            for step in list(lightshow.main_playback.steps):
                if step.cue and step.cue.number == node.cue_id:
                    lightshow.main_playback.steps.remove(step)
            lightshow.main_playback.last = len(lightshow.main_playback.steps)

        lightshow.set_modified()
        self.app.emit("cue.deleted", 1, node.cue_id)
        return CommandResult(True, f"Deleted Cue {node.cue_id}")

    def _get_device_active_values(self, dev: typing.Any) -> dict[str, typing.Any]:  # noqa: ANN401
        """Extract active physical parameters from a device instance."""
        vals: dict[str, typing.Any] = {}
        if hasattr(dev, "pan_degrees") and getattr(dev, "pan_degrees", 0.0) != 0.0:
            vals["pan"] = dev.pan_degrees
        if hasattr(dev, "tilt_degrees") and getattr(dev, "tilt_degrees", 0.0) != 0.0:
            vals["tilt"] = dev.tilt_degrees
        if hasattr(dev, "zoom_degrees") and dev.zoom_degrees is not None:
            vals["zoom"] = dev.zoom_degrees
        if hasattr(dev, "color_srgb") and hasattr(dev.color_srgb, "to_hex"):
            vals["color"] = dev.color_srgb.to_hex()
        return vals

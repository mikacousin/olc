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

from olc.actions.effect import (
    EffectApplyAction,
    EffectDeleteAction,
    EffectRenameAction,
    EffectStopAction,
    EffectUpdateAction,
    format_effect_number,
)
from olc.actions.group import (
    DeleteGroupAction,
    GroupRenameAction,
    GroupUpdateChannelsAction,
    NewGroupAction,
)
from olc.actions.palette import (
    PaletteApplyAction,
    PaletteDeleteAction,
    PaletteRecordAction,
    PaletteUpdateAction,
    format_palette_label,
)
from olc.core.parser.ast_nodes import (
    AddressLevelCommandNode,
    AddressNumberNode,
    AddressParkCommandNode,
    AddressRangeNode,
    AddressSelectionNode,
    AddressUnparkCommandNode,
    AllSelectionNode,
    ApplyEffectCommandNode,
    ApplyPaletteCommandNode,
    AttributeCommandNode,
    BlockCueCommandNode,
    ChannelCheckCommandNode,
    ChannelNumberNode,
    ChannelParkCommandNode,
    ChannelRangeNode,
    ChannelUnparkCommandNode,
    CommandNode,
    DeleteCueCommandNode,
    DeleteEffectCommandNode,
    DeleteGroupCommandNode,
    DeletePaletteCommandNode,
    EditEffectCommandNode,
    GotoCueCommandNode,
    GroupSelectionNode,
    HomeCommandNode,
    IntensityCommandNode,
    LabelGroupCommandNode,
    LocateCommandNode,
    ParkUnparkAllCommandNode,
    PatchCommandNode,
    RecordCueCommandNode,
    RecordGroupCommandNode,
    RecordPaletteCommandNode,
    RelativeThruNode,
    SelectionItemNode,
    SelectionNode,
    SelectOnlyCommandNode,
    SneakCommandNode,
    StopEffectCommandNode,
    UnblockCueCommandNode,
    UnpatchCommandNode,
    UpdateCueCommandNode,
    UpdateGroupCommandNode,
    UpdatePaletteCommandNode,
)
from olc.core.tracking import TrackingEngine
from olc.define import MAX_CHANNELS
from olc.devices.channel import ChannelType
from olc.devices.device import FixtureType
from olc.show.cue import Cue
from olc.show.palette import PaletteRef
from olc.show.step import Step

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.lightshow import LightShow


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

        if isinstance(node, SneakCommandNode):
            return self._execute_sneak(node)

        if isinstance(node, HomeCommandNode):
            return self._execute_home(node)

        if isinstance(node, LocateCommandNode):
            return self._execute_locate(node)

        if isinstance(node, ChannelParkCommandNode):
            return self._execute_channel_park(node)

        if isinstance(node, ChannelUnparkCommandNode):
            return self._execute_channel_unpark(node)

        if isinstance(node, AddressParkCommandNode):
            return self._execute_address_park(node)

        if isinstance(node, AddressLevelCommandNode):
            return self._execute_address_level(node)

        if isinstance(node, ChannelCheckCommandNode):
            return self._execute_channel_check(node)

        if isinstance(node, AddressUnparkCommandNode):
            return self._execute_address_unpark(node)

        if isinstance(node, ParkUnparkAllCommandNode):
            return self._execute_park_unpark_all(node)

        if isinstance(node, PatchCommandNode):
            return self._execute_patch(node)

        if isinstance(node, UnpatchCommandNode):
            return self._execute_unpatch(node)

        if isinstance(node, ApplyPaletteCommandNode):
            return self._execute_apply_palette(node)

        if isinstance(node, RecordPaletteCommandNode):
            return self._execute_record_palette(node)

        if isinstance(node, UpdatePaletteCommandNode):
            return self._execute_update_palette(node)

        if isinstance(node, DeletePaletteCommandNode):
            return self._execute_delete_palette(node)

        if isinstance(node, ApplyEffectCommandNode):
            return self._execute_apply_effect(node)

        if isinstance(node, StopEffectCommandNode):
            return self._execute_stop_effect(node)

        if isinstance(node, EditEffectCommandNode):
            return self._execute_edit_effect(node)

        if isinstance(node, DeleteEffectCommandNode):
            return self._execute_delete_effect(node)

        if isinstance(node, RecordGroupCommandNode):
            return self._execute_record_group(node)

        if isinstance(node, UpdateGroupCommandNode):
            return self._execute_update_group(node)

        if isinstance(node, DeleteGroupCommandNode):
            return self._execute_delete_group(node)

        if isinstance(node, LabelGroupCommandNode):
            return self._execute_label_group(node)

        return CommandResult(False, f"Unsupported command node: {type(node).__name__}")

    # --- Selection Resolution ---

    def resolve_selection(self, selection: SelectionNode | None) -> list[int]:
        """Resolve a SelectionNode into a sorted, unique list of channel numbers."""
        if selection is None:
            return list(getattr(self.app, "selected_channels", []))

        # 1. Resolve positive items
        included: set[int] = set()
        if selection.is_relative:
            included.update(getattr(self.app, "selected_channels", []))

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

    def resolve_ordered_selection(self, selection: SelectionNode | None) -> list[int]:
        """Resolve a SelectionNode preserving explicit channel order (for Effects)."""
        if selection is None:
            return list(getattr(self.app, "selected_channels", []))

        ordered: list[int] = []
        if selection.is_relative:
            ordered.extend(getattr(self.app, "selected_channels", []))

        for item in selection.items:
            ordered.extend(self._resolve_ordered_selection_item(item))

        excluded: set[int] = set()
        for item in selection.exclusions:
            excluded.update(self._resolve_selection_item(item))

        result: list[int] = []
        seen: set[int] = set()
        for ch in ordered:
            if ch in excluded or ch in seen or not 1 <= ch <= MAX_CHANNELS:
                continue
            if selection.filter_mode == "odd" and ch % 2 == 0:
                continue
            if selection.filter_mode == "even" and ch % 2 == 1:
                continue
            seen.add(ch)
            result.append(ch)
        return result

    def _resolve_ordered_selection_item(self, item: SelectionItemNode) -> list[int]:
        if isinstance(item, ChannelNumberNode):
            return [item.channel] if 1 <= item.channel <= MAX_CHANNELS else []

        if isinstance(item, ChannelRangeNode):
            step = 1 if item.end >= item.start else -1
            return [
                ch
                for ch in range(item.start, item.end + step, step)
                if 1 <= ch <= MAX_CHANNELS
            ]

        if isinstance(item, RelativeThruNode):
            last_sel = getattr(self.app, "last_selected_channel", None)
            if last_sel is not None:
                start_val = int(last_sel)
            else:
                active = getattr(self.app, "selected_channels", [])
                start_val = int(active[-1]) if active else 1
            step = 1 if item.end >= start_val else -1
            return [
                ch
                for ch in range(start_val, item.end + step, step)
                if 1 <= ch <= MAX_CHANNELS
            ]

        if isinstance(item, GroupSelectionNode):
            if hasattr(self.app, "lightshow") and self.app.lightshow:
                groups = getattr(self.app.lightshow, "groups", None)
                grp = None
                if isinstance(groups, dict):
                    grp = groups.get(item.group_id) or groups.get(float(item.group_id))
                elif groups is not None and hasattr(groups, "get"):
                    grp = groups.get(float(item.group_id))
                if grp is not None:
                    channels = getattr(grp, "channels", [])
                    return [int(ch) for ch in channels if 1 <= int(ch) <= MAX_CHANNELS]
            return []

        return sorted(self._resolve_selection_item(item))

    def _resolve_selection_item(  # pylint: disable=too-many-return-statements
        self, item: SelectionItemNode
    ) -> set[int]:
        if isinstance(item, ChannelNumberNode):
            return {item.channel} if 1 <= item.channel <= MAX_CHANNELS else set()

        if isinstance(item, ChannelRangeNode):
            low = min(item.start, item.end)
            high = max(item.start, item.end)
            return {ch for ch in range(low, high + 1) if 1 <= ch <= MAX_CHANNELS}

        if isinstance(item, RelativeThruNode):
            last_sel = getattr(self.app, "last_selected_channel", None)
            if last_sel is not None:
                start_val = last_sel
            else:
                active = getattr(self.app, "selected_channels", [])
                start_val = active[-1] if active else 1
            low = min(start_val, item.end)
            high = max(start_val, item.end)
            return {ch for ch in range(low, high + 1) if 1 <= ch <= MAX_CHANNELS}

        if isinstance(item, GroupSelectionNode):
            if hasattr(self.app, "lightshow") and self.app.lightshow:
                groups = getattr(self.app.lightshow, "groups", None)
                grp = None
                if isinstance(groups, dict):
                    grp = groups.get(item.group_id) or groups.get(float(item.group_id))
                elif groups is not None and hasattr(groups, "get"):
                    grp = groups.get(float(item.group_id))
                if grp is not None:
                    channels = getattr(grp, "channels", [])
                    return {int(ch) for ch in channels if 1 <= int(ch) <= MAX_CHANNELS}
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
                patched_set: set[int] = set(getattr(patch_mgr, "devices", {}).keys())
                patched_set.update(
                    ch
                    for ch, outs in getattr(patch_mgr, "channels", {}).items()
                    if outs and outs != [[None, None]] and None not in outs[0]
                )
                if patched_set:
                    return patched_set
            # Fallback to all channels with level > 0 or 1..MAX_CHANNELS
            backend = getattr(self.app, "backend", None)
            if backend and getattr(backend, "dmx", None):
                levels = backend.dmx.levels.get("user", [])
                active = {i + 1 for i, lvl in enumerate(levels) if lvl > 0}
                if active:
                    return active
            return set(range(1, 101))  # Default first 100 channels

        return set()

    def _get_registry(self) -> typing.Any:  # noqa: ANN401
        """Get the application action registry if available."""
        return getattr(self.app, "action_registry", getattr(self.app, "actions", None))

    # --- Command Implementations ---

    def _execute_select_only(self, node: SelectOnlyCommandNode) -> CommandResult:
        channels = self.resolve_ordered_selection(node.selection)
        last_sel: int | None = None
        if node.selection.items:
            last_item = node.selection.items[-1]
            if isinstance(last_item, ChannelNumberNode):
                last_sel = last_item.channel
            elif isinstance(last_item, (ChannelRangeNode, RelativeThruNode)):
                last_sel = last_item.end
        if last_sel not in channels:
            last_sel = channels[-1] if channels else None

        registry = self._get_registry()
        if registry is not None and "channel.select_channels" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute(
                "channel.select_channels",
                channels=channels,
                last_selected=last_sel,
            )
        else:
            self.app.selected_channels = list(channels)
            self.app.last_selected_channel = last_sel
            self.app.emit("channels.selected_changed", channels)

        return CommandResult(
            True, f"Selected {len(channels)} channel(s)", affected_channels=channels
        )

    def _execute_intensity(self, node: IntensityCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        registry = self._get_registry()

        if node.selection is not None:
            last_sel = channels[-1] if channels else None
            if registry is not None and "channel.select_channels" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "channel.select_channels",
                    channels=channels,
                    last_selected=last_sel,
                )
            else:
                self.app.selected_channels = list(channels)
                self.app.last_selected_channel = last_sel
                self.app.emit("channels.selected_changed", channels)

        if not channels:
            return CommandResult(False, "No channels selected")

        backend = getattr(self.app, "backend", None)
        levels_dict: dict[int, float] = {}

        for ch in channels:
            if node.is_relative:
                current_raw = (
                    float(backend.dmx.levels["user"][ch - 1])
                    if backend and getattr(backend, "dmx", None)
                    else 0.0
                )
                current_pct = max(0.0, current_raw) * 100.0
                new_pct = max(0.0, min(100.0, current_pct + node.level))
                target_level = new_pct / 100.0
            else:
                target_level = node.level / 100.0

            target_level = max(0.0, min(1.0, target_level))
            levels_dict[ch] = target_level

        if registry is not None and "channel.set_multi_levels" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute(
                "channel.set_multi_levels",
                levels=levels_dict,
            )
        else:
            for ch, target_level in levels_dict.items():
                if backend and getattr(backend, "dmx", None):
                    backend.dmx.levels["user"][ch - 1] = target_level
                if (
                    hasattr(self.app, "lightshow")
                    and self.app.lightshow
                    and hasattr(self.app.lightshow, "patch")
                ):
                    dev = self.app.lightshow.patch.get_device(ch)
                    if dev is not None and hasattr(dev, "set_intensity"):
                        dev.set_intensity(target_level)
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
        registry = self._get_registry()

        if node.selection is not None:
            last_sel = channels[-1] if channels else None
            if registry is not None and "channel.select_channels" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "channel.select_channels",
                    channels=channels,
                    last_selected=last_sel,
                )
            else:
                self.app.selected_channels = list(channels)
                self.app.last_selected_channel = last_sel
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

        # Handle Pan & Tilt via device.set_pan_tilt
        if "pan" in node.attributes or "tilt" in node.attributes:
            pan_val = (
                float(node.attributes["pan"]) if "pan" in node.attributes else None
            )
            tilt_val = (
                float(node.attributes["tilt"]) if "tilt" in node.attributes else None
            )
            if registry is not None and "device.set_pan_tilt" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "device.set_pan_tilt",
                    pan=pan_val,
                    tilt=tilt_val,
                    channels=channels,
                )
            else:
                patch = getattr(getattr(self.app, "lightshow", None), "patch", None)
                live_state = getattr(self.app, "live_state", None)
                if patch is not None:
                    for ch in channels:
                        dev = patch.get_device(ch)
                        if dev is not None:
                            edited: list[str] = []
                            if pan_val is not None and hasattr(dev, "set_pan_degrees"):
                                dev.set_pan_degrees(pan_val)
                                edited.append("pan")
                            if tilt_val is not None and hasattr(
                                dev, "set_tilt_degrees"
                            ):
                                dev.set_tilt_degrees(tilt_val)
                                edited.append("tilt")
                            if live_state is not None and edited:
                                live_state.mark_manual_params(
                                    ch, edited, break_refs=True
                                )

        # Handle Color via device.set_color
        if "color" in node.attributes:
            color_str = str(node.attributes["color"])
            color_hex = COLOR_PRESETS.get(color_str.upper(), color_str)
            rgb = None
            if color_hex.startswith("#") and len(color_hex) in (7, 9):
                try:
                    rgb = (
                        int(color_hex[1:3], 16) / 255.0,
                        int(color_hex[3:5], 16) / 255.0,
                        int(color_hex[5:7], 16) / 255.0,
                    )
                except ValueError:
                    pass
            has_color_act = bool(
                registry is not None
                and "device.set_color" in getattr(registry, "_action_classes", {})
            )
            if rgb is not None and has_color_act and registry is not None:
                registry.execute(
                    "device.set_color",
                    r=rgb[0],
                    g=rgb[1],
                    b=rgb[2],
                    channels=channels,
                )
            else:
                patch = getattr(getattr(self.app, "lightshow", None), "patch", None)
                if patch is not None:
                    for ch in channels:
                        dev = patch.get_device(ch)
                        if dev is not None:
                            self._apply_device_color(dev, color_str)

        # Handle other device parameters via device.set_parameter
        for attr, val in node.attributes.items():
            if attr in ("pan", "tilt", "color"):
                continue
            if registry is not None and "device.set_parameter" in getattr(
                registry, "_action_classes", {}
            ):
                try:
                    registry.execute(
                        "device.set_parameter",
                        parameter=attr,
                        value=float(val),
                        channels=channels,
                        is_physical=True,
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    self._apply_direct_parameter(channels, attr, val)
            else:
                self._apply_direct_parameter(channels, attr, val)

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

    def _apply_direct_parameter(
        self,
        channels: list[int],
        attr: str,
        val: typing.Any,  # noqa: ANN401
    ) -> None:
        patch = getattr(getattr(self.app, "lightshow", None), "patch", None)
        if patch is None:
            return
        live_state = getattr(self.app, "live_state", None)
        attr_key = str(attr).lower()
        for ch in channels:
            dev = patch.get_device(ch)
            if dev is None:
                continue
            modified = False
            if hasattr(dev, "apply_device_parameter"):
                dev.apply_device_parameter(attr, val)
                modified = True
            elif attr == "zoom" and hasattr(dev, "set_zoom_degrees"):
                dev.set_zoom_degrees(float(val))
                modified = True
            elif attr == "focus" and hasattr(dev, "set_focus_meters"):
                dev.set_focus_meters(float(val))
                modified = True
            elif attr == "strobe" and hasattr(dev, "set_strobe_hz"):
                dev.set_strobe_hz(float(val))
                modified = True
            elif attr == "cct" and hasattr(dev, "set_color_temp_kelvin"):
                dev.set_color_temp_kelvin(float(val))
                modified = True
            if modified and live_state is not None:
                live_state.mark_manual_params(ch, (attr_key,), break_refs=True)

    def _apply_device_color(self, dev: typing.Any, color_str: str) -> None:  # noqa: ANN401
        color_hex = COLOR_PRESETS.get(color_str.upper(), color_str)
        if color_hex.startswith("#") and len(color_hex) in (7, 9):
            try:
                r = int(color_hex[1:3], 16) / 255.0
                g = int(color_hex[3:5], 16) / 255.0
                b = int(color_hex[5:7], 16) / 255.0
                applied = False
                if hasattr(dev, "set_color_srgb"):
                    dev.set_color_srgb(r, g, b)
                    applied = True
                elif hasattr(dev, "set_rgb"):
                    dev.set_rgb(r, g, b)
                    applied = True
                elif hasattr(dev, "apply_device_values"):
                    dev.apply_device_values({"color": color_hex})
                    applied = True
                live_state = getattr(self.app, "live_state", None)
                dev_id = getattr(dev, "fixture_id", None)
                if applied and live_state is not None and isinstance(dev_id, int):
                    live_state.mark_manual_params(dev_id, ("color",), break_refs=True)
            except ValueError:
                pass

    def _execute_home(self, node: HomeCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels selected for HOME")

        if node.selection is not None:
            self.app.selected_channels = list(channels)

        registry = getattr(
            self.app, "action_registry", getattr(self.app, "actions", None)
        )
        if registry is None:
            return CommandResult(False, "Action registry not available")

        registry.execute("device.home", channels=channels, category=node.category)

        cat_str = f" {node.category.upper()}" if node.category else ""
        return CommandResult(
            True,
            f"Homed{cat_str} on {len(channels)} fixture(s)",
            affected_channels=channels,
        )

    def _execute_locate(self, node: LocateCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels selected for LOCATE")

        if node.selection is not None:
            self.app.selected_channels = list(channels)

        registry = getattr(
            self.app, "action_registry", getattr(self.app, "actions", None)
        )
        if registry is None:
            return CommandResult(False, "Action registry not available")

        registry.execute("device.locate", channels=channels)

        return CommandResult(
            True,
            f"Located {len(channels)} fixture(s) at full",
            affected_channels=channels,
        )

    def _execute_sneak(self, node: SneakCommandNode) -> CommandResult:
        sneak_ctrl = getattr(self.app, "sneak_controller", None)
        if sneak_ctrl is None:
            return CommandResult(False, "Sneak controller not available")

        # Case 1: Sneak independents
        if node.independents is not None:
            affected = sneak_ctrl.sneak_independents(
                numbers=node.independents, duration=node.duration
            )
            time_str = (
                f" in {node.duration:.1f}s"
                if node.duration is not None
                else f" in {sneak_ctrl.get_default_sneak_time():.1f}s"
            )
            return CommandResult(
                True,
                f"Sneaking independent(s) {affected}{time_str}",
            )

        # Case 2: Sneak channels
        if node.selection is not None:
            target_channels: list[int] | None = self.resolve_selection(node.selection)
            self.app.selected_channels = list(target_channels)
            self.app.last_selected_channel = (
                target_channels[-1] if target_channels else None
            )
            self.app.emit("channels.selected_changed", target_channels)
        else:
            active_sel = list(getattr(self.app, "selected_channels", []))
            target_channels = active_sel if active_sel else None

        affected_ch = sneak_ctrl.sneak_channels(
            channels=target_channels, duration=node.duration
        )
        if not affected_ch:
            if target_channels is not None:
                return CommandResult(True, "No manual levels on selected channel(s)")
            return CommandResult(True, "No manual levels to sneak")

        time_str = (
            f" in {node.duration:.1f}s"
            if node.duration is not None
            else f" in {sneak_ctrl.get_default_sneak_time():.1f}s"
        )
        return CommandResult(
            True,
            f"Sneaking {len(affected_ch)} channel(s){time_str}",
            affected_channels=affected_ch,
        )

    def _capture_live_cue_state(
        self, lightshow: LightShow
    ) -> tuple[dict[int, float], dict[int, dict[str, typing.Any]]]:
        """Capture current live user channel levels and device values."""
        channels_dict: dict[int, float] = {}
        excluded_fader_chs: set[int] = set()
        non_excluded_fader_chs: set[int] = set()
        fader_bank = getattr(lightshow, "fader_bank", None)
        if fader_bank is not None:
            for fader in getattr(fader_bank, "active_faders", ()):
                if float(getattr(fader, "level", 0.0)) <= 0.0:
                    continue
                if getattr(fader, "inhibitive", False):
                    continue
                f_chs = getattr(fader, "channels", ())
                if getattr(fader, "exclude_record", False):
                    excluded_fader_chs.update(int(c) for c in f_chs)
                else:
                    non_excluded_fader_chs.update(int(c) for c in f_chs)
        record_excluded_chs = excluded_fader_chs - non_excluded_fader_chs

        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels.get("user", [])
            limit = min(MAX_CHANNELS, len(user_levels))
            for ch in range(1, limit + 1):
                lvl = float(user_levels[ch - 1])
                if lvl > 0.0 and ch not in record_excluded_chs:
                    channels_dict[ch] = lvl

        device_values: dict[int, dict[str, typing.Any]] = {}
        patch = getattr(lightshow, "patch", None)
        if patch is not None:
            for dev_id, dev in patch.devices.items():
                if dev_id in record_excluded_chs:
                    continue
                vals = self._get_device_active_values(dev)
                dev_int = float(getattr(dev, "intensity", 0.0))
                if dev_id in channels_dict:
                    dev_int = max(dev_int, channels_dict[dev_id])
                elif dev_int > 0.0:
                    channels_dict[dev_id] = dev_int
                if dev_int > 0.0:
                    vals["intensity"] = dev_int
                if vals:
                    device_values[dev_id] = vals

        return channels_dict, device_values

    def _capture_live_palette_refs(  # pylint: disable=too-many-locals,too-many-branches
        self,
        lightshow: LightShow,
        channels_dict: dict[int, float],
        device_values: dict[int, dict[str, typing.Any]],
        *,
        base_refs: dict[int, dict[str, PaletteRef]] | None = None,
    ) -> dict[int, dict[str, PaletteRef]]:
        """Build cue palette_refs by merging active base refs with live overrides."""
        if base_refs is not None:
            source_base = base_refs
        else:
            source_base = {}
            main_pb = getattr(lightshow, "main_playback", None)
            steps = getattr(main_pb, "steps", None) if main_pb is not None else None
            pos = getattr(main_pb, "position", -1) if main_pb is not None else -1
            if isinstance(steps, list) and 0 <= pos < len(steps):
                resolved = TrackingEngine.resolve_step_state(
                    main_pb,
                    pos,
                    tracking_mode=bool(getattr(main_pb, "tracking_mode", False)),
                    patch=getattr(lightshow, "patch", None),
                )
                source_base = getattr(resolved, "palette_refs", {}) or {}

        live_state = getattr(self.app, "live_state", None)
        alias_lookup: dict[str, tuple[str, ...]] = {
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

        result: dict[int, dict[str, PaletteRef]] = {}
        all_channels = set(channels_dict.keys()) | set(device_values.keys())
        for ch in sorted(all_channels):
            ch_base = source_base.get(ch, {})
            wildcard_ref = ch_base.get("*")
            ch_manual = (
                live_state.get_manual_params(ch) if live_state is not None else set()
            )
            if wildcard_ref is not None and not ch_manual and len(ch_base) == 1:
                result[ch] = {"*": (str(wildcard_ref[0]), float(wildcard_ref[1]))}
                continue

            recorded_params: list[str] = list(device_values.get(ch, {}).keys())
            if ch in channels_dict and "intensity" not in recorded_params:
                recorded_params.append("intensity")

            ch_refs: dict[str, PaletteRef] = {}
            for param_name in recorded_params:
                if live_state is not None and live_state.is_param_manual(
                    ch, param_name
                ):
                    live_ref = live_state.get_palette_ref(ch, param_name)
                    if live_ref is not None:
                        ch_refs[param_name] = (str(live_ref[0]), float(live_ref[1]))
                    continue

                p_low = str(param_name).lower()
                found: PaletteRef | None = None
                for cand in (param_name, p_low, *alias_lookup.get(p_low, ())):
                    if cand in ch_base:
                        found = ch_base[cand]
                        break
                if found is None and wildcard_ref is not None:
                    found = wildcard_ref
                if found is not None:
                    ch_refs[param_name] = (str(found[0]), float(found[1]))

            if ch_refs:
                result[ch] = ch_refs
        return result

    def _capture_live_effect_refs(  # pylint: disable=too-many-locals,too-many-branches
        self,
        lightshow: LightShow,
        *,
        base_refs: dict[int, dict[str, typing.Any]] | None = None,
    ) -> dict[int, dict[str, typing.Any]]:
        """Build cue effect_refs by merging active/running effects with live state."""
        if base_refs is not None:
            source_base = {int(ch): dict(spec) for ch, spec in base_refs.items()}
        else:
            source_base = {}
            main_pb = getattr(lightshow, "main_playback", None)
            steps = getattr(main_pb, "steps", None) if main_pb is not None else None
            pos = getattr(main_pb, "position", -1) if main_pb is not None else -1
            if isinstance(steps, list) and 0 <= pos < len(steps):
                resolved = TrackingEngine.resolve_step_state(
                    main_pb,
                    pos,
                    tracking_mode=bool(getattr(main_pb, "tracking_mode", False)),
                    patch=getattr(lightshow, "patch", None),
                )
                raw_base = getattr(resolved, "effect_refs", {}) or {}
                source_base = {int(ch): dict(spec) for ch, spec in raw_base.items()}

        # Also include currently running engine instances so recording sequential cues
        # before GO still captures running effects and stomps against earlier cues.
        eff_eng = getattr(self.app, "effects_engine", None)
        if eff_eng is not None and hasattr(eff_eng, "get_active_instances"):
            for inst in eff_eng.get_active_instances():
                if getattr(inst, "remove_on_fade_end", False):
                    continue
                for idx, ch in enumerate(inst.channels):
                    ch_int = int(ch)
                    if ch_int not in source_base:
                        entry: dict[str, typing.Any] = {
                            "effect": float(inst.effect_number),
                            "order_index": idx,
                            "channels": list(inst.channels),
                            "rate_scale": float(inst.rate_scale),
                            "size_scale": float(inst.size_scale),
                        }
                        if inst.groups_override is not None:
                            entry["groups"] = int(inst.groups_override)
                        if inst.blocks_override is not None:
                            entry["blocks"] = int(inst.blocks_override)
                        if inst.wings_override is not None:
                            entry["wings"] = int(inst.wings_override)
                        if inst.direction_override is not None:
                            entry["direction"] = str(inst.direction_override.value)
                        source_base[ch_int] = entry

        tracking_mode = bool(
            getattr(getattr(lightshow, "main_playback", None), "tracking_mode", False)
        )
        live_state = getattr(self.app, "live_state", None)
        live_fx = (
            live_state.get_all_effect_refs()
            if live_state is not None and hasattr(live_state, "get_all_effect_refs")
            else {}
        )

        result: dict[int, dict[str, typing.Any]] = {}
        for ch, spec in source_base.items():
            if not spec.get("stop"):
                result[int(ch)] = dict(spec)

        for ch, spec in live_fx.items():
            ch_id = int(ch)
            if spec.get("stop"):
                if tracking_mode:
                    result[ch_id] = {"stop": True}
                else:
                    result.pop(ch_id, None)
            else:
                result[ch_id] = dict(spec)

        return result

    @staticmethod
    def _apply_record_node_timings(step: Step, node: RecordCueCommandNode) -> None:
        """Apply optional fade, delay, and IFCB family timings from node to step."""
        if node.time_in is not None:
            step.time_in = node.time_in
            step.time_out = node.time_out if node.time_out is not None else node.time_in
        if node.delay is not None:
            step.delay_in = node.delay
        if node.time_position is not None:
            step.time_position = node.time_position
        if node.delay_position is not None:
            step.delay_position = node.delay_position
        if node.time_color is not None:
            step.time_color = node.time_color
        if node.delay_color is not None:
            step.delay_color = node.delay_color
        if node.time_beam is not None:
            step.time_beam = node.time_beam
        if node.delay_beam is not None:
            step.delay_beam = node.delay_beam
        step.update_total_time()

    @staticmethod
    def _format_cue_label(sequence_id: int, cue_id: float) -> str:
        """Format human-readable cue reference ('Cue 1.0' or 'Seq 2 Cue 1.0')."""
        return (
            f"Cue {cue_id}" if sequence_id == 1 else f"Seq {sequence_id} Cue {cue_id}"
        )

    @staticmethod
    def _get_target_sequence(lightshow: typing.Any, sequence_id: int) -> typing.Any:  # noqa: ANN401
        """Resolve Sequence object by index (1 = main_playback, >=2 = secondary)."""
        if sequence_id == 1:
            return lightshow.main_playback
        return lightshow.get_sequence(float(sequence_id))

    def _execute_record_cue(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self, node: RecordCueCommandNode
    ) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow:
            return CommandResult(False, "LightShow not available")

        seq_id = node.sequence_id
        target_seq = self._get_target_sequence(lightshow, seq_id)
        if not target_seq:
            return CommandResult(False, f"Sequence {seq_id} does not exist")

        channels_dict, device_values = self._capture_live_cue_state(lightshow)
        palette_refs = self._capture_live_palette_refs(
            lightshow, channels_dict, device_values
        )
        effect_refs = self._capture_live_effect_refs(lightshow)

        # Check if cue already exists in target sequence
        existing_cue = lightshow.get_cue(node.cue_id, seq_id)
        if existing_cue is not None:
            existing_cue.channels = channels_dict
            existing_cue.device_values = device_values
            existing_cue.palette_refs = palette_refs
            existing_cue.effect_refs = effect_refs
            if node.is_block:
                existing_cue.is_block = True
            cue = existing_cue
        else:
            cue = Cue(
                sequence=seq_id,
                number=node.cue_id,
                channels=channels_dict,
                device_values=device_values,
                is_block=node.is_block,
                palette_refs=palette_refs,
                effect_refs=effect_refs,
            )

        # Create or update step in target sequence (preserving sentinel last step)
        step = None
        existing_step_idx = -1
        for idx, s in enumerate(target_seq.steps):
            if s.cue and s.cue.number == node.cue_id:
                step = s
                existing_step_idx = idx
                break
        if step is None:
            step = Step(
                sequence=target_seq.index,
                cue=cue,
            )
            self._apply_record_node_timings(step, node)
            if (
                len(target_seq.steps) >= 2
                and target_seq.steps[-1].cue is not None
                and target_seq.steps[-1].cue.number == 0.0
            ):
                _found, step_idx = target_seq.get_step(cue=node.cue_id)
                step_idx = max(1, min(step_idx, len(target_seq.steps) - 1))
            else:
                step_idx = len(target_seq.steps)
                for idx, s in enumerate(target_seq.steps):
                    if s.cue and s.cue.number > node.cue_id:
                        step_idx = idx
                        break
            target_seq.insert_step(step_idx, step)
            target_seq.update_channels()
            lightshow.set_modified()
            self.app.emit("cue.created", seq_id, node.cue_id)
            self.app.emit("step.inserted", float(target_seq.index), step_idx)
            self.app.emit(
                "playback.cue_recorded",
                float(target_seq.index),
                step_idx,
                node.cue_id,
            )
        else:
            self._apply_record_node_timings(step, node)
            target_seq.update_channels()
            lightshow.set_modified()
            self.app.emit("cue.updated", seq_id, node.cue_id)
            self.app.emit("step.updated", float(target_seq.index), existing_step_idx)

        # If recording current active cue on main playback, release manual overrides
        if seq_id == 1:
            current_cue_num = None
            if 0 <= target_seq.position < len(target_seq.steps):
                s = target_seq.steps[target_seq.position]
                if s and s.cue:
                    current_cue_num = s.cue.number
            if current_cue_num is not None and current_cue_num == node.cue_id:
                self._release_manual_overrides(cue.channels)
                live_state = getattr(self.app, "live_state", None)
                if live_state is not None:
                    for ch in (
                        set(cue.channels)
                        | set(cue.device_values)
                        | set(cue.effect_refs)
                    ):
                        live_state.clear_channel(ch)
                    if hasattr(live_state, "clear_effect_refs"):
                        live_state.clear_effect_refs()

        return CommandResult(
            True, f"Recorded {self._format_cue_label(seq_id, node.cue_id)}"
        )

    def _release_manual_overrides(self, channels: typing.Iterable[int]) -> None:
        """Release manual user overrides for *channels* via ActionRegistry."""
        registry = self._get_registry()
        if registry is not None and "channel.set_level" in getattr(
            registry, "_action_classes", {}
        ):
            for ch in channels:
                registry.execute("channel.set_level", ch, -1.0)
            return
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels.get("user")
            if user_levels is not None:
                released = []
                for ch in channels:
                    if 1 <= ch <= len(user_levels):
                        user_levels[ch - 1] = -1.0
                        released.append(ch)
                backend.dmx.set_levels()
                if released:
                    self.app.emit("channels.updated", released)

    def _execute_update_cue(  # pylint: disable=too-many-locals,too-many-branches
        self, node: UpdateCueCommandNode
    ) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow:
            return CommandResult(False, "LightShow not available")

        seq_id = node.sequence_id
        target_seq = self._get_target_sequence(lightshow, seq_id)
        if not target_seq:
            return CommandResult(False, f"Sequence {seq_id} does not exist")

        cue_num = node.cue_id
        if cue_num is None:
            if hasattr(target_seq, "get_current_step"):
                step = target_seq.get_current_step()
            elif 0 <= target_seq.position < len(target_seq.steps):
                step = target_seq.steps[target_seq.position]
            else:
                step = None
            if not step or not step.cue:
                return CommandResult(False, "No active cue to update")
            cue_num = step.cue.number

        cue = lightshow.get_cue(cue_num, seq_id)
        if cue is None:
            return CommandResult(
                False, f"{self._format_cue_label(seq_id, cue_num)} does not exist"
            )

        new_channels = dict(cue.channels)
        backend = getattr(self.app, "backend", None)
        if backend and getattr(backend, "dmx", None):
            user_levels = backend.dmx.levels.get("user", [])
            limit = min(MAX_CHANNELS, len(user_levels))
            for ch in range(1, limit + 1):
                lvl = float(user_levels[ch - 1])
                if lvl > 0.0:
                    new_channels[ch] = lvl
                elif ch in new_channels:
                    new_channels[ch] = 0.0

        new_device_values: dict[int, dict[str, float]] = {}
        patch = getattr(lightshow, "patch", None)
        if patch is not None:
            for dev_id, dev in patch.devices.items():
                vals = self._get_device_active_values(dev)
                dev_int = float(getattr(dev, "intensity", 0.0))
                if dev_id in new_channels and new_channels[dev_id] > 0.0:
                    dev_int = max(dev_int, float(new_channels[dev_id]))
                if dev_int > 0.0:
                    vals["intensity"] = dev_int
                if vals:
                    new_device_values[dev_id] = vals

        merged_device_values = {
            int(dev_id): dict(vals) for dev_id, vals in cue.device_values.items()
        }
        for dev_id, vals in new_device_values.items():
            merged_device_values.setdefault(int(dev_id), {}).update(vals)
        updated_refs = self._capture_live_palette_refs(
            lightshow,
            new_channels,
            merged_device_values,
            base_refs=cue.palette_refs,
        )
        updated_effect_refs = self._capture_live_effect_refs(
            lightshow,
            base_refs=cue.effect_refs,
        )

        registry = self._get_registry()
        if registry is not None and "cue.update" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute(
                "cue.update",
                cue.number,
                cue.sequence,
                new_channels,
                device_values=new_device_values,
                palette_refs=updated_refs,
                effect_refs=updated_effect_refs,
            )
        else:
            cue.channels = new_channels
            for dev_id, vals in new_device_values.items():
                cue.device_values.setdefault(dev_id, {}).update(vals)
            cue.palette_refs = updated_refs
            cue.effect_refs = updated_effect_refs
            target_seq.update_channels()
            lightshow.set_modified()
            self.app.emit("cue.updated", seq_id, cue_num)

        # If updating current active cue on main playback, release manual overrides
        if seq_id == 1:
            current_cue_num = None
            if 0 <= target_seq.position < len(target_seq.steps):
                s = target_seq.steps[target_seq.position]
                if s and s.cue:
                    current_cue_num = s.cue.number
            if current_cue_num is not None and current_cue_num == cue_num:
                self._release_manual_overrides(cue.channels)
                live_state = getattr(self.app, "live_state", None)
                if live_state is not None:
                    for ch in (
                        set(cue.channels)
                        | set(cue.device_values)
                        | set(new_device_values)
                        | set(cue.effect_refs)
                    ):
                        live_state.clear_channel(ch)
                    if hasattr(live_state, "clear_effect_refs"):
                        live_state.clear_effect_refs()

        return CommandResult(True, f"Updated {self._format_cue_label(seq_id, cue_num)}")

    def _execute_goto_cue(self, node: GotoCueCommandNode) -> CommandResult:
        seq_id = node.sequence_id
        if seq_id == 1:
            registry = self._get_registry()
            if registry is not None and "playback.goto" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "playback.goto", target=str(node.cue_id), override_time=node.time
                )
            else:
                lightshow = getattr(self.app, "lightshow", None)
                if not lightshow or not lightshow.main_playback:
                    return CommandResult(False, "Main playback sequence not available")
                lightshow.main_playback.goto(str(node.cue_id), override_time=node.time)
        else:
            lightshow = getattr(self.app, "lightshow", None)
            target_seq = (
                self._get_target_sequence(lightshow, seq_id) if lightshow else None
            )
            if not target_seq:
                return CommandResult(False, f"Sequence {seq_id} does not exist")
            target_seq.goto(str(node.cue_id), override_time=node.time)
        return CommandResult(
            True, f"Jumped to {self._format_cue_label(seq_id, node.cue_id)}"
        )

    def _execute_block_cue(
        self, node: BlockCueCommandNode | UnblockCueCommandNode, is_block: bool
    ) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow:
            return CommandResult(False, "LightShow not available")

        seq_id = node.sequence_id
        label = self._format_cue_label(seq_id, node.cue_id)
        cue = lightshow.get_cue(node.cue_id, seq_id)
        if cue is None:
            return CommandResult(False, f"{label} not found")

        registry = self._get_registry()
        if registry is not None and "cue.set_block" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("cue.set_block", node.cue_id, is_block, seq_id)
        else:
            cue.is_block = is_block
            lightshow.set_modified()
        action_name = "Blocked" if is_block else "Unblocked"
        return CommandResult(True, f"{action_name} {label}")

    def _execute_delete_cue(self, node: DeleteCueCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if not lightshow:
            return CommandResult(False, "LightShow not available")

        seq_id = node.sequence_id
        label = self._format_cue_label(seq_id, node.cue_id)
        target_seq = self._get_target_sequence(lightshow, seq_id)
        cue = lightshow.get_cue(node.cue_id, seq_id)
        if cue is None:
            return CommandResult(False, f"{label} not found")

        registry = self._get_registry()
        if registry is not None and "cue.delete" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("cue.delete", number=node.cue_id, sequence=seq_id)
        else:
            if target_seq:
                for step in list(target_seq.steps):
                    if step.cue and step.cue.number == node.cue_id:
                        target_seq.steps.remove(step)
                target_seq.last = len(target_seq.steps)
                target_seq.update_channels()
            lightshow.set_modified()
            self.app.emit("cue.deleted", seq_id, node.cue_id)

        return CommandResult(True, f"Deleted {label}")

    @staticmethod
    def _is_channel_modified(dev: typing.Any, ch_type_val: str) -> bool:  # noqa: ANN401
        """Check if any resolution channel of ch_type_val differs from default_value."""
        for ch in getattr(dev, "channels", []):
            ctype = getattr(ch, "channel_type", None)
            if getattr(ctype, "value", ctype) == ch_type_val:
                if getattr(ch, "value", 0) != getattr(ch, "default_value", 0):
                    return True
        return False

    def _get_device_active_values(  # pylint: disable=too-many-branches
        self,
        dev: typing.Any,  # noqa: ANN401
    ) -> dict[str, typing.Any]:
        """Extract active physical parameters from a device instance."""
        vals: dict[str, typing.Any] = {}
        dev_id = getattr(dev, "fixture_id", None)
        eff_eng = getattr(self.app, "effects_engine", None)

        def _base_or(param: str, current_val: typing.Any) -> typing.Any:  # noqa: ANN401
            if (
                eff_eng is not None
                and isinstance(dev_id, int)
                and hasattr(eff_eng, "get_base_device_value")
            ):
                base_val = eff_eng.get_base_device_value(dev_id, param)
                if base_val is not None:
                    return base_val
            return current_val

        if hasattr(dev, "channels"):
            if self._is_channel_modified(dev, "pan"):
                vals["pan"] = float(_base_or("pan", dev.pan_degrees))
            if self._is_channel_modified(dev, "tilt"):
                vals["tilt"] = float(_base_or("tilt", dev.tilt_degrees))
            if self._is_channel_modified(dev, "zoom") and dev.zoom_degrees is not None:
                vals["zoom"] = float(_base_or("zoom", dev.zoom_degrees))
            if self._is_channel_modified(dev, "focus") and dev.focus_meters is not None:
                vals["focus"] = float(_base_or("focus", dev.focus_meters))
            if self._is_channel_modified(dev, "strobe") and dev.strobe_hz is not None:
                vals["strobe"] = float(_base_or("strobe", dev.strobe_hz))
            if (
                self._is_channel_modified(dev, "color_temp")
                and dev.color_temp_kelvin is not None
            ):
                vals["cct"] = float(_base_or("cct", dev.color_temp_kelvin))
            if (
                self._is_channel_modified(dev, "iris")
                and getattr(dev, "iris", None) is not None
            ):
                vals["iris"] = float(_base_or("iris", dev.iris))
            if getattr(dev, "gobo", None) is not None:
                vals["gobo"] = dev.gobo
            base_color = _base_or("color", None)
            if isinstance(base_color, tuple) and len(base_color) == 3:
                r, g, b = base_color
                if any(v > 0.0 for v in (r, g, b)):
                    vals["color"] = (
                        f"#{int(round(r * 255)):02X}"
                        f"{int(round(g * 255)):02X}"
                        f"{int(round(b * 255)):02X}"
                    )
            else:
                base_emitters = getattr(dev, "_base_emitters", {})
                if any(v > 0.0 for v in base_emitters.values()):
                    vals["color"] = dev.color_srgb.to_hex()
                    if getattr(dev, "is_subtractive_cmy", False):
                        vals["cyan"] = float(base_emitters.get(ChannelType.CYAN, 0.0))
                        vals["magenta"] = float(
                            base_emitters.get(ChannelType.MAGENTA, 0.0)
                        )
                        vals["yellow"] = float(
                            base_emitters.get(ChannelType.YELLOW, 0.0)
                        )
        else:
            if hasattr(dev, "pan_degrees") and getattr(dev, "pan_degrees", 0.0) != 0.0:
                vals["pan"] = float(_base_or("pan", dev.pan_degrees))
            if (
                hasattr(dev, "tilt_degrees")
                and getattr(dev, "tilt_degrees", 0.0) != 0.0
            ):
                vals["tilt"] = float(_base_or("tilt", dev.tilt_degrees))
            if hasattr(dev, "zoom_degrees") and dev.zoom_degrees is not None:
                vals["zoom"] = float(_base_or("zoom", dev.zoom_degrees))
            if hasattr(dev, "color_srgb") and hasattr(dev.color_srgb, "to_hex"):
                vals["color"] = dev.color_srgb.to_hex()
        return vals

    # --- Park Commands Resolution & Execution ---

    def resolve_address_selection(
        self, addresses: AddressSelectionNode
    ) -> list[tuple[int, int]]:
        """Resolve an AddressSelectionNode into sorted unique (univ, out) tuples."""
        included: set[tuple[int, int]] = set()
        for item in addresses.items:
            if isinstance(item, AddressNumberNode):
                included.add((item.universe, item.output))
            elif isinstance(item, AddressRangeNode):
                low, high = min(item.start, item.end), max(item.start, item.end)
                for out in range(low, high + 1):
                    included.add((item.universe, out))

        excluded: set[tuple[int, int]] = set()
        for item in addresses.exclusions:
            if isinstance(item, AddressNumberNode):
                excluded.add((item.universe, item.output))
            elif isinstance(item, AddressRangeNode):
                low, high = min(item.start, item.end), max(item.start, item.end)
                for out in range(low, high + 1):
                    excluded.add((item.universe, out))

        return sorted(list(included - excluded))

    def _execute_channel_park(self, node: ChannelParkCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels selected to park")

        registry = self._get_registry()
        target_norm: float | None = None
        if node.level is not None:
            target_norm = max(0.0, min(1.0, node.level / 100.0))

        if registry is not None:
            registry.execute("channel.park", channels, target_norm)
        else:
            for ch in channels:
                self.app.lightshow.park.park_channel(ch, target_norm or 0.0)

        return CommandResult(
            True, f"Parked {len(channels)} channel(s)", affected_channels=channels
        )

    def _execute_channel_unpark(self, node: ChannelUnparkCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels selected to unpark")

        registry = self._get_registry()
        if registry is not None:
            registry.execute("channel.unpark", channels)
        else:
            for ch in channels:
                self.app.lightshow.park.unpark_channel(ch)

        return CommandResult(
            True, f"Unparked {len(channels)} channel(s)", affected_channels=channels
        )

    def _execute_address_park(self, node: AddressParkCommandNode) -> CommandResult:
        addresses = self.resolve_address_selection(node.addresses)
        if not addresses:
            return CommandResult(False, "No addresses specified to park")

        target_dmx = max(0, min(255, int(round((node.level / 100.0) * 255.0))))
        registry = self._get_registry()
        if registry is not None:
            registry.execute("address.park", addresses, target_dmx)
        else:
            for u, o in addresses:
                self.app.lightshow.park.park_address(u, o, target_dmx)

        return CommandResult(True, f"Parked {len(addresses)} address(es)")

    def _execute_address_level(self, node: AddressLevelCommandNode) -> CommandResult:
        addresses = self.resolve_address_selection(node.addresses)
        if not addresses:
            return CommandResult(False, "No addresses specified")

        targets = [(o, u) for u, o in addresses]
        if node.level is None or node.level <= 0.0:
            dmx_level = 0
        else:
            dmx_level = max(0, min(255, int(round((node.level / 100.0) * 255.0))))

        registry = self._get_registry()
        if registry is not None:
            registry.execute("dmx.test_output", targets, level=dmx_level)
        else:
            backend = getattr(self.app, "backend", None)
            if backend is not None and getattr(backend, "dmx", None) is not None:
                for out, univ in targets:
                    backend.dmx.send_user_output(out, univ, dmx_level)

        if dmx_level > 0:
            last_univ, last_out = addresses[-1]
            if hasattr(self.app, "address_check"):
                self.app.address_check = (last_univ, last_out, dmx_level)
            pct = int(round((dmx_level / 255.0) * 100))
            if len(addresses) == 1:
                return CommandResult(True, f"Address {last_univ}/{last_out} at {pct}%")
            return CommandResult(True, f"{len(addresses)} address(es) at {pct}%")

        if hasattr(self.app, "address_check"):
            self.app.address_check = None
        return CommandResult(True, f"Released {len(addresses)} address(es)")

    def _execute_channel_check(self, node: ChannelCheckCommandNode) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels specified")

        raw_level = node.level
        if raw_level is None:
            default_fn = getattr(self.app, "get_default_channel_check_level", None)
            raw_level = default_fn() if callable(default_fn) else 80.0

        if raw_level <= 0.0:
            clear_fn = getattr(self.app, "clear_channel_check", None)
            if callable(clear_fn):
                clear_fn()
            registry = self._get_registry()
            for ch in channels:
                if registry is not None:
                    registry.execute("channel.set_level", ch, -1.0)
                else:
                    backend = getattr(self.app, "backend", None)
                    if (
                        backend is not None
                        and getattr(backend, "dmx", None) is not None
                    ):
                        backend.dmx.levels["user"][ch - 1] = -1.0
                        backend.dmx.set_levels()
            return CommandResult(True, "Channel Check released")

        for attr in ("clear_address_check", "clear_channel_check"):
            fn = getattr(self.app, attr, None)
            if callable(fn):
                fn()

        ch = channels[0]
        norm_lvl = max(0.0, min(1.0, float(raw_level) / 100.0))
        get_user_fn = getattr(self.app, "get_channel_user_level", None)
        old_user = get_user_fn(ch) if callable(get_user_fn) else -1.0

        registry = self._get_registry()
        if registry is not None:
            registry.execute("channel.set_level", ch, norm_lvl)
        else:
            backend = getattr(self.app, "backend", None)
            if backend is not None and getattr(backend, "dmx", None) is not None:
                backend.dmx.levels["user"][ch - 1] = norm_lvl
                backend.dmx.set_levels()

        if hasattr(self.app, "channel_check"):
            self.app.channel_check = (ch, norm_lvl, old_user)

        pct = int(round(norm_lvl * 100.0))
        return CommandResult(
            True, f"Channel {ch} Check at {pct}%", affected_channels=[ch]
        )

    def _execute_address_unpark(self, node: AddressUnparkCommandNode) -> CommandResult:
        addresses = self.resolve_address_selection(node.addresses)
        if not addresses:
            return CommandResult(False, "No addresses specified to unpark")

        registry = self._get_registry()
        if registry is not None:
            registry.execute("address.unpark", addresses)
        else:
            for u, o in addresses:
                self.app.lightshow.park.unpark_address(u, o)

        return CommandResult(True, f"Unparked {len(addresses)} address(es)")

    def _execute_park_unpark_all(
        self, _node: ParkUnparkAllCommandNode
    ) -> CommandResult:
        registry = self._get_registry()
        if registry is not None:
            registry.execute("park.unpark_all")
        else:
            self.app.lightshow.park.unpark_all()

        return CommandResult(True, "All channels and addresses unparked")

    def _apply_patch_assignments(
        self, assignments: list[tuple[int, int, int, int]]
    ) -> None:
        registry = self._get_registry()
        if registry is not None and "patch.add_outputs" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("patch.add_outputs", assignments)
        else:
            patch = self.app.lightshow.patch
            for ch, out, univ, curve in assignments:
                if patch.get_address_occupant(univ, out) is not None:
                    patch.unpatch_address(univ, out)
                patch.add_output(ch, out, univ, curve)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def _execute_patch(  # pylint: disable=too-many-locals,too-many-branches
        self, node: PatchCommandNode, *, force: bool = False
    ) -> CommandResult:
        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels selected to patch")

        addresses = self.resolve_address_selection(node.addresses)
        if not addresses:
            return CommandResult(False, "No addresses specified to patch")

        for univ, out in addresses:
            if univ < 1 or not 1 <= out <= 512:
                return CommandResult(False, f"Invalid DMX address: {univ}/{out}")

        assignments: list[tuple[int, int, int, int]] = []
        if len(channels) == 1:
            ch = channels[0]
            assignments = [(ch, out, univ, 0) for univ, out in addresses]
        elif len(addresses) == len(channels):
            assignments = [
                (ch, out, univ, 0)
                for ch, (univ, out) in zip(channels, addresses, strict=True)
            ]
        elif len(addresses) == 1:
            start_univ, start_out = addresses[0]
            for idx, ch in enumerate(channels):
                abs_offset = (start_out - 1) + idx
                u = start_univ + (abs_offset // 512)
                o = (abs_offset % 512) + 1
                assignments.append((ch, o, u, 0))
        else:
            return CommandResult(
                False,
                f"Cannot map {len(channels)} channels to {len(addresses)} addresses",
            )

        patch = self.app.lightshow.patch
        for ch, _out, _univ, _curve in assignments:
            dev = patch.get_device(ch)
            if dev is not None and dev.fixture_type != FixtureType.DIMMER:
                return CommandResult(
                    False,
                    f"Channel {ch} is patched to non-dimmer ({dev.fixture_name})",
                )

        collisions: list[str] = []
        for ch, out, univ, _curve in assignments:
            occ = patch.get_address_occupant(univ, out)
            if occ is not None and occ != ch:
                occ_dev = patch.get_device(occ)
                occ_name = occ_dev.fixture_name if occ_dev is not None else "Dimmer"
                collisions.append(f"{univ}/{out} (Channel {occ} - {occ_name})")

        if collisions and not force:
            confirm_msg = (
                "The following DMX address(es) are already patched:\n"
                + "\n".join(f"• {c}" for c in collisions)
                + "\n\nOverwrite existing patch?"
            )
            confirmed = False

            def _on_confirm() -> None:
                nonlocal confirmed
                confirmed = True
                self._apply_patch_assignments(assignments)

            self.app.emit("commandline.confirm_required", confirm_msg, _on_confirm)
            if not confirmed:
                return CommandResult(
                    False,
                    "Address already patched (confirmation required): "
                    + ", ".join(collisions),
                )
        else:
            self._apply_patch_assignments(assignments)

        unique_channels = sorted({ch for ch, _, _, _ in assignments})
        return CommandResult(
            True,
            f"Patched {len(assignments)} address(es)",
            affected_channels=unique_channels,
        )

    def _apply_unpatch_batch(
        self,
        *,
        device_ids: list[int] | None = None,
        addresses: list[tuple[int, int]] | None = None,
    ) -> None:
        registry = self._get_registry()
        if registry is not None and "patch.unpatch_batch" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute(
                "patch.unpatch_batch",
                device_ids=device_ids,
                addresses=addresses,
            )
        else:
            patch = self.app.lightshow.patch
            for dev_id in device_ids or []:
                patch.unpatch_device(dev_id)
            for univ, out in addresses or []:
                patch.unpatch_address(univ, out)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def _execute_unpatch(self, node: UnpatchCommandNode) -> CommandResult:
        patch = self.app.lightshow.patch

        if node.selection is None and node.addresses is not None:
            addresses = self.resolve_address_selection(node.addresses)
            if not addresses:
                return CommandResult(False, "No addresses specified to unpatch")
            self._apply_unpatch_batch(addresses=addresses)
            return CommandResult(True, f"Unpatched {len(addresses)} address(es)")

        channels = self.resolve_selection(node.selection)
        if not channels:
            return CommandResult(False, "No channels selected to unpatch")

        if node.addresses is None:
            patched_ids = [ch for ch in channels if patch.get_device(ch) is not None]
            if not patched_ids:
                return CommandResult(False, "Selected channels are not patched")
            self._apply_unpatch_batch(device_ids=patched_ids)
            return CommandResult(
                True,
                f"Unpatched {len(patched_ids)} channel(s)",
                affected_channels=patched_ids,
            )

        target_channels = set(channels)
        addresses = self.resolve_address_selection(node.addresses)
        filtered = [
            (u, o)
            for u, o in addresses
            if patch.get_address_occupant(u, o) in target_channels
        ]
        if not filtered:
            return CommandResult(
                False, "No matching patched addresses found on selected channels"
            )
        self._apply_unpatch_batch(addresses=filtered)
        return CommandResult(
            True,
            f"Unpatched {len(filtered)} address(es)",
            affected_channels=sorted(target_channels),
        )

    # --- Palette & Preset Commands ---

    def _execute_apply_palette(self, node: ApplyPaletteCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "palettes"):
            return CommandResult(False, "Palettes store not available")

        registry = self._get_registry()
        target_channels: list[int] | None = None
        if node.selection is not None:
            channels = self.resolve_selection(node.selection)
            last_sel = channels[-1] if channels else None
            if registry is not None and "channel.select_channels" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "channel.select_channels",
                    channels=channels,
                    last_selected=last_sel,
                )
            else:
                self.app.selected_channels = list(channels)
                self.app.last_selected_channel = last_sel
                self.app.emit("channels.selected_changed", channels)
            if not channels:
                return CommandResult(False, "No channels selected")
            target_channels = channels

        label = format_palette_label(node.category, node.palette_id)
        palette = lightshow.palettes.get(node.category, node.palette_id)
        if palette is None:
            return CommandResult(False, f"{label} not found")

        if registry is not None and "palette.apply" in getattr(
            registry, "_action_classes", {}
        ):
            affected = registry.execute(
                "palette.apply",
                node.category,
                node.palette_id,
                channels=target_channels,
            )
        else:
            action = PaletteApplyAction(self.app)
            action.configure(node.category, node.palette_id, channels=target_channels)
            affected = action.execute()

        affected_list = list(affected) if isinstance(affected, list) else []
        if not affected_list:
            return CommandResult(False, f"{label} has no matching channel data")
        return CommandResult(
            True,
            f"Applied {label} to {len(affected_list)} channel(s)",
            affected_channels=affected_list,
        )

    def _execute_record_palette(self, node: RecordPaletteCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "palettes"):
            return CommandResult(False, "Palettes store not available")

        registry = self._get_registry()
        if registry is not None and "palette.record" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("palette.record", node.category, node.palette_id)
        else:
            action = PaletteRecordAction(self.app)
            action.configure(node.category, node.palette_id)
            action.execute()

        label = format_palette_label(node.category, node.palette_id)
        return CommandResult(True, f"Recorded {label}")

    def _execute_update_palette(self, node: UpdatePaletteCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "palettes"):
            return CommandResult(False, "Palettes store not available")

        label = format_palette_label(node.category, node.palette_id)
        if lightshow.palettes.get(node.category, node.palette_id) is None:
            return CommandResult(False, f"{label} does not exist")

        registry = self._get_registry()
        if registry is not None and "palette.update" in getattr(
            registry, "_action_classes", {}
        ):
            res = registry.execute("palette.update", node.category, node.palette_id)
        else:
            action = PaletteUpdateAction(self.app)
            action.configure(node.category, node.palette_id)
            res = action.execute()

        propagation = res.get("propagation", {}) if isinstance(res, dict) else {}
        cues_upd = propagation.get("cues", 0)
        presets_upd = propagation.get("presets", 0)
        effects_upd = propagation.get("effects", 0)
        if presets_upd or cues_upd or effects_upd:
            msg = (
                f"Updated {label} (propagated to {presets_upd} preset(s), "
                f"{cues_upd} cue(s)"
            )
            if effects_upd:
                msg += f", {effects_upd} effect(s)"
            return CommandResult(True, f"{msg})")
        return CommandResult(True, f"Updated {label}")

    def _execute_delete_palette(self, node: DeletePaletteCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "palettes"):
            return CommandResult(False, "Palettes store not available")

        label = format_palette_label(node.category, node.palette_id)
        if lightshow.palettes.get(node.category, node.palette_id) is None:
            return CommandResult(False, f"{label} not found")

        registry = self._get_registry()
        if registry is not None and "palette.delete" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("palette.delete", node.category, node.palette_id)
        else:
            action = PaletteDeleteAction(self.app)
            action.configure(node.category, node.palette_id)
            action.execute()

        return CommandResult(True, f"Deleted {label}")

    # --- Effect Commands ---

    def _execute_apply_effect(self, node: ApplyEffectCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "effects"):
            return CommandResult(False, "Effects store not available")

        registry = self._get_registry()
        if node.selection is not None:
            ordered_channels = self.resolve_ordered_selection(node.selection)
            sorted_channels = self.resolve_selection(node.selection)
            last_sel = ordered_channels[-1] if ordered_channels else None
            if registry is not None and "channel.select_channels" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "channel.select_channels",
                    channels=sorted_channels,
                    last_selected=last_sel,
                )
            else:
                self.app.selected_channels = list(sorted_channels)
                self.app.last_selected_channel = last_sel
                self.app.emit("channels.selected_changed", sorted_channels)
            target_channels = ordered_channels
        else:
            target_channels = list(getattr(self.app, "selected_channels", []))

        if not target_channels:
            return CommandResult(False, "No channels selected for EFFECT")

        effect = lightshow.effects.get(node.effect_id)
        if effect is None:
            return CommandResult(
                False, f"Effect {format_effect_number(node.effect_id)} not found"
            )

        rate_scale = (node.rate / 100.0) if node.rate is not None else 1.0
        size_scale = (node.size / 100.0) if node.size is not None else 1.0

        if registry is not None and "effect.apply" in getattr(
            registry, "_action_classes", {}
        ):
            affected = registry.execute(
                "effect.apply",
                node.effect_id,
                channels=target_channels,
                rate_scale=rate_scale,
                size_scale=size_scale,
                groups=node.groups,
                blocks=node.blocks,
                wings=node.wings,
            )
        else:
            action = EffectApplyAction(self.app)
            action.configure(
                node.effect_id,
                channels=target_channels,
                rate_scale=rate_scale,
                size_scale=size_scale,
                groups=node.groups,
                blocks=node.blocks,
                wings=node.wings,
            )
            affected = action.execute()

        affected_list = (
            list(affected) if isinstance(affected, list) else list(target_channels)
        )
        num_str = format_effect_number(node.effect_id)
        return CommandResult(
            True,
            f"Applied Effect {num_str} to {len(affected_list)} channel(s)",
            affected_channels=affected_list,
        )

    def _execute_stop_effect(self, node: StopEffectCommandNode) -> CommandResult:
        registry = self._get_registry()
        target_channels: list[int] | None = None
        if node.selection is not None:
            target_channels = self.resolve_selection(node.selection)
            last_sel = target_channels[-1] if target_channels else None
            if registry is not None and "channel.select_channels" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "channel.select_channels",
                    channels=target_channels,
                    last_selected=last_sel,
                )
            else:
                self.app.selected_channels = list(target_channels)
                self.app.last_selected_channel = last_sel
                self.app.emit("channels.selected_changed", target_channels)
            if not target_channels:
                return CommandResult(False, "No channels selected to stop effect")

        if registry is not None and "effect.stop" in getattr(
            registry, "_action_classes", {}
        ):
            stopped = registry.execute(
                "effect.stop",
                number=node.effect_id,
                channels=target_channels,
            )
        else:
            action = EffectStopAction(self.app)
            action.configure(number=node.effect_id, channels=target_channels)
            stopped = action.execute()

        stopped_list = list(stopped) if isinstance(stopped, list) else []
        if node.effect_id is not None:
            num_str = format_effect_number(node.effect_id)
            return CommandResult(
                True,
                f"Stopped Effect {num_str}",
                affected_channels=stopped_list,
            )
        if target_channels is not None:
            return CommandResult(
                True,
                f"Stopped effects on {len(target_channels)} channel(s)",
                affected_channels=target_channels,
            )
        return CommandResult(
            True,
            "Stopped all running effects",
            affected_channels=stopped_list,
        )

    def _execute_edit_effect(self, node: EditEffectCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "effects"):
            return CommandResult(False, "Effects store not available")

        num_str = format_effect_number(node.effect_id)
        if lightshow.effects.get(node.effect_id) is None:
            return CommandResult(False, f"Effect {num_str} not found")

        registry = self._get_registry()
        has_param_changes = any(
            v is not None
            for v in (node.rate, node.size, node.groups, node.blocks, node.wings)
        )
        if has_param_changes:
            if registry is not None and "effect.update" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute(
                    "effect.update",
                    node.effect_id,
                    rate=node.rate,
                    size=node.size,
                    groups=node.groups,
                    blocks=node.blocks,
                    wings=node.wings,
                    label=node.label,
                )
            else:
                action = EffectUpdateAction(self.app)
                action.configure(
                    node.effect_id,
                    rate=node.rate,
                    size=node.size,
                    groups=node.groups,
                    blocks=node.blocks,
                    wings=node.wings,
                    label=node.label,
                )
                action.execute()
            return CommandResult(True, f"Updated Effect {num_str}")

        if node.label is not None:
            if registry is not None and "effect.rename" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute("effect.rename", node.effect_id, node.label)
            else:
                action_ren = EffectRenameAction(self.app)
                action_ren.configure(node.effect_id, node.label)
                action_ren.execute()
            return CommandResult(True, f"Labeled Effect {num_str} '{node.label}'")

        return CommandResult(False, f"No changes specified for Effect {num_str}")

    def _execute_delete_effect(self, node: DeleteEffectCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "effects"):
            return CommandResult(False, "Effects store not available")

        num_str = format_effect_number(node.effect_id)
        if lightshow.effects.get(node.effect_id) is None:
            return CommandResult(False, f"Effect {num_str} not found")

        registry = self._get_registry()
        if registry is not None and "effect.delete" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("effect.delete", node.effect_id)
        else:
            action = EffectDeleteAction(self.app)
            action.configure(node.effect_id)
            action.execute()

        return CommandResult(True, f"Deleted Effect {num_str}")

    # --- Group Commands ---

    @staticmethod
    def _format_group_id(group_id: float) -> str:
        val = float(group_id)
        return str(int(val)) if val.is_integer() else f"{val:g}"

    def _execute_record_group(self, node: RecordGroupCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "groups"):
            return CommandResult(False, "Groups store not available")

        channels = (
            self.resolve_ordered_selection(node.selection)
            if node.selection is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        group_id = (
            float(node.group_id)
            if node.group_id is not None
            else lightshow.groups.get_next_index()
        )
        num_str = self._format_group_id(group_id)
        registry = self._get_registry()

        if lightshow.groups.get(group_id) is None:
            if registry is not None and "group.new" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute("group.new", group_id, channels, label=node.label)
            else:
                action = NewGroupAction(self.app)
                action.configure(group_id, channels, label=node.label)
                action.execute()
        else:
            if registry is not None and "group.update_channels" in getattr(
                registry, "_action_classes", {}
            ):
                registry.execute("group.update_channels", group_id, channels)
            else:
                action_upd = GroupUpdateChannelsAction(self.app)
                action_upd.configure(group_id, channels)
                action_upd.execute()
            if node.label is not None:
                if registry is not None and "group.rename" in getattr(
                    registry, "_action_classes", {}
                ):
                    registry.execute("group.rename", group_id, node.label)
                else:
                    action_ren = GroupRenameAction(self.app)
                    action_ren.configure(group_id, node.label)
                    action_ren.execute()

        return CommandResult(
            True,
            f"Recorded Group {num_str} ({len(channels)} ch)",
            affected_channels=channels,
        )

    def _execute_update_group(self, node: UpdateGroupCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "groups"):
            return CommandResult(False, "Groups store not available")

        group_id = float(node.group_id)
        num_str = self._format_group_id(group_id)
        if lightshow.groups.get(group_id) is None:
            return CommandResult(False, f"Group {num_str} not found")

        channels = (
            self.resolve_ordered_selection(node.selection)
            if node.selection is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        registry = self._get_registry()
        if registry is not None and "group.update_channels" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("group.update_channels", group_id, channels)
        else:
            action = GroupUpdateChannelsAction(self.app)
            action.configure(group_id, channels)
            action.execute()

        return CommandResult(
            True,
            f"Updated Group {num_str} ({len(channels)} ch)",
            affected_channels=channels,
        )

    def _execute_delete_group(self, node: DeleteGroupCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "groups"):
            return CommandResult(False, "Groups store not available")

        group_id = float(node.group_id)
        num_str = self._format_group_id(group_id)
        if lightshow.groups.get(group_id) is None:
            return CommandResult(False, f"Group {num_str} not found")

        registry = self._get_registry()
        if registry is not None and "group.delete" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("group.delete", group_id)
        else:
            action = DeleteGroupAction(self.app)
            action.configure(group_id)
            action.execute()

        return CommandResult(True, f"Deleted Group {num_str}")

    def _execute_label_group(self, node: LabelGroupCommandNode) -> CommandResult:
        lightshow = getattr(self.app, "lightshow", None)
        if lightshow is None or not hasattr(lightshow, "groups"):
            return CommandResult(False, "Groups store not available")

        group_id = float(node.group_id)
        num_str = self._format_group_id(group_id)
        if lightshow.groups.get(group_id) is None:
            return CommandResult(False, f"Group {num_str} not found")

        registry = self._get_registry()
        if registry is not None and "group.rename" in getattr(
            registry, "_action_classes", {}
        ):
            registry.execute("group.rename", group_id, node.label)
        else:
            action = GroupRenameAction(self.app)
            action.configure(group_id, node.label)
            action.execute()

        return CommandResult(True, f'Labeled Group {num_str} "{node.label}"')

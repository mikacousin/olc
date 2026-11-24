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
"""Abstract Syntax Tree (AST) node definitions for lighting commands."""

from __future__ import annotations

import dataclasses
import typing


@dataclasses.dataclass
class ASTNode:
    """Base class for all AST nodes."""


# --- Selection Nodes ---


@dataclasses.dataclass
class SelectionItemNode(ASTNode):
    """Base class for atomic selection elements."""


@dataclasses.dataclass
class ChannelNumberNode(SelectionItemNode):
    """Single channel number (e.g. 5)."""

    channel: int


@dataclasses.dataclass
class ChannelRangeNode(SelectionItemNode):
    """Range of channels (e.g. 1 THRU 10)."""

    start: int
    end: int


@dataclasses.dataclass
class RelativeThruNode(SelectionItemNode):
    """Range of channels extending from last selected channel (e.g. THRU 10)."""

    end: int


@dataclasses.dataclass
class GroupSelectionNode(SelectionItemNode):
    """Group of channels (e.g. GROUP 2 or GROUP 1.5)."""

    group_id: float


@dataclasses.dataclass
class AllSelectionNode(SelectionItemNode):
    """Universal selection (ALL)."""


# --- Address Selection Nodes ---


@dataclasses.dataclass
class AddressItemNode(ASTNode):
    """Base class for atomic DMX address selection elements."""


@dataclasses.dataclass
class AddressNumberNode(AddressItemNode):
    """Single DMX output address (e.g. ADDRESS 12 or ADDRESS 2/15)."""

    universe: int
    output: int


@dataclasses.dataclass
class AddressRangeNode(AddressItemNode):
    """Range of DMX output addresses in a universe (e.g. ADDRESS 1/1 THRU 10)."""

    universe: int
    start: int
    end: int


@dataclasses.dataclass
class AddressSelectionNode(ASTNode):
    """Composite selection of physical DMX addresses."""

    items: list[AddressItemNode] = dataclasses.field(default_factory=list)
    exclusions: list[AddressItemNode] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SelectionNode(ASTNode):
    """Composite selection with additions, exclusions and optional odd/even filter."""

    items: list[SelectionItemNode] = dataclasses.field(default_factory=list)
    exclusions: list[SelectionItemNode] = dataclasses.field(default_factory=list)
    filter_mode: typing.Literal["all", "odd", "even"] = "all"
    is_relative: bool = False


# --- Command Nodes ---


@dataclasses.dataclass
class CommandNode(ASTNode):
    """Base class for executable command instructions."""


@dataclasses.dataclass
class SelectOnlyCommandNode(CommandNode):
    """Command that only updates channel selection (e.g. 1 THRU 10 ENTER)."""

    selection: SelectionNode


@dataclasses.dataclass
class IntensityCommandNode(CommandNode):
    """Command setting intensity level (e.g. 1 THRU 5 AT 80, AT FULL, AT +10)."""

    selection: SelectionNode | None
    level: float
    is_relative: bool = False


@dataclasses.dataclass
class HomeCommandNode(CommandNode):
    """Command to reset fixture parameters to Home defaults (e.g. 1 HOME)."""

    selection: SelectionNode | None = None
    category: str | None = None


@dataclasses.dataclass
class LocateCommandNode(CommandNode):
    """Command to locate fixtures at Home with full intensity (e.g. 1 LOCATE)."""

    selection: SelectionNode | None = None


@dataclasses.dataclass
class AttributeCommandNode(CommandNode):
    """Command setting moving light attributes (e.g. 1 PAN 45 TILT -30 COLOR RED)."""

    selection: SelectionNode | None
    attributes: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    intensity_level: float | None = None
    is_intensity_relative: bool = False


@dataclasses.dataclass
class RecordCueCommandNode(CommandNode):  # pylint: disable=too-many-instance-attributes
    """Command to record a scene cue (e.g. RECORD CUE 5 TIME 3 / 2)."""

    cue_id: float
    sequence_id: int = 1
    time_in: float | None = None
    time_out: float | None = None
    delay: float | None = None
    is_block: bool = False
    time_position: float | None = None
    delay_position: float | None = None
    time_color: float | None = None
    delay_color: float | None = None
    time_beam: float | None = None
    delay_beam: float | None = None


@dataclasses.dataclass
class UpdateCueCommandNode(CommandNode):
    """Command to update current or specified cue (e.g. UPDATE CUE 4)."""

    cue_id: float | None = None
    sequence_id: int = 1


@dataclasses.dataclass
class GotoCueCommandNode(CommandNode):
    """Command to jump directly to a cue (e.g. GOTO CUE 12 TIME 0)."""

    cue_id: float
    time: float | None = None
    sequence_id: int = 1


@dataclasses.dataclass
class BlockCueCommandNode(CommandNode):
    """Command to mark a cue as a blocking cue (e.g. BLOCK CUE 8)."""

    cue_id: float
    sequence_id: int = 1


@dataclasses.dataclass
class UnblockCueCommandNode(CommandNode):
    """Command to unblock a cue (e.g. UNBLOCK CUE 8)."""

    cue_id: float
    sequence_id: int = 1


@dataclasses.dataclass
class DeleteCueCommandNode(CommandNode):
    """Command to delete a cue (e.g. DELETE CUE 4)."""

    cue_id: float
    sequence_id: int = 1


@dataclasses.dataclass
class CreateSequenceCommandNode(CommandNode):
    """Command to create a new secondary sequence (e.g. RECORD SEQ 2)."""

    sequence_id: int


@dataclasses.dataclass
class DeleteSequenceCommandNode(CommandNode):
    """Command to delete a secondary sequence (e.g. DELETE SEQ 2)."""

    sequence_id: int


@dataclasses.dataclass
class SneakCommandNode(CommandNode):
    """Command to sneak channels or independents over a duration."""

    selection: SelectionNode | None = None
    independents: list[int] | None = None
    duration: float | None = None


@dataclasses.dataclass
class PatchCommandNode(CommandNode):
    """Command to patch dimmer outputs to channels (e.g. 1 PATCH AT 10 THRU 15)."""

    selection: SelectionNode
    addresses: AddressSelectionNode


@dataclasses.dataclass
class UnpatchCommandNode(CommandNode):
    """Command to unpatch channels or DMX addresses."""

    selection: SelectionNode | None = None
    addresses: AddressSelectionNode | None = None


# --- Park Command Nodes ---


@dataclasses.dataclass
class ChannelParkCommandNode(CommandNode):
    """Command to park channels at a level or current level."""

    selection: SelectionNode | None = None
    level: float | None = None


@dataclasses.dataclass
class ChannelUnparkCommandNode(CommandNode):
    """Command to unpark channels."""

    selection: SelectionNode | None = None


@dataclasses.dataclass
class AddressParkCommandNode(CommandNode):
    """Command to park physical DMX addresses."""

    addresses: AddressSelectionNode
    level: float


@dataclasses.dataclass
class AddressLevelCommandNode(CommandNode):
    """Command to temporarily set DMX output test level(s) (ADDRESS ... AT ...)."""

    addresses: AddressSelectionNode
    level: float | None = None


@dataclasses.dataclass
class ChannelCheckCommandNode(CommandNode):
    """Command to enter or release Channel Check mode (1 CHECK [AT <level>])."""

    selection: SelectionNode
    level: float | None = None


@dataclasses.dataclass
class AddressUnparkCommandNode(CommandNode):
    """Command to unpark physical DMX addresses."""

    addresses: AddressSelectionNode


@dataclasses.dataclass
class ParkUnparkAllCommandNode(CommandNode):
    """Command to unpark all channels and physical DMX addresses."""


# --- Palette & Preset Command Nodes ---


@dataclasses.dataclass
class ApplyPaletteCommandNode(CommandNode):
    """Command to apply an IFCB palette or preset (e.g. 1 COLOR PALETTE 2)."""

    selection: SelectionNode | None
    category: str
    palette_id: float
    absolute: bool = False


@dataclasses.dataclass
class RecordPaletteCommandNode(CommandNode):
    """Command to record an IFCB palette or preset (e.g. RECORD COLOR PALETTE 2)."""

    category: str
    palette_id: float
    mode: str | None = None


@dataclasses.dataclass
class UpdatePaletteCommandNode(CommandNode):
    """Command to update an existing palette or preset (e.g. UPDATE PRESET 1)."""

    category: str
    palette_id: float
    selective: bool = False


@dataclasses.dataclass
class SequenceControlCommandNode(CommandNode):
    """Command to control a sequence playback (GO, PAUSE, RELEASE, ASSERT)."""

    action: str
    sequence_id: int | None = 1


@dataclasses.dataclass
class DeletePaletteCommandNode(CommandNode):
    """Command to delete an IFCB palette or preset (e.g. DELETE BEAM PALETTE 1)."""

    category: str
    palette_id: float


# --- Effect Command Nodes ---


@dataclasses.dataclass
class ApplyEffectCommandNode(CommandNode):
    """Command to apply an effect to a channel selection."""

    selection: SelectionNode | None
    effect_id: float
    rate: float | None = None
    size: float | None = None
    groups: int | None = None
    blocks: int | None = None
    wings: int | None = None


@dataclasses.dataclass
class StopEffectCommandNode(CommandNode):
    """Command to stop/stomp running effect(s) on a selection or globally."""

    selection: SelectionNode | None = None
    effect_id: float | None = None


@dataclasses.dataclass
class EditEffectCommandNode(CommandNode):
    """Command to edit an effect's definition or label (e.g. EFFECT 1 RATE 120)."""

    effect_id: float
    rate: float | None = None
    size: float | None = None
    groups: int | None = None
    blocks: int | None = None
    wings: int | None = None
    label: str | None = None


@dataclasses.dataclass
class DeleteEffectCommandNode(CommandNode):
    """Command to delete an effect from the show pool (e.g. DELETE EFFECT 1)."""

    effect_id: float


# --- Group Command Nodes ---


@dataclasses.dataclass
class RecordGroupCommandNode(CommandNode):
    """Command to record a Group (e.g. RECORD GROUP 1 or 1 RECORD GROUP 2)."""

    group_id: float | None = None
    selection: SelectionNode | None = None
    label: str | None = None


@dataclasses.dataclass
class UpdateGroupCommandNode(CommandNode):
    """Command to update a Group's channel selection (e.g. 1 THRU 4 UPDATE GROUP 1)."""

    group_id: float
    selection: SelectionNode | None = None


@dataclasses.dataclass
class DeleteGroupCommandNode(CommandNode):
    """Command to delete a Group from the show (e.g. DELETE GROUP 2)."""

    group_id: float


@dataclasses.dataclass
class LabelGroupCommandNode(CommandNode):
    """Command to rename a Group (e.g. LABEL GROUP 2 "Front")."""

    group_id: float
    label: str

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
class GroupSelectionNode(SelectionItemNode):
    """Group of channels (e.g. GROUP 2)."""

    group_id: int


@dataclasses.dataclass
class AllSelectionNode(SelectionItemNode):
    """Universal selection (ALL)."""


@dataclasses.dataclass
class SelectionNode(ASTNode):
    """Composite selection with additions, exclusions and optional odd/even filter."""

    items: list[SelectionItemNode] = dataclasses.field(default_factory=list)
    exclusions: list[SelectionItemNode] = dataclasses.field(default_factory=list)
    filter_mode: typing.Literal["all", "odd", "even"] = "all"


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
class AttributeCommandNode(CommandNode):
    """Command setting moving light attributes (e.g. 1 PAN 45 TILT -30 COLOR RED)."""

    selection: SelectionNode | None
    attributes: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    intensity_level: float | None = None
    is_intensity_relative: bool = False


@dataclasses.dataclass
class RecordCueCommandNode(CommandNode):
    """Command to record a scene cue (e.g. RECORD CUE 5 TIME 3 / 2)."""

    cue_id: float
    time_in: float | None = None
    time_out: float | None = None
    delay: float | None = None
    is_block: bool = False


@dataclasses.dataclass
class UpdateCueCommandNode(CommandNode):
    """Command to update current or specified cue (e.g. UPDATE CUE 4)."""

    cue_id: float | None = None


@dataclasses.dataclass
class GotoCueCommandNode(CommandNode):
    """Command to jump directly to a cue (e.g. GOTO CUE 12 TIME 0)."""

    cue_id: float
    time: float | None = None


@dataclasses.dataclass
class BlockCueCommandNode(CommandNode):
    """Command to mark a cue as a blocking cue (e.g. BLOCK CUE 8)."""

    cue_id: float


@dataclasses.dataclass
class UnblockCueCommandNode(CommandNode):
    """Command to unblock a cue (e.g. UNBLOCK CUE 8)."""

    cue_id: float


@dataclasses.dataclass
class DeleteCueCommandNode(CommandNode):
    """Command to delete a cue (e.g. DELETE CUE 4)."""

    cue_id: float

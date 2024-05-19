# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2024 Mika Cousin <mika.cousin@gmail.com>
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
from dataclasses import dataclass

from olc.define import MAX_CHANNELS, App


# pylint: disable=C0115,C0116,R0903
@dataclass
class TreeNode:
    pass


@dataclass
class Int(TreeNode):
    value: int

    def eval(self):
        return self.value


class ChanNumber(Int):

    def __init__(self, value):
        if value < 0 or value > MAX_CHANNELS:
            raise ValueError(f"channel number must be between 1 and {MAX_CHANNELS}")
        super().__init__(value)

    def __str__(self):
        return f"{self.value}"


class Level(Int):

    def __init__(self, value):
        if App().settings.get_boolean("percent"):
            max_value = 100
        else:
            max_value = 255
        if value < 0 or value > max_value:
            raise ValueError(f"level must be between 0 and {max_value}")
        super().__init__(value)

    def __str__(self):
        return f"{self.value}"


@dataclass
class SelOp(TreeNode):
    pass


@dataclass
class SelStart(SelOp):
    channel: ChanNumber

    def __str__(self):
        return f"chan {self.channel}"

    def eval(self, context):
        chan = self.channel.eval()
        context.select_channel(chan)

    def get_selection(self):
        return str(self)


@dataclass
class SelAddOp(SelOp):
    op: str
    sel_op: TreeNode
    channel: ChanNumber
    to_channel: ChanNumber | None = None

    def __str__(self):
        if self.op == "+":
            return f"{self.sel_op} + {self.channel}"
        if self.sel_op.channel.value == self.channel.value:
            return f"{self.sel_op} thru {self.to_channel}"
        return f"{self.sel_op} + {self.channel} thru {self.to_channel}"

    def eval(self, context):
        self.sel_op.eval(context)
        chan = self.channel.eval()
        if self.op == "+":
            context.select_plus(chan)
        elif self.op == "thru":
            to_chan = self.to_channel.eval()
            context.select_thru(chan, to_chan)

    def get_selection(self):
        return str(self)


@dataclass
class SelMinusOp(SelOp):
    op: str
    sel_op: TreeNode
    channel: ChanNumber
    to_channel: ChanNumber | None = None

    def __str__(self):
        if self.op == "-":
            return f"{self.sel_op} - {self.channel}"
        return f"{self.sel_op} - {self.channel} thru {self.to_channel}"

    def eval(self, context):
        self.sel_op.eval(context)
        chan = self.channel.eval()
        if self.op == "-":
            context.select_minus(chan)
        elif self.op == "thru":
            to_chan = self.to_channel.eval()
            context.deselect_thru(chan, to_chan)

    def get_selection(self):
        return str(self)


@dataclass
class LevelOp(TreeNode):
    selection: SelOp
    op: str
    level: Level
    to_level: Level

    def __str__(self):
        if self.op == "at":
            return f"{self.selection} at {self.level}"
        return f"{self.selection} at {self.level} thru {self.to_level}"

    def eval(self, context):
        self.selection.eval(context)
        if self.op == "at":
            level = self.level.eval()
            context.at_level(level)
        elif self.op == "thru":
            from_level = self.level.eval()
            to_level = self.to_level.eval()
            context.thru_level(from_level, to_level)
        else:
            raise SyntaxError(f"unknown level operand: {self.op}")

    def get_selection(self):
        return f"{self.selection}"

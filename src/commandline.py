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
from __future__ import annotations

from collections import deque
from gettext import gettext as _

from gi.repository import GLib, Gtk
from olc.command.lexer import Lexer, TokenType
from olc.command.parser_direct import ParserDirect
from olc.define import App


class History:
    """Command line history"""

    commandline: CommandLine
    history: deque
    history_idx: int

    def __init__(self, commandline):
        self.commandline = commandline
        self.history = deque(maxlen=500)
        self.history_idx = 0
        super().__init__(commandline)

    def add_entry(self, string: str) -> None:
        """Add history entry

        Args:
            string: command line string
        """
        self.history.append(string)
        self.history_idx = len(self.history)

    def prev(self) -> None:
        """Previous command line string"""
        if not self.history:
            return
        self.history_idx -= 1
        self.history_idx = max(self.history_idx, 0)
        string = self.history[self.history_idx]
        self.commandline.set_string(string)

    def next(self) -> None:
        """Next command line string"""
        if not self.history:
            return
        self.history_idx += 1
        self.history_idx = min(self.history_idx, len(self.history) - 1)
        string = self.history[self.history_idx]
        self.commandline.set_string(string)


class Cursor:
    """Command line cursor"""

    def __init__(self, commandline):
        self.commandline = commandline
        self.cursor = "_"

        # Blink every second
        GLib.timeout_add(1000, self.blink_cursor)

    def __str__(self) -> str:
        return self.cursor

    def blink_cursor(self) -> bool:
        """Display blinking cursor

        Returns:
            True for infinite loop
        """
        if self.cursor == " ":
            self.cursor = "_"
        else:
            self.cursor = " "
        self.commandline.set_label()
        return True


class CommandLine(History, Cursor):
    """Display keyboard entries"""

    def __init__(self):
        super().__init__(self)
        self.keystring = ""
        self.error = ""

        self.statusbar = Gtk.Label()
        self.set_label()
        self.widget = Gtk.Grid()
        self.widget.set_name("command_line")
        label = Gtk.Label()
        prompt = _("Command")
        label.set_markup(f"<b>{prompt} :  </b>")
        self.widget.add(label)
        self.widget.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)

    def set_label(self) -> None:
        """Display command line"""
        if self.error:
            self.statusbar.set_markup(
                f"<b><span color='#AA2222'>"
                f"{self.keystring.title()}{self.error}{self.cursor}"
                f"</span></b>")
        else:
            self.statusbar.set_markup(f"<b>{self.keystring.title()}{self.cursor}</b>")

    def interpret(self, context, run=False) -> None:
        """Interpret Command-line

        Args:
            context: Widget sending string
            run: Interpret flag
        """
        lexer = list(Lexer(self.keystring))
        parser = ParserDirect(lexer)
        try:
            tree = parser.parse()
            if not run and len(lexer) > 1 and lexer[-2].type is not TokenType.INT:
                # Interpret selection as user enter command-line
                # but not when enter number
                parser.interpret_selec(tree, context)
            if run:
                # Interpret command-line (when user enter Return)
                parser.interpret(tree, context)
                self.add_entry(self.keystring)
                self.keystring = parser.get_selection(tree)
            if App().osc:
                App().osc.client.send("/olc/command_line", ("s", self.keystring))
        except SyntaxError as error:
            self.error = f" : {error}"
        except ValueError as error:
            self.error = f" : {error}"
        finally:
            self.set_label()

    def del_last_part(self, context) -> None:
        """Remove last element of the command string

        Args:
            context: Widget sending delete
        """
        self.error = ""
        # Remove trailing spaces
        self.keystring = self.keystring.rstrip()
        # Remove string last part
        self.keystring = " ".join(self.keystring.split(" ")[:-1])
        self.interpret(context)

    def add_string(self, string: str, context=None) -> None:
        """Add string to displayed string

        Args:
            string: String to add
            context: Widget sending string
        """
        if string == "\n":
            self.interpret(context, run=True)
            return
        if not self.keystring and string.isdigit():
            string = f"chan {string}"
        if self.keystring and self.keystring[
                -1] != " " and not self.keystring[-1].isdigit() and string.isdigit():
            self.keystring += " "
        self.keystring += string
        self.interpret(context)

    def set_string(self, string: str, context=None) -> None:
        """Set string to display

        Args:
            string: String to display
            context: Widget sending string
        """
        self.error = ""
        self.keystring = string
        self.interpret(context, run=True)

    def get_string(self) -> str:
        """Return displayed string

        Returns:
            String
        """
        return self.keystring

    def get_selection_string(self, channels: list[int]) -> str:
        """Create selection string from channels list

        Args:
            channels: List of channels

        Returns:
            Selection string
        """
        ranges = self._detect_range(channels)
        string = ""
        start = True
        for elem in ranges:
            if isinstance(elem, tuple):
                if start:
                    if elem[1] - elem[0] != 1:
                        string = f"chan {elem[0]} thru {elem[1]}"
                    else:
                        string = f"chan {elem[0]} + {elem[1]}"
                    start = False
                else:
                    if elem[1] - elem[0] != 1:
                        string += f" + {elem[0]} thru {elem[1]}"
                    else:
                        string += f" + {elem[0]} + {elem[1]}"
            elif isinstance(elem, int):
                if start:
                    string = f"chan {elem}"
                    start = False
                else:
                    string += f" + {elem}"
        return string

    def _detect_range(self, channels: list[int]):
        start = 0
        length = 0

        for elem in channels:
            # First element
            if start == 0:
                start = elem
                length = 1
                continue
            # Element in row, just count up
            if elem == start + length:
                length += 1
                continue
            # Otherwise, yield
            if length == 1:
                yield start
            else:
                yield (start, start + length - 1)

            start = elem
            length = 1

        if length == 0:
            # Channels list is empty
            yield None
        elif length == 1:
            yield start
        else:
            yield (start, start + length - 1)

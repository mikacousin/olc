# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
import mido
from olc.define import App


class MackieLCD:
    """To display on LCD of Mackie Control"""

    def __init__(self):
        pass

    def send(self, text: str, line: int) -> None:
        """Send text to LCD

        Args:
            text: Text to send
            line: 0 (first line) or 1 (second line)
        """
        if line not in (0, 1):
            return
        chars = [ord(c) for c in text]
        start = line * 56
        data = [0, 0, 102, 20, 18, start] + chars
        msg = mido.Message("sysex", data=data)
        for outport in App().midi.ports.outports:
            outport.send(msg)

    def send_to_strip(self, text: str, line: int, strip: int) -> None:
        """Send text to LCD

        Args:
            text: Text to send
            line: 0 (first line) or 1 (second line)
            strip: Strip number (0 - 7)
        """
        if line not in (0, 1):
            return
        text = f"{text.ljust(7)}"
        text = text[:-1] + "|"
        chars = [ord(c) for c in text]
        start = (line * 56) + (strip * 7)
        data = [0, 0, 102, 20, 18, start] + chars
        msg = mido.Message("sysex", data=data)
        for outport in App().midi.ports.outports:
            outport.send(msg)

    def clear(self) -> None:
        """Clear LCD"""
        text = 56 * " "
        self.send(text, 0)
        self.send(text, 1)

    def show_masters(self) -> None:
        """Show masters name"""
        for master in App().masters:
            if master.page == App().fader_page and master.number <= 8:
                text = master.text[:7]
                strip = master.number - 1
                self.send_to_strip(text, 0, strip)
        self.show_page_number()

    def show_page_number(self) -> None:
        """Show masters page number"""
        text = 56 * " "
        self.send(text, 1)
        text = f"Page {App().fader_page}"
        chars = [ord(c) for c in text]
        start = 56 + int((56 - len(text)) / 2)
        data = [0, 0, 102, 20, 18, start] + chars
        msg = mido.Message("sysex", data=data)
        for outport in App().midi.ports.outports:
            outport.send(msg)

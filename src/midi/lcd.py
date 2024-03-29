# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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

import typing

import mido
from olc.define import App, strip_accents

if typing.TYPE_CHECKING:
    from olc.fader import Fader


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
        text = strip_accents(text)
        chars = [ord(c) for c in text]
        start = line * 56
        data = [0, 0, 102, 20, 18, start] + chars
        msg = mido.Message("sysex", data=data)
        App().midi.enqueue(msg)

    def send_to_strip(self, text: str, line: int, strip: int) -> None:
        """Send text to LCD

        Args:
            text: Text to send
            line: 0 (first line) or 1 (second line)
            strip: Strip number (0 - 7)
        """
        if line not in (0, 1):
            return
        text = strip_accents(text)
        text = f"{text.ljust(7)}"
        text = text[:-1] + "|"
        chars = [ord(c) for c in text]
        start = (line * 56) + (strip * 7)
        data = [0, 0, 102, 20, 18, start] + chars
        msg = mido.Message("sysex", data=data)
        App().midi.enqueue(msg)

    def clear(self) -> None:
        """Clear LCD"""
        text = 56 * " "
        self.send(text, 0)
        self.send(text, 1)

    def show_faders(self) -> None:
        """Show faders name"""
        fader_bank = App().lightshow.fader_bank
        for fader in fader_bank.faders[fader_bank.active_page].values():
            if fader.index <= 8:
                text = fader.text[:7]
                strip = fader.index - 1
                self.send_to_strip(text, 0, strip)
        self.show_page_number()

    def show_fader(self, fader: Fader) -> None:
        """Show fader name

        Args:
            fader: Fader to display
        """
        if fader.index <= 8:
            text = fader.text[:7]
            strip = fader.index - 1
            self.send_to_strip(text, 0, strip)

    def show_page_number(self) -> None:
        """Show fader page number"""
        text = 56 * " "
        self.send(text, 1)
        text = f"Page {App().lightshow.fader_bank.active_page}"
        chars = [ord(c) for c in text]
        start = 56 + int((56 - len(text)) / 2)
        data = [0, 0, 102, 20, 18, start] + chars
        msg = mido.Message("sysex", data=data)
        App().midi.enqueue(msg)

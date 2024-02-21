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
from typing import Any

from gi.repository import Gdk, Gtk
from olc.define import App
from olc.fader import (FaderChannels, FaderGM, FaderGroup, FaderPreset, FaderSequence,
                       FaderType)


class FaderEdit(Gtk.Box):
    """Fader edition widget"""

    page: int
    index: int
    label: Gtk.Label
    type_button: Gtk.MenuButton
    contents_button: Gtk.MenuButton

    def __init__(self, page: int, index: int):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.page = page
        self.index = index

        fader = App().lightshow.fader_bank.faders[page][index]

        self.label = Gtk.Label()

        fader_type = [[FaderType.NONE, ""], [FaderType.PRESET, "Preset"],
                      [FaderType.CHANNELS, "Channels"],
                      [FaderType.SEQUENCE, "Sequence"], [FaderType.GROUP, "Group"],
                      [FaderType.GM, "GM"]]
        self.type_button = Gtk.MenuButton()
        popover = Gtk.Popover()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        for ftype, ftext in fader_type:
            button = Gtk.ModelButton()
            button.set_label(ftext)
            button.connect("clicked", self._on_type_changed, ftype)
            vbox.add(button)
        vbox.show_all()
        popover.add(vbox)
        popover.set_position(Gtk.PositionType.BOTTOM)
        self.type_button.set_popover(popover)

        if isinstance(fader, FaderPreset):
            self._fader_preset()
        elif isinstance(fader, FaderGroup):
            self._fader_group()
        elif isinstance(fader, FaderSequence):
            self._fader_sequence()
        elif isinstance(fader, FaderChannels):
            self._fader_channels()
        elif isinstance(fader, FaderGM):
            self._fader_gm()
        else:
            self._fader_none()

        self.add(self.label)
        self.add(self.type_button)
        self.add(self.contents_button)

    def _fader_none(self) -> None:
        """Create edition of not defined fader"""
        self.label.set_markup(f"<span foreground='#666666'>Fader {self.index}</span>")
        self.set_name("fader_box_empty")
        self.type_button.set_label("")
        self.contents_button = Gtk.MenuButton()
        self.contents_button.set_label("")

    def _fader_gm(self) -> None:
        """Create edition of grand master fader"""
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.set_name("fader_box")
        self.type_button.set_label("GM")
        self.contents_button = Gtk.MenuButton()
        self.contents_button.set_label("")

    def _fader_group(self) -> None:
        """Create edition of group fader"""
        fader = App().lightshow.fader_bank.faders[self.page][self.index]
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.set_name("fader_box")
        self.type_button.set_label("Group")
        self.contents_button = Gtk.MenuButton()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        for group in App().lightshow.groups:
            button = Gtk.ModelButton()
            button.set_label(f"{group.index:g} : {group.text}")
            button.connect("clicked", self._on_contents_changed, FaderType.GROUP,
                           group.index)
            vbox.add(button)
            if group is fader.contents:
                self.contents_button.set_label(f"{group.index:g} : {group.text}")
        self._contents_popup(vbox)

    def _fader_sequence(self) -> None:
        """Create edition of sequence fader"""
        fader = App().lightshow.fader_bank.faders[self.page][self.index]
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.set_name("fader_box")
        self.type_button.set_label("Sequence")
        self.contents_button = Gtk.MenuButton()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        for chaser in App().lightshow.chasers:
            button = Gtk.ModelButton()
            button.set_label(f"{chaser.index:g} : {chaser.text}")
            button.connect("clicked", self._on_contents_changed, FaderType.SEQUENCE,
                           chaser.index)
            vbox.add(button)
            if chaser is fader.contents:
                self.contents_button.set_label(f"{chaser.index:g} : {chaser.text}")
        self._contents_popup(vbox)

    def _fader_preset(self) -> None:
        """Create edition of preset fader"""
        fader = App().lightshow.fader_bank.faders[self.page][self.index]
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.set_name("fader_box")
        self.type_button.set_label("Preset")
        self.contents_button = Gtk.MenuButton()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        for cue in App().lightshow.cues:
            button = Gtk.ModelButton()
            button.set_label(f"{cue.memory} : {cue.text}")
            button.connect("clicked", self._on_contents_changed, FaderType.PRESET,
                           cue.memory)
            vbox.add(button)
            if cue is fader.contents:
                self.contents_button.set_label(f"{cue.memory} : {cue.text}")
        self._contents_popup(vbox)

    def _fader_channels(self) -> None:
        """Create edition of channels fader"""
        self.label.set_markup(f"<span foreground='#666666'>Fader {self.index}</span>")
        self.set_name("fader_box_empty")
        self.type_button.set_label("Channels")
        self.contents_button = Gtk.MenuButton()
        self.contents_button.set_label("")

    def _on_type_changed(self, _widget: Gtk.ModelButton, fader_type: FaderType) -> None:
        App().lightshow.fader_bank.set_fader(self.page, self.index, fader_type)

        self.remove(self.contents_button)

        if fader_type == FaderType.NONE:
            self._fader_none()
        elif fader_type == FaderType.GM:
            self._fader_gm()
        elif fader_type == FaderType.GROUP:
            self._fader_group()
        elif fader_type == FaderType.PRESET:
            self._fader_preset()
        elif fader_type == FaderType.SEQUENCE:
            self._fader_sequence()
        elif fader_type == FaderType.CHANNELS:
            self._fader_channels()
        self.add(self.contents_button)
        self.show_all()

    def _on_contents_changed(self, widget: Gtk.ModelButton, fader_type: FaderType,
                             contents: Any) -> None:
        """Fader contents has been changed

        Args:
            widget: Button clicked
            fader_type: Fader Type
            contents: New contents
        """
        if self.contents_button:
            # Max label size: 30 characters
            self.contents_button.set_label(f"{widget.get_label():<.30}")
        App().lightshow.fader_bank.set_fader(self.page, self.index, fader_type,
                                             contents)

    def _contents_popup(self, vbox: Gtk.Box) -> None:
        """Create contents popover

        Args:
            vbox: Popover box
        """
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(vbox)
        scrollable.show_all()
        popover = Gtk.Popover()
        popover.add(scrollable)
        popover.set_position(Gtk.PositionType.BOTTOM)
        height, _ = vbox.get_preferred_height()
        height = min(height, 600)
        scrollable.set_min_content_height(height)
        if self.contents_button:
            self.contents_button.set_popover(popover)


class FaderTab(Gtk.Box):
    """Fader edition"""

    def __init__(self, fader_bank):
        super().__init__()
        self.fader_bank = fader_bank

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._populate_faders()
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(self.stack)
        vbox.pack_start(stack_switcher, False, True, 0)
        vbox.pack_start(self.stack, True, True, 0)

        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.set_hexpand(True)
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(vbox)
        self.add(scrollable)

    def refresh(self) -> None:
        """Refresh display"""
        widgets = self.stack.get_children()
        for widget in widgets:
            self.stack.remove(widget)
        self._populate_faders()
        self.show_all()

    def on_close_icon(self, _widget) -> None:
        """Close Tab on close clicked"""
        App().tabs.close("faders")

    def _populate_faders(self) -> None:
        """Add faders to tab"""
        for page, faders in self.fader_bank.faders.items():
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            hbox1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hbox1.set_homogeneous(True)
            hbox2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hbox2.set_homogeneous(True)
            for index in faders.keys():
                fader_edit = FaderEdit(page, index)
                # Display faders on 2 lines
                if index <= self.fader_bank.max_fader_per_page / 2:
                    hbox1.add(fader_edit)
                else:
                    hbox2.add(fader_edit)
            vbox.add(hbox1)
            vbox.add(hbox2)
            self.stack.add_titled(vbox, str(page), f"Page {page}")

    def on_key_press_event(self, _widget, event: Gdk.Event) -> Any:
        """Key has been pressed

        Args:
            event: Gdk.EventKey

        Returns:
            False or function
        """
        keyname = Gdk.keyval_name(event.keyval)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        App().tabs.close("faders")

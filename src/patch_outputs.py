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
from typing import List, Tuple
from gi.repository import Gdk, Gtk
from olc.define import App, NB_UNIVERSES, UNIVERSES, is_int, is_non_nul_int
from olc.widgets.patch_outputs import PatchWidget


class PatchOutputsTab(Gtk.Box):
    """Tab to Patch by outputs"""

    def __init__(self, patch):
        self.patch = patch
        self.test = False

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        # Headerbar with buttons
        header = Gtk.HeaderBar()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button()
        button = Gtk.Button("Patch 1:1")
        button.connect("clicked", self.on_button_clicked)
        box.add(button)
        button = Gtk.Button("Unpatch all")
        button.connect("clicked", self.on_button_clicked)
        box.add(button)
        header.pack_end(box)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.outputs = []
        self.channels = []

        for universe in UNIVERSES:
            for out in range(1, 513):
                output = PatchWidget(universe, out)
                self.outputs.extend([output])
                self.flowbox.add(output)

        # Set name for CSS style
        for child in self.flowbox.get_children():
            child.set_name("flowbox_outputs")

        scrolled.add(self.flowbox)

        self.pack_start(header, False, False, 0)
        self.pack_start(scrolled, True, True, 0)

    def on_button_clicked(self, widget):
        """On buttons clicked

        Args:
            widget: Clicked button
        """
        button_label = widget.get_label()

        if button_label == "Unpatch all":
            self.patch.patch_empty()
            self.flowbox.queue_draw()
            App().window.live_view.channels_view.update()
            App().backend.dmx.user_outputs.clear()
            App().backend.dmx.all_outputs_at_zero()

        elif button_label == "Patch 1:1":
            self.patch.patch_1on1()
            self.flowbox.queue_draw()

            for univ in range(NB_UNIVERSES):
                for channel in range(512):
                    level = App().backend.dmx.frame[univ][channel]
                    widget = App().window.live_view.channels_view.get_channel_widget(
                        channel + 1
                    )
                    widget.level = level
                    widget.queue_draw()
            App().window.live_view.channels_view.update()
        App().ascii.set_modified()

    def refresh(self) -> None:
        """Refresh display"""
        self.flowbox.queue_draw()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        if self.test:
            self._stop_test()
        App().tabs.close("patch_outputs")

    def select_outputs(self) -> None:
        """Select Outputs"""
        self.flowbox.unselect_all()
        for output_index in self.patch.by_outputs.outputs:
            output_index -= 1
            child = self.flowbox.get_child_at_index(output_index)
            self.flowbox.select_child(child)
            App().window.set_focus(child)

    def on_key_press_event(self, _widget, event):
        """On key press event

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            App().window.commandline.add_string(keyname)

        if keyname in (
            "KP_1",
            "KP_2",
            "KP_3",
            "KP_4",
            "KP_5",
            "KP_6",
            "KP_7",
            "KP_8",
            "KP_9",
            "KP_0",
        ):
            App().window.commandline.add_string(keyname[3:])

        if keyname == "period":
            App().window.commandline.add_string(".")

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_escape(self) -> None:
        """Close Tab"""
        if self.test:
            self._stop_test()
        App().tabs.close("patch_outputs")

    def _keypress_backspace(self) -> None:
        """Empty keys buffer"""
        App().window.commandline.set_string("")

    def _change_test_output(self, old: int, new: int) -> None:
        """Test a new output

        Args:
            old: Old Output
            new: New Output
        """
        # Get old output level
        child = self.flowbox.get_child_at_index(old)
        output = child.get_child().output
        universe = child.get_child().universe
        level = App().backend.dmx.user_outputs.get((output, universe))
        # Old output at 0
        App().backend.dmx.send_user_output(output, universe, 0)
        # New output at old output level
        child = self.flowbox.get_child_at_index(new)
        output = child.get_child().output
        universe = child.get_child().universe
        App().backend.dmx.send_user_output(output, universe, level)

    def _keypress_right(self) -> None:
        """Next Output"""

        if self.patch.by_outputs.get_selected() == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            App().window.commandline.set_string("1")
            self.patch.by_outputs.select_output()
        elif self.patch.by_outputs.last < (NB_UNIVERSES * 512):
            old_output = self.patch.by_outputs.last
            new_output = old_output + 1
            output, universe = self.patch.by_outputs.get_output_universe(new_output)
            App().window.commandline.set_string(f"{output}.{universe}")
            self.patch.by_outputs.select_output()
            if self.test:
                self._change_test_output(old_output, new_output)

    def _keypress_left(self) -> None:
        """Previous Output"""

        if self.patch.by_outputs.get_selected() == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            App().window.commandline.set_string("1")
            self.patch.by_outputs.select_output()
        elif self.patch.by_outputs.last > 1:
            old_output = self.patch.by_outputs.last
            new_output = old_output - 1
            output, universe = self.patch.by_outputs.get_output_universe(new_output)
            App().window.commandline.set_string(f"{output}.{universe}")
            self.patch.by_outputs.select_output()
            if self.test:
                self._change_test_output(old_output, new_output)

    def _keypress_down(self) -> None:
        """Next Line"""

        if self.patch.by_outputs.get_selected() == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            App().window.commandline.set_string("1")
            self.patch.by_outputs.select_output()
        else:
            old_output = self.patch.by_outputs.last
            child = self.flowbox.get_child_at_index(old_output - 1)
            allocation = child.get_allocation()
            if child := self.flowbox.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            ):
                index = child.get_index()
                new_output = index + 1
                output, universe = self.patch.by_outputs.get_output_universe(new_output)
                App().window.commandline.set_string(f"{output}.{universe}")
                self.patch.by_outputs.select_output()
                if self.test:
                    self._change_test_output(old_output, new_output)

    def _keypress_up(self) -> None:
        """Previous Line"""

        if self.patch.by_outputs.get_selected() == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            App().window.commandline.set_string("1")
            self.patch.by_outputs.select_output()
        else:
            old_output = self.patch.by_outputs.last
            child = self.flowbox.get_child_at_index(old_output - 1)
            allocation = child.get_allocation()
            if child := self.flowbox.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            ):
                index = child.get_index()
                new_output = index + 1
                output, universe = self.patch.by_outputs.get_output_universe(new_output)
                App().window.commandline.set_string(f"{output}.{universe}")
                self.patch.by_outputs.select_output()
                if self.test:
                    self._change_test_output(old_output, new_output)

    def _keypress_o(self) -> None:
        """Select Output"""
        self.patch.by_outputs.select_output()

    def _keypress_equal(self) -> None:
        """Output @ level"""
        keystring = App().window.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        outputs = self.get_selected_outputs()
        for output in outputs:
            out = output[0]
            univ = output[1]
            App().backend.dmx.send_user_output(out, univ, level)
            index = UNIVERSES.index(univ)
            self.outputs[out - 1 + (512 * index)].queue_draw()
        App().window.commandline.set_string("")

    def _keypress_t(self) -> None:
        """Test Output @ level"""
        if self.test:
            self._stop_test()
            return
        keystring = App().window.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        selected_outputs = self.get_selected_outputs()
        if selected_outputs:
            output = selected_outputs[0]
            out = output[0]
            univ = output[1]
            App().backend.dmx.send_user_output(out, univ, level)
            index = UNIVERSES.index(univ)
            self.outputs[out - 1 + (512 * index)].queue_draw()
        self.test = True
        App().window.commandline.set_string("")

    def _stop_test(self) -> None:
        """Stop test mode"""
        App().backend.dmx.user_outputs.clear()
        self.test = False

    def get_selected_outputs(self) -> List[Tuple[int, int]]:
        """Return selected outputs

        Returns:
            Selected outputs/universe numbers
        """
        outputs = []
        selected = self.flowbox.get_selected_children()
        for flowboxchild in selected:
            output_widget = flowboxchild.get_child()
            output = output_widget.output
            universe = output_widget.universe
            outputs.append((output, universe))
        return outputs

    def _keypress_kp_divide(self) -> None:
        """Output Thru"""
        self.thru()

    def _keypress_greater(self) -> None:
        """Output Thru"""
        self.thru()

    def thru(self) -> None:
        """Output Thru"""
        self.patch.by_outputs.thru()

    def _keypress_kp_add(self) -> None:
        """+"""
        self._keypress_plus()

    def _keypress_plus(self) -> None:
        """+"""
        self.patch.by_outputs.add_output()

    def _keypress_kp_subtract(self) -> None:
        """-"""
        self._keypress_minus()

    def _keypress_minus(self) -> None:
        """-"""
        self.patch.by_outputs.del_output()

    def _keypress_c(self) -> None:
        """Patch Channel(s)"""
        several = False
        # Find Selected Outputs
        sel = self.flowbox.get_selected_children()
        keystring = App().window.commandline.get_string()
        if keystring and (not sel or not is_int(keystring)):
            App().window.commandline.set_string("")
            return
        # If several outputs: choose how to patch
        if len(sel) > 1 and is_non_nul_int(keystring):
            dialog = SeveralOutputsDialog(App().window, int(keystring), len(sel))
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                several = True
            dialog.destroy()

        self.patch.by_outputs.patch_channel(several)

        App().ascii.set_modified()
        App().window.commandline.set_string("")


class SeveralOutputsDialog(Gtk.Dialog):
    """Several Outputs Dialog"""

    def __init__(self, parent, channel, out):
        Gtk.Dialog.__init__(
            self,
            "Patch confirmation",
            parent,
            0,
            (
                f"Patch to channel {channel}",
                Gtk.ResponseType.CANCEL,
                f"Patch to {out} channels starting at {channel}",
                Gtk.ResponseType.OK,
            ),
        )

        self.set_default_size(150, 100)

        label = Gtk.Label(
            f"Do you want to patch {out} selected outputs to one or several channels ?"
        )

        box = self.get_content_area()
        box.add(label)
        self.show_all()

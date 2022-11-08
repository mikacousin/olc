# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from typing import List, Optional, Tuple
from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, NB_UNIVERSES, App, is_int, is_non_nul_int
from olc.widgets.patch_outputs import PatchWidget
from olc.zoom import zoom


class PatchOutputsTab(Gtk.Box):
    """Tab to Patch by outputs"""

    def __init__(self):

        self.keystring = ""
        self.last_out_selected = ""
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

        for universe in App().universes:
            self.outputs.extend(PatchWidget(universe, i + 1) for i in range(512))
        for output in self.outputs:
            self.flowbox.add(output)

        # Set name for CSS style
        for child in self.flowbox.get_children():
            child.set_name("flowbox_outputs")

        scrolled.add(self.flowbox)

        self.pack_start(header, False, False, 0)
        self.pack_start(scrolled, True, True, 0)

        self.flowbox.add_events(Gdk.EventMask.SCROLL_MASK)
        self.flowbox.connect("scroll-event", zoom)

    def on_button_clicked(self, widget):
        """On buttons clicked

        Args:
            widget: Clicked button
        """
        button_label = widget.get_label()

        if button_label == "Unpatch all":
            App().patch.patch_empty()
            self.flowbox.queue_draw()
            App().window.live_view.channels_view.update()
            App().dmx.user_outputs.clear()
            App().dmx.all_outputs_at_zero()

        elif button_label == "Patch 1:1":
            App().patch.patch_1on1()
            self.flowbox.queue_draw()

            for univ in range(NB_UNIVERSES):
                for channel in range(512):
                    level = App().dmx.frame[univ][channel]
                    widget = App().window.live_view.channels_view.get_channel_widget(
                        channel + 1
                    )
                    widget.level = level
                    widget.queue_draw()
            App().window.live_view.channels_view.update()
        self.get_parent().grab_focus()

    def on_close_icon(self, _widget):
        """Close Tab on close clicked"""
        notebook = self.get_parent()
        page = notebook.page_num(self)
        notebook.remove_page(page)
        App().patch_outputs_tab = None

    def on_key_press_event(self, _widget, event):
        """On key press event

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.keystring += keyname
            App().window.statusbar.push(App().window.context_id, self.keystring)

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
            self.keystring += keyname[3:]
            App().window.statusbar.push(App().window.context_id, self.keystring)

        if keyname == "period":
            self.keystring += "."
            App().window.statusbar.push(App().window.context_id, self.keystring)

        if func := getattr(self, f"_keypress_{keyname}", None):
            return func()
        return False

    def _keypress_Escape(self):  # pylint: disable=C0103
        """Close Tab"""
        if self.test:
            self._stop_test()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)
        notebook = self.get_parent()
        page = notebook.get_current_page()
        notebook.remove_page(page)
        App().patch_outputs_tab = None

    def _keypress_BackSpace(self):  # pylint: disable=C0103
        """Empty keys buffer"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

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
        level = App().dmx.user_outputs.get((output, universe))
        # Old output at 0
        App().dmx.send_user_output(output, universe, 0)
        # New output at old output level
        child = self.flowbox.get_child_at_index(new)
        output = child.get_child().output
        universe = child.get_child().universe
        App().dmx.send_user_output(output, universe, level)

    def _keypress_Right(self):  # pylint: disable=C0103
        """Next Output"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        elif int(self.last_out_selected) < (len(App().universes) * 512) - 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_out_selected) + 1)
            self.flowbox.select_child(child)
            self.last_out_selected = str(int(self.last_out_selected) + 1)
            if self.test:
                old = int(self.last_out_selected) - 1
                new = int(self.last_out_selected)
                self._change_test_output(old, new)

    def _keypress_Left(self):  # pylint: disable=C0103
        """Previous Output"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        elif int(self.last_out_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_out_selected) - 1)
            self.flowbox.select_child(child)
            self.last_out_selected = str(int(self.last_out_selected) - 1)
            if self.test:
                old = int(self.last_out_selected) + 1
                new = int(self.last_out_selected)
                self._change_test_output(old, new)

    def _keypress_Down(self):  # pylint: disable=C0103
        """Next Line"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        else:
            child = self.flowbox.get_child_at_index(int(self.last_out_selected))
            allocation = child.get_allocation()
            if child := self.flowbox.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            ):
                self.flowbox.unselect_all()
                index = child.get_index()
                self.flowbox.select_child(child)
                self.last_out_selected = str(index)

    def _keypress_Up(self):  # pylint: disable=C0103
        """Previous Line"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        else:
            child = self.flowbox.get_child_at_index(int(self.last_out_selected))
            allocation = child.get_allocation()
            if child := self.flowbox.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            ):
                self.flowbox.unselect_all()
                index = child.get_index()
                self.flowbox.select_child(child)
                self.last_out_selected = str(index)

    def _keypress_o(self):
        """Select Output"""
        self.flowbox.unselect_all()

        if output := self.__get_output_index():
            output -= 1
            child = self.flowbox.get_child_at_index(output)
            self.flowbox.select_child(child)
            self.last_out_selected = str(output)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_equal(self) -> None:
        """Output @ level"""
        if not is_int(self.keystring):
            return
        level = int(self.keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        outputs = self.get_selected_outputs()
        for output in outputs:
            out = output[0]
            univ = output[1]
            App().dmx.send_user_output(out, univ, level)
            index = App().universes.index(univ)
            self.outputs[out - 1 + (512 * index)].queue_draw()
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_t(self) -> None:
        """Test Output @ level"""
        if self.test:
            self._stop_test()
            return
        if not is_int(self.keystring):
            return
        level = int(self.keystring)
        if App().settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        selected_outputs = self.get_selected_outputs()
        if selected_outputs:
            output = selected_outputs[0]
            out = output[0]
            univ = output[1]
            App().dmx.send_user_output(out, univ, level)
            index = App().universes.index(univ)
            self.outputs[out - 1 + (512 * index)].queue_draw()
        self.test = True
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _stop_test(self) -> None:
        """Stop test mode"""
        App().dmx.user_outputs.clear()
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

    def _keypress_KP_Divide(self):  # pylint: disable=C0103
        """Output Thru"""
        self.thru()

    def _keypress_greater(self):
        """Output Thru"""
        self.thru()

    def thru(self):
        """Output Thru"""
        to_out = self.__get_output_index()

        if not self.last_out_selected or not to_out:
            return

        if to_out > int(self.last_out_selected):
            for out in range(int(self.last_out_selected), to_out):
                child = self.flowbox.get_child_at_index(out)
                self.flowbox.select_child(child)
                self.last_out_selected = str(to_out)
        else:
            for out in range(to_out - 1, int(self.last_out_selected)):
                child = self.flowbox.get_child_at_index(out)
                self.flowbox.select_child(child)
                self.last_out_selected = str(to_out)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Add(self):  # pylint: disable=C0103
        """+"""
        self._keypress_plus()

    def _keypress_plus(self):
        """+"""
        if output := self.__get_output_index():
            output -= 1
            child = self.flowbox.get_child_at_index(output)
            self.flowbox.select_child(child)
            self.last_out_selected = str(output)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Subtract(self):  # pylint: disable=C0103
        """-"""
        self._keypress_minus()

    def _keypress_minus(self):
        """-"""
        if output := self.__get_output_index():
            output -= 1
            child = self.flowbox.get_child_at_index(output)
            self.flowbox.unselect_child(child)
            self.last_out_selected = str(output)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_c(self):
        """Patch Channel(s)"""
        several = False
        # Find Selected Outputs
        sel = self.flowbox.get_selected_children()
        if self.keystring and (not sel or not is_int(self.keystring)):
            self.keystring = ""
            App().window.statusbar.push(App().window.context_id, self.keystring)
            return
        # If several outputs: choose how to patch
        if len(sel) > 1 and is_non_nul_int(self.keystring):
            dialog = SeveralOutputsDialog(App().window, int(self.keystring), len(sel))
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                several = True
            dialog.destroy()

        output, index = self._patch(sel, several)

        # Select next output
        if output + (512 * index) < (len(App().universes) * 512):
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(output + (512 * index))
            self.flowbox.select_child(child)
            self.last_out_selected = str(output + (512 * index))

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _patch(self, sel, several):
        """Patch Channel

        Args:
            sel: Widgets selected
            several: Patch Multi-selection on 1 or several channel(s)

        Returns:
            Output (1-512) and Widget index (1-NB_UNIVERSES*512)
        """
        for i, flowboxchild in enumerate(sel):
            patchwidget = flowboxchild.get_child()
            output = patchwidget.output
            univ = patchwidget.universe
            index = App().universes.index(univ)
            # Unpatch if no entry
            if self.keystring in ["", "0"]:
                if univ in App().patch.outputs and output in App().patch.outputs[univ]:
                    channel = App().patch.outputs[univ][output][0]
                    App().patch.unpatch(channel, output, univ)
                else:
                    channel = 0
            # Patch
            else:
                channel = int(self.keystring)
                if 0 < channel <= MAX_CHANNELS:
                    self.__patch(channel, patchwidget, several, i)
            # Update outputs view
            self.outputs[output - 1 + (512 * index)].queue_draw()
            # Update channels view
            if 0 < channel <= MAX_CHANNELS:
                level = App().dmx.frame[index][output - 1]
                widget = App().window.live_view.channels_view.get_channel_widget(
                    channel
                )
                widget.level = level
                widget.queue_draw()
                App().window.live_view.channels_view.update()
        return output, index

    def __patch(self, channel, patchwidget, several, i):
        # Unpatch old value if exist
        output = patchwidget.output
        univ = patchwidget.universe
        old_channel = None
        if univ in App().patch.outputs and output in App().patch.outputs[univ]:
            old_channel = App().patch.outputs[univ][output][0]
        if old_channel:
            App().patch.channels[old_channel].remove([output, univ])
            if len(App().patch.channels[old_channel]) == 0:
                del App().patch.channels[old_channel]
        if several:
            # Patch Channel : increment channels for each output
            App().patch.add_output(channel + i, output, univ)
        else:
            # Patch Channel : same channel for every outputs
            App().patch.add_output(channel, output, univ)

    def _keypress_exclam(self):
        """Proportional level +"""
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            patchwidget = flowboxchild.get_child()
            output = patchwidget.output
            univ = patchwidget.universe
            if App().patch.outputs.get(univ) and App().patch.outputs[univ].get(output):
                App().patch.outputs[univ][output][1] += 1
                App().patch.outputs[univ][output][1] = min(
                    App().patch.outputs[univ][output][1], 100
                )
            index = App().universes.index(univ)
            self.outputs[output - 1 + (512 * index)].queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Proportional level -"""
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            patchwidget = flowboxchild.get_child()
            output = patchwidget.output
            univ = patchwidget.universe
            if App().patch.outputs.get(univ) and App().patch.outputs[univ].get(output):
                App().patch.outputs[univ][output][1] -= 1
                App().patch.outputs[univ][output][1] = max(
                    App().patch.outputs[univ][output][1], 0
                )
            index = App().universes.index(univ)
            self.outputs[output - 1 + (512 * index)].queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def __get_output_index(self) -> Optional[int]:
        """Get Output number

        Returns:
            Integer from 1 to (NB_UNIVERSES * 512).
            Fox example, Output 1 of first universe is 1 and Output 1 of second
            universe is 513.
        """
        output = None
        if self.keystring:
            if "." in self.keystring:
                if self.keystring.index("."):
                    split = self.keystring.split(".")
                    out = int(split[0])
                    if 0 < out <= 512:
                        univ = int(split[1])
                        if univ in App().universes:
                            index = App().universes.index(univ)
                            output = out + (index * 512)
            else:
                output = int(self.keystring)
                if output < 1 or output > 512:
                    output = None
        return output


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

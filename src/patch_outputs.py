"""Patch by outputs"""

from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.widgets_patch_outputs import PatchWidget
from olc.zoom import zoom


class PatchOutputsTab(Gtk.Box):
    """Tab to Patch by outputs"""

    def __init__(self):

        self.keystring = ""
        self.last_out_selected = ""

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

        for universe in range(NB_UNIVERSES):
            for i in range(512):
                self.outputs.append(PatchWidget(universe, i + 1))
        for output in self.outputs:
            self.flowbox.add(output)

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
            App().window.channels_view.flowbox.invalidate_filter()

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    App().dmx.frame[univ][output] = 0

        elif button_label == "Patch 1:1":
            App().patch.patch_1on1()
            self.flowbox.queue_draw()

            for univ in range(NB_UNIVERSES):
                for channel in range(512):
                    level = App().dmx.frame[univ][channel]
                    App().window.channels_view.channels[channel].level = level
                    App().window.channels_view.channels[channel].queue_draw()
            App().window.channels_view.flowbox.invalidate_filter()

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
        # print(keyname)

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

        func = getattr(self, "_keypress_" + keyname, None)
        if func:
            return func()
        return False

    def _keypress_Escape(self):
        """Close Tab"""
        notebook = self.get_parent()
        page = notebook.get_current_page()
        notebook.remove_page(page)
        App().patch_outputs_tab = None

    def _keypress_BackSpace(self):
        """Empty keys buffer"""
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Right(self):
        """Next Output"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        elif int(self.last_out_selected) < 511:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_out_selected) + 1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = str(int(self.last_out_selected) + 1)

    def _keypress_Left(self):
        """Previous Output"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        elif int(self.last_out_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_out_selected) - 1)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = str(int(self.last_out_selected) - 1)

    def _keypress_Down(self):
        """Next Line"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        else:
            child = self.flowbox.get_child_at_index(int(self.last_out_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(
                allocation.x, allocation.y + allocation.height
            )
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(index)

    def _keypress_Up(self):
        """Previous Line"""

        if self.last_out_selected == "":
            child = self.flowbox.get_child_at_index(0)
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = "0"
        else:
            child = self.flowbox.get_child_at_index(int(self.last_out_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(
                allocation.x, allocation.y - allocation.height / 2
            )
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(index)

    def _keypress_o(self):
        """Select Output"""

        self.flowbox.unselect_all()

        if self.keystring != "":
            if "." in self.keystring:
                if self.keystring[0] != ".":
                    split = self.keystring.split(".")
                    output = int(split[0]) - 1
                    univ = int(split[1])
            else:
                output = int(self.keystring) - 1
                univ = 0

            if 0 <= output < 512 and 0 <= univ < NB_UNIVERSES:
                index = output + (univ * 512)
                child = self.flowbox.get_child_at_index(index)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(output)
        else:
            # Verify focus is on Output Widget
            widget = App().window.get_focus()
            if widget.get_path().is_type(Gtk.FlowBoxChild):
                self.flowbox.select_child(widget)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Divide(self):
        """Output Thru"""
        self.thru()

    def _keypress_greater(self):
        """Output Thru"""
        self.thru()

    def thru(self):
        """Output Thru"""
        # If just one output is selected, start from it
        selected = self.flowbox.get_selected_children()
        if len(selected) == 1:
            patchwidget = selected[0].get_children()
            output = patchwidget[0].output - 1
            self.last_out_selected = str(output)

        if not self.last_out_selected:
            return

        to_out = int(self.keystring)

        if to_out > int(self.last_out_selected):
            for out in range(int(self.last_out_selected), to_out):
                child = self.flowbox.get_child_at_index(out)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = self.keystring
        else:
            for out in range(to_out - 1, int(self.last_out_selected)):
                child = self.flowbox.get_child_at_index(out)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = self.keystring

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Add(self):
        """+"""
        self._keypress_plus()

    def _keypress_plus(self):
        """+"""
        if self.keystring != "":
            if "." in self.keystring:
                if self.keystring[0] != ".":
                    split = self.keystring.split(".")
                    output = int(split[0]) - 1
                    univ = int(split[1])
            else:
                output = int(self.keystring) - 1
                univ = 0

            if 0 <= output < 512 and 0 <= univ < NB_UNIVERSES:
                index = output + (univ * 512)
                child = self.flowbox.get_child_at_index(index)
                App().window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(output)
        else:
            # Verify focus is on Output Widget
            widget = App().window.get_focus()
            if widget.get_path().is_type(Gtk.FlowBoxChild):
                self.flowbox.select_child(widget)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_KP_Subtract(self):
        """-"""
        self._keypress_minus()

    def _keypress_minus(self):
        """-"""
        if self.keystring != "":
            if "." in self.keystring:
                if self.keystring[0] != ".":
                    split = self.keystring.split(".")
                    output = int(split[0]) - 1
                    univ = int(split[1])
            else:
                output = int(self.keystring) - 1
                univ = 0

            if 0 <= output < 512 and 0 <= univ < NB_UNIVERSES:
                index = output + (univ * 512)
                child = self.flowbox.get_child_at_index(index)
                App().window.set_focus(child)
                self.flowbox.unselect_child(child)
                self.last_out_selected = str(output)
        else:
            # Verify focus is on Output Widget
            widget = App().window.get_focus()
            if widget.get_path().is_type(Gtk.FlowBoxChild):
                self.flowbox.unselect_child(widget)

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_c(self):
        """Patch Channel(s)"""
        several = False
        # Find Selected Outputs
        sel = self.flowbox.get_selected_children()
        # If several outputs: choose how to patch
        if len(sel) > 1 and self.keystring not in ["", "0"]:
            dialog = SeveralOutputsDialog(App().window, int(self.keystring), len(sel))
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                several = True
            dialog.destroy()
        for i, flowboxchild in enumerate(sel):
            children = flowboxchild.get_children()
            for patchwidget in children:
                output = patchwidget.output - 1
                univ = patchwidget.universe
                # Unpatch if no entry
                if self.keystring in ["", "0"]:
                    channel = App().patch.outputs[univ][output][0]
                    if channel != 0:
                        channel -= 1
                        App().patch.outputs[univ][output][0] = 0
                        App().patch.channels[channel].remove([output + 1, univ])
                        if len(App().patch.channels[channel]) == 0:
                            App().patch.channels[channel] = [[0, 0]]
                        App().dmx.frame[univ][output] = 0
                # Patch
                else:
                    channel = int(self.keystring) - 1
                    if 0 <= channel < MAX_CHANNELS:
                        # Unpatch old value if exist
                        old_channel = App().patch.outputs[univ][output][0]
                        if old_channel != 0:
                            App().patch.channels[old_channel - 1].remove(
                                [output + 1, univ]
                            )
                            if len(App().patch.channels[old_channel - 1]) == 0:
                                App().patch.channels[old_channel - 1] = [[0, 0]]
                        if several:
                            # Patch Channel : increment channels for each output
                            App().patch.add_output(channel + 1 + i, output + 1, univ)
                        else:
                            # Patch Channel : same channel for every outputs
                            App().patch.add_output(channel + 1, output + 1, univ)
                # Update outputs view
                self.outputs[output + (512 * univ)].queue_draw()
                # Update channels view
                if 0 <= channel < MAX_CHANNELS:
                    level = App().dmx.frame[univ][output]
                    App().window.channels_view.channels[channel].level = level
                    App().window.channels_view.channels[channel].queue_draw()
                    App().window.channels_view.flowbox.invalidate_filter()
        # Select next output
        if output < 511:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(output + 1 + (512 * univ))
            App().window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = str(output + 1 + (512 * univ))

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_exclam(self):
        """Proportional level +"""

        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchwidget in children:
                output = patchwidget.output - 1
                univ = patchwidget.universe

                App().patch.outputs[univ][output][1] += 1

                if App().patch.outputs[univ][output][1] > 100:
                    App().patch.outputs[univ][output][1] = 100

                self.outputs[output + (512 * univ)].queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_colon(self):
        """Proportional level -"""

        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()

            for patchwidget in children:
                output = patchwidget.output - 1
                univ = patchwidget.universe

                App().patch.outputs[univ][output][1] -= 1

                if App().patch.outputs[univ][output][1] < 0:
                    App().patch.outputs[univ][output][1] = 0

                self.outputs[output + (512 * univ)].queue_draw()

        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)


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

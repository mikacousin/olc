from gi.repository import Gdk, Gtk
from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.widgets_patch_outputs import PatchWidget


class PatchOutputsTab(Gtk.Grid):
    def __init__(self):

        self.keystring = ""
        self.last_out_selected = ""
        self.last_chan_selected = ""

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        # Headerbar with buttons
        self.header = Gtk.HeaderBar()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button()
        button = Gtk.Button("Patch 1:1")
        button.connect("clicked", self.on_button_clicked)
        box.add(button)
        button = Gtk.Button("Patch Vide")
        button.connect("clicked", self.on_button_clicked)
        box.add(button)
        self.label = Gtk.Label("View: by Outputs")
        self.header.pack_start(self.label)
        self.header.pack_end(box)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.connect("scroll-event", self.on_scroll)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        # self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.outputs = []
        self.channels = []

        for universe in range(NB_UNIVERSES):
            for i in range(512):
                self.outputs.append(PatchWidget(universe, i + 1))
        for output in self.outputs:
            self.flowbox.add(output)

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrolled.add(self.flowbox)

        self.attach(self.header, 0, 0, 1, 1)
        self.attach_next_to(self.scrolled, self.header, Gtk.PositionType.BOTTOM, 1, 10)

    def filter_func(self, child, _user_data):
        return child

    def on_scroll(self, _widget, event):
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if (
            event.state & accel_mask
            == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        ):
            (scroll, direction) = event.get_scroll_direction()
            if scroll and direction == Gdk.ScrollDirection.UP:
                for output in self.outputs:
                    if output.scale <= 2:
                        output.scale += 0.1
                self.flowbox.queue_draw()
            if scroll and direction == Gdk.ScrollDirection.DOWN:
                for output in self.outputs:
                    if output.scale >= 1.1:
                        output.scale -= 0.1
                self.flowbox.queue_draw()

    def on_button_clicked(self, widget):

        button_label = widget.get_label()

        if button_label == "Patch Vide":
            App().patch.patch_empty()
            self.flowbox.queue_draw()
            App().window.flowbox.invalidate_filter()

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    App().dmx.frame[univ][output] = 0

        elif button_label == "Patch 1:1":
            App().patch.patch_1on1()
            self.flowbox.queue_draw()

            for univ in range(NB_UNIVERSES):
                for channel in range(512):
                    level = App().dmx.frame[univ][channel]
                    App().window.channels[channel].level = level
                    App().window.channels[channel].queue_draw()
            App().window.flowbox.invalidate_filter()

    def on_close_icon(self, _widget):
        """ Close Tab on close clicked """
        page = App().window.notebook.page_num(self)
        App().window.notebook.remove_page(page)
        App().patch_outputs_tab = None

    def on_key_press_event(self, _widget, event):
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
        """ Close Tab """
        page = App().window.notebook.get_current_page()
        App().window.notebook.remove_page(page)
        App().patch_outputs_tab = None

    def _keypress_BackSpace(self):
        self.keystring = ""
        App().window.statusbar.push(App().window.context_id, self.keystring)

    def _keypress_Right(self):
        """ Next Output """

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
        """ Previous Output """

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
        """ Next Line """

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
        """ Previous Line """

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
        """ Select Output """

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
        self._keypress_greater()

    def _keypress_greater(self):
        """ Output Thru """

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

    def _keypress_c(self):
        """ Attribute Channel """

        # Find Selected Output
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
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
                        App().dmx.frame[univ][output] = 0
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

                        # Patch Channel : same channel for every outputs
                        App().patch.add_output(channel + 1, output + 1, univ)
                # Update ui
                self.outputs[output + (512 * univ)].queue_draw()

                # Update list of channels
                if 0 <= channel < MAX_CHANNELS:
                    level = App().dmx.frame[univ][output]
                    App().window.channels[channel].level = level
                    App().window.channels[channel].queue_draw()
                    App().window.flowbox.invalidate_filter()
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
        """ Proportional level + """

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
        """ Proportional level - """

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

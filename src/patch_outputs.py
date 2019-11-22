from gi.repository import Gio, Gtk, Gdk

from olc.define import NB_UNIVERSES, MAX_CHANNELS
from olc.dmx import Dmx, PatchDmx
from olc.widgets_patch_outputs import PatchWidget

class PatchOutputsTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

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
        button = Gtk.Button('Patch 1:1')
        button.connect('clicked', self.on_button_clicked)
        box.add(button)
        button = Gtk.Button('Patch Vide')
        button.connect('clicked', self.on_button_clicked)
        box.add(button)
        self.label = Gtk.Label("View: by Outputs")
        self.header.pack_start(self.label)
        self.header.pack_end(box)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        #self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.outputs = []
        self.channels = []

        for universe in range(NB_UNIVERSES):
            for i in range(512):
                self.outputs.append(PatchWidget(universe, i+1, self.app.patch))
        for i in range(len(self.outputs)):
            self.flowbox.add(self.outputs[i])

        self.flowbox.set_filter_func(self.filter_func, None)

        self.scrolled.add(self.flowbox)

        self.attach(self.header, 0, 0, 1, 1)
        self.attach_next_to(self.scrolled, self.header, Gtk.PositionType.BOTTOM, 1, 10)

    def filter_func(self, child, user_data):
        if child.get_children()[0].type == 'Output':
            return child
        else:
            return False

    def on_button_clicked(self, widget):

        button_label = widget.get_label()

        if button_label == "Patch Vide":
            self.app.patch.patch_empty()
            self.flowbox.queue_draw()
            self.app.window.flowbox.invalidate_filter()

            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    self.app.dmx.frame[univ][output] = 0

        elif button_label == "Patch 1:1":
            self.app.patch.patch_1on1()
            self.flowbox.queue_draw()

            for univ in range(NB_UNIVERSES):
                for channel in range(512):
                    level = self.app.dmx.frame[univ][channel]
                    self.app.window.channels[channel].level = level
                    self.app.window.channels[channel].queue_draw()
            self.app.window.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.patch_outputs_tab)
        self.app.window.notebook.remove_page(page)
        self.app.patch_outputs_tab = None

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print(keyname)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'period':
            self.keystring += '.'
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.patch_outputs_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_m(self):
        for i in range(len(self.outputs)):
            if self.outputs[i].scale <= 2:
                self.outputs[i].scale += 0.1
        self.flowbox.queue_draw()

    def keypress_l(self):
        for i in range(len(self.outputs)):
            if self.outputs[i].scale >= 1.1:
                self.outputs[i].scale -= 0.1
        self.flowbox.queue_draw()

    def keypress_Right(self):
        """ Next Output """

        if self.last_out_selected == '':
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = '0'
        elif int(self.last_out_selected) < 511:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_out_selected) + 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = str(int(self.last_out_selected) + 1)

    def keypress_Left(self):
        """ Previous Output """

        if self.last_out_selected == '':
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = '0'
        elif int(self.last_out_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_out_selected) - 1)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = str(int(self.last_out_selected) - 1)

    def keypress_Down(self):
        """ Next Line """

        if self.last_out_selected == '':
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = '0'
        else:
            child = self.flowbox.get_child_at_index(int(self.last_out_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(allocation.x, allocation.y + allocation.height)
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(index)

    def keypress_Up(self):
        """ Previous Line """

        if self.last_out_selected == '':
            child = self.flowbox.get_child_at_index(0)
            self.app.window.set_focus(child)
            self.flowbox.select_child(child)
            self.last_out_selected = '0'
        else:
            child = self.flowbox.get_child_at_index(int(self.last_out_selected))
            allocation = child.get_allocation()
            child = self.flowbox.get_child_at_pos(allocation.x, allocation.y - allocation.height/2)
            if child:
                self.flowbox.unselect_all()
                index = child.get_index()
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(index)

    def keypress_o(self):
        """ Select Output """

        self.flowbox.unselect_all()

        if self.keystring != "":
            if '.' in self.keystring:
                if self.keystring[0] != '.':
                    split = self.keystring.split('.')
                    output = int(split[0]) - 1
                    univ = int(split[1])
            else:
                output = int(self.keystring) - 1
                univ = 0

            if output >= 0 and output < 512 and univ >= 0 and univ < NB_UNIVERSES:
                index = output + (univ * 512)
                child = self.flowbox.get_child_at_index(index)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(output)
        else:
            # Verify focus is on Output Widget
            widget = self.app.window.get_focus()
            if widget.get_path().is_type(Gtk.FlowBoxChild):
                self.flowbox.select_child(widget)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_KP_Divide(self):
        self.keypress_greater()

    def keypress_greater(self):
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
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = self.keystring
        else:
            for out in range(to_out - 1, int(self.last_out_selected)):
                child = self.flowbox.get_child_at_index(out)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = self.keystring

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
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
                if self.keystring == "" or self.keystring == "0":
                    channel = self.app.patch.outputs[univ][output]
                    if channel != 0:
                        channel -= 1
                        self.app.patch.outputs[univ][output] = 0
                        self.app.patch.channels[channel].remove([output + 1, univ])
                        self.app.dmx.frame[univ][output] = 0
                else:
                    channel = int(self.keystring) - 1

                    if channel >= 0 and channel < MAX_CHANNELS:
                        # Unpatch old value if exist
                        old_channel = self.app.patch.outputs[univ][output]
                        if old_channel != 0:
                            self.app.patch.channels[old_channel - 1].remove([output + 1, univ])
                            if not len(self.app.patch.channels[old_channel - 1]):
                                self.app.patch.channels[old_channel - 1] = [[0, 0]]

                        # Patch Channel : same channel for every outputs
                        self.app.patch.add_output(channel+1, output+1, univ)
                # Update ui
                self.outputs[output].queue_draw()

                # Update list of channels
                level = self.app.dmx.frame[univ][output]
                self.app.window.channels[channel].level = level
                self.app.window.channels[channel].queue_draw()
                self.app.window.flowbox.invalidate_filter()
            # Select next output
            if output < 511:
                self.flowbox.unselect_all()
                child = self.flowbox.get_child_at_index(output+1)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(output+1)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

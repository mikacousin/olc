from gi.repository import Gio, Gtk, Gdk

from olc.dmx import Dmx, PatchDmx
from olc.customwidgets   import PatchWidget, PatchChannelWidget

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
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.outputs = []
        self.channels = []

        for i in range(512):
            self.outputs.append(PatchWidget(i+1, self.app.patch))
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

        elif button_label == "Patch 1:1":
            self.app.patch.patch_1on1()
            self.flowbox.queue_draw()

            for channel in range(512):
                level = self.app.dmx.frame[channel]
                self.app.window.channels[channel].level = level
                self.app.window.channels[channel].queue_draw()
            self.app.window.flowbox.invalidate_filter()

    def on_close_icon(self, widget):
        """ Close Tab on close clicked """
        page = self.app.window.notebook.page_num(self.app.patch_tab)
        self.app.window.notebook.remove_page(page)
        self.app.patch_tab = None

    def on_key_press_event(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        #print(keyname)

        if keyname == '1' or keyname == '2' or keyname == '3' or keyname == '4' or keyname == '5' or keyname == '6' or keyname == '7' or keyname == '8' or keyname == '9' or keyname == '0':
            self.keystring += keyname
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        if keyname == 'KP_1' or keyname == 'KP_2' or keyname == 'KP_3' or keyname == 'KP_4' or keyname == 'KP_5' or keyname == 'KP_6' or keyname == 'KP_7' or keyname == 'KP_8' or keyname == 'KP_9' or keyname == 'KP_0':
            self.keystring += keyname[3:]
            self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

        func = getattr(self, 'keypress_' + keyname, None)
        if func:
            return func()

    def keypress_Escape(self):
        """ Close Tab """
        page = self.app.window.notebook.get_current_page()
        self.app.window.notebook.remove_page(page)
        self.app.patch_tab = None

    def keypress_BackSpace(self):
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_o(self):
        """ Select Output """

        self.flowbox.unselect_all()

        if self.keystring != "":
            output = int(self.keystring) - 1
            if output >= 0 and output < 512:
                child = self.flowbox.get_child_at_index(output * 2)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = self.keystring
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
                child = self.flowbox.get_child_at_index(out * 2)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = self.keystring
        else:
            for out in range(to_out - 1, int(self.last_out_selected)):
                child = self.flowbox.get_child_at_index(out * 2)
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

                # Unpatch if no entry
                if self.keystring == "" or self.keystring == "0":
                    channel = self.app.patch.outputs[output]
                    if channel != 0:
                        channel -= 1
                        self.app.patch.outputs[output] = 0
                        self.app.patch.channels[channel].remove(output + 1)
                else:
                    channel = int(self.keystring) - 1

                    if channel >= 0 and channel < 512:
                        # Unpatch old value if exist
                        if self.app.patch.outputs[output] != 0:
                            self.app.patch.channels[self.app.patch.outputs[output]-1].remove(output + 1)
                        # Patch Channel : same channel for every outputs
                        self.app.patch.add_output(channel+1, output+1)
                # Update ui
                self.outputs[output].queue_draw()
                # Update list of channels
                level = self.app.dmx.frame[output]
                self.app.window.channels[channel].level = level
                self.app.window.channels[channel].queue_draw()
                self.app.window.flowbox.invalidate_filter()
            # Select next output
            if output < 511:
                self.flowbox.unselect_all()
                child = self.flowbox.get_child_at_index((output+1) * 2)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
                self.last_out_selected = str(output+1)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

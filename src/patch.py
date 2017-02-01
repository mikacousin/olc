from gi.repository import Gio, Gtk, Gdk

from olc.dmx import Dmx, PatchDmx
from olc.customwidgets   import PatchWidget

class PatchTab(Gtk.Grid):
    def __init__(self):

        self.app = Gio.Application.get_default()

        self.keystring = ""
        self.last_out_selected = ""

        Gtk.Grid.__init__(self)
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_homogeneous(True)
        # TODO: Find how we can patch with thru
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        self.outputs = []

        for i in range(512):
            self.outputs.append(PatchWidget(i+1, self.app.patch))
            self.flowbox.add(self.outputs[i])

        self.scrolled.add(self.flowbox)

        self.buttons = list()
        for type in ["Patch 1:1", "Patch Vide"]:
            button = Gtk.Button(type)
            self.buttons.append(button)
            button.connect('clicked', self.on_button_clicked)

        self.attach(self.scrolled, 0, 0, 2, 12)
        self.attach_next_to(self.buttons[0], self.scrolled, Gtk.PositionType.BOTTOM, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)

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
        """ Output """
        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_o(self):
        """ Select Output """
        if self.keystring != "":
            output = int(self.keystring) - 1
            if output >= 0 and output < 512:
                child = self.flowbox.get_child_at_index(output)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

    def keypress_c(self):
        """ Attribute Channel """

        # Find Selected Output
        output = -1
        sel = self.flowbox.get_selected_children()
        children = []
        for flowboxchild in sel:
            children = flowboxchild.get_children()
        for patchwidget in children:
            output = patchwidget.output - 1

        if output != -1:
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
                    # Patch Channel
                    self.app.patch.add_output(channel+1, output+1)
            # Update ui
            # Select next output
            if output < 511:
                child = self.flowbox.get_child_at_index(output+1)
                self.app.window.set_focus(child)
                self.flowbox.select_child(child)
            self.outputs[output].queue_draw()
            # Update list of channels
            level = self.app.dmx.frame[output]
            self.app.window.channels[channel].level = level
            self.app.window.channels[channel].queue_draw()
            self.app.window.flowbox.invalidate_filter()

        self.keystring = ""
        self.app.window.statusbar.push(self.app.window.context_id, self.keystring)

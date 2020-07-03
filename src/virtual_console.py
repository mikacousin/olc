from gi.repository import Gtk, Gdk

from olc.define import App
from olc.widgets_button import ButtonWidget
from olc.widgets_go import GoWidget
from olc.widgets_fader import FaderWidget
from olc.widgets_flash import FlashWidget


class VirtualConsoleWindow(Gtk.Window):
    def __init__(self):

        self.midi_learn = False

        Gtk.Window.__init__(self, title="Virtual Console")
        self.set_default_size(400, 300)

        # Headerbar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Virtual Console"
        self.set_titlebar(self.header)
        self.midi = Gtk.ToggleButton("MIDI")
        self.midi.set_name("midi_toggle")
        self.midi.connect("toggled", self.on_button_toggled, "MIDI")
        self.header.pack_end(self.midi)

        # Numeric Pad
        self.num_pad = Gtk.Grid()
        # self.num_pad.set_column_homogeneous(True)
        # self.num_pad.set_row_homogeneous(True)
        self.zero = ButtonWidget("0", "Zero")
        self.zero.connect("clicked", self.on_zero)
        self.one = ButtonWidget("1", "1")
        self.one.connect("clicked", self.on_1)
        self.two = ButtonWidget("2", "2")
        self.two.connect("clicked", self.on_2)
        self.three = ButtonWidget("3", "3")
        self.three.connect("clicked", self.on_3)
        self.four = ButtonWidget("4", "4")
        self.four.connect("clicked", self.on_4)
        self.five = ButtonWidget("5", "5")
        self.five.connect("clicked", self.on_5)
        self.six = ButtonWidget("6", "6")
        self.six.connect("clicked", self.on_6)
        self.seven = ButtonWidget("7", "7")
        self.seven.connect("clicked", self.on_7)
        self.eight = ButtonWidget("8", "8")
        self.eight.connect("clicked", self.on_8)
        self.nine = ButtonWidget("9", "9")
        self.nine.connect("clicked", self.on_9)
        self.dot = ButtonWidget(".", "Dot")
        self.dot.connect("clicked", self.on_dot)
        self.clear = ButtonWidget("C", "Clear")
        self.clear.connect("clicked", self.on_clear)
        self.num_pad.attach(self.zero, 0, 3, 1, 1)
        self.num_pad.attach(self.clear, 1, 3, 1, 1)
        self.num_pad.attach(self.dot, 2, 3, 1, 1)
        self.num_pad.attach(self.one, 0, 2, 1, 1)
        self.num_pad.attach(self.two, 1, 2, 1, 1)
        self.num_pad.attach(self.three, 2, 2, 1, 1)
        self.num_pad.attach(self.four, 0, 1, 1, 1)
        self.num_pad.attach(self.five, 1, 1, 1, 1)
        self.num_pad.attach(self.six, 2, 1, 1, 1)
        self.num_pad.attach(self.seven, 0, 0, 1, 1)
        self.num_pad.attach(self.eight, 1, 0, 1, 1)
        self.num_pad.attach(self.nine, 2, 0, 1, 1)

        # Time keys
        self.time_pad = Gtk.Grid()
        # self.time_pad.set_column_homogeneous(True)
        # self.time_pad.set_row_homogeneous(True)
        self.time = ButtonWidget("Time")
        self.delay = ButtonWidget("Delay")
        self.button_in = ButtonWidget("In")
        self.button_out = ButtonWidget("Out")
        # self.labelGM = Gtk.Label('Grand Master')
        self.label = Gtk.Label("")
        self.time_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label("")
        self.time_pad.attach(self.label, 1, 0, 1, 1)
        self.time_pad.attach(self.time, 2, 0, 1, 1)
        self.time_pad.attach(self.delay, 2, 1, 1, 1)
        self.time_pad.attach(self.button_in, 2, 2, 1, 1)
        self.time_pad.attach(self.button_out, 2, 3, 1, 1)

        # Seq, Preset, Group ...
        self.seq_pad = Gtk.Grid()
        # self.seq_pad.set_column_homogeneous(True)
        # self.seq_pad.set_row_homogeneous(True)
        self.seq = ButtonWidget("Seq", "Seq")
        self.seq.connect("clicked", self.on_seq)
        self.empty1 = ButtonWidget(" ")
        self.empty2 = ButtonWidget(" ")
        self.preset = ButtonWidget("Preset", "Preset")
        self.preset.connect("clicked", self.on_preset)
        self.group = ButtonWidget("Group", "Group")
        self.group.connect("clicked", self.on_group)
        self.effect = ButtonWidget("Effect")
        self.seq_pad.attach(self.seq, 0, 2, 1, 1)
        self.seq_pad.attach(self.empty1, 1, 2, 1, 1)
        self.seq_pad.attach(self.empty2, 2, 2, 1, 1)
        self.seq_pad.attach(self.preset, 0, 3, 1, 1)
        self.seq_pad.attach(self.group, 1, 3, 1, 1)
        self.seq_pad.attach(self.effect, 2, 3, 1, 1)
        self.label = Gtk.Label("")
        self.seq_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label("")
        self.seq_pad.attach(self.label, 0, 1, 1, 1)

        # Grand Master and Output grid
        self.output_pad = Gtk.Grid()
        # self.output_pad.set_column_homogeneous(True)
        # self.output_pad.set_row_homogeneous(True)
        ad = Gtk.Adjustment(255, 0, 255, 1, 10, 0)
        self.scaleGM = FaderWidget(
            text="GM", orientation=Gtk.Orientation.VERTICAL, adjustment=ad
        )
        self.scaleGM.value = 255
        # self.scaleGM.height = 160
        self.scaleGM.connect("clicked", self.scale_clicked)
        self.scaleGM.connect("value-changed", self.GM_moved)
        self.scaleGM.set_draw_value(False)
        self.scaleGM.set_vexpand(True)
        self.scaleGM.set_inverted(True)
        self.output = ButtonWidget("Output", "Output")
        self.output.connect("clicked", self.on_output)
        self.output_pad.attach(self.scaleGM, 0, 0, 1, 4)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 1, 0, 1, 1)
        self.output_pad.attach(self.output, 2, 0, 1, 1)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 2, 1, 1, 1)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 2, 2, 1, 1)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 2, 3, 1, 1)

        # Update, Record, Track
        self.rec_pad = Gtk.Grid()
        # self.rec_pad.set_column_homogeneous(True)
        # self.rec_pad.set_row_homogeneous(True)
        self.update = ButtonWidget("Update", "Update")
        self.update.connect("clicked", self.on_update)
        self.record = ButtonWidget("Record", "Record")
        self.record.connect("clicked", self.on_record)
        self.track = ButtonWidget("Track", "Track")
        self.track.connect("clicked", self.on_track)
        self.rec_pad.attach(self.update, 0, 0, 1, 1)
        self.rec_pad.attach(self.record, 2, 0, 1, 1)
        self.rec_pad.attach(self.track, 0, 2, 1, 1)
        self.label = Gtk.Label("")
        self.rec_pad.attach(self.label, 0, 1, 1, 1)
        self.label = Gtk.Label("")
        self.rec_pad.attach(self.label, 0, 3, 1, 1)
        self.label = Gtk.Label("")
        self.rec_pad.attach(self.label, 1, 3, 1, 1)

        # Thru, Channel, +, -, All, @, +%, -%
        self.thru_pad = Gtk.Grid()
        # self.thru_pad.set_column_homogeneous(True)
        # self.thru_pad.set_row_homogeneous(True)
        self.thru = ButtonWidget("Thru", "Thru")
        self.thru.connect("clicked", self.on_thru)
        self.channel = ButtonWidget("Ch", "Ch")
        self.channel.connect("clicked", self.on_channel)
        self.plus = ButtonWidget("+", "Plus")
        self.plus.connect("clicked", self.on_plus)
        self.minus = ButtonWidget("-", "Minus")
        self.minus.connect("clicked", self.on_minus)
        self.all = ButtonWidget("All", "All")
        self.all.connect("clicked", self.on_all)
        self.at = ButtonWidget("@", "At")
        self.at.connect("clicked", self.on_at)
        self.percent_plus = ButtonWidget("+%", "PercentPlus")
        self.percent_plus.connect("clicked", self.on_percent_plus)
        self.percent_minus = ButtonWidget("-%", "PercentMinus")
        self.percent_minus.connect("clicked", self.on_percent_minus)
        self.thru_pad.attach(self.thru, 0, 0, 1, 1)
        self.thru_pad.attach(self.channel, 0, 1, 1, 1)
        self.thru_pad.attach(self.plus, 0, 2, 1, 1)
        self.thru_pad.attach(self.minus, 0, 3, 1, 1)
        self.thru_pad.attach(self.all, 0, 4, 1, 1)
        self.thru_pad.attach(self.at, 2, 0, 1, 1)
        self.thru_pad.attach(self.percent_plus, 2, 1, 1, 1)
        self.thru_pad.attach(self.percent_minus, 2, 2, 1, 1)
        self.label = Gtk.Label("")
        self.thru_pad.attach(self.label, 1, 0, 1, 1)
        self.label = Gtk.Label("")
        self.thru_pad.attach(self.label, 2, 3, 1, 1)
        self.label = Gtk.Label("")
        self.thru_pad.attach(self.label, 2, 4, 1, 1)

        # Insert, Delete, Esc, Modify, Up, Down, Left, Right
        self.modify_pad = Gtk.Grid()
        # self.modify_pad.set_column_homogeneous(True)
        # self.modify_pad.set_row_homogeneous(True)
        self.insert = ButtonWidget("Insert")
        self.delete = ButtonWidget("Delete")
        self.esc = ButtonWidget("Esc")
        self.modify = ButtonWidget("Modify")
        self.up = ButtonWidget("^", "Up")
        self.up.connect("clicked", self.on_up)
        self.down = ButtonWidget("v", "Down")
        self.down.connect("clicked", self.on_down)
        self.left = ButtonWidget("<", "Left")
        self.left.connect("clicked", self.on_left)
        self.right = ButtonWidget(">", "Right")
        self.right.connect("clicked", self.on_right)
        self.modify_pad.attach(self.insert, 0, 0, 1, 1)
        self.modify_pad.attach(self.delete, 2, 0, 1, 1)
        self.modify_pad.attach(self.esc, 0, 2, 1, 1)
        self.modify_pad.attach(self.modify, 2, 2, 1, 1)
        self.modify_pad.attach(self.up, 1, 2, 1, 1)
        self.modify_pad.attach(self.down, 1, 3, 1, 1)
        self.modify_pad.attach(self.left, 0, 3, 1, 1)
        self.modify_pad.attach(self.right, 2, 3, 1, 1)
        self.label = Gtk.Label("")
        self.modify_pad.attach(self.label, 0, 1, 1, 1)

        # Crossfade and more
        self.crossfade_pad = Gtk.Grid()
        # self.crossfade_pad.set_column_homogeneous(True)
        # self.crossfade_pad.set_row_homogeneous(True)
        self.live = ButtonWidget("Live")
        self.format = ButtonWidget("Format")
        self.blind = ButtonWidget("Blind")
        self.goto = ButtonWidget("Goto", "Goto")
        self.goto.connect("clicked", self.on_goto)
        self.a = ButtonWidget("A")
        self.b = ButtonWidget("B")

        self.adA = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scale_a = FaderWidget(
            "Crossfade_out",
            red=0.3,
            green=0.3,
            blue=0.7,
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=self.adA,
        )
        self.scale_a.connect("clicked", self.scale_clicked)
        self.scale_a.set_draw_value(False)
        self.scale_a.set_vexpand(True)
        self.scale_a.set_inverted(True)
        self.scale_a.connect("value-changed", self.scale_moved)

        self.adB = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scale_b = FaderWidget(
            text="Crossfade_in",
            red=0.6,
            green=0.2,
            blue=0.2,
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=self.adB,
        )
        self.scale_b.connect("clicked", self.scale_clicked)
        self.scale_b.set_draw_value(False)
        self.scale_b.set_vexpand(True)
        self.scale_b.set_inverted(True)
        self.scale_b.connect("value-changed", self.scale_moved)

        self.crossfade_pad.attach(self.live, 0, 4, 1, 1)
        self.crossfade_pad.attach(self.format, 0, 5, 1, 1)
        self.crossfade_pad.attach(self.blind, 0, 6, 1, 1)
        self.crossfade_pad.attach(self.goto, 1, 0, 1, 1)
        self.crossfade_pad.attach(self.a, 1, 1, 1, 1)
        self.crossfade_pad.attach(self.b, 2, 1, 1, 1)
        self.crossfade_pad.attach(self.scale_a, 1, 2, 1, 6)
        self.crossfade_pad.attach(self.scale_b, 2, 2, 1, 6)
        self.label = Gtk.Label("")
        self.crossfade_pad.attach(self.label, 0, 7, 1, 1)

        # Go, Seq-, Seq+, Pause, Go Back
        self.go_pad = Gtk.Grid()
        # self.go_pad.set_column_homogeneous(True)
        # self.go_pad.set_row_homogeneous(True)
        self.go = GoWidget()
        self.go.connect("clicked", self.on_go)
        self.seq_plus = ButtonWidget("Seq+", "Seq_plus")
        self.seq_plus.connect("clicked", self.on_seq_plus)
        self.seq_minus = ButtonWidget("Seq-", "Seq_minus")
        self.seq_minus.connect("clicked", self.on_seq_minus)
        self.goback = ButtonWidget("Go Back", "Go_Back")
        self.goback.connect("clicked", self.on_go_back)
        self.pause = ButtonWidget("Pause")
        self.go_pad.attach(self.seq_minus, 0, 0, 1, 1)
        self.go_pad.attach(self.seq_plus, 1, 0, 1, 1)
        self.go_pad.attach(self.pause, 0, 1, 1, 1)
        self.go_pad.attach(self.goback, 1, 1, 1, 1)
        self.go_pad.attach(self.go, 0, 2, 2, 1)
        self.label = Gtk.Label("")
        self.go_pad.attach(self.label, 2, 3, 1, 1)

        # Masters
        self.masters_pad = Gtk.Grid()
        self.masters = []
        self.flashes = []
        for page in range(2):
            for i in range(20):
                ad = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
                self.masters.append(
                    FaderWidget(
                        text="Master " + str(i + (page * 20) + 1),
                        orientation=Gtk.Orientation.VERTICAL,
                        adjustment=ad,
                    )
                )
                self.masters[i + (page * 20)].set_vexpand(True)
                self.masters[i + (page * 20)].set_draw_value(False)
                self.masters[i + (page * 20)].set_inverted(True)
                self.masters[i + (page * 20)].connect(
                    "value-changed", self.master_moved
                )
                self.masters[i + (page * 20)].connect("clicked", self.master_clicked)
                self.flashes.append(FlashWidget(""))
                self.flashes[i + (page * 20)].connect(
                    "button-press-event", self.flash_on
                )
                self.flashes[i + (page * 20)].connect(
                    "button-release-event", self.flash_off
                )
                self.flashes[i + (page * 20)].connect("clicked", self.on_flash)
                self.masters_pad.attach(
                    self.masters[i + (page * 20)], i, 0 + (page * 2), 1, 1
                )
                self.masters_pad.attach(
                    self.flashes[i + (page * 20)], i, 1 + (page * 2), 1, 1
                )
                text = "Flash " + str(i + (page * 20) + 1)
                self.flashes[i + (page * 20)].text = text
            for master in App().masters:
                if master.page == page + 1:
                    self.flashes[master.number - 1 + (page * 20)].label = master.text

        # General Grid
        self.grid = Gtk.Grid()
        # self.grid.set_column_homogeneous(True)
        # self.grid.set_row_homogeneous(True)
        self.grid.set_row_spacing(10)
        self.grid.set_column_spacing(10)
        self.grid.attach(self.output_pad, 0, 0, 1, 1)
        self.grid.attach(self.time_pad, 0, 1, 1, 1)
        self.grid.attach(self.seq_pad, 1, 0, 1, 1)
        self.grid.attach(self.num_pad, 1, 1, 1, 1)
        self.grid.attach(self.rec_pad, 2, 0, 1, 1)
        self.grid.attach(self.thru_pad, 2, 1, 1, 1)
        self.grid.attach(self.modify_pad, 3, 0, 1, 1)
        self.grid.attach(self.crossfade_pad, 4, 0, 1, 2)
        self.grid.attach(self.go_pad, 5, 1, 1, 1)
        self.grid.attach(self.masters_pad, 6, 0, 1, 2)

        self.add(self.grid)

    def on_button_toggled(self, button, name):
        if button.get_active() and name == "MIDI":
            self.midi_learn = True
            App().midi.midi_learn = " "
        elif name == "MIDI":
            self.midi_learn = False
            App().midi.midi_learn = ""
            App().virtual_console.queue_draw()

    def on_go(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Go"
            self.queue_draw()
        else:
            App().sequence.sequence_go(None, None)

    def on_go_back(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Go_Back"
            self.queue_draw()
        else:
            App().sequence.go_back(None, None)

    def on_seq_plus(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Seq_plus"
            self.queue_draw()
        else:
            App().sequence.sequence_plus()

    def on_seq_minus(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Seq_minus"
            self.queue_draw()
        else:
            App().sequence.sequence_minus()

    def on_output(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Output"
            self.queue_draw()
        else:
            App().patch_outputs(None, None)

    def on_seq(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Seq"
            self.queue_draw()
        else:
            App().sequences(None, None)

    def on_preset(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Preset"
            self.queue_draw()
        else:
            App().memories_cb(None, None)

    def on_group(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Group"
            self.queue_draw()
        else:
            App().groups_cb(None, None)

    def on_track(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Track"
            self.queue_draw()
        else:
            App().track_channels(None, None)

    def on_goto(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Goto"
            self.queue_draw()
        else:
            App().sequence.sequence_goto(App().window.keystring)
            App().window.keystring = ""
            App().window.statusbar.push(App().window.context_id, "")

    def on_channel(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Ch"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_c
            App().window.on_key_press_event(None, event)

    def on_thru(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Thru"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_greater
            App().window.on_key_press_event(None, event)

    def on_plus(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_plus
            App().window.on_key_press_event(None, event)

    def on_minus(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_minus
            App().window.on_key_press_event(None, event)

    def on_all(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "All"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_a
            App().window.on_key_press_event(None, event)

    def on_at(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "At"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_equal
            App().window.on_key_press_event(None, event)

    def on_percent_plus(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "PercentPlus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_exclam
            App().window.on_key_press_event(None, event)

    def on_percent_minus(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "PercentMinus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_colon
            App().window.on_key_press_event(None, event)

    def on_update(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Update"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_U
            App().window.on_key_press_event(None, event)

    def on_record(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Record"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_R
            App().window.on_key_press_event(None, event)

    def on_right(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Right"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Right
            App().window.on_key_press_event(None, event)

    def on_left(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Left"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Left
            App().window.on_key_press_event(None, event)

    def on_up(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Up"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Up
            App().window.on_key_press_event(None, event)

    def on_down(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Down"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Down
            App().window.on_key_press_event(None, event)

    def on_clear(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Clear"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_BackSpace
            App().window.on_key_press_event(None, event)

    def on_zero(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Zero"
            self.queue_draw()
        else:
            App().window.keystring += "0"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_1(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "1"
            self.queue_draw()
        else:
            App().window.keystring += "1"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_2(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "2"
            self.queue_draw()
        else:
            App().window.keystring += "2"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_3(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "3"
            self.queue_draw()
        else:
            App().window.keystring += "3"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_4(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "4"
            self.queue_draw()
        else:
            App().window.keystring += "4"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_5(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "5"
            self.queue_draw()
        else:
            App().window.keystring += "5"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_6(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "6"
            self.queue_draw()
        else:
            App().window.keystring += "6"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_7(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "7"
            self.queue_draw()
        else:
            App().window.keystring += "7"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_8(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "8"
            self.queue_draw()
        else:
            App().window.keystring += "8"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_9(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "9"
            self.queue_draw()
        else:
            App().window.keystring += "9"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_dot(self, _widget):
        if self.midi_learn:
            App().midi.midi_learn = "Dot"
            self.queue_draw()
        else:
            App().window.keystring += "."
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def flash_on(self, widget, _event):
        if not self.midi_learn:
            for i, flash in enumerate(self.flashes):
                if flash == widget:
                    # Save Master's value
                    App().masters[i].old_value = App().masters[i].value
                    self.masters[i].set_value(255)
                    App().masters[i].value = 255
                    App().masters[i].level_changed()

    def flash_off(self, widget, _event):
        if not self.midi_learn:
            for i, flash in enumerate(self.flashes):
                if flash == widget:
                    # Restore Master's value
                    self.masters[i].set_value(App().masters[i].old_value)
                    App().masters[i].value = App().masters[i].old_value
                    App().masters[i].level_changed()

    def on_flash(self, widget):
        if self.midi_learn:
            index = self.flashes.index(widget) + 1
            text = "Flash " + str(index)
            App().midi.midi_learn = text
            self.queue_draw()

    def master_moved(self, master):
        if self.midi_learn:
            index = self.masters.index(master) + 1
            text = "Master " + str(index)
            App().midi.midi_learn = text
            self.queue_draw()
        else:
            value = master.get_value()
            index = self.masters.index(master)
            App().masters[index].value = value
            App().masters[index].level_changed()

    def master_clicked(self, master):
        if self.midi_learn:
            index = self.masters.index(master) + 1
            text = "Master " + str(index)
            App().midi.midi_learn = text
            self.queue_draw()

    def scale_moved(self, scale):
        if self.midi_learn:
            if scale == self.scale_a:
                App().midi.midi_learn = "Crossfade_out"
            elif scale == self.scale_b:
                App().midi.midi_learn = "Crossfade_in"
            self.queue_draw()
        else:
            value = scale.get_value()

            if scale == self.scale_a:
                App().crossfade.scale_a.set_value(value)
                if App().crossfade.manual:
                    App().crossfade.scale_moved(App().crossfade.scale_a)
            elif scale == self.scale_b:
                App().crossfade.scale_b.set_value(value)
                if App().crossfade.manual:
                    App().crossfade.scale_moved(App().crossfade.scale_b)

            if (
                self.scale_a.get_value() == 255
                and self.scale_b.get_value() == 255
                and App().crossfade.manual
            ):
                if self.scale_a.get_inverted():
                    self.scale_a.set_inverted(False)
                    self.scale_b.set_inverted(False)
                else:
                    self.scale_a.set_inverted(True)
                    self.scale_b.set_inverted(True)
                self.scale_a.set_value(0)
                self.scale_b.set_value(0)
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.scale_a.emit("button-release-event", event)
                self.scale_b.emit("button-release-event", event)

    def scale_clicked(self, scale):
        if self.midi_learn:
            if scale == self.scale_a:
                App().midi.midi_learn = "Crossfade_out"
            elif scale == self.scale_b:
                App().midi.midi_learn = "Crossfade_in"
            elif scale == self.scaleGM:
                App().midi.midi_learn = "GM"
            self.queue_draw()

    def GM_moved(self, scale):
        if self.midi_learn:
            App().midi.midi_learn = "GM"
            self.queue_draw()
        else:
            value = scale.get_value()

            App().dmx.grand_master = value
            App().window.gm.queue_draw()

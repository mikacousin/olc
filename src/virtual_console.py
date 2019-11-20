import mido
from gi.repository import Gtk, Gio, Gdk
import cairo
import math

from olc.widgets_button import ButtonWidget
from olc.widgets_go import GoWidget
from olc.widgets_fader import FaderWidget

class VirtualConsoleWindow(Gtk.Window):
    def __init__(self):

        self.midi_learn = False

        self.app = Gio.Application.get_default()

        Gtk.Window.__init__(self, title='Virtual Console')
        self.set_default_size(400, 300)

        # Headerbar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Virtual Console"
        self.set_titlebar(self.header)
        self.midi = Gtk.ToggleButton('MIDI')
        self.midi.set_name('midi_toggle')
        self.midi.connect('toggled', self.on_button_toggled, 'MIDI')
        self.header.pack_end(self.midi)

        # Numeric Pad
        self.num_pad = Gtk.Grid()
        #self.num_pad.set_column_homogeneous(True)
        #self.num_pad.set_row_homogeneous(True)
        self.zero = ButtonWidget('0', 'Zero')
        self.zero.connect('clicked', self.on_zero)
        self.one = ButtonWidget('1', '1')
        self.one.connect('clicked', self.on_1)
        self.two = ButtonWidget('2', '2')
        self.two.connect('clicked', self.on_2)
        self.three = ButtonWidget('3', '3')
        self.three.connect('clicked', self.on_3)
        self.four = ButtonWidget('4', '4')
        self.four.connect('clicked', self.on_4)
        self.five = ButtonWidget('5', '5')
        self.five.connect('clicked', self.on_5)
        self.six = ButtonWidget('6', '6')
        self.six.connect('clicked', self.on_6)
        self.seven = ButtonWidget('7', '7')
        self.seven.connect('clicked', self.on_7)
        self.eight = ButtonWidget('8', '8')
        self.eight.connect('clicked', self.on_8)
        self.nine = ButtonWidget('9', '9')
        self.nine.connect('clicked', self.on_9)
        self.dot = ButtonWidget('.', 'Dot')
        self.dot.connect('clicked', self.on_dot)
        self.clear = ButtonWidget('C', 'Clear')
        self.clear.connect('clicked', self.on_clear)
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
        #self.time_pad.set_column_homogeneous(True)
        #self.time_pad.set_row_homogeneous(True)
        self.time = ButtonWidget('Time')
        self.delay = ButtonWidget('Delay')
        self.button_in = ButtonWidget('In')
        self.button_out = ButtonWidget('Out')
        #self.labelGM = Gtk.Label('Grand Master')
        self.label = Gtk.Label('')
        self.time_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label('')
        self.time_pad.attach(self.label, 1, 0, 1, 1)
        self.time_pad.attach(self.time, 2, 0, 1, 1)
        self.time_pad.attach(self.delay, 2, 1, 1, 1)
        self.time_pad.attach(self.button_in, 2, 2, 1, 1)
        self.time_pad.attach(self.button_out, 2, 3, 1, 1)

        # Seq, Preset, Group ...
        self.seq_pad = Gtk.Grid()
        #self.seq_pad.set_column_homogeneous(True)
        #self.seq_pad.set_row_homogeneous(True)
        self.seq = ButtonWidget('Seq')
        self.empty1 = ButtonWidget(' ')
        self.empty2 = ButtonWidget(' ')
        self.preset = ButtonWidget('Preset')
        self.group = ButtonWidget('Group')
        self.effect = ButtonWidget('Effect')
        self.seq_pad.attach(self.seq, 0, 2, 1, 1)
        self.seq_pad.attach(self.empty1, 1, 2, 1, 1)
        self.seq_pad.attach(self.empty2, 2, 2, 1, 1)
        self.seq_pad.attach(self.preset, 0, 3, 1, 1)
        self.seq_pad.attach(self.group, 1, 3, 1, 1)
        self.seq_pad.attach(self.effect, 2, 3, 1, 1)
        self.label = Gtk.Label('')
        self.seq_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label('')
        self.seq_pad.attach(self.label, 0, 1, 1, 1)

        # Grand Master and Output grid
        self.output_pad = Gtk.Grid()
        #self.output_pad.set_column_homogeneous(True)
        #self.output_pad.set_row_homogeneous(True)
        self.adGM = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleGM = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adGM)
        #self.scaleGM.set_draw_value(False)
        self.scaleGM.set_vexpand(True)
        self.scaleGM.set_inverted(True)
        self.output = ButtonWidget('Output', 'Output')
        self.output.connect('clicked', self.on_output)
        self.output_pad.attach(self.scaleGM, 0, 0, 1, 4)
        self.label = Gtk.Label('')
        self.output_pad.attach(self.label, 1, 0, 1, 1)
        self.output_pad.attach(self.output, 2, 0, 1, 1)
        self.label = Gtk.Label('')
        self.output_pad.attach(self.label, 2, 1, 1, 1)
        self.label = Gtk.Label('')
        self.output_pad.attach(self.label, 2, 2, 1, 1)
        self.label = Gtk.Label('')
        self.output_pad.attach(self.label, 2, 3, 1, 1)

        # Update, Record, Track
        self.rec_pad = Gtk.Grid()
        #self.rec_pad.set_column_homogeneous(True)
        #self.rec_pad.set_row_homogeneous(True)
        self.update = ButtonWidget('Update', 'Update')
        self.update.connect('clicked', self.on_update)
        self.record = ButtonWidget('Record')
        self.track = ButtonWidget('Track', 'Track')
        self.track.connect('clicked', self.on_track)
        self.rec_pad.attach(self.update, 0, 0, 1, 1)
        self.rec_pad.attach(self.record, 2, 0, 1, 1)
        self.rec_pad.attach(self.track, 0, 2, 1, 1)
        self.label = Gtk.Label('')
        self.rec_pad.attach(self.label, 0, 1, 1, 1)
        self.label = Gtk.Label('')
        self.rec_pad.attach(self.label, 0, 3, 1, 1)
        self.label = Gtk.Label('')
        self.rec_pad.attach(self.label, 1, 3, 1, 1)

        # Thru, Channel, +, -, All, @, +%, -%
        self.thru_pad = Gtk.Grid()
        #self.thru_pad.set_column_homogeneous(True)
        #self.thru_pad.set_row_homogeneous(True)
        self.thru = ButtonWidget('Thru', 'Thru')
        self.thru.connect('clicked', self.on_thru)
        self.channel = ButtonWidget('Ch', 'Ch')
        self.channel.connect('clicked', self.on_channel)
        self.plus = ButtonWidget('+', 'Plus')
        self.plus.connect('clicked', self.on_plus)
        self.minus = ButtonWidget('-', 'Minus')
        self.minus.connect('clicked', self.on_minus)
        self.all = ButtonWidget('All', 'All')
        self.all.connect('clicked', self.on_all)
        self.at = ButtonWidget('@', 'At')
        self.at.connect('clicked', self.on_at)
        self.percent_plus = ButtonWidget('+%')
        self.percent_minus = ButtonWidget('-%')
        self.thru_pad.attach(self.thru, 0, 0, 1, 1)
        self.thru_pad.attach(self.channel, 0, 1, 1, 1)
        self.thru_pad.attach(self.plus, 0, 2, 1, 1)
        self.thru_pad.attach(self.minus, 0, 3, 1, 1)
        self.thru_pad.attach(self.all, 0, 4, 1, 1)
        self.thru_pad.attach(self.at, 2, 0, 1, 1)
        self.thru_pad.attach(self.percent_plus, 2, 1, 1, 1)
        self.thru_pad.attach(self.percent_minus, 2, 2, 1, 1)
        self.label = Gtk.Label('')
        self.thru_pad.attach(self.label, 1, 0, 1, 1)
        self.label = Gtk.Label('')
        self.thru_pad.attach(self.label, 2, 3, 1, 1)
        self.label = Gtk.Label('')
        self.thru_pad.attach(self.label, 2, 4, 1, 1)

        # Insert, Delete, Esc, Modify, Up, Down, Left, Right
        self.modify_pad = Gtk.Grid()
        #self.modify_pad.set_column_homogeneous(True)
        #self.modify_pad.set_row_homogeneous(True)
        self.insert = ButtonWidget('Insert')
        self.delete = ButtonWidget('Delete')
        self.esc = ButtonWidget('Esc')
        self.modify = ButtonWidget('Modify')
        self.up = ButtonWidget('^')
        self.down = ButtonWidget('v')
        self.left = ButtonWidget('<')
        self.right = ButtonWidget('>')
        self.modify_pad.attach(self.insert, 0, 0, 1, 1)
        self.modify_pad.attach(self.delete, 2, 0, 1, 1)
        self.modify_pad.attach(self.esc, 0, 2, 1, 1)
        self.modify_pad.attach(self.modify, 2, 2, 1, 1)
        self.modify_pad.attach(self.up, 1, 2, 1, 1)
        self.modify_pad.attach(self.down, 1, 3, 1, 1)
        self.modify_pad.attach(self.left, 0, 3, 1, 1)
        self.modify_pad.attach(self.right, 2, 3, 1, 1)
        self.label = Gtk.Label('')
        self.modify_pad.attach(self.label, 0, 1, 1, 1)

        # Crossfade and more
        self.crossfade_pad = Gtk.Grid()
        #self.crossfade_pad.set_column_homogeneous(True)
        #self.crossfade_pad.set_row_homogeneous(True)
        self.live = ButtonWidget('Live')
        self.format = ButtonWidget('Format')
        self.blind = ButtonWidget('Blind')
        self.goto = ButtonWidget('Goto', 'Goto')
        self.goto.connect('clicked', self.on_goto)
        self.a = ButtonWidget('A')
        self.b = ButtonWidget('B')

        """
        self.adA = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleA = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adA)
        self.scaleA.set_draw_value(False)
        self.scaleA.set_vexpand(True)
        self.scaleA.set_inverted(True)
        self.scaleA.connect('value-changed', self.scale_moved)
        self.scaleA.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.scaleA.connect('button-release-event', self.scale_released)
        """
        self.scaleA = FaderWidget(text='Crossfade_out', red=0.3, green=0.3, blue=0.7)
        self.scaleA.connect('clicked', self.scale_clicked)
        self.scaleA.connect('value-changed', self.scale_moved)

        """
        self.adB = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scaleB = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.adB)
        self.scaleB.set_draw_value(False)
        self.scaleB.set_vexpand(True)
        self.scaleB.set_inverted(True)
        self.scaleB.connect('value-changed', self.scale_moved)
        self.scaleB.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.scaleB.connect('button-release-event', self.scale_released)
        """
        self.scaleB = FaderWidget(text='Crossfade_in', red=0.6, green=0.2, blue=0.2)
        self.scaleB.connect('clicked', self.scale_clicked)
        self.scaleB.connect('value-changed', self.scale_moved)

        self.crossfade_pad.attach(self.live, 0, 4, 1, 1)
        self.crossfade_pad.attach(self.format, 0, 5, 1, 1)
        self.crossfade_pad.attach(self.blind, 0, 6, 1, 1)
        self.crossfade_pad.attach(self.goto, 1, 0, 1, 1)
        self.crossfade_pad.attach(self.a, 1, 1, 1, 1)
        self.crossfade_pad.attach(self.b, 2, 1, 1, 1)
        self.crossfade_pad.attach(self.scaleA, 1, 2, 1, 6)
        self.crossfade_pad.attach(self.scaleB, 2, 2, 1, 6)
        self.label = Gtk.Label('')
        self.crossfade_pad.attach(self.label, 0, 7, 1, 1)

        # Go, Seq-, Seq+, Pause, Go Back
        self.go_pad = Gtk.Grid()
        #self.go_pad.set_column_homogeneous(True)
        #self.go_pad.set_row_homogeneous(True)
        self.go = GoWidget()
        self.go.connect('clicked', self.on_go)
        self.seq_plus = ButtonWidget('Seq+', 'Seq_plus')
        self.seq_plus.connect('clicked', self.on_seq_plus)
        self.seq_minus = ButtonWidget('Seq-', 'Seq_minus')
        self.seq_minus.connect('clicked', self.on_seq_minus)
        self.goback = ButtonWidget('Go Back')
        self.pause = ButtonWidget('Pause')
        self.go_pad.attach(self.seq_minus, 0, 0, 1, 1)
        self.go_pad.attach(self.seq_plus, 1, 0, 1, 1)
        self.go_pad.attach(self.pause, 0, 1, 1, 1)
        self.go_pad.attach(self.goback, 1, 1, 1, 1)
        self.go_pad.attach(self.go, 0, 2, 2, 1)
        self.label = Gtk.Label('')
        self.go_pad.attach(self.label, 2, 3, 1, 1)

        # General Grid
        self.grid = Gtk.Grid()
        #self.grid.set_column_homogeneous(True)
        #self.grid.set_row_homogeneous(True)
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

        self.add(self.grid)

    def on_button_toggled(self, button, name):
        if button.get_active() and name == 'MIDI':
            self.midi_learn = True
            self.app.midi.midi_learn = ' '
        elif name == 'MIDI':
            self.midi_learn = False
            self.app.midi.midi_learn = ''
            self.app.virtual_console.queue_draw()

    def on_go(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Go'
            self.queue_draw()
        else:
            self.app.sequence.sequence_go(None, None)

    def on_seq_plus(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Seq_plus'
            self.queue_draw()
        else:
            self.app.sequence.sequence_plus(self.app)

    def on_seq_minus(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Seq_minus'
            self.queue_draw()
        else:
            self.app.sequence.sequence_minus(self.app)

    def on_output(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Output'
            self.queue_draw()
        else:
            self.app._patch_outputs(None, None)

    def on_track(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Track'
            self.queue_draw()
        else:
            self.app._track_channels(None, None)

    def on_goto(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Goto'
            self.queue_draw()
        else:
            self.app.sequence.sequence_goto(self.app, self.app.window.keystring)
            self.app.window.keystring = ''
            self.app.window.statusbar.push(self.app.window.context_id, '')

    def on_channel(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Ch'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_c
            self.app.window.on_key_press_event(None, event)

    def on_thru(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Thru'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_greater
            self.app.window.on_key_press_event(None, event)

    def on_plus(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Plus'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_plus
            self.app.window.on_key_press_event(None, event)

    def on_minus(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Minus'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_minus
            self.app.window.on_key_press_event(None, event)

    def on_all(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'All'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_a
            self.app.window.on_key_press_event(None, event)

    def on_at(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'At'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_equal
            self.app.window.on_key_press_event(None, event)

    def on_update(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Update'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_U
            self.app.window.on_key_press_event(None, event)

    def on_clear(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Clear'
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_BackSpace
            self.app.window.on_key_press_event(None, event)

    def on_zero(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Zero'
            self.queue_draw()
        else:
            self.app.window.keystring += '0'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_1(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '1'
            self.queue_draw()
        else:
            self.app.window.keystring += '1'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_2(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '2'
            self.queue_draw()
        else:
            self.app.window.keystring += '2'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_3(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '3'
            self.queue_draw()
        else:
            self.app.window.keystring += '3'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_4(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '4'
            self.queue_draw()
        else:
            self.app.window.keystring += '4'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_5(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '5'
            self.queue_draw()
        else:
            self.app.window.keystring += '5'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_6(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '6'
            self.queue_draw()
        else:
            self.app.window.keystring += '6'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_7(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '7'
            self.queue_draw()
        else:
            self.app.window.keystring += '7'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_8(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '8'
            self.queue_draw()
        else:
            self.app.window.keystring += '8'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_9(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = '9'
            self.queue_draw()
        else:
            self.app.window.keystring += '9'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def on_dot(self, widget):
        if self.midi_learn:
            self.app.midi.midi_learn = 'Dot'
            self.queue_draw()
        else:
            self.app.window.keystring += '.'
            self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)

    def scale_moved(self, scale):
        if self.midi_learn:
            if scale == self.scaleA:
                self.app.midi.midi_learn = 'Crossfade_out'
            elif scale == self.scaleB:
                self.app.midi.midi_learn = 'Crossfade_in'
            self.queue_draw()
        else:
            value = scale.get_value()

            if scale == self.scaleA:
                self.app.crossfade.scaleA.set_value(value)
            elif scale == self.scaleB:
                self.app.crossfade.scaleB.set_value(value)

            if self.scaleA.get_value() == 255 and self.scaleB.get_value() == 255:
                if self.scaleA.get_inverted():
                    self.scaleA.set_inverted(False)
                    self.scaleB.set_inverted(False)
                else:
                    self.scaleA.set_inverted(True)
                    self.scaleB.set_inverted(True)
                self.scaleA.set_value(0)
                self.scaleB.set_value(0)
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.scaleA.emit('button-release-event', event)
                self.scaleB.emit('button-release-event', event)

    def scale_clicked(self, scale):
        if self.midi_learn:
            if scale == self.scaleA:
                self.app.midi.midi_learn = 'Crossfade_out'
            elif scale == self.scaleB:
                self.app.midi.midi_learn = 'Crossfade_in'
            self.queue_draw()

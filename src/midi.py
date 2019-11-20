import mido
from gi.repository import Gio, Gdk

class MidiFader(object):
    def __init__(self):
        self.value = 0
        self.inverted = True

    def get_inverted(self):
        return self.inverted

    def set_inverted(self, inv):
        if inv == False or inv == True:
            self.inverted = inv

    def get_value(self):
        return self.value

    def set_value(self, value):
        if value >= 0 and value < 128:
            self.value = value

class Midi(object):

    def __init__(self):
        self.inport = None

        self.midi_learn = ''

        # Default MIDI values : Channel, Note / Channel, CC
        self.midi_table = [['Go', 0, 11],
                ['Seq_minus', 0, 12],
                ['Seq_plus', 0, 13],
                ['Output', 0, -1],
                ['Track', 0, -1],
                ['Goto', 0, -1],
                ['Zero', 0, 0],
                ['1', 0, 1],
                ['2', 0, 2],
                ['3', 0, 3],
                ['4', 0, 4],
                ['5', 0, 5],
                ['6', 0, 6],
                ['7', 0, 7],
                ['8', 0, 8],
                ['9', 0, 9],
                ['Dot', 0, -1],
                ['Crossfade_out', 0, 8],
                ['Crossfade_in', 0, 9]]

        self.app = Gio.Application.get_default()

        # Create xfade Faders
        self.xfade_out = MidiFader()
        self.xfade_in = MidiFader()

    def open_input(self, port):
        input_names = mido.get_input_names()
        if port in input_names:
            self.inport = mido.open_input(port)
        else:
            self.inport = mido.open_input()

    def close_input(self):
        if self.inport:
            self.inport.close()

    def scan(self):

        self.percent_view = self.app.settings.get_boolean('percent')

        for msg in self.inport.iter_pending():
            #print(msg)

            # Go
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Go':
                    break
            if self.midi_learn == 'Go':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Go', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.go.emit('button-press-event', event)
                else:
                    self.app.sequence.sequence_go(self.app, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.go.emit('button-release-event', event)

            # Seq -
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Seq_minus':
                    break
            if self.midi_learn == 'Seq_minus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Seq_minus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seq_minus.emit('button-press-event', event)
                else:
                    self.app.window.keypress_q()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seq_minus.emit('button-release-event', event)

            # Seq +
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Seq_plus':
                    break
            if self.midi_learn == 'Seq_plus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Seq_plus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seq_plus.emit('button-press-event', event)
                else:
                    self.app.window.keypress_w()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seq_plus.emit('button-release-event', event)

            # Output
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Output':
                    break
            if self.midi_learn == 'Output':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Output', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.output.emit('button-press-event', event)
                else:
                    self.app._patch_outputs(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.output.emit('button-release-event', event)

            # Track
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Track':
                    break
            if self.midi_learn == 'Track':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Track', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.track.emit('button-press-event', event)
                else:
                    self.app._track_channels(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.track.emit('button-release-event', event)

            # Goto
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Goto':
                    break
            if self.midi_learn == 'Goto':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Goto', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.goto.emit('button-press-event', event)
                else:
                    self.app.sequence.sequence_goto(self.app, self.app.window.keystring)
                    self.app.window.keystring = ''
                    self.app.window.statusbar.push(self.app.window.context_id, '')
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.goto.emit('button-release-event', event)

            # 0
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Zero':
                    break
            if self.midi_learn == 'Zero':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Zero', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.zero.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '0'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.zero.emit('button-release-event', event)

            # 1
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '1':
                    break
            if self.midi_learn == '1':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['1', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.one.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '1'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.one.emit('button-release-event', event)

            # 2
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '2':
                    break
            if self.midi_learn == '2':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['2', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.two.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '2'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.two.emit('button-release-event', event)

            # 3
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '3':
                    break
            if self.midi_learn == '3':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['3', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.three.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '3'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.three.emit('button-release-event', event)

            # 4
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '4':
                    break
            if self.midi_learn == '4':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['4', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.four.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '4'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.four.emit('button-release-event', event)

            # 5
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '5':
                    break
            if self.midi_learn == '5':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['5', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.five.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '5'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.five.emit('button-release-event', event)

            # 6
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '6':
                    break
            if self.midi_learn == '6':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['6', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.six.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '6'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.six.emit('button-release-event', event)

            # 7
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '7':
                    break
            if self.midi_learn == '7':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['7', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seven.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '7'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seven.emit('button-release-event', event)

            # 8
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '8':
                    break
            if self.midi_learn == '8':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['8', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.eight.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '8'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.eight.emit('button-release-event', event)

            # 9
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == '9':
                    break
            if self.midi_learn == '9':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['9', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.nine.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '9'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.nine.emit('button-release-event', event)

            # .
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Dot':
                    break
            if self.midi_learn == 'Dot':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Dot', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.dot.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '.'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == self.midi_table[index][1]
                    and msg.note == self.midi_table[index][2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.dot.emit('button-release-event', event)

            # Manual Crossfade Out
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Crossfade_out':
                    break
            if self.midi_learn == 'Crossfade_out':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Crossfade_out', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == self.midi_table[index][1]
                    and msg.control == self.midi_table[index][2]):
                self.xfade(self.xfade_out, msg.value)

            # Manual Crossfade In
            for index in range(len(self.midi_table)):
                if self.midi_table[index][0] == 'Crossfade_in':
                    break
            if self.midi_learn == 'Crossfade_in':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = 0
                    # Learn new values
                    self.midi_table[index] = ['Crossfade_in', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == self.midi_table[index][1]
                    and msg.control == self.midi_table[index][2]):
                self.xfade(self.xfade_in, msg.value)

    def xfade(self, fader, value):
        if fader.get_inverted():
            val = (value / 127) * 255
            fader.set_value(value)
        else:
            val = abs(((value - 127) / 127) * 255)
            fader.set_value(abs(value - 127))

        if self.app.virtual_console:
            if fader == self.xfade_out:
                self.app.virtual_console.scaleA.set_value(val)
                self.app.virtual_console.scale_moved(self.app.virtual_console.scaleA)
            elif fader == self.xfade_in:
                self.app.virtual_console.scaleB.set_value(val)
                self.app.virtual_console.scale_moved(self.app.virtual_console.scaleB)
        else:
            if fader == self.xfade_out:
                self.app.crossfade.scaleA.set_value(val)
            elif fader == self.xfade_in:
                self.app.crossfade.scaleB.set_value(val)

        if self.xfade_out.get_value() == 127 and self.xfade_in.get_value() == 127:
            if self.xfade_out.get_inverted():
                self.xfade_out.set_inverted(False)
                self.xfade_in.set_inverted(False)
            else:
                self.xfade_out.set_inverted(True)
                self.xfade_in.set_inverted(True)
            self.xfade_out.set_value(0)
            self.xfade_in.set_value(0)

            """
            # Flash 1
            if msg.type == 'note_on' and msg.note == 1 and msg.velocity == 127:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = 100
                    else:
                        val = 255
                    self.app.master_tab.scale[5].set_value(val)
                self.app.masters[5].value = 255
                self.app.masters[5].level_changed()
            elif msg.type == 'note_on' and msg.note == 1 and msg.velocity == 0:
                if self.app.master_tab != None:
                    self.app.master_tab.scale[5].set_value(0)
                self.app.masters[5].value = 0
                self.app.masters[5].level_changed()

            # Flash 3
            if msg.type == 'note_on' and msg.note == 3 and msg.velocity == 127:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = 100
                    else:
                        val = 255
                    self.app.master_tab.scale[14].set_value(val)
                self.app.masters[14].value = 255
                self.app.masters[14].level_changed()
            elif msg.type == 'note_on' and msg.note == 3 and msg.velocity == 0:
                if self.app.master_tab != None:
                    self.app.master_tab.scale[14].set_value(0)
                self.app.masters[14].value = 0
                self.app.masters[14].level_changed()

            # Flash 7
            if msg.type == 'note_on' and msg.note == 7 and msg.velocity == 127:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = 100
                    else:
                        val = 255
                    self.app.master_tab.scale[2].set_value(val)
                self.app.masters[2].value = 255
                self.app.masters[2].level_changed()
            elif msg.type == 'note_on' and msg.note == 7 and msg.velocity == 0:
                if self.app.master_tab != None:
                    self.app.master_tab.scale[2].set_value(0)
                self.app.masters[2].value = 0
                self.app.masters[2].level_changed()

            # Fader 1
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 0:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[10].set_value(val)
                if self.percent_view:
                    self.app.masters[10].value = (msg.value / 127) * 100
                else:
                    self.app.masters[10].value = (msg.value / 127) * 255
                self.app.masters[10].level_changed()

            # Fader 2
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 1:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[11].set_value(val)
                if self.percent_view:
                    self.app.masters[11].value = (msg.value / 127) * 100
                else:
                    self.app.masters[11].value = (msg.value / 127) * 255
                self.app.masters[11].level_changed()

            # Fader 3
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 2:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[0].set_value(val)
                self.app.masters[0].value = (msg.value / 127) * 255
                self.app.masters[0].level_changed()

            # Fader 4
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 3:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[1].set_value(val)
                self.app.masters[1].value = (msg.value / 127) * 255
                self.app.masters[1].level_changed()

            # Fader 5
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 4:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[8].set_value(val)
                self.app.masters[8].value = (msg.value / 127) * 255
                self.app.masters[8].level_changed()

            # Fader 6
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 5:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[4].set_value(val)
                self.app.masters[4].value = (msg.value / 127) * 255
                self.app.masters[4].level_changed()

            # Fader 7
            if msg.type == 'control_change' and msg.channel == 0 and msg.control == 6:
                if self.app.master_tab != None:
                    if self.percent_view:
                        val = (msg.value / 127) * 100
                    else:
                        val = (msg.value / 127) * 255
                    self.app.master_tab.scale[3].set_value(val)
                self.app.masters[3].value = (msg.value / 127) * 255
                self.app.masters[3].level_changed()
            """

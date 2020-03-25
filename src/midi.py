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
                ['Go_Back', 0, -1],
                ['Seq_minus', 0, 12],
                ['Seq_plus', 0, 13],
                ['Output', 0, -1],
                ['Seq', 0, -1],
                ['Group', 0, -1],
                ['Preset', 0, -1],
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
                ['Clear', 0, -1],
                ['Dot', 0, -1],
                ['Right', 0, -1],
                ['Left', 0, -1],
                ['Up', 0, -1],
                ['Down', 0, -1],
                ['Ch', 0, -1],
                ['Thru', 0, -1],
                ['Plus', 0, -1],
                ['Minus', 0, -1],
                ['All', 0, -1],
                ['At', 0, -1],
                ['PercentPlus', 0, -1],
                ['PercentMinus', 0, -1],
                ['Update', 0, -1],
                ['Record', 0, -1],
                ['GM', 0, -1],
                ['Flash 1', 0, -1],
                ['Flash 2', 0, -1],
                ['Flash 3', 0, -1],
                ['Flash 4', 0, -1],
                ['Flash 5', 0, -1],
                ['Flash 6', 0, -1],
                ['Flash 7', 0, -1],
                ['Flash 8', 0, -1],
                ['Flash 9', 0, -1],
                ['Flash 10', 0, -1],
                ['Flash 11', 0, -1],
                ['Flash 12', 0, -1],
                ['Flash 13', 0, -1],
                ['Flash 14', 0, -1],
                ['Flash 15', 0, -1],
                ['Flash 16', 0, -1],
                ['Flash 17', 0, -1],
                ['Flash 18', 0, -1],
                ['Flash 19', 0, -1],
                ['Flash 20', 0, -1],
                ['Flash 21', 0, -1],
                ['Flash 22', 0, -1],
                ['Flash 23', 0, -1],
                ['Flash 24', 0, -1],
                ['Flash 25', 0, -1],
                ['Flash 26', 0, -1],
                ['Flash 27', 0, -1],
                ['Flash 28', 0, -1],
                ['Flash 29', 0, -1],
                ['Flash 30', 0, -1],
                ['Flash 31', 0, -1],
                ['Flash 32', 0, -1],
                ['Flash 33', 0, -1],
                ['Flash 34', 0, -1],
                ['Flash 35', 0, -1],
                ['Flash 36', 0, -1],
                ['Flash 37', 0, -1],
                ['Flash 38', 0, -1],
                ['Flash 39', 0, -1],
                ['Flash 40', 0, -1],
                ['Master 1', 0, -1],
                ['Master 2', 0, -1],
                ['Master 3', 0, -1],
                ['Master 4', 0, -1],
                ['Master 5', 0, -1],
                ['Master 6', 0, -1],
                ['Master 7', 0, -1],
                ['Master 8', 0, -1],
                ['Master 9', 0, -1],
                ['Master 10', 0, -1],
                ['Master 11', 0, -1],
                ['Master 12', 0, -1],
                ['Master 13', 0, -1],
                ['Master 14', 0, -1],
                ['Master 15', 0, -1],
                ['Master 16', 0, -1],
                ['Master 17', 0, -1],
                ['Master 18', 0, -1],
                ['Master 19', 0, -1],
                ['Master 20', 0, -1],
                ['Master 21', 0, -1],
                ['Master 22', 0, -1],
                ['Master 23', 0, -1],
                ['Master 24', 0, -1],
                ['Master 25', 0, -1],
                ['Master 26', 0, -1],
                ['Master 27', 0, -1],
                ['Master 28', 0, -1],
                ['Master 29', 0, -1],
                ['Master 30', 0, -1],
                ['Master 31', 0, -1],
                ['Master 32', 0, -1],
                ['Master 33', 0, -1],
                ['Master 34', 0, -1],
                ['Master 35', 0, -1],
                ['Master 36', 0, -1],
                ['Master 37', 0, -1],
                ['Master 38', 0, -1],
                ['Master 39', 0, -1],
                ['Master 40', 0, -1],
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
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Go':
                    break
            if self.midi_learn == 'Go':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Go', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.go.emit('button-press-event', event)
                else:
                    self.app.sequence.sequence_go(self.app, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.go.emit('button-release-event', event)

            # Go Back
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Go_Back':
                    break
            if self.midi_learn == 'Go_Back':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Go_Back', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.goback.emit('button-press-event', event)
                else:
                    self.app.sequence.go_back(self.app, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.goback.emit('button-release-event', event)

            # Seq -
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Seq_minus':
                    break
            if self.midi_learn == 'Seq_minus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Seq_minus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seq_minus.emit('button-press-event', event)
                else:
                    self.app.window.keypress_q()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seq_minus.emit('button-release-event', event)

            # Seq +
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Seq_plus':
                    break
            if self.midi_learn == 'Seq_plus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Seq_plus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seq_plus.emit('button-press-event', event)
                else:
                    self.app.window.keypress_w()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seq_plus.emit('button-release-event', event)

            # Output
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Output':
                    break
            if self.midi_learn == 'Output':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Output', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.output.emit('button-press-event', event)
                else:
                    self.app._patch_outputs(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.output.emit('button-release-event', event)

            # Sequences
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Seq':
                    break
            if self.midi_learn == 'Seq':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Seq', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seq.emit('button-press-event', event)
                else:
                    self.app._sequences(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seq.emit('button-release-event', event)

            # Group
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Group':
                    break
            if self.midi_learn == 'Group':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Group', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.group.emit('button-press-event', event)
                else:
                    self.app._groups(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.group.emit('button-release-event', event)

            # Preset
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Preset':
                    break
            if self.midi_learn == 'Preset':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Preset', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.preset.emit('button-press-event', event)
                else:
                    self.app._groups(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.preset.emit('button-release-event', event)

            # Track
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Track':
                    break
            if self.midi_learn == 'Track':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Track', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.track.emit('button-press-event', event)
                else:
                    self.app._track_channels(None, None)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.track.emit('button-release-event', event)

            # Goto
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Goto':
                    break
            if self.midi_learn == 'Goto':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Goto', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.goto.emit('button-press-event', event)
                else:
                    self.app.sequence.sequence_goto(self.app.window.keystring)
                    self.app.window.keystring = ''
                    self.app.window.statusbar.push(self.app.window.context_id, '')
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.goto.emit('button-release-event', event)

            # Channel
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Ch':
                    break
            if self.midi_learn == 'Ch':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Ch', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.channel.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_c
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.channel.emit('button-release-event', event)

            # Thru
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Thru':
                    break
            if self.midi_learn == 'Thru':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Thru', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.thru.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_greater
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.thru.emit('button-release-event', event)

            # Channel +
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Plus':
                    break
            if self.midi_learn == 'Plus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Plus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.plus.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_plus
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.plus.emit('button-release-event', event)

            # Channel -
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Minus':
                    break
            if self.midi_learn == 'Minus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Minus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.minus.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_minus
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.minus.emit('button-release-event', event)

            # All
            for index, item in enumerate(self.midi_table):
                if item[0] == 'All':
                    break
            if self.midi_learn == 'All':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['All', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.all.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_a
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.all.emit('button-release-event', event)

            # Right
            for index, item in enumerate(self.midi_table):
                if self.midi_table[index][0] == 'Right':
                    break
            if self.midi_learn == 'Right':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Right', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.right.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_Right
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.right.emit('button-release-event', event)

            # Left
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Left':
                    break
            if self.midi_learn == 'Left':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Left', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.left.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_Left
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.left.emit('button-release-event', event)

            # Up
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Up':
                    break
            if self.midi_learn == 'Up':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Up', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.up.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_Up
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.up.emit('button-release-event', event)

            # Down
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Down':
                    break
            if self.midi_learn == 'Down':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Down', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.down.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_Down
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.down.emit('button-release-event', event)

            # Clear
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Clear':
                    break
            if self.midi_learn == 'Clear':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Clear', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.clear.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_BackSpace
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.clear.emit('button-release-event', event)

            # At level
            for index, item in enumerate(self.midi_table):
                if item[0] == 'At':
                    break
            if self.midi_learn == 'At':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['At', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.at.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_equal
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.at.emit('button-release-event', event)

            # Percent Plus
            for index, item in enumerate(self.midi_table):
                if item[0] == 'PercentPlus':
                    break
            if self.midi_learn == 'PercentPlus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['PercentPlus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.percent_plus.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_exclam
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.percent_plus.emit('button-release-event', event)

            # Percent Minus
            for index, item in enumerate(self.midi_table):
                if item[0] == 'PercentMinus':
                    break
            if self.midi_learn == 'PercentMinus':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['PercentMinus', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.percent_minus.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_colon
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.percent_minus.emit('button-release-event', event)

            # Update
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Update':
                    break
            if self.midi_learn == 'Update':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Update', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.update.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_U
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.update.emit('button-release-event', event)

            # Record
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Record':
                    break
            if self.midi_learn == 'Record':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Record', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.record.emit('button-press-event', event)
                else:
                    event = Gdk.EventKey()
                    event.keyval = Gdk.KEY_R
                    self.app.window.on_key_press_event(None, event)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.record.emit('button-release-event', event)

            # 0
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Zero':
                    break
            if self.midi_learn == 'Zero':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Zero', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.zero.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '0'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.zero.emit('button-release-event', event)

            # 1
            for index, item in enumerate(self.midi_table):
                if item[0] == '1':
                    break
            if self.midi_learn == '1':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['1', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.one.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '1'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.one.emit('button-release-event', event)

            # 2
            for index, item in enumerate(self.midi_table):
                if item[0] == '2':
                    break
            if self.midi_learn == '2':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['2', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.two.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '2'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.two.emit('button-release-event', event)

            # 3
            for index, item in enumerate(self.midi_table):
                if item[0] == '3':
                    break
            if self.midi_learn == '3':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['3', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.three.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '3'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.three.emit('button-release-event', event)

            # 4
            for index, item in enumerate(self.midi_table):
                if item[0] == '4':
                    break
            if self.midi_learn == '4':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['4', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.four.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '4'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.four.emit('button-release-event', event)

            # 5
            for index, item in enumerate(self.midi_table):
                if item[0] == '5':
                    break
            if self.midi_learn == '5':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['5', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.five.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '5'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.five.emit('button-release-event', event)

            # 6
            for index, item in enumerate(self.midi_table):
                if item[0] == '6':
                    break
            if self.midi_learn == '6':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['6', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.six.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '6'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.six.emit('button-release-event', event)

            # 7
            for index, item in enumerate(self.midi_table):
                if item[0] == '7':
                    break
            if self.midi_learn == '7':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['7', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.seven.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '7'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.seven.emit('button-release-event', event)

            # 8
            for index, item in enumerate(self.midi_table):
                if item[0] == '8':
                    break
            if self.midi_learn == '8':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['8', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.eight.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '8'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.eight.emit('button-release-event', event)

            # 9
            for index, item in enumerate(self.midi_table):
                if item[0] == '9':
                    break
            if self.midi_learn == '9':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['9', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.nine.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '9'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.nine.emit('button-release-event', event)

            # .
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Dot':
                    break
            if self.midi_learn == 'Dot':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Dot', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.dot.emit('button-press-event', event)
                else:
                    self.app.window.keystring += '.'
                    self.app.window.statusbar.push(self.app.window.context_id, self.app.window.keystring)
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.dot.emit('button-release-event', event)

            # Flash 1
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 1':
                    break
            if self.midi_learn == 'Flash 1':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 1', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[0].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 1:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[0].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 1:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 2
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 2':
                    break
            if self.midi_learn == 'Flash 2':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 2', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[1].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 2:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[1].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 2:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 3
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 3':
                    break
            if self.midi_learn == 'Flash 3':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 3', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[2].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 3:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[2].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 3:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 4
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 4':
                    break
            if self.midi_learn == 'Flash 4':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 4', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[3].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 4:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[3].emit('button-release-event', event)
                else:
                    for master in enumerate(self.app.masters):
                        if master.page == 1 and master.number == 4:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 5
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 5':
                    break
            if self.midi_learn == 'Flash 5':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 5', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[4].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 5:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[4].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 5:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 6
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 6':
                    break
            if self.midi_learn == 'Flash 6':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 6', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[5].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 6:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[5].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 6:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 7
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 7':
                    break
            if self.midi_learn == 'Flash 7':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 7', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[6].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 7:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[6].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 7:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 8
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 8':
                    break
            if self.midi_learn == 'Flash 8':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 8', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[7].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 8:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[7].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 8:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 9
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 9':
                    break
            if self.midi_learn == 'Flash 9':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 9', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[8].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 9:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[8].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 9:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 10
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 10':
                    break
            if self.midi_learn == 'Flash 10':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 10', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[9].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if self.app.masters[i].page == 1 and self.app.masters[i].number == 10:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[9].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 10:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 11
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 11':
                    break
            if self.midi_learn == 'Flash 11':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 11', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[10].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 11:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[10].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 11:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 12
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 12':
                    break
            if self.midi_learn == 'Flash 12':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 12', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[11].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 12:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[11].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 12:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 13
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 13':
                    break
            if self.midi_learn == 'Flash 13':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 13', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[12].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 13:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[12].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 13:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 14
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 14':
                    break
            if self.midi_learn == 'Flash 14':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 14', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[13].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 14:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[13].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 14:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 15
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 15':
                    break
            if self.midi_learn == 'Flash 15':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 15', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[14].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 15:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[14].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 15:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 16
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 16':
                    break
            if self.midi_learn == 'Flash 16':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 16', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[15].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 16:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[15].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 16:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 17
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 17':
                    break
            if self.midi_learn == 'Flash 17':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 17', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[16].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 17:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[16].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 17:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 18
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 18':
                    break
            if self.midi_learn == 'Flash 18':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 18', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[17].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 18:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[17].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 18:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 19
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 19':
                    break
            if self.midi_learn == 'Flash 19':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 19', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[18].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 19:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[18].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 19:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 20
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 20':
                    break
            if self.midi_learn == 'Flash 20':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 20', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[19].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 20:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[19].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 20:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 21
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 21':
                    break
            if self.midi_learn == 'Flash 21':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 21', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[20].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 1:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[20].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 1:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 22
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 22':
                    break
            if self.midi_learn == 'Flash 22':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 22', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[21].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 2:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[21].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 2:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 23
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 23':
                    break
            if self.midi_learn == 'Flash 23':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 23', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[22].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 3:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[22].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 3:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 24
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 24':
                    break
            if self.midi_learn == 'Flash 24':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 24', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[23].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 4:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[23].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 4:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 25
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 25':
                    break
            if self.midi_learn == 'Flash 25':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 25', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[24].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 5:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[24].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 5:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 26
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 26':
                    break
            if self.midi_learn == 'Flash 26':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 26', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[25].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 6:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[25].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 6:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 27
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 27':
                    break
            if self.midi_learn == 'Flash 27':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 27', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[26].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 7:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[26].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 7:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 28
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 28':
                    break
            if self.midi_learn == 'Flash 28':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 28', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[27].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 8:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[27].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 8:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 29
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 29':
                    break
            if self.midi_learn == 'Flash 29':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 29', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[28].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 9:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[28].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 9:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 30
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 30':
                    break
            if self.midi_learn == 'Flash 30':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 30', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[29].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 10:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[29].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 10:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 31
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 31':
                    break
            if self.midi_learn == 'Flash 31':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 31', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[30].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 11:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[30].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 11:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 32
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 32':
                    break
            if self.midi_learn == 'Flash 32':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 32', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[31].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 12:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[31].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 12:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 33
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 33':
                    break
            if self.midi_learn == 'Flash 33':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 33', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[32].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 13:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[32].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 13:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 34
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 34':
                    break
            if self.midi_learn == 'Flash 34':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 34', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[33].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 14:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[33].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 14:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 35
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 35':
                    break
            if self.midi_learn == 'Flash 35':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 35', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[34].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 15:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[34].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 15:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 36
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 36':
                    break
            if self.midi_learn == 'Flash 36':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 36', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[35].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 16:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[35].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 16:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 37
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 37':
                    break
            if self.midi_learn == 'Flash 37':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 37', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[36].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 17:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[36].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 17:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 38
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 38':
                    break
            if self.midi_learn == 'Flash 38':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 38', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[37].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 18:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[37].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 18:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 39
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 39':
                    break
            if self.midi_learn == 'Flash 39':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 39', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[38].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 19:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[38].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 19:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Flash 40
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Flash 40':
                    break
            if self.midi_learn == 'Flash 40':
                if msg.type == 'note_on':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.note:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Flash 40', msg.channel, msg.note]
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 127):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_PRESS)
                    self.app.virtual_console.flashes[39].emit('button-press-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 20:
                            break
                    master.old_value = master.value
                    master.value = 255
                    master.level_changed()
            elif (not self.midi_learn and msg.type == 'note_on'
                    and msg.channel == item[1]
                    and msg.note == item[2]
                    and msg.velocity == 0):
                if self.app.virtual_console:
                    event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                    self.app.virtual_console.flashes[39].emit('button-release-event', event)
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 20:
                            break
                    master.value = master.old_value
                    master.level_changed()

            # Master 1
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 1':
                    break
            if self.midi_learn == 'Master 1':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 1', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[0].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[0])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 1:
                            break
                    master.value = val
                    master.level_changed()

            # Master 2
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 2':
                    break
            if self.midi_learn == 'Master 2':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 2', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[1].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[1])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 2:
                            break
                    master.value = val
                    master.level_changed()

            # Master 3
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 3':
                    break
            if self.midi_learn == 'Master 3':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 3', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[2].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[2])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 3:
                            break
                    master.value = val
                    master.level_changed()

            # Master 4
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 4':
                    break
            if self.midi_learn == 'Master 4':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 4', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[3].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[3])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 4:
                            break
                    master.value = val
                    master.level_changed()

            # Master 5
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 5':
                    break
            if self.midi_learn == 'Master 5':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 5', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[4].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[4])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 5:
                            break
                    master.value = val
                    master.level_changed()

            # Master 6
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 6':
                    break
            if self.midi_learn == 'Master 6':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 6', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[5].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[5])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 6:
                            break
                    master.value = val
                    master.level_changed()

            # Master 7
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 7':
                    break
            if self.midi_learn == 'Master 7':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 7', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[6].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[6])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 7:
                            break
                    master.value = val
                    master.level_changed()

            # Master 8
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 8':
                    break
            if self.midi_learn == 'Master 8':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 8', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[7].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[7])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 8:
                            break
                    master.value = val
                    master.level_changed()

            # Master 9
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 9':
                    break
            if self.midi_learn == 'Master 9':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 9', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[8].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[8])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 9:
                            break
                    master.value = val
                    master.level_changed()

            # Master 10
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 10':
                    break
            if self.midi_learn == 'Master 10':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 10', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[9].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[9])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 10:
                            break
                    master.value = val
                    master.level_changed()

            # Master 11
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 11':
                    break
            if self.midi_learn == 'Master 11':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 11', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[10].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[10])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 11:
                            break
                    master.value = val
                    master.level_changed()

            # Master 12
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 12':
                    break
            if self.midi_learn == 'Master 12':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 12', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[11].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[11])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 12:
                            break
                    master.value = val
                    master.level_changed()

            # Master 13
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 13':
                    break
            if self.midi_learn == 'Master 13':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 13', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[12].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[12])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 13:
                            break
                    master.value = val
                    master.level_changed()

            # Master 14
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 14':
                    break
            if self.midi_learn == 'Master 14':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 14', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[13].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[13])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 14:
                            break
                    master.value = val
                    master.level_changed()

            # Master 15
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 15':
                    break
            if self.midi_learn == 'Master 15':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 15', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[14].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[14])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 15:
                            break
                    master.value = val
                    master.level_changed()

            # Master 16
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 16':
                    break
            if self.midi_learn == 'Master 16':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 16', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[15].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[15])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 16:
                            break
                    master.value = val
                    master.level_changed()

            # Master 17
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 17':
                    break
            if self.midi_learn == 'Master 17':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 17', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[16].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[16])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 17:
                            break
                    master.value = val
                    master.level_changed()

            # Master 18
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 18':
                    break
            if self.midi_learn == 'Master 18':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 18', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[17].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[17])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 18:
                            break
                    master.value = val
                    master.level_changed()

            # Master 19
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 19':
                    break
            if self.midi_learn == 'Master 19':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 19', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[18].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[18])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 19:
                            break
                    master.value = val
                    master.level_changed()

            # Master 20
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 20':
                    break
            if self.midi_learn == 'Master 20':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 20', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[19].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[19])
                else:
                    for master in self.app.masters:
                        if master.page == 1 and master.number == 20:
                            break
                    master.value = val
                    master.level_changed()

            # Master 21
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 21':
                    break
            if self.midi_learn == 'Master 21':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 21', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[20].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[20])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 1:
                            break
                    master.value = val
                    master.level_changed()

            # Master 22
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 22':
                    break
            if self.midi_learn == 'Master 22':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 22', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[21].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[21])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 2:
                            break
                    master.value = val
                    master.level_changed()

            # Master 23
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 23':
                    break
            if self.midi_learn == 'Master 23':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 23', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[22].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[22])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 3:
                            break
                    master.value = val
                    master.level_changed()

            # Master 24
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 24':
                    break
            if self.midi_learn == 'Master 24':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 24', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[23].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[23])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 4:
                            break
                    master.value = val
                    master.level_changed()

            # Master 25
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 25':
                    break
            if self.midi_learn == 'Master 25':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 25', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[24].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[24])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 5:
                            break
                    master.value = val
                    master.level_changed()

            # Master 26
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 26':
                    break
            if self.midi_learn == 'Master 26':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 26', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[25].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[25])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 6:
                            break
                    master.value = val
                    master.level_changed()

            # Master 27
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 27':
                    break
            if self.midi_learn == 'Master 27':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 27', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[26].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[26])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 7:
                            break
                    master.value = val
                    master.level_changed()

            # Master 28
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 28':
                    break
            if self.midi_learn == 'Master 28':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 28', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[27].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[27])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 8:
                            break
                    master.value = val
                    master.level_changed()

            # Master 29
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 29':
                    break
            if self.midi_learn == 'Master 29':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 29', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[28].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[28])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 9:
                            break
                    master.value = val
                    master.level_changed()

            # Master 30
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 30':
                    break
            if self.midi_learn == 'Master 30':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 30', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[29].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[29])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 10:
                            break
                    master.value = val
                    master.level_changed()

            # Master 31
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 31':
                    break
            if self.midi_learn == 'Master 31':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 31', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[30].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[30])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 11:
                            break
                    master.value = val
                    master.level_changed()

            # Master 32
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 32':
                    break
            if self.midi_learn == 'Master 32':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 32', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[31].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[31])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 12:
                            break
                    master.value = val
                    master.level_changed()

            # Master 33
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 33':
                    break
            if self.midi_learn == 'Master 33':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 33', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[32].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[32])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 13:
                            break
                    master.value = val
                    master.level_changed()

            # Master 34
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 34':
                    break
            if self.midi_learn == 'Master 34':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 34', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[33].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[33])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 14:
                            break
                    master.value = val
                    master.level_changed()

            # Master 35
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 35':
                    break
            if self.midi_learn == 'Master 35':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 35', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[34].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[34])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 15:
                            break
                    master.value = val
                    master.level_changed()

            # Master 36
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 36':
                    break
            if self.midi_learn == 'Master 36':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 36', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[35].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[35])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 16:
                            break
                    master.value = val
                    master.level_changed()

            # Master 37
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 37':
                    break
            if self.midi_learn == 'Master 37':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 37', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[36].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[36])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 17:
                            break
                    master.value = val
                    master.level_changed()

            # Master 38
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 38':
                    break
            if self.midi_learn == 'Master 38':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 38', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[37].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[37])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 18:
                            break
                    master.value = val
                    master.level_changed()

            # Master 39
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 39':
                    break
            if self.midi_learn == 'Master 39':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 39', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[38].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[38])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 19:
                            break
                    master.value = val
                    master.level_changed()

            # Master 40
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Master 40':
                    break
            if self.midi_learn == 'Master 40':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Master 40', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.masters[39].set_value(val)
                    self.app.virtual_console.master_moved(self.app.virtual_console.masters[39])
                else:
                    for master in self.app.masters:
                        if master.page == 2 and master.number == 20:
                            break
                    master.value = val
                    master.level_changed()

            # Grand Master
            for index, item in enumerate(self.midi_table):
                if item[0] == 'GM':
                    break
            if self.midi_learn == 'GM':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['GM', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                val = (msg.value / 127) * 255
                if self.app.virtual_console:
                    self.app.virtual_console.scaleGM.set_value(val)
                    self.app.virtual_console.GM_moved(self.app.virtual_console.scaleGM)
                else:
                    self.app.dmx.grand_master = val
                    self.app.window.gm.queue_draw()

            # Manual Crossfade Out
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Crossfade_out':
                    break
            if self.midi_learn == 'Crossfade_out':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Crossfade_out', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                self.xfade(self.xfade_out, msg.value)

            # Manual Crossfade In
            for index, item in enumerate(self.midi_table):
                if item[0] == 'Crossfade_in':
                    break
            if self.midi_learn == 'Crossfade_in':
                if msg.type == 'control_change':
                    # Delete if used
                    for i, message in enumerate(self.midi_table):
                        if message[1] == msg.channel and message[2] == msg.control:
                            self.midi_table[i][1] = 0
                            self.midi_table[i][2] = -1
                    # Learn new values
                    self.midi_table[index] = ['Crossfade_in', msg.channel, msg.control]
            elif (not self.midi_learn and msg.type == 'control_change'
                    and msg.channel == item[1]
                    and msg.control == item[2]):
                self.xfade(self.xfade_in, msg.value)

    def xfade(self, fader, value):

        self.app.crossfade.manual = True

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
                self.app.crossfade.scale_moved(self.app.crossfade.scaleA)
            elif fader == self.xfade_in:
                self.app.crossfade.scaleB.set_value(val)
                self.app.crossfade.scale_moved(self.app.crossfade.scaleB)

        if self.xfade_out.get_value() == 127 and self.xfade_in.get_value() == 127:
            if self.xfade_out.get_inverted():
                self.xfade_out.set_inverted(False)
                self.xfade_in.set_inverted(False)
            else:
                self.xfade_out.set_inverted(True)
                self.xfade_in.set_inverted(True)
            self.xfade_out.set_value(0)
            self.xfade_in.set_value(0)

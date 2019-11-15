import mido
from gi.repository import Gio

class Midi(object):

    def __init__(self):
        self.inport = None

        self.midi_learn = ''

        # Default MIDI values : Channel, Note / Channel, CC
        self.midi_table = [['Go', 0, 103],
                ['Seq_minus', 0, 12],
                ['Seq_plus', 0, 13],
                ['Output', 0, 0],
                ['Crossfade_out', 0, 100],
                ['Crossfade_in', 0, 101]]

        self.app = Gio.Application.get_default()

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
                self.app.sequence.sequence_go(self.app, None)

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
                self.app.window.keypress_q()

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
                self.app.window.keypress_w()

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
                self.app._patch_outputs(None, None)

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
                if self.app.crossfade.scaleA.get_inverted():
                    val = (msg.value / 127) * 255
                else:
                    val = abs(((msg.value - 127) / 127) * 255)
                self.app.crossfade.scaleA.set_value(val)
                # TODO: Tester si virtual_console existe
                self.app.virtual_console.scaleA.set_value(val)
                self.app.virtual_console.scale_moved(self.app.virtual_console.scaleA)

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
                if self.app.crossfade.scaleB.get_inverted():
                    val = (msg.value / 127) * 255
                else:
                    val = abs(((msg.value - 127) / 127) * 255)
                self.app.crossfade.scaleB.set_value(val)
                # TODO: Tester si virtual_console existe
                self.app.virtual_console.scaleB.set_value(val)
                self.app.virtual_console.scale_moved(self.app.virtual_console.scaleB)

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

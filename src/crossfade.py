import array
from gi.repository import Gtk, Gio, Pango

from olc.define import NB_UNIVERSES, MAX_CHANNELS

class Scale(object):
    def __init__(self):
        self.value = 0

        self.app = Gio.Application.get_default()

    def set_value(self, value):
        if value >= 0 and value < 256:
            self.value = value
            self.app.crossfade.scale_moved(self)

    def get_value(self):
        return self.value

class CrossFade(object):
    """ For Manual Crossfade """

    def __init__(self):
        self.scaleA = Scale()
        self.scaleB = Scale()

    def scale_moved(self, scale):
        app = Gio.Application.get_default()
        level = scale.get_value()
        position = app.sequence.position

        if level != 255 and level != 0:
            app.sequence.on_go = True
            # If Go is sent, stop it
            try:
                if app.sequence.thread.is_alive():
                    app.sequence.thread.stop()
                    app.sequence.thread.join()
            except:
                pass

        if scale == self.scaleA:
            # Scale for Out

            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return
            # Update slider A position
            total_time = app.sequence.cues[position + 1].total_time * 1000
            time_out = app.sequence.cues[position + 1].time_out * 1000
            delay_out = app.sequence.cues[position + 1].delay_out * 1000
            wait = app.sequence.cues[position + 1].wait * 1000
            pos = (level / 255) * total_time
            # Get SequentialWindow's width to place cursor
            allocation = app.window.sequential.get_allocation()
            app.window.sequential.pos_xA = ((allocation.width - 32) / total_time) * pos
            app.window.sequential.queue_draw()
            # Update levels
            if pos >= wait:
                for univ in range(NB_UNIVERSES):
                    for output in range(512):

                        lvl = -1
                        channel = app.patch.outputs[univ][output]

                        old_level = app.sequence.cues[position].channels[channel - 1]

                        if channel:

                            if position < app.sequence.last - 1:
                                next_level = app.sequence.cues[position + 1].channels[channel - 1]
                            else:
                                next_level = app.sequence.cues[0].channels[channel - 1]

                            channel_time = app.sequence.cues[position+1].channel_time

                            if channel in channel_time:
                                # Channel Time
                                ct_delay = channel_time[channel].delay * 1000
                                ct_time = channel_time[channel].time * 1000
                                if next_level < old_level:

                                    if pos < ct_delay + wait:
                                        lvl = old_level

                                    elif pos >= ct_delay + wait and pos < ct_delay + ct_time + wait:
                                        lvl = old_level - abs(int(round(((next_level - old_level) / ct_time)
                                            * (pos - ct_delay - wait))))

                                    elif pos >= ct_delay + ct_time + wait:
                                        lvl = next_level

                            elif app.dmx.user[channel - 1] != -1:
                                # User changed channel's value
                                user_level = app.dmx.user[channel - 1]
                                if next_level < user_level and pos <= wait + delay_out:
                                    lvl = old_level

                                elif (next_level < user_level and pos < time_out + wait + delay_out and
                                        pos > wait_delay_out):

                                    lvl = user_level - abs(int(round(((next_level - user_level) / time_out)
                                        * (pos - wait - delay_out))))

                                elif next_level < user_level and pos >= time_out + wait + delay_out:
                                    lvl = next_level

                            else:
                                # Normal sequential
                                if next_level < old_level and pos <= wait + delay_out:
                                    lvl = old_level

                                elif (next_level < old_level and pos < time_out + wait + delay_out and
                                        pos > wait + delay_out):

                                    lvl = old_level - abs(int(round(((next_level - old_level) / time_out)
                                        * (pos - wait - delay_out))))

                                elif next_level < old_level and pos >= time_out + wait + delay_out:
                                    lvl = next_level

                            if lvl != -1:
                                app.dmx.sequence[channel - 1] = lvl

        elif scale == self.scaleB:
            # Scale for In

            # If sequential is empty, don't do anything
            if app.sequence.last == 0:
                app.sequence.on_go = False
                return
            # Update slider B position
            total_time = app.sequence.cues[position + 1].total_time * 1000
            time_in = app.sequence.cues[position + 1].time_in * 1000
            delay_in = app.sequence.cues[position + 1].delay_in * 1000
            wait = app.sequence.cues[position + 1].wait * 1000
            pos = (level / 255) * total_time
            # Get SequentialWindow's width to place cursor
            allocation = app.window.sequential.get_allocation()
            app.window.sequential.pos_xB = ((allocation.width - 32) / total_time) * pos
            app.window.sequential.queue_draw()
            # Update levels
            if pos >= wait:
                for univ in range(NB_UNIVERSES):
                    for output in range(512):

                        lvl = -1
                        channel = app.patch.outputs[univ][output]

                        old_level = app.sequence.cues[position].channels[channel - 1]

                        if channel:
                            if position < app.sequence.last - 1:
                                next_level = app.sequence.cues[position + 1].channels[channel - 1]
                            else:
                                next_level = app.sequence.cues[0].channels[channel - 1]

                            channel_time = app.sequence.cues[position + 1].channel_time

                            if channel in channel_time:
                                # Channel Time
                                ct_delay = channel_time[channel].delay * 1000
                                ct_time = channel_time[channel].time * 1000
                                if next_level > old_level:

                                    if pos < ct_delay + wait:
                                        lvl = old_level

                                    elif pos >= ct_delay + wait and pos < ct_delay + ct_time + wait:
                                        lvl = int(round(((next_level - old_level) / ct_time)
                                            * (pos - ct_delay - wait)) + old_level)

                                    elif pos >= ct_delay + ct_time + wait:
                                        lvl = next_level

                            elif app.dmx.user[channel - 1] != -1:
                                # User change channel's value
                                user_level = app.dmx.user[channel - 1]
                                if next_level > user_level and pos <= wait + delay_in:
                                    lvl = old_level

                                elif (next_level > user_level and pos < time_in + wait + delay_in and
                                        pos > wait + delay_in):

                                    lvl = int(round(((next_level - user_level) / time_in)
                                        * (pos - wait - delay_in)) + user_level)

                                elif next_level > user_level and pos >= time_in + wait + delay_in:
                                    lvl = next_level

                            else:
                                # Normal channel
                                if next_level > old_level and pos <= wait + delay_in:
                                    lvl = old_level

                                elif (next_level > old_level and pos < time_in + wait + delay_in and
                                        pos > wait + delay_in):

                                    lvl = int(round(((next_level - old_level) / time_in)
                                        * (pos - wait - delay_in)) + old_level)

                                elif next_level > old_level and pos >= time_in + wait + delay_in:
                                    lvl = next_level

                            if lvl != -1:
                                app.dmx.sequence[channel - 1] = lvl

        if self.scaleA.get_value() == 255 and self.scaleB.get_value() == 255:
            # In and Out Crossfades at Full

            if app.sequence.on_go == True:
                app.sequence.on_go = False
                # Empty array of levels enter by user
                app.dmx.user = array.array('h', [-1] * MAX_CHANNELS)
                # Go to next cue
                position = app.sequence.position
                position += 1

                # If exist
                if position < app.sequence.last - 1:
                    app.sequence.position += 1
                    t_in = app.sequence.cues[position + 1].time_in
                    t_out = app.sequence.cues[position + 1].time_out
                    d_in = app.sequence.cues[position + 1].delay_in
                    d_out = app.sequence.cues[position + 1].delay_out
                    t_wait = app.sequence.cues[position + 1].wait
                    app.window.sequential.total_time = app.sequence.cues[position + 1].total_time
                    app.window.sequential.time_in = t_in
                    app.window.sequential.time_out = t_out
                    app.window.sequential.delay_in = d_in
                    app.window.sequential.delay_out = d_out
                    app.window.sequential.wait = t_wait
                    app.window.sequential.channel_time = app.sequence.cues[position + 1].channel_time
                    app.window.sequential.pos_xA = 0
                    app.window.sequential.pos_xB = 0

                    subtitle = ("Mem. :" + app.sequence.cues[position].memory + " "
                            + app.sequence.cues[position].text + " - Next Mem. : "
                            + app.sequence.cues[position + 1].memory + " "
                            + app.sequence.cues[position + 1].text)
                    app.window.header.set_subtitle(subtitle)

                    if position == 0:
                        app.window.cues_liststore1[position][9] = "#232729"
                        app.window.cues_liststore1[position + 1][9] = "#232729"
                        app.window.cues_liststore1[position + 2][9] = "#997004"
                        app.window.cues_liststore1[position + 3][9] = "#555555"
                        app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                        app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
                    else:
                        app.window.cues_liststore1[position][9] = "#232729"
                        app.window.cues_liststore1[position + 1][9] = "#232729"
                        app.window.cues_liststore1[position + 2][9] = "#997004"
                        app.window.cues_liststore1[position + 3][9] = "#555555"
                        app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                        app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
                    app.window.step_filter1.refilter()
                    app.window.step_filter2.refilter()
                    path = Gtk.TreePath.new_first()
                    app.window.treeview1.set_cursor(path, None, False)
                    app.window.treeview2.set_cursor(path, None, False)
                    app.window.seq_grid.queue_draw()

                    self.scaleA.set_value(0)
                    self.scaleB.set_value(0)

                    # If Wait
                    if app.sequence.cues[position + 1].wait:
                        app.sequence.on_go = False
                        app.sequence.sequence_go(None, None)

                # Else, we return to first cue
                else:
                    app.sequence.position = 0
                    position = 0
                    t_in = app.sequence.cues[position + 1].time_in
                    t_out = app.sequence.cues[position + 1].time_out
                    d_in = app.sequence.cues[position + 1].delay_in
                    d_out = app.sequence.cues[position + 1].delay_out
                    t_wait = app.sequence.cues[position + 1].wait
                    app.window.sequential.total_time = app.sequence.cues[position + 1].total_time
                    app.window.sequential.time_in = t_in
                    app.window.sequential.time_out = t_out
                    app.window.sequential.delay_in = d_in
                    app.window.sequential.delay_out = d_out
                    app.window.sequential.wait = t_wait
                    app.window.sequential.channel_time = app.sequence.cues[position + 1].channel_time
                    app.window.sequential.pos_xA = 0
                    app.window.sequential.pos_xB = 0

                    subtitle = ("Mem. :" + app.sequence.cues[position].memory + " "
                            + app.sequence.cues[position].text+" - Next Mem. : "
                            + app.sequence.cues[position + 1].memory + " "
                            + app.sequence.cues[position + 1].text)
                    app.window.header.set_subtitle(subtitle)

                    if position == 0:
                        app.window.cues_liststore1[position][9] = "#232729"
                        app.window.cues_liststore1[position + 1][9] = "#232729"
                        app.window.cues_liststore1[position + 2][9] = "#997004"
                        app.window.cues_liststore1[position + 3][9] = "#555555"
                        app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                        app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
                    else:
                        app.window.cues_liststore1[position][9] = "#232729"
                        app.window.cues_liststore1[position + 1][9] = "#232729"
                        app.window.cues_liststore1[position + 2][9] = "#997004"
                        app.window.cues_liststore1[position + 3][9] = "#555555"
                        app.window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 1][10] = Pango.Weight.NORMAL
                        app.window.cues_liststore1[position + 2][10] = Pango.Weight.HEAVY
                        app.window.cues_liststore1[position + 3][10] = Pango.Weight.HEAVY
                    app.window.step_filter1.refilter()
                    app.window.step_filter2.refilter()
                    path = Gtk.TreePath.new_first()
                    app.window.treeview1.set_cursor(path, None, False)
                    app.window.treeview2.set_cursor(path, None, False)
                    app.window.seq_grid.queue_draw()

                    self.scaleA.set_value(0)
                    self.scaleB.set_value(0)

                    # If Wait
                    if app.sequence.cues[position + 1].wait:
                        app.sequence.on_go = False
                        app.sequence.sequence_go(None, None)

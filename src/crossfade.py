import array
from gi.repository import Gtk, Pango

from olc.define import NB_UNIVERSES, MAX_CHANNELS, App


class Scale:
    def __init__(self):
        self.value = 0

    def set_value(self, value):
        if 0 <= value < 256:
            self.value = value

    def get_value(self):
        return self.value


class CrossFade:
    """ For Manual Crossfade """

    def __init__(self):
        self.scale_a = Scale()
        self.scale_b = Scale()

        self.manual = False

    def scale_moved(self, scale):
        level = scale.get_value()
        position = App().sequence.position

        if level not in (255, 0):
            App().sequence.on_go = True
            # If Go is sent, stop it
            if App().crossfade.manual and App().sequence.thread:
                try:
                    if App().sequence.thread.is_alive():
                        App().sequence.thread.stop()
                        App().sequence.thread.join()
                except Exception as e:
                    print("Error :", str(e))

        if scale == self.scale_a:
            # Scale for Out

            # If sequential is empty, don't do anything
            if App().sequence.last == 0:
                App().sequence.on_go = False
                return
            # Update slider A position
            total_time = App().sequence.steps[position + 1].total_time * 1000
            time_out = App().sequence.steps[position + 1].time_out * 1000
            delay_out = App().sequence.steps[position + 1].delay_out * 1000
            wait = App().sequence.steps[position + 1].wait * 1000
            pos = (level / 255) * total_time
            # Get SequentialWindow's width to place cursor
            allocation = App().window.sequential.get_allocation()
            App().window.sequential.position_a = (
                (allocation.width - 32) / total_time
            ) * pos
            App().window.sequential.queue_draw()
            # Update levels
            if pos >= wait:
                for univ in range(NB_UNIVERSES):
                    for output in range(512):

                        lvl = -1
                        channel = App().patch.outputs[univ][output][0]

                        old_level = (
                            App().sequence.steps[position].cue.channels[channel - 1]
                        )

                        if channel:

                            if position < App().sequence.last - 1:
                                next_level = (
                                    App()
                                    .sequence.steps[position + 1]
                                    .cue.channels[channel - 1]
                                )
                            else:
                                next_level = (
                                    App().sequence.steps[0].cue.channels[channel - 1]
                                )

                            channel_time = (
                                App().sequence.steps[position + 1].channel_time
                            )

                            if channel in channel_time:
                                # Channel Time
                                ct_delay = channel_time[channel].delay * 1000
                                ct_time = channel_time[channel].time * 1000
                                if next_level < old_level:

                                    if pos < ct_delay + wait:
                                        lvl = old_level

                                    elif (
                                        ct_delay + wait
                                        <= pos
                                        < ct_delay + ct_time + wait
                                    ):
                                        lvl = old_level - abs(
                                            int(
                                                round(
                                                    ((next_level - old_level) / ct_time)
                                                    * (pos - ct_delay - wait)
                                                )
                                            )
                                        )

                                    elif pos >= ct_delay + ct_time + wait:
                                        lvl = next_level

                            elif App().dmx.user[channel - 1] != -1:
                                # User changed channel's value
                                user_level = App().dmx.user[channel - 1]
                                if next_level < user_level and pos <= wait + delay_out:
                                    lvl = old_level

                                elif (
                                    next_level < user_level
                                    and wait + delay_out
                                    < pos
                                    < time_out + wait + delay_out
                                ):

                                    lvl = user_level - abs(
                                        int(
                                            round(
                                                ((next_level - user_level) / time_out)
                                            )
                                            * (pos - wait - delay_out)
                                        )
                                    )

                                elif (
                                    next_level < user_level
                                    and pos >= time_out + wait + delay_out
                                ):
                                    lvl = next_level

                            else:
                                # Normal sequential
                                if next_level < old_level and pos <= wait + delay_out:
                                    lvl = old_level

                                elif (
                                    next_level < old_level
                                    and wait + delay_out
                                    < pos
                                    < time_out + wait + delay_out
                                ):

                                    lvl = old_level - abs(
                                        int(
                                            round(
                                                ((next_level - old_level) / time_out)
                                                * (pos - wait - delay_out)
                                            )
                                        )
                                    )

                                elif (
                                    next_level < old_level
                                    and pos >= time_out + wait + delay_out
                                ):
                                    lvl = next_level

                            if lvl != -1:
                                App().dmx.sequence[channel - 1] = lvl

        elif scale == self.scale_b:
            # Scale for In

            # If sequential is empty, don't do anything
            if App().sequence.last == 0:
                App().sequence.on_go = False
                return
            # Update slider B position
            total_time = App().sequence.steps[position + 1].total_time * 1000
            time_in = App().sequence.steps[position + 1].time_in * 1000
            delay_in = App().sequence.steps[position + 1].delay_in * 1000
            wait = App().sequence.steps[position + 1].wait * 1000
            pos = (level / 255) * total_time
            # Get SequentialWindow's width to place cursor
            allocation = App().window.sequential.get_allocation()
            App().window.sequential.position_b = (
                (allocation.width - 32) / total_time
            ) * pos
            App().window.sequential.queue_draw()
            # Update levels
            if pos >= wait:
                for univ in range(NB_UNIVERSES):
                    for output in range(512):

                        lvl = -1
                        channel = App().patch.outputs[univ][output][0]

                        old_level = (
                            App().sequence.steps[position].cue.channels[channel - 1]
                        )

                        if channel:
                            if position < App().sequence.last - 1:
                                next_level = (
                                    App()
                                    .sequence.steps[position + 1]
                                    .cue.channels[channel - 1]
                                )
                            else:
                                next_level = (
                                    App().sequence.steps[0].cue.channels[channel - 1]
                                )

                            channel_time = (
                                App().sequence.steps[position + 1].channel_time
                            )

                            if channel in channel_time:
                                # Channel Time
                                ct_delay = channel_time[channel].delay * 1000
                                ct_time = channel_time[channel].time * 1000
                                if next_level > old_level:

                                    if pos < ct_delay + wait:
                                        lvl = old_level

                                    elif (
                                        ct_delay + wait
                                        <= pos
                                        < ct_delay + ct_time + wait
                                    ):
                                        lvl = int(
                                            round(
                                                ((next_level - old_level) / ct_time)
                                                * (pos - ct_delay - wait)
                                            )
                                            + old_level
                                        )

                                    elif pos >= ct_delay + ct_time + wait:
                                        lvl = next_level

                            elif App().dmx.user[channel - 1] != -1:
                                # User change channel's value
                                user_level = App().dmx.user[channel - 1]
                                if next_level > user_level and pos <= wait + delay_in:
                                    lvl = old_level

                                elif (
                                    next_level > user_level
                                    and wait + delay_in
                                    < pos
                                    < time_in + wait + delay_in
                                ):

                                    lvl = int(
                                        round(
                                            ((next_level - user_level) / time_in)
                                            * (pos - wait - delay_in)
                                        )
                                        + user_level
                                    )

                                elif (
                                    next_level > user_level
                                    and pos >= time_in + wait + delay_in
                                ):
                                    lvl = next_level

                            else:
                                # Normal channel
                                if next_level > old_level and pos <= wait + delay_in:
                                    lvl = old_level

                                elif (
                                    next_level > old_level
                                    and wait + delay_in
                                    < pos
                                    < time_in + wait + delay_in
                                ):

                                    lvl = int(
                                        round(
                                            ((next_level - old_level) / time_in)
                                            * (pos - wait - delay_in)
                                        )
                                        + old_level
                                    )

                                elif (
                                    next_level > old_level
                                    and pos >= time_in + wait + delay_in
                                ):
                                    lvl = next_level

                            if lvl != -1:
                                App().dmx.sequence[channel - 1] = lvl

        if self.scale_a.get_value() == 255 and self.scale_b.get_value() == 255:
            # In and Out Crossfades at Full

            if App().sequence.on_go:
                self.manual = False
                App().sequence.on_go = False
                # Empty array of levels enter by user
                App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)
                # Go to next cue
                position = App().sequence.position
                position += 1

                # If exist
                if position < App().sequence.last - 1:
                    App().sequence.position += 1
                    t_in = App().sequence.steps[position + 1].time_in
                    t_out = App().sequence.steps[position + 1].time_out
                    d_in = App().sequence.steps[position + 1].delay_in
                    d_out = App().sequence.steps[position + 1].delay_out
                    t_wait = App().sequence.steps[position + 1].wait
                    App().window.sequential.total_time = (
                        App().sequence.steps[position + 1].total_time
                    )
                    App().window.sequential.time_in = t_in
                    App().window.sequential.time_out = t_out
                    App().window.sequential.delay_in = d_in
                    App().window.sequential.delay_out = d_out
                    App().window.sequential.wait = t_wait
                    App().window.sequential.channel_time = (
                        App().sequence.steps[position + 1].channel_time
                    )
                    App().window.sequential.position_a = 0
                    App().window.sequential.position_b = 0

                    subtitle = (
                        "Mem. :"
                        + str(App().sequence.steps[position].cue.memory)
                        + " "
                        + App().sequence.steps[position].text
                        + " - Next Mem. : "
                        + str(App().sequence.steps[position + 1].cue.memory)
                        + " "
                        + App().sequence.steps[position + 1].text
                    )
                    App().window.header.set_subtitle(subtitle)

                    if position == 0:
                        App().window.cues_liststore1[position][9] = "#232729"
                        App().window.cues_liststore1[position + 1][9] = "#232729"
                        App().window.cues_liststore1[position + 2][9] = "#997004"
                        App().window.cues_liststore1[position + 3][9] = "#555555"
                        App().window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 1][
                            10
                        ] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 2][
                            10
                        ] = Pango.Weight.HEAVY
                        App().window.cues_liststore1[position + 3][
                            10
                        ] = Pango.Weight.HEAVY
                    else:
                        App().window.cues_liststore1[position][9] = "#232729"
                        App().window.cues_liststore1[position + 1][9] = "#232729"
                        App().window.cues_liststore1[position + 2][9] = "#997004"
                        App().window.cues_liststore1[position + 3][9] = "#555555"
                        App().window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 1][
                            10
                        ] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 2][
                            10
                        ] = Pango.Weight.HEAVY
                        App().window.cues_liststore1[position + 3][
                            10
                        ] = Pango.Weight.HEAVY
                    App().window.step_filter1.refilter()
                    App().window.step_filter2.refilter()
                    path = Gtk.TreePath.new_first()
                    App().window.treeview1.set_cursor(path, None, False)
                    App().window.treeview2.set_cursor(path, None, False)
                    App().window.seq_grid.queue_draw()

                    self.scale_a.set_value(0)
                    self.scale_b.set_value(0)

                    if App().virtual_console:
                        if App().virtual_console.scale_a.get_inverted():
                            App().virtual_console.scale_a.set_inverted(False)
                            App().virtual_console.scale_b.set_inverted(False)
                        else:
                            App().virtual_console.scale_a.set_inverted(True)
                            App().virtual_console.scale_b.set_inverted(True)
                        App().virtual_console.scale_a.set_value(0)
                        App().virtual_console.scale_b.set_value(0)

                    # If Wait
                    if App().sequence.steps[position + 1].wait:
                        App().sequence.on_go = False
                        App().sequence.go(None, None)

                # Else, we return to first cue
                else:
                    App().sequence.position = 0
                    position = 0
                    t_in = App().sequence.steps[position + 1].time_in
                    t_out = App().sequence.steps[position + 1].time_out
                    d_in = App().sequence.steps[position + 1].delay_in
                    d_out = App().sequence.steps[position + 1].delay_out
                    t_wait = App().sequence.steps[position + 1].wait
                    App().window.sequential.total_time = (
                        App().sequence.steps[position + 1].total_time
                    )
                    App().window.sequential.time_in = t_in
                    App().window.sequential.time_out = t_out
                    App().window.sequential.delay_in = d_in
                    App().window.sequential.delay_out = d_out
                    App().window.sequential.wait = t_wait
                    App().window.sequential.channel_time = (
                        App().sequence.steps[position + 1].channel_time
                    )
                    App().window.sequential.position_a = 0
                    App().window.sequential.position_b = 0

                    subtitle = (
                        "Mem. :"
                        + str(App().sequence.steps[position].cue.memory)
                        + " "
                        + App().sequence.steps[position].text
                        + " - Next Mem. : "
                        + str(App().sequence.steps[position + 1].cue.memory)
                        + " "
                        + App().sequence.steps[position + 1].text
                    )
                    App().window.header.set_subtitle(subtitle)

                    if position == 0:
                        App().window.cues_liststore1[position][9] = "#232729"
                        App().window.cues_liststore1[position + 1][9] = "#232729"
                        App().window.cues_liststore1[position + 2][9] = "#997004"
                        App().window.cues_liststore1[position + 3][9] = "#555555"
                        App().window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 1][
                            10
                        ] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 2][
                            10
                        ] = Pango.Weight.HEAVY
                        App().window.cues_liststore1[position + 3][
                            10
                        ] = Pango.Weight.HEAVY
                    else:
                        App().window.cues_liststore1[position][9] = "#232729"
                        App().window.cues_liststore1[position + 1][9] = "#232729"
                        App().window.cues_liststore1[position + 2][9] = "#997004"
                        App().window.cues_liststore1[position + 3][9] = "#555555"
                        App().window.cues_liststore1[position][10] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 1][
                            10
                        ] = Pango.Weight.NORMAL
                        App().window.cues_liststore1[position + 2][
                            10
                        ] = Pango.Weight.HEAVY
                        App().window.cues_liststore1[position + 3][
                            10
                        ] = Pango.Weight.HEAVY
                    App().window.step_filter1.refilter()
                    App().window.step_filter2.refilter()
                    path = Gtk.TreePath.new_first()
                    App().window.treeview1.set_cursor(path, None, False)
                    App().window.treeview2.set_cursor(path, None, False)
                    App().window.seq_grid.queue_draw()

                    self.scale_a.set_value(0)
                    self.scale_b.set_value(0)

                    if App().virtual_console:
                        if App().virtual_console.scale_a.get_inverted():
                            App().virtual_console.scale_a.set_inverted(False)
                            App().virtual_console.scale_b.set_inverted(False)
                        else:
                            App().virtual_console.scale_a.set_inverted(True)
                            App().virtual_console.scale_b.set_inverted(True)
                        App().virtual_console.scale_a.set_value(0)
                        App().virtual_console.scale_b.set_value(0)

                    # If Wait
                    if App().sequence.steps[position + 1].wait:
                        App().sequence.on_go = False
                        App().sequence.go(None, None)

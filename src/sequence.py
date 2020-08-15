"""A Sequence is a collection of Steps"""

import array
import threading
import time
from gi.repository import GLib, Pango

from olc.define import NB_UNIVERSES, MAX_CHANNELS, App
from olc.cue import Cue
from olc.step import Step


def update_ui(position, subtitle):
    """Update UI when Step is in scene"""
    # Update Sequential Tab
    App().window.update_active_cues_display()
    App().window.seq_grid.queue_draw()
    # Update Main Window's Subtitle
    App().window.header.set_subtitle(subtitle)
    # Virtual Console's Xfade
    if App().virtual_console and App().virtual_console.props.visible:
        if App().virtual_console.scale_a.get_inverted():
            App().virtual_console.scale_a.set_inverted(False)
            App().virtual_console.scale_b.set_inverted(False)
        else:
            App().virtual_console.scale_a.set_inverted(True)
            App().virtual_console.scale_b.set_inverted(True)
        App().virtual_console.scale_a.set_value(0)
        App().virtual_console.scale_b.set_value(0)
    update_channels(position)


def update_channels(position):
    """Update levels of main window channels"""
    for channel in range(MAX_CHANNELS):
        level = App().sequence.steps[position].cue.channels[channel]
        if (
            App().sequence.last > 1
            and App().sequence.position < App().sequence.last - 1
        ):
            next_level = (
                App().sequence.steps[App().sequence.position + 1].cue.channels[channel]
            )
        elif App().sequence.last:
            next_level = App().sequence.steps[0].cue.channels[channel]
        else:
            next_level = level
        # App().window.channels[channel].level = level
        App().window.channels[channel].next_level = next_level
        App().window.channels[channel].queue_draw()


class Sequence:
    """Sequence"""

    def __init__(self, index, type_seq="Normal", text=""):
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.steps = []
        self.position = 0
        self.last = 0
        # Flag to know if we have a Go in progress
        self.on_go = False
        # Channels present in this sequence
        self.channels = array.array("B", [0] * MAX_CHANNELS)
        # Flag for chasers
        self.run = False
        # Thread for chasers
        self.thread = None

        # Step and Cue 0
        cue = Cue(0, 0.0)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

    def add_step(self, step):
        """Add step at the end"""
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        for channel in range(MAX_CHANNELS):
            if step.cue.channels[channel] != 0:
                self.channels[channel] = 1

    def insert_step(self, index, step):
        """Insert step at index"""
        self.steps.insert(index, step)
        self.last = len(self.steps)
        # Channels used in sequential
        for channel in range(MAX_CHANNELS):
            if step.cue.channels[channel] != 0:
                self.channels[channel] = 1

    def get_step(self, cue=None):
        """Get Cues's Step

        Args:
            cue (float): Cue number

        Return:
            found (bool), step (int)
        """
        found = False
        step = 0
        # Cue already exist ?
        for step, item in enumerate(self.steps):
            if item.cue.memory == cue:
                found = True
                break
        step -= 1
        # If new Cue, find step index
        if not found:
            exist = False
            step = 0
            for step, item in enumerate(self.steps):
                if item.cue.memory > cue:
                    exist = True
                    break
            if not exist and self is not App().sequence:
                step += 1
        elif step:
            step += 1

        return found, step

    def get_next_cue(self, step=None):
        """Get next free Cue

        Args:
            step (int): Actual Cue's Step number

        Return:
            cue (float)
        """
        mem = 1.0  # Default first cue number

        memory = self.steps[step].cue.memory
        # Find next cue number
        if step < self.last - 1:
            next_memory = self.steps[step + 1].cue.memory
            if next_memory != 0.0 and (next_memory - memory) <= 1:
                mem = ((next_memory - memory) / 2) + memory
            else:
                mem = memory + 1
        else:
            mem = memory + 1

        return mem

    def sequence_plus(self):
        """Sequence +"""
        if App().sequence.on_go and App().sequence.thread:
            try:
                # Stop actual Thread
                App().sequence.thread.stop()
                App().sequence.on_go = False
                # Stop at the end
                if self.position > self.last - 3:
                    self.position = self.last - 3
            except Exception as e:
                print("Error :", str(e))

        # Jump to next Step
        position = self.position
        position += 1
        if position < self.last - 1:  # Stop on the last cue
            self.position += 1
            t_in = self.steps[position + 1].time_in
            t_out = self.steps[position + 1].time_out
            d_in = self.steps[position + 1].delay_in
            d_out = self.steps[position + 1].delay_out
            t_wait = self.steps[position + 1].wait
            App().window.sequential.total_time = self.steps[position + 1].total_time
            App().window.sequential.time_in = t_in
            App().window.sequential.time_out = t_out
            App().window.sequential.delay_in = d_in
            App().window.sequential.delay_out = d_out
            App().window.sequential.wait = t_wait
            App().window.sequential.channel_time = self.steps[position + 1].channel_time
            App().window.sequential.position_a = 0
            App().window.sequential.position_b = 0

            # Window's subtitle
            subtitle = (
                "Mem. : "
                + str(self.steps[position].cue.memory)
                + " "
                + self.steps[position].text
                + " - Next Mem. : "
                + str(self.steps[position + 1].cue.memory)
                + " "
                + self.steps[position + 1].text
            )
            # Update display
            update_ui(position, subtitle)

            # Empty DMX user array
            App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)

            # Send DMX values
            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = App().patch.outputs[univ][output][0]
                    if channel:
                        level = self.steps[position].cue.channels[channel - 1]
                        App().dmx.sequence[channel - 1] = level
            # App().dmx.send()
            update_channels(position)

    def sequence_minus(self):
        """Sequence -"""
        if self.on_go and App().sequence.thread:
            try:
                # Stop actual Thread
                App().sequence.thread.stop()
                App().sequence.on_go = False
                # Stop at the begining
                if App().sequence.position < 1:
                    App().sequence.position = 1
            except Exception as e:
                print("Error :", str(e))

        # Jump to previous Step
        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1
            # Always use times for next cue
            t_in = self.steps[position + 1].time_in
            t_out = self.steps[position + 1].time_out
            d_in = self.steps[position + 1].delay_in
            d_out = self.steps[position + 1].delay_out
            t_wait = self.steps[position + 1].wait
            App().window.sequential.total_time = self.steps[position + 1].total_time
            App().window.sequential.time_in = t_in
            App().window.sequential.time_out = t_out
            App().window.sequential.delay_in = d_in
            App().window.sequential.delay_out = d_out
            App().window.sequential.wait = t_wait
            App().window.sequential.channel_time = self.steps[position + 1].channel_time
            App().window.sequential.position_a = 0
            App().window.sequential.position_b = 0

            # Window's subtitle
            subtitle = (
                "Mem. : "
                + str(self.steps[position].cue.memory)
                + " "
                + self.steps[position].text
                + " - Next Mem. : "
                + str(self.steps[position + 1].cue.memory)
                + " "
                + self.steps[position + 1].text
            )
            # Update display
            update_ui(position, subtitle)

            # Empty DMX user array
            App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)

            # Send DMX values
            for univ in range(NB_UNIVERSES):
                for output in range(512):
                    channel = App().patch.outputs[univ][output][0]
                    if channel:
                        level = self.steps[position].cue.channels[channel - 1]
                        App().dmx.sequence[channel - 1] = level
            # App().dmx.send()
            update_channels(position)

    def goto(self, keystring):
        """ Jump to cue number """
        old_pos = App().sequence.position

        if not keystring:
            return

        # Scan all cues
        for i, step in enumerate(self.steps):
            # Until we find the good one
            if float(step.cue.memory) == float(keystring):
                # Position to the one just before
                App().sequence.position = i - 1
                position = App().sequence.position
                # Redraw Sequential window with new times
                t_in = App().sequence.steps[position + 1].time_in
                t_out = App().sequence.steps[position + 1].time_out
                d_in = self.steps[position + 1].delay_in
                d_out = self.steps[position + 1].delay_out
                t_wait = App().sequence.steps[position + 1].wait
                App().window.sequential.total_time = self.steps[position + 1].total_time
                App().window.sequential.time_in = t_in
                App().window.sequential.time_out = t_out
                App().window.sequential.delay_in = d_in
                App().window.sequential.delay_out = d_out
                App().window.sequential.wait = t_wait
                App().window.sequential.channel_time = self.steps[
                    position + 1
                ].channel_time
                App().window.sequential.position_a = 0
                App().window.sequential.position_b = 0

                # Update ui
                App().window.cues_liststore1[old_pos][9] = "#232729"
                App().window.cues_liststore1[old_pos][10] = Pango.Weight.NORMAL
                App().window.update_active_cues_display()
                App().window.seq_grid.queue_draw()

                # Launch Go
                self.go(None, None)
                break

    def go(self, _action, _param):
        """Go"""
        # Si un Go est en cours, on bascule sur la mémoire suivante
        if App().sequence.on_go and App().sequence.thread:
            # Stop actual Thread
            try:
                App().sequence.thread.stop()
                App().sequence.thread.join()
            except Exception as e:
                print("Error :", str(e))
            App().sequence.on_go = False
            # Launch another Go
            position = App().sequence.position
            position += 1
            if position < App().sequence.last - 1:
                App().sequence.position += 1
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

            # Set main window's subtitle
            subtitle = (
                "Mem. : "
                + str(App().sequence.steps[position].cue.memory)
                + " "
                + App().sequence.steps[position].text
                + " - Next Mem. : "
                + str(App().sequence.steps[position + 1].cue.memory)
                + " "
                + App().sequence.steps[position + 1].text
            )
            # Update Sequential Tab
            App().window.update_active_cues_display()
            App().window.seq_grid.queue_draw()
            # Update Main Window's Subtitle
            App().window.header.set_subtitle(subtitle)

            self.go(None, None)

        else:
            # On indique qu'un Go est en cours
            App().sequence.on_go = True
            App().sequence.thread = ThreadGo()
            App().sequence.thread.start()

    def go_back(self, _action, _param):
        """Go Back"""
        # Just return if we are at the beginning
        position = App().sequence.position
        if position == 0:
            return False

        if App().sequence.on_go and App().sequence.thread:
            try:
                App().sequence.thread.stop()
                App().sequence.thread.join()
            except Exception as e:
                print("Error :", str(e))
            App().sequence.on_go = False

        # Time for Go Back in Settings
        # go_back_time = App().settings.get_double("go-back-time")

        App().window.sequential.total_time = (
            App().sequence.steps[position - 1].total_time
        )
        App().window.sequential.time_in = App().sequence.steps[position - 1].time_in
        App().window.sequential.time_out = App().sequence.steps[position - 1].time_out
        App().window.sequential.delay_in = App().sequence.steps[position - 1].delay_in
        App().window.sequential.delay_out = App().sequence.steps[position - 1].delay_out
        App().window.sequential.wait = App().sequence.steps[position - 1].wait
        App().window.sequential.channel_time = (
            App().sequence.steps[position - 1].channel_time
        )
        App().window.sequential.position_a = 0
        App().window.sequential.position_b = 0

        App().window.seq_grid.queue_draw()

        subtitle = (
            "Mem. : "
            + str(App().sequence.steps[position].cue.memory)
            + " "
            + App().sequence.steps[position].text
            + " - Next Mem. : "
            + str(App().sequence.steps[position - 1].cue.memory)
            + " "
            + App().sequence.steps[position - 1].text
        )
        App().window.header.set_subtitle(subtitle)

        App().sequence.on_go = True
        App().sequence.thread = ThreadGoBack()
        App().sequence.thread.start()
        return True


class ThreadGo(threading.Thread):
    """Thread object for Go"""

    def __init__(self):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
        # To save dmx levels when user send Go
        self.dmxlevels = []
        for _univ in range(NB_UNIVERSES):
            self.dmxlevels.append(array.array("B", [0] * 512))
        next_step = App().sequence.position + 1
        self.total_time = App().sequence.steps[next_step].total_time * 1000
        self.time_in = App().sequence.steps[next_step].time_in * 1000
        self.time_out = App().sequence.steps[next_step].time_out * 1000
        self.wait = App().sequence.steps[next_step].wait * 1000
        self.delay_in = App().sequence.steps[next_step].delay_in * 1000
        self.delay_out = App().sequence.steps[next_step].delay_out * 1000

    def run(self):
        # Levels when Go is sent
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.dmxlevels[univ][output] = App().dmx.frame[univ][output]

        start_time = time.time() * 1000  # actual time in ms
        i = (time.time() * 1000) - start_time

        # Loop on total time
        while i < self.total_time and not self._stopevent.isSet():
            # Update DMX levels
            self.update_levels(i)
            # Sleep for 50ms
            time.sleep(0.05)
            i = (time.time() * 1000) - start_time

        # Stop thread if we send stop message
        if self._stopevent.isSet():
            return

        # Finish to load memory
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = App().patch.outputs[univ][output][0]
                if channel:
                    if App().sequence.position < App().sequence.last - 1:
                        level = (
                            App()
                            .sequence.steps[App().sequence.position + 1]
                            .cue.channels[channel - 1]
                        )
                    else:
                        level = App().sequence.steps[0].cue.channels[channel - 1]
                    App().dmx.sequence[channel - 1] = level
                    App().dmx.frame[univ][output] = level

        # Go is completed
        # App().dmx.send()
        App().sequence.on_go = False
        # Empty DMX user array
        App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)

        # Next step
        next_step = App().sequence.position + 1

        # If there is a next step
        if next_step < App().sequence.last - 1:
            App().sequence.position += 1
            next_step += 1
        # If no next step, go to beggining
        else:
            App().sequence.position = 0
            next_step = 1

        App().window.sequential.total_time = App().sequence.steps[next_step].total_time
        App().window.sequential.time_in = App().sequence.steps[next_step].time_in
        App().window.sequential.time_out = App().sequence.steps[next_step].time_out
        App().window.sequential.delay_in = App().sequence.steps[next_step].delay_in
        App().window.sequential.delay_out = App().sequence.steps[next_step].delay_out
        App().window.sequential.wait = App().sequence.steps[next_step].wait
        App().window.sequential.channel_time = (
            App().sequence.steps[next_step].channel_time
        )
        App().window.sequential.position_a = 0
        App().window.sequential.position_b = 0

        # Set main window's subtitle
        subtitle = (
            "Mem. : "
            + str(App().sequence.steps[App().sequence.position].cue.memory)
            + " "
            + App().sequence.steps[App().sequence.position].text
            + " - Next Mem. : "
            + str(App().sequence.steps[next_step].cue.memory)
            + " "
            + App().sequence.steps[next_step].text
        )

        # Update Gtk in main thread
        GLib.idle_add(update_ui, App().sequence.position, subtitle)

        # Wait, launch next step
        if App().sequence.steps[next_step].wait:
            App().sequence.go(None, None)

    def stop(self):
        """Stop"""
        self._stopevent.set()

    def update_levels(self, i):
        """Update levels"""
        # Update sliders position
        App().window.sequential.position_a = (
            (App().window.sequential.get_allocation().width - 32) / self.total_time
        ) * i
        App().window.sequential.position_b = (
            (App().window.sequential.get_allocation().width - 32) / self.total_time
        ) * i
        GLib.idle_add(App().window.sequential.queue_draw)
        # Move Virtual Console's XFade
        if App().virtual_console:
            if App().virtual_console.props.visible:
                val = round((255 / self.total_time) * i)
                GLib.idle_add(App().virtual_console.scale_a.set_value, val)
                GLib.idle_add(App().virtual_console.scale_b.set_value, val)
        # Wait for wait time
        if i > self.wait:
            for channel in range(MAX_CHANNELS):
                for chan in App().patch.channels[channel]:
                    output = chan[0]
                    if output:
                        output -= 1
                        univ = chan[1]
                        old_level = round(
                            self.dmxlevels[univ][output]
                            * (255 / App().dmx.grand_master)
                        )
                        if App().sequence.position < App().sequence.last - 1:
                            next_level = (
                                App()
                                .sequence.steps[App().sequence.position + 1]
                                .cue.channels[channel]
                            )
                        else:
                            next_level = App().sequence.steps[0].cue.channels[channel]
                            App().sequence.position = 0

                        self._set_level(channel, i, old_level, next_level)
            # App().dmx.send()

    def _set_level(self, channel, i, old_level, next_level):
        """Get level"""
        channel_time = App().sequence.steps[App().sequence.position + 1].channel_time
        if channel + 1 in channel_time:
            # Channel is in a channel time
            level = self._channel_time_level(
                i, channel_time[channel + 1], old_level, next_level
            )
        # Else channel is normal
        else:
            level = self._channel_level(i, old_level, next_level)
        App().dmx.sequence[channel] = level

    def _channel_level(self, i, old_level, next_level):
        """Return channel level"""
        # If level increases, use Time In
        if (
            next_level > old_level
            and self.wait + self.delay_in < i < self.time_in + self.wait + self.delay_in
        ):
            level = (
                int(
                    ((next_level - old_level + 1) / self.time_in)
                    * (i - self.wait - self.delay_in)
                )
                + old_level
            )
        elif next_level > old_level and i > self.time_in + self.wait + self.delay_in:
            level = next_level
        # If level decreases, use Time Out
        elif (
            next_level < old_level
            and self.wait + self.delay_out
            < i
            < self.time_out + self.wait + self.delay_out
        ):
            level = old_level - abs(
                int(
                    ((next_level - old_level - 1) / self.time_out)
                    * (i - self.wait - self.delay_out)
                )
            )
        elif next_level < old_level and i > self.time_out + self.wait + self.delay_out:
            level = next_level
        # Level doesn't change
        else:
            level = old_level
        return level

    def _channel_time_level(self, i, channel_time, old_level, next_level):
        """Return channel level if in channel time"""
        ct_delay = channel_time.delay * 1000
        ct_time = channel_time.time * 1000
        if next_level > old_level:
            if i < ct_delay + self.wait:
                level = old_level
            elif ct_delay + self.wait <= i < ct_delay + ct_time + self.wait:
                level = (
                    int(
                        ((next_level - old_level + 1) / ct_time)
                        * (i - ct_delay - self.wait)
                    )
                    + old_level
                )
            elif i >= ct_delay + ct_time + self.wait:
                level = next_level
        else:
            if i < ct_delay + self.wait:
                level = old_level
            elif ct_delay + self.wait <= i < ct_delay + ct_time + self.wait:
                level = old_level - abs(
                    int(
                        ((next_level - old_level - 1) / ct_time)
                        * (i - ct_delay - self.wait)
                    )
                )
            elif i >= ct_delay + ct_time + self.wait:
                level = next_level
        return level


class ThreadGoBack(threading.Thread):
    """Thread Object for Go Back"""

    def __init__(self):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()

        self.dmxlevels = []
        for _univ in range(NB_UNIVERSES):
            self.dmxlevels.append(array.array("B", [0] * 512))

    def run(self):
        # If sequential is empty, just return
        if App().sequence.last == 2:
            return

        position = App().sequence.position

        # Levels when Go Back starts
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.dmxlevels[univ][output] = App().dmx.frame[univ][output]

        # Go Back's default time
        go_back_time = App().settings.get_double("go-back-time") * 1000

        # Actual time in ms
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time

        while i < go_back_time and not self._stopevent.isSet():
            # Update DMX levels
            self.update_levels(go_back_time, i, position)
            # Sleep 50ms
            time.sleep(0.05)
            i = (time.time() * 1000) - start_time

        # Finish to load preset
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = App().patch.outputs[univ][output][0]
                if channel:
                    # TODO: Handle first position
                    level = App().sequence.steps[position - 1].cue.channels[channel - 1]
                    App().dmx.sequence[channel - 1] = level

        # App().dmx.send()
        App().sequence.go = False

        App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)

        # TODO: Gérer la position
        position -= 1

        App().sequence.position = position
        App().window.sequential.time_in = App().sequence.steps[position + 1].time_in
        App().window.sequential.time_out = App().sequence.steps[position + 1].time_out
        App().window.sequential.delay_in = App().sequence.steps[position + 1].delay_in
        App().window.sequential.delay_out = App().sequence.steps[position + 1].delay_out
        App().window.sequential.wait = App().sequence.steps[position + 1].wait
        App().window.sequential.total_time = (
            App().sequence.steps[position + 1].total_time
        )
        App().window.sequential.channel_time = (
            App().sequence.steps[position + 1].channel_time
        )
        App().window.sequential.position_a = 0
        App().window.sequential.position_b = 0

        # Set main window's subtitle
        subtitle = (
            "Mem. : "
            + str(App().sequence.steps[position].cue.memory)
            + " "
            + App().sequence.steps[position].text
            + " - Next Mem. : "
            + str(App().sequence.steps[position + 1].cue.memory)
            + " "
            + App().sequence.steps[position + 1].text
        )

        # Update Gtk in the main thread
        GLib.idle_add(update_ui, position, subtitle)

        if App().sequence.steps[position + 1].wait:
            App().sequence.go(None, None)

    def stop(self):
        """Stop"""
        self._stopevent.set()

    def update_levels(self, go_back_time, i, position):
        """Update levels"""
        # Update sliders position
        allocation = App().window.sequential.get_allocation()
        App().window.sequential.position_a = (
            (allocation.width - 32) / go_back_time
        ) * i
        App().window.sequential.position_b = (
            (allocation.width - 32) / go_back_time
        ) * i
        GLib.idle_add(App().window.sequential.queue_draw)

        # Move Virtual Console's XFade
        if App().virtual_console and App().virtual_console.props.visible:
            val = round((255 / go_back_time) * i)
            GLib.idle_add(App().virtual_console.scale_a.set_value, val)
            GLib.idle_add(App().virtual_console.scale_b.set_value, val)

        for univ in range(NB_UNIVERSES):

            for output in range(512):

                old_level = round(
                    self.dmxlevels[univ][output] * (255 / App().dmx.grand_master)
                )

                channel = App().patch.outputs[univ][output][0]

                if channel:

                    next_level = (
                        App().sequence.steps[position - 1].cue.channels[channel - 1]
                    )

                    if next_level > old_level:
                        level = (
                            round(((next_level - old_level) / go_back_time) * i)
                            + old_level
                        )
                    elif next_level < old_level:
                        level = old_level - abs(
                            round(((next_level - old_level) / go_back_time) * i)
                        )
                    else:
                        level = next_level

                    App().dmx.sequence[channel - 1] = level

        # App().dmx.send()

"""A Sequence is a collection of Steps"""

import array
import threading
import time

from gi.repository import GLib, Pango
from olc.cue import Cue
from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.step import Step


def update_ui(position, subtitle):
    """Update UI when Step is in scene

    Args:
        position: Step
        subtitle: Memories number in headerbar
    """
    # Update Sequential Tab
    App().window.playback.update_active_cues_display()
    App().window.playback.grid.queue_draw()
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
    """Update levels of main window channels

    Args:
        position: Step
    """
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
        App().window.channels_view.channels[channel].next_level = next_level
        App().window.channels_view.channels[channel].queue_draw()


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
        """Add step at the end

        Args:
            step: Step number
        """
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        for channel in range(MAX_CHANNELS):
            if step.cue.channels[channel] != 0:
                self.channels[channel] = 1

    def insert_step(self, index, step):
        """Insert step at index

        Args:
            index: Index
            step: Step
        """
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

        Returns:
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

        Returns:
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
        if self.on_go and self.thread:
            try:
                # Stop actual Thread
                self.thread.stop()
                self.on_go = False
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
            App().window.playback.sequential.total_time = self.steps[
                position + 1
            ].total_time
            App().window.playback.sequential.time_in = self.steps[position + 1].time_in
            App().window.playback.sequential.time_out = self.steps[
                position + 1
            ].time_out
            App().window.playback.sequential.delay_in = self.steps[
                position + 1
            ].delay_in
            App().window.playback.sequential.delay_out = self.steps[
                position + 1
            ].delay_out
            App().window.playback.sequential.wait = self.steps[position + 1].wait
            App().window.playback.sequential.channel_time = self.steps[
                position + 1
            ].channel_time
            App().window.playback.sequential.position_a = 0
            App().window.playback.sequential.position_b = 0

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
            for channel in range(MAX_CHANNELS):
                for i in App().patch.channels[channel]:
                    output = i[0]
                    # Intensity
                    if output:
                        level = self.steps[position].cue.channels[channel]
                        App().dmx.sequence[channel] = level
            update_channels(position)

    def sequence_minus(self):
        """Sequence -"""
        if self.on_go and self.thread:
            try:
                # Stop actual Thread
                self.thread.stop()
                self.on_go = False
                # Stop at the begining
                if self.position < 1:
                    self.position = 1
            except Exception as e:
                print("Error :", str(e))

        # Jump to previous Step
        position = self.position
        position -= 1
        if position >= 0:
            self.position -= 1
            # Always use times for next cue
            App().window.playback.sequential.total_time = self.steps[
                position + 1
            ].total_time
            App().window.playback.sequential.time_in = self.steps[position + 1].time_in
            App().window.playback.sequential.time_out = self.steps[
                position + 1
            ].time_out
            App().window.playback.sequential.delay_in = self.steps[
                position + 1
            ].delay_in
            App().window.playback.sequential.delay_out = self.steps[
                position + 1
            ].delay_out
            App().window.playback.sequential.wait = self.steps[position + 1].wait
            App().window.playback.sequential.channel_time = self.steps[
                position + 1
            ].channel_time
            App().window.playback.sequential.position_a = 0
            App().window.playback.sequential.position_b = 0

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

            for channel in range(MAX_CHANNELS):
                # Intensity
                for i in App().patch.channels[channel]:
                    output = i[0]
                    if output:
                        level = self.steps[position].cue.channels[channel]
                        App().dmx.sequence[channel] = level
            update_channels(position)

    def goto(self, keystring):
        """Jump to cue number

        Args:
            keystring (str): Memory number
        """
        old_pos = self.position

        if not keystring:
            return

        # Scan all cues
        for i, step in enumerate(self.steps):
            # Until we find the good one
            if float(step.cue.memory) == float(keystring):
                # Position to the one just before
                self.position = i - 1
                # position = self.position
                next_step = self.position + 1
                # Redraw Sequential window with new times
                App().window.playback.sequential.total_time = self.steps[
                    next_step
                ].total_time
                App().window.playback.sequential.time_in = self.steps[next_step].time_in
                App().window.playback.sequential.time_out = self.steps[
                    next_step
                ].time_out
                App().window.playback.sequential.delay_in = self.steps[
                    next_step
                ].delay_in
                App().window.playback.sequential.delay_out = self.steps[
                    next_step
                ].delay_out
                App().window.playback.sequential.wait = self.steps[next_step].wait
                App().window.playback.sequential.channel_time = self.steps[
                    next_step
                ].channel_time
                App().window.playback.sequential.position_a = 0
                App().window.playback.sequential.position_b = 0

                # Update ui
                App().window.playback.cues_liststore1[old_pos][9] = "#232729"
                App().window.playback.cues_liststore1[old_pos][10] = Pango.Weight.NORMAL
                App().window.playback.update_active_cues_display()
                App().window.playback.grid.queue_draw()

                # Launch Go
                self.do_go(None, True)
                break

    def do_go(self, _action, goto):
        """Go

        Args:
            goto:  True if Goto, False if Go
        """
        # Si un Go est en cours, on bascule sur la mémoire suivante
        if self.on_go and self.thread:
            # Stop actual Thread
            try:
                self.thread.stop()
                self.thread.join()
            except Exception as e:
                print("Error :", str(e))
            self.on_go = False
            # Launch another Go
            position = self.position
            position += 1
            if position < self.last - 1:
                self.position += 1
            else:
                self.position = 0
                position = 0
            App().window.playback.sequential.total_time = self.steps[
                position + 1
            ].total_time
            App().window.playback.sequential.time_in = self.steps[position + 1].time_in
            App().window.playback.sequential.time_out = self.steps[
                position + 1
            ].time_out
            App().window.playback.sequential.delay_in = self.steps[
                position + 1
            ].delay_in
            App().window.playback.sequential.delay_out = self.steps[
                position + 1
            ].delay_out
            App().window.playback.sequential.wait = self.steps[position + 1].wait
            App().window.playback.sequential.channel_time = self.steps[
                position + 1
            ].channel_time
            App().window.playback.sequential.position_a = 0
            App().window.playback.sequential.position_b = 0

            # Set main window's subtitle
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
            # Update Sequential Tab
            App().window.playback.update_active_cues_display()
            App().window.playback.grid.queue_draw()
            # Update Main Window's Subtitle
            App().window.header.set_subtitle(subtitle)

            self.do_go(None, None)

        else:
            # On indique qu'un Go est en cours
            self.on_go = True
            self.thread = ThreadGo(goto)
            self.thread.start()

    def go_back(self, _action, _param):
        """Go Back

        Returns:
            True or False
        """
        # Just return if we are at the beginning
        position = self.position
        if position == 0:
            return False

        if self.on_go and self.thread:
            try:
                self.thread.stop()
                self.thread.join()
            except Exception as e:
                print("Error :", str(e))
            self.on_go = False

        App().window.playback.sequential.total_time = self.steps[
            position - 1
        ].total_time
        App().window.playback.sequential.time_in = self.steps[position - 1].time_in
        App().window.playback.sequential.time_out = self.steps[position - 1].time_out
        App().window.playback.sequential.delay_in = self.steps[position - 1].delay_in
        App().window.playback.sequential.delay_out = self.steps[position - 1].delay_out
        App().window.playback.sequential.wait = self.steps[position - 1].wait
        App().window.playback.sequential.channel_time = self.steps[
            position - 1
        ].channel_time
        App().window.playback.sequential.position_a = 0
        App().window.playback.sequential.position_b = 0

        App().window.playback.grid.queue_draw()

        subtitle = (
            "Mem. : "
            + str(self.steps[position].cue.memory)
            + " "
            + self.steps[position].text
            + " - Next Mem. : "
            + str(self.steps[position - 1].cue.memory)
            + " "
            + self.steps[position - 1].text
        )
        App().window.header.set_subtitle(subtitle)

        self.on_go = True
        self.thread = ThreadGoBack()
        self.thread.start()
        return True


class ThreadGo(threading.Thread):
    """Thread object for Go"""

    def __init__(self, goto):
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
        self.goto = goto

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
        App().sequence.on_go = False
        # Empty DMX user array
        App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)
        next_step = _next_step()
        # Wait, launch next step
        if App().sequence.steps[next_step].wait:
            App().sequence.do_go(None, None)

    def stop(self):
        """Stop"""
        self._stopevent.set()

    def update_levels(self, i):
        """Update levels

        Args:
            i: Time spent
        """
        # Update sliders position
        App().window.playback.sequential.position_a = (
            (App().window.playback.sequential.get_allocation().width - 32)
            / self.total_time
        ) * i
        App().window.playback.sequential.position_b = (
            (App().window.playback.sequential.get_allocation().width - 32)
            / self.total_time
        ) * i
        GLib.idle_add(App().window.playback.sequential.queue_draw)
        # Move Virtual Console's XFade
        if App().virtual_console and App().virtual_console.props.visible:
            val = round((255 / self.total_time) * i)
            GLib.idle_add(App().virtual_console.scale_a.set_value, val)
            GLib.idle_add(App().virtual_console.scale_b.set_value, val)
        # Wait for wait time
        if i > self.wait:
            if self.goto:
                self._do_goto(i)
            else:
                self._do_go(i)

    def _do_goto(self, i):
        """Goto

        Args:
            i: Time spent
        """
        for channel in range(MAX_CHANNELS):
            for chan in App().patch.channels[channel]:
                output = chan[0]
                if output:
                    output -= 1
                    univ = chan[1]
                    old_level = self.dmxlevels[univ][output]
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

    def _do_go(self, i):
        """Go

        Args:
            i: Time spent
        """
        for channel in range(MAX_CHANNELS):
            for chan in App().patch.channels[channel]:
                output = chan[0]
                # Dimmers
                if output:
                    output -= 1
                    univ = chan[1]
                    old_level = self.dmxlevels[univ][output]
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

    def _set_level(self, channel, i, old_level, next_level):
        """Get level

        Args:
            channel: Channel number
            i: Time spent
            old_level: Old level
            next_level: Next level
        """
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
        """Return channel level

        Args:
            i: Time spent
            old_level: Old level
            next_level: Next level

        Returns:
            channel level
        """
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
        """Return channel level if in channel time

        Args:
            i: Time spent
            channel_time: Channel time
            old_level: Old level
            next_level: Next level

        Returns:
            Channel level
        """
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
            else:
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
            else:
                level = next_level
        return level


def _next_step():
    """Next Step after Go

    Returns:
        Step
    """
    next_step = App().sequence.position + 1
    # If there is a next step
    if next_step < App().sequence.last - 1:
        App().sequence.position += 1
        next_step += 1
    # If no next step, go to beggining
    else:
        App().sequence.position = 0
        next_step = 1
    # Update times for visual xfade
    App().window.playback.sequential.total_time = (
        App().sequence.steps[next_step].total_time
    )
    App().window.playback.sequential.time_in = App().sequence.steps[next_step].time_in
    App().window.playback.sequential.time_out = App().sequence.steps[next_step].time_out
    App().window.playback.sequential.delay_in = App().sequence.steps[next_step].delay_in
    App().window.playback.sequential.delay_out = (
        App().sequence.steps[next_step].delay_out
    )
    App().window.playback.sequential.wait = App().sequence.steps[next_step].wait
    App().window.playback.sequential.channel_time = (
        App().sequence.steps[next_step].channel_time
    )
    App().window.playback.sequential.position_a = 0
    App().window.playback.sequential.position_b = 0
    # Main window's subtitle
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
    return next_step


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

        prev_step = App().sequence.position - 1

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
            self.update_levels(go_back_time, i, App().sequence.position)
            # Sleep 50ms
            time.sleep(0.05)
            i = (time.time() * 1000) - start_time
        # Finish to load preset
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = App().patch.outputs[univ][output][0]
                if channel:
                    level = App().sequence.steps[prev_step].cue.channels[channel - 1]
                    App().dmx.sequence[channel - 1] = level
                    App().dmx.frame[univ][output] = level
        App().sequence.on_go = False
        # Reset user levels
        App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)
        # Prev step
        App().sequence.position = prev_step
        App().window.playback.sequential.time_in = (
            App().sequence.steps[prev_step + 1].time_in
        )
        App().window.playback.sequential.time_out = (
            App().sequence.steps[prev_step + 1].time_out
        )
        App().window.playback.sequential.delay_in = (
            App().sequence.steps[prev_step + 1].delay_in
        )
        App().window.playback.sequential.delay_out = (
            App().sequence.steps[prev_step + 1].delay_out
        )
        App().window.playback.sequential.wait = App().sequence.steps[prev_step + 1].wait
        App().window.playback.sequential.total_time = (
            App().sequence.steps[prev_step + 1].total_time
        )
        App().window.playback.sequential.channel_time = (
            App().sequence.steps[prev_step + 1].channel_time
        )
        App().window.playback.sequential.position_a = 0
        App().window.playback.sequential.position_b = 0
        # Main window's subtitle
        subtitle = (
            "Mem. : "
            + str(App().sequence.steps[prev_step].cue.memory)
            + " "
            + App().sequence.steps[prev_step].text
            + " - Next Mem. : "
            + str(App().sequence.steps[prev_step + 1].cue.memory)
            + " "
            + App().sequence.steps[prev_step + 1].text
        )
        # Update Gtk in the main thread
        GLib.idle_add(update_ui, prev_step, subtitle)
        # Wait
        if App().sequence.steps[prev_step + 1].wait:
            App().sequence.do_go(None, None)

    def stop(self):
        """Stop"""
        self._stopevent.set()

    def update_levels(self, go_back_time, i, position):
        """Update levels

        Args:
            go_back_time: Default GoBack time
            i: Time spent
            position: Step
        """
        # Update sliders position
        allocation = App().window.playback.sequential.get_allocation()
        App().window.playback.sequential.position_a = (
            (allocation.width - 32) / go_back_time
        ) * i
        App().window.playback.sequential.position_b = (
            (allocation.width - 32) / go_back_time
        ) * i
        GLib.idle_add(App().window.playback.sequential.queue_draw)
        # Move Virtual Console's XFade
        if App().virtual_console and App().virtual_console.props.visible:
            val = round((255 / go_back_time) * i)
            GLib.idle_add(App().virtual_console.scale_a.set_value, val)
            GLib.idle_add(App().virtual_console.scale_b.set_value, val)
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                channel = App().patch.outputs[univ][output][0]
                if channel:
                    old_level = self.dmxlevels[univ][output]
                    next_level = (
                        App().sequence.steps[position - 1].cue.channels[channel - 1]
                    )
                    level = self._channel_level(i, old_level, next_level, go_back_time)
                    App().dmx.sequence[channel - 1] = level

    def _channel_level(self, i, old_level, next_level, go_back_time):
        """Return channel level

        Args:
            i: Time spent
            old_level: Old level
            next_level: Next level
            go_back_time: Default GoBack time

        Returns:
            Channel level
        """
        if next_level > old_level:
            level = round(((next_level - old_level) / go_back_time) * i) + old_level
        elif next_level < old_level:
            level = old_level - abs(
                round(((next_level - old_level) / go_back_time) * i)
            )
        else:
            level = next_level
        return level

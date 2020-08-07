import array
import threading
import time
from gi.repository import GLib, Pango

from olc.define import NB_UNIVERSES, MAX_CHANNELS, App
from olc.cue import Cue
from olc.step import Step


def update_ui(position, subtitle):
    # Update Sequential Tab
    App().window.update_active_cues_display()
    App().window.seq_grid.queue_draw()
    # Update Main Window's Subtitle
    App().window.header.set_subtitle(subtitle)
    # Virtual Console's Xfade
    if App().virtual_console:
        if App().virtual_console.props.visible:
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
    # Update levels of main window channels
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
    def __init__(self, index, patch, type_seq="Normal", text=""):
        self.index = index
        self.type_seq = type_seq
        self.text = text
        self.steps = []
        self.position = 0
        self.last = 0
        # Flag pour savoir si on a un Go en cours
        self.on_go = False
        # Liste des channels présent dans le sequentiel
        self.channels = array.array("B", [0] * MAX_CHANNELS)
        # Flag for chasers
        self.run = False
        # Thread for chasers
        self.thread = None
        # Pour accéder à la fenêtre du séquentiel
        self.window = None
        # On a besoin de connaitre le patch
        self.patch = patch

        # Step and Cue 0
        cue = Cue(0, 0.0)
        step = Step(sequence=self.index, cue=cue)
        self.add_step(step)
        # Last Step
        self.add_step(step)

    def add_step(self, step):
        self.steps.append(step)
        self.last = len(self.steps)
        # Channels used in sequential
        for channel in range(MAX_CHANNELS):
            if step.cue.channels[channel] != 0:
                self.channels[channel] = 1

    def insert_step(self, index, step):
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
            if next_memory == 0.0:
                mem = memory + 1
            else:
                if (next_memory - memory) <= 1:
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
            self.window.sequential.total_time = self.steps[position + 1].total_time
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            self.window.sequential.delay_in = d_in
            self.window.sequential.delay_out = d_out
            self.window.sequential.wait = t_wait
            self.window.sequential.channel_time = self.steps[position + 1].channel_time
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
                    channel = self.patch.outputs[univ][output][0]
                    if channel:
                        level = self.steps[position].cue.channels[channel - 1]
                        App().dmx.sequence[channel - 1] = level
            App().dmx.send()
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
            self.window.sequential.total_time = self.steps[position + 1].total_time
            self.window.sequential.time_in = t_in
            self.window.sequential.time_out = t_out
            self.window.sequential.delay_in = d_in
            self.window.sequential.delay_out = d_out
            self.window.sequential.wait = t_wait
            self.window.sequential.channel_time = self.steps[position + 1].channel_time
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
                    channel = self.patch.outputs[univ][output][0]
                    if channel:
                        level = self.steps[position].cue.channels[channel - 1]
                        App().dmx.sequence[channel - 1] = level
            App().dmx.send()
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
                self.window.sequential.total_time = self.steps[position + 1].total_time
                App().window.sequential.time_in = t_in
                App().window.sequential.time_out = t_out
                self.window.sequential.delay_in = d_in
                self.window.sequential.delay_out = d_out
                App().window.sequential.wait = t_wait
                self.window.sequential.channel_time = self.steps[
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

    def __init__(self, name=""):
        threading.Thread.__init__(self)
        self.name = name
        self._stopevent = threading.Event()
        # To save dmx levels when user send Go
        self.dmxlevels = []
        for _univ in range(NB_UNIVERSES):
            self.dmxlevels.append(array.array("B", [0] * 512))

    def run(self):
        # Position dans le séquentiel
        position = App().sequence.position

        # Levels when Go is sent
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.dmxlevels[univ][output] = App().dmx.frame[univ][output]

        # If sequential is empty, just return
        if App().sequence.last == 0:
            return

        # On récupère les temps de montée et de descente de la mémoire suivante
        t_in = App().sequence.steps[position + 1].time_in
        t_out = App().sequence.steps[position + 1].time_out
        d_in = App().sequence.steps[position + 1].delay_in
        d_out = App().sequence.steps[position + 1].delay_out
        t_wait = App().sequence.steps[position + 1].wait
        t_total = App().sequence.steps[position + 1].total_time

        # Quel est le temps le plus long
        if t_in + d_in > t_out + d_out:
            t_max = t_in + d_in
            t_min = t_out + d_out
        else:
            t_max = t_out + d_out
            t_min = t_in + d_in

        t_max = t_max + t_wait
        t_min = t_min + t_wait

        start_time = time.time() * 1000  # actual time in ms
        delay = t_total * 1000
        delay_in = t_in * 1000
        delay_out = t_out * 1000
        delay_wait = t_wait * 1000
        delay_d_in = d_in * 1000
        delay_d_out = d_out * 1000
        i = (time.time() * 1000) - start_time

        # Boucle sur le temps de montée ou de descente (le plus grand)
        while i < delay and not self._stopevent.isSet():
            # Update DMX levels
            self.update_levels(
                delay,
                delay_in,
                delay_out,
                delay_d_in,
                delay_d_out,
                delay_wait,
                i,
                position,
            )
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
                    if position < App().sequence.last - 1:
                        level = (
                            App().sequence.steps[position + 1].cue.channels[channel - 1]
                        )
                    else:
                        level = App().sequence.steps[0].cue.channels[channel - 1]
                    App().dmx.sequence[channel - 1] = level

        # Le Go est terminé
        App().dmx.send()
        App().sequence.on_go = False
        # On vide le tableau des valeurs entrées par l'utilisateur
        App().dmx.user = array.array("h", [-1] * MAX_CHANNELS)

        # On se positionne à la mémoire suivante
        position = App().sequence.position
        position += 1

        # Si elle existe
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

            # Si la mémoire a un Wait
            if App().sequence.steps[position + 1].wait:
                App().sequence.go(None, None)

        # Sinon, on revient au début
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

            # Update Gtk in the main thread
            GLib.idle_add(update_ui, position, subtitle)

    def stop(self):
        self._stopevent.set()

    def update_levels(
        self,
        delay,
        delay_in,
        delay_out,
        delay_d_in,
        delay_d_out,
        delay_wait,
        i,
        position,
    ):
        # Update sliders position
        # Get width of the sequential widget to place cursors correctly
        allocation = App().window.sequential.get_allocation()
        App().window.sequential.position_a = ((allocation.width - 32) / delay) * i
        App().window.sequential.position_b = ((allocation.width - 32) / delay) * i
        GLib.idle_add(App().window.sequential.queue_draw)

        # Move Virtual Console's XFade
        if App().virtual_console:
            if App().virtual_console.props.visible:
                val = round((255 / delay) * i)
                GLib.idle_add(App().virtual_console.scale_a.set_value, val)
                GLib.idle_add(App().virtual_console.scale_b.set_value, val)

        # On attend que le temps d'un éventuel wait soit passé pour changer
        # les levels
        if i > delay_wait:

            for univ in range(NB_UNIVERSES):

                for output in range(512):

                    # DMX values with Grand Master correction
                    old_level = round(
                        self.dmxlevels[univ][output] * (255 / App().dmx.grand_master)
                    )

                    channel = App().patch.outputs[univ][output][0]

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

                        channel_time = App().sequence.steps[position + 1].channel_time

                        # If channel is in a channel time
                        if channel in channel_time:
                            ct_delay = channel_time[channel].delay * 1000
                            ct_time = channel_time[channel].time * 1000

                            if next_level > old_level:

                                if i < ct_delay + delay_wait:
                                    level = old_level

                                elif (
                                    ct_delay + delay_wait
                                    <= i
                                    < ct_delay + ct_time + delay_wait
                                ):
                                    level = (
                                        int(
                                            ((next_level - old_level + 1) / ct_time)
                                            * (i - ct_delay - delay_wait)
                                        )
                                        + old_level
                                    )

                                elif i >= ct_delay + ct_time + delay_wait:
                                    level = next_level

                            else:
                                if i < ct_delay + delay_wait:
                                    level = old_level

                                elif (
                                    ct_delay + delay_wait
                                    <= i
                                    < ct_delay + ct_time + delay_wait
                                ):
                                    level = old_level - abs(
                                        int(
                                            ((next_level - old_level - 1) / ct_time)
                                            * (i - ct_delay - delay_wait)
                                        )
                                    )

                                elif i >= ct_delay + ct_time + delay_wait:
                                    level = next_level

                            App().dmx.sequence[channel - 1] = level

                        # Else channel is normal
                        else:
                            # On boucle sur les mémoires et on revient à 0
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
                                App().sequence.position = 0

                            # Si le level augmente,
                            # on prends le temps de montée
                            if (
                                next_level > old_level
                                and delay_wait + delay_d_in
                                < i
                                < delay_in + delay_wait + delay_d_in
                            ):
                                level = (
                                    int(
                                        ((next_level - old_level + 1) / delay_in)
                                        * (i - delay_wait - delay_d_in)
                                    )
                                    + old_level
                                )

                            elif (
                                next_level > old_level
                                and i > delay_in + delay_wait + delay_d_in
                            ):
                                level = next_level

                            # Si le level descend,
                            # on prend le temps de descente
                            elif (
                                next_level < old_level
                                and delay_wait + delay_d_out
                                < i
                                < delay_out + delay_wait + delay_d_out
                            ):
                                level = old_level - abs(
                                    int(
                                        ((next_level - old_level - 1) / delay_out)
                                        * (i - delay_wait - delay_d_out)
                                    )
                                )

                            elif (
                                next_level < old_level
                                and i > delay_out + delay_wait + delay_d_out
                            ):
                                level = next_level

                            # Sinon, la valeur est déjà bonne
                            else:
                                level = old_level

                            App().dmx.sequence[channel - 1] = level

            App().dmx.send()


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

        App().dmx.send()
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
        self._stopevent.set()

    def update_levels(self, go_back_time, i, position):
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
        if App().virtual_console:
            if App().virtual_console.props.visible:
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

        App().dmx.send()

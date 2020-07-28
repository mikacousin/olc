import threading
import array

from ola import OlaClient
from gi.repository import GLib

from olc.define import NB_UNIVERSES, App


class OlaThread(threading.Thread):
    def __init__(self, universes):
        threading.Thread.__init__(self)
        self.universes = universes
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()

        self.old_frame = []
        for _ in range(NB_UNIVERSES):
            self.old_frame.append(array.array("B", [0] * 512))

    def run(self):
        for i, univ in enumerate(self.universes):
            func = getattr(self, "on_dmx_" + str(i), None)
            self.ola_client.RegisterUniverse(univ, self.ola_client.REGISTER, func)

    def on_dmx_0(self, dmxframe):
        diff = [
            (index, e1)
            for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[0]))
            if e1 != e2
        ]
        for output, level in diff:
            channel = App().patch.outputs[0][output][0] - 1
            App().dmx.frame[0][output] = level
            App().window.channels[channel].level = level
            if (
                App().sequence.last > 1
                and App().sequence.position < App().sequence.last - 1
            ):
                next_level = (
                    App()
                    .sequence.steps[App().sequence.position + 1]
                    .cue.channels[channel]
                )
            elif App().sequence.last:
                next_level = App().sequence.steps[0].cue.channels[channel]
            else:
                next_level = level
            App().window.channels[channel].next_level = next_level
            GLib.idle_add(App().window.channels[channel].queue_draw)
            if App().patch_outputs_tab:
                GLib.idle_add(App().patch_outputs_tab.outputs[output].queue_draw)
        self.old_frame[0] = dmxframe

    def on_dmx_1(self, dmxframe):
        diff = [
            (index, e1)
            for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[1]))
            if e1 != e2
        ]
        for output, level in diff:
            channel = App().patch.outputs[1][output][0]
            App().dmx.frame[1][output] = level
            App().window.channels[channel - 1].level = level
            if (
                App().sequence.last > 1
                and App().sequence.position < App().sequence.last - 1
            ):
                next_level = (
                    App()
                    .sequence.steps[App().sequence.position + 1]
                    .cue.channels[channel - 1]
                )
            elif App().sequence.last:
                next_level = App().sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            App().window.channels[channel - 1].next_level = next_level
            GLib.idle_add(App().window.channels[channel - 1].queue_draw)
            if App().patch_outputs_tab:
                GLib.idle_add(App().patch_outputs_tab.outputs[output + 512].queue_draw)
        self.old_frame[1] = dmxframe

    def on_dmx_2(self, dmxframe):
        diff = [
            (index, e1)
            for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[2]))
            if e1 != e2
        ]
        for output, level in diff:
            channel = App().patch.outputs[2][output][0]
            App().dmx.frame[2][output] = level
            App().window.channels[channel - 1].level = level
            if (
                App().sequence.last > 1
                and App().sequence.position < App().sequence.last - 1
            ):
                next_level = (
                    App()
                    .sequence.steps[App().sequence.position + 1]
                    .cue.channels[channel - 1]
                )
            elif App().sequence.last:
                next_level = App().sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            App().window.channels[channel - 1].next_level = next_level
            GLib.idle_add(App().window.channels[channel - 1].queue_draw)
            if App().patch_outputs_tab:
                GLib.idle_add(App().patch_outputs_tab.outputs[output + 1024].queue_draw)
        self.old_frame[2] = dmxframe

    def on_dmx_3(self, dmxframe):
        diff = [
            (index, e1)
            for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[3]))
            if e1 != e2
        ]
        for output, level in diff:
            channel = App().patch.outputs[3][output][0]
            App().dmx.frame[3][output] = level
            App().window.channels[channel - 1].level = level
            if (
                App().sequence.last > 1
                and App().sequence.position < App().sequence.last - 1
            ):
                next_level = (
                    App()
                    .sequence.steps[App().sequence.position + 1]
                    .cue.channels[channel - 1]
                )
            elif App().sequence.last:
                next_level = App().sequence.steps[0].cue.channels[channel - 1]
            else:
                next_level = level
            App().window.channels[channel - 1].next_level = next_level
            GLib.idle_add(App().window.channels[channel - 1].queue_draw)
            if App().patch_outputs_tab:
                GLib.idle_add(App().patch_outputs_tab.outputs[output + 1536].queue_draw)
        self.old_frame[3] = dmxframe

"""ASCII file: Load functions"""

import array

from olc.channel_time import ChannelTime
from olc.cue import Cue
from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.group import Group
from olc.independent import Independent
from olc.master import Master
from olc.sequence import Sequence
from olc.step import Step


def get_time(string):
    """Convert a string time to float

    Args:
        string: format = [[hours:]minutes:]seconds[.tenths]

    Returns:
        time in seconds
    """
    if ":" in string:
        tsplit = string.split(":")
        if len(tsplit) == 2:
            time = int(tsplit[0]) * 60 + float(tsplit[1])
        elif len(tsplit) == 3:
            time = int(tsplit[0]) * 3600 + int(tsplit[1]) * 60 + float(tsplit[2])
        else:
            print("Time format Error")
            time = 0
    else:
        time = float(string)

    return time


class AsciiParser:
    """Parse ASCII files"""

    def __init__(self):
        self.default_time = App().settings.get_double("default-time")

    def parse(self, readlines):
        """Parse stream

        Args:
            readlines (list): Lines to parse
        """
        flag_seq = False
        in_cue = False
        flag_patch = False
        flag_master = False
        flag_group = False
        flag_preset = False
        flag_inde = False

        type_seq = "MainPlayback"
        playback = False
        txt = False
        t_in = False
        t_out = False
        d_in = False
        d_out = False
        wait = False
        channels = False
        mem = False
        channel_time = {}

        console = ""
        item = ""

        for line in readlines:
            # Remove not needed endline
            line = line.replace("\r", "")
            line = line.replace("\n", "")
            # Marker for end of file
            if line[:7].upper() == "ENDDATA":
                break
            # Console type
            if line[:7].upper() == "CONSOLE":
                console = line[8:]
            # Clear all
            if line[:9].upper() == "CLEAR ALL":
                del App().memories[:]
                del App().chasers[:]
                del App().groups[:]
                del App().masters[:]
                for page in range(2):
                    for i in range(20):
                        App().masters.append(Master(page + 1, i + 1, 0, 0))
                App().patch.patch_empty()
                App().sequence.__init__(1, text="Main Playback")
                del App().sequence.steps[1:]
                App().independents.__init__()
            # Sequence
            if line[:9].upper() == "$SEQUENCE":
                p = line[10:].split(" ")
                if int(p[0]) < 2 and not playback:
                    playback = True
                    type_seq = "MainPlayback"
                else:
                    type_seq = "Chaser"
                    index_seq = int(p[0])
                    App().chasers.append(Sequence(index_seq, type_seq=type_seq))
                    del App().chasers[-1].steps[1:]
                flag_seq = True
                flag_patch = False
                flag_master = False
                flag_group = False
                flag_inde = False
                flag_preset = False
            # Chasers
            if flag_seq and type_seq == "Chaser":
                if line[:4].upper() == "TEXT":
                    App().chasers[-1].text = line[5:]
                if line[:4].upper() == "$CUE":
                    in_cue = True
                    channels = array.array("B", [0] * MAX_CHANNELS)
                    p = line[5:].split(" ")
                    seq = p[0]
                    mem = float(p[1])
                if in_cue:
                    if line[:4].upper() == "DOWN":
                        p = line[5:]
                        time = p.split(" ")[0]
                        delay = p.split(" ")[1]
                        t_out = get_time(time)
                        if t_out == 0:
                            t_out = self.default_time
                        d_out = get_time(delay)
                    if line[:2].upper() == "UP":
                        p = line[3:]
                        time = p.split(" ")[0]
                        delay = p.split(" ")[1]
                        t_in = get_time(time)
                        if t_in == 0:
                            t_in = self.default_time
                        d_in = get_time(delay)
                    if line[:4].upper() == "CHAN":
                        p = line[5:].split(" ")
                        for q in p:
                            r = q.split("/")
                            if r[0] != "":
                                channel = int(r[0])
                                level = int(r[1][1:], 16)
                                channels[channel - 1] = level
                    if line == "":
                        if not wait:
                            wait = 0.0
                        if not txt:
                            txt = ""
                        if not t_out:
                            t_out = 5.0
                        if not t_in:
                            t_in = 5.0
                        cue = Cue(seq, mem, channels, text=txt)
                        step = Step(
                            seq,
                            cue,
                            time_in=t_in,
                            time_out=t_out,
                            delay_out=d_out,
                            delay_in=d_in,
                            wait=wait,
                            text=txt,
                        )
                        App().chasers[-1].add_step(step)
                        in_cue = False
                        t_out = False
                        t_in = False
                        channels = False
            # Main Playback
            if flag_seq and type_seq == "MainPlayback":
                if line[:0] == "!":
                    flag_seq = False
                if line[:3].upper() == "CUE":
                    in_cue = True
                    channels = array.array("B", [0] * MAX_CHANNELS)
                    mem = float(line[4:])
                if line[:4].upper() == "$CUE":
                    in_cue = True
                    channels = array.array("B", [0] * MAX_CHANNELS)
                    mem = float(line[5:])

                if in_cue:
                    if line[:4].upper() == "TEXT":
                        txt = line[5:]
                    if line[:6].upper() == "$$TEXT" and not txt:
                        txt = line[7:]
                    if line[:12].upper() == "$$PRESETTEXT":
                        txt = line[13:]
                    if line[:4].upper() == "DOWN":
                        p = line[5:]
                        time = p.split(" ")[0]
                        delay = p.split(" ")[1] if len(p.split(" ")) == 2 else "0"
                        t_out = get_time(time)
                        if t_out == 0:
                            t_out = self.default_time

                        d_out = get_time(delay)

                    if line[:2].upper() == "UP":
                        p = line[3:]
                        time = p.split(" ")[0]
                        delay = p.split(" ")[1] if len(p.split(" ")) == 2 else "0"
                        t_in = get_time(time)
                        if t_in == 0:
                            t_in = self.default_time

                        d_in = get_time(delay)

                    if line[:6].upper() == "$$WAIT":
                        time = line[7:].split(" ")[0]
                        wait = get_time(time)

                    if line[:11].upper() == "$$PARTTIME ":
                        p = line[11:]
                        d = p.split(" ")[0]
                        if d == ".":
                            d = 0
                        delay = float(d)
                        time_str = p.split(" ")[1]
                        time = get_time(time_str)

                    if line[:14].upper() == "$$PARTTIMECHAN":
                        p = line[15:].split(" ")
                        # We could have several channels
                        for chan in p:
                            if chan.isdigit():
                                channel_time[int(chan)] = ChannelTime(delay, time)
                    if line[:4].upper() == "CHAN":
                        p = line[5:].split(" ")
                        for q in p:
                            r = q.split("/")
                            if r[0] != "":
                                channel = int(r[0])
                                # Ignore channels greater than MAX_CHANNELS
                                if channel < MAX_CHANNELS:
                                    level = int(r[1][1:], 16)
                                    channels[channel - 1] = level
                    if line == "":
                        if not wait:
                            wait = 0.0
                        if not txt:
                            txt = ""
                        if not t_out:
                            t_out = 5.0
                        if not t_in:
                            t_in = 5.0
                        if not d_in:
                            d_in = 0.0
                        if not d_out:
                            d_out = 0.0
                        # Create Cue
                        cue = Cue(0, mem, channels, text=txt)
                        # Add cue to the list
                        App().memories.append(cue)
                        # Create Step
                        step = Step(
                            1,
                            cue,
                            time_in=t_in,
                            time_out=t_out,
                            delay_in=d_in,
                            delay_out=d_out,
                            wait=wait,
                            channel_time=channel_time,
                            text=txt,
                        )
                        # Add Step to the Sequence
                        App().sequence.add_step(step)
                        in_cue = False
                        txt = False
                        t_out = False
                        t_in = False
                        wait = False
                        mem = False
                        channels = False
                        channel_time = {}
            # Dimmers Patch
            if line[:11].upper() == "CLEAR PATCH":
                flag_seq = False
                flag_patch = True
                flag_master = False
                flag_group = False
                flag_inde = False
                flag_preset = False
                App().patch.patch_empty()  # Empty patch
                App().window.channels_view.flowbox.invalidate_filter()
            if flag_patch and line[:0] == "!":
                flag_patch = False
            if line[:7].upper() == "PATCH 1":
                for p in line[8:].split(" "):
                    q = p.split("<")
                    if q[0]:
                        r = q[1].split("@")
                        channel = int(q[0])
                        output = int(r[0])
                        univ = int((output - 1) / 512)
                        level = int(r[1])
                        if univ < NB_UNIVERSES:
                            if channel < MAX_CHANNELS:
                                out = output - (512 * univ)
                                App().patch.add_output(channel, out, univ, level)
                                App().window.channels_view.flowbox.invalidate_filter()
                            else:
                                print("More than", MAX_CHANNELS, "channels")
                        else:
                            print("More than", NB_UNIVERSES, "universes")
            # Presets not in sequence
            if line[:5].upper() == "GROUP" and console == "CONGO":
                # On Congo, Preset not in sequence
                flag_seq = False
                flag_patch = False
                flag_master = False
                flag_group = False
                flag_inde = False
                flag_preset = True
                channels = array.array("B", [0] * MAX_CHANNELS)
                preset_nb = float(line[6:])
            if line[:7].upper() == "$PRESET" and (console in ("DLIGHT", "VLC")):
                # On DLight, Preset not in sequence
                flag_seq = False
                flag_patch = False
                flag_master = False
                flag_group = False
                flag_inde = False
                flag_preset = True
                channels = array.array("B", [0] * MAX_CHANNELS)
                preset_nb = float(line[8:])
            if flag_preset:
                if line[:1] == "!":
                    flag_preset = False
                if line[:4].upper() == "TEXT":
                    txt = line[5:]
                if line[:6].upper() == "$$TEXT":
                    txt = line[7:]
                if line[:4].upper() == "CHAN":
                    p = line[5:].split(" ")
                    for q in p:
                        r = q.split("/")
                        if r[0] != "":
                            channel = int(r[0])
                            level = int(r[1][1:], 16)
                            if channel <= MAX_CHANNELS:
                                channels[channel - 1] = level
                if line == "":
                    # Find Preset's position
                    found = False
                    i = 0
                    for i, _ in enumerate(App().memories):
                        if App().memories[i].memory > preset_nb:
                            found = True
                            break
                    if not found:
                        # Preset is at the end
                        i += 1

                    if not txt:
                        txt = ""

                    # Create Preset
                    cue = Cue(0, preset_nb, channels, text=txt)
                    # Add preset to the list
                    App().memories.insert(i, cue)
                    flag_preset = False
                    txt = ""
            # Groups
            if line[:5].upper() == "GROUP" and console != "CONGO":
                flag_seq = False
                flag_patch = False
                flag_master = False
                flag_preset = False
                flag_inde = False
                flag_group = True
                channels = array.array("B", [0] * MAX_CHANNELS)
                group_nb = float(line[6:])
            if line[:6].upper() == "$GROUP":
                flag_seq = False
                flag_patch = False
                flag_master = False
                flag_preset = False
                flag_inde = False
                flag_group = True
                channels = array.array("B", [0] * MAX_CHANNELS)
                group_nb = float(line[7:])
            if flag_group:
                if line[:1] == "!":
                    flag_group = False
                if line[:4].upper() == "TEXT":
                    txt = line[5:]
                if line[:6].upper() == "$$TEXT":
                    txt = line[7:]
                if line[:4].upper() == "CHAN":
                    p = line[5:].split(" ")
                    for q in p:
                        r = q.split("/")
                        if r[0] != "":
                            channel = int(r[0])
                            level = int(r[1][1:], 16)
                            if channel <= MAX_CHANNELS:
                                channels[channel - 1] = level
                if line == "":
                    if not txt:
                        txt = ""
                    # We don't create a group who already exist
                    group_exist = False
                    for grp in App().groups:
                        if group_nb == grp.index:
                            group_exist = True
                    if not group_exist:
                        App().groups.append(Group(group_nb, channels, txt))
                    flag_group = False
                    txt = ""
            # Masters
            if flag_master:
                if line[:1] == "!":
                    flag_master = False
                if line[:4].upper() == "CHAN":
                    p = line[5:].split(" ")
                    for q in p:
                        r = q.split("/")
                        if r[0] != "":
                            channel = int(r[0])
                            level = int(r[1][1:], 16)
                            if channel <= MAX_CHANNELS:
                                channels[channel - 1] = level
                if (line == "" or line[:13].upper() == "$MASTPAGEITEM") and int(
                    item[1]
                ) <= 20:
                    index = int(item[1]) - 1 + ((int(item[0]) - 1) * 20)
                    App().masters[index] = Master(
                        int(item[0]), int(item[1]), item[2], channels
                    )
                    flag_master = False
            if line[:13].upper() == "$MASTPAGEITEM":
                item = line[14:].split(" ")
                # DLight use Type "2" for Groups
                if console == "DLIGHT" and item[2] == "2":
                    item[2] = "13"
                if item[2] == "2":
                    flag_seq = False
                    flag_patch = False
                    flag_group = False
                    flag_preset = False
                    flag_inde = False
                    flag_master = True
                    channels = array.array("B", [0] * MAX_CHANNELS)
                # Only 20 Masters per pages
                elif int(item[1]) <= 20:
                    index = int(item[1]) - 1 + ((int(item[0]) - 1) * 20)
                    App().masters[index] = Master(
                        int(item[0]), int(item[1]), item[2], item[3]
                    )
            # Independents
            if line[:16].upper() == "$SPECIALFUNCTION":
                flag_seq = False
                flag_patch = False
                flag_master = False
                flag_preset = False
                flag_group = False
                flag_inde = True
                channels = array.array("B", [0] * MAX_CHANNELS)
                text = ""
                items = line[17:].split(" ")
                number = int(items[0])
                # Parameters not implemented:
                # ftype = items[1]  # 0: inclusive, 1: Inhibit, 2: Exclusive
                # button_mode = items[2]  # 0: Momentary, 1: Toggling
            if flag_inde:
                if line[:1] == "!":
                    flag_inde = False
                if line[:4].upper() == "TEXT":
                    text = line[5:]
                if line[:6].upper() == "$$TEXT" and not text:
                    text = line[7:]
                if line[:4].upper() == "CHAN":
                    chan_list = line[5:].split(" ")
                    for channel in chan_list:
                        item = channel.split("/")
                        if item[0]:
                            chan = int(item[0])
                            level = int(item[1][1:], 16)
                            if chan <= MAX_CHANNELS:
                                channels[chan - 1] = level
                if line == "":
                    inde = Independent(number, text=text, levels=channels)
                    App().independents.update(inde)
                    flag_inde = False
            # MIDI mapping
            if line[:10].upper() == "$$MIDINOTE":
                item = line[11:].split(" ")
                App().midi.midi_notes.update({item[0]: [int(item[1]), int(item[2])]})
            if line[:8].upper() == "$$MIDICC":
                item = line[9:].split(" ")
                App().midi.midi_cc.update({item[0]: [int(item[1]), int(item[2])]})

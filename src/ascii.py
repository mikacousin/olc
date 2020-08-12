import array
from io import StringIO
from gi.repository import Gio, Gtk, GObject, Pango

from olc.define import MAX_CHANNELS, NB_UNIVERSES, App
from olc.cue import Cue
from olc.step import Step
from olc.channel_time import ChannelTime
from olc.sequence import Sequence
from olc.group import Group
from olc.master import Master
from olc.widgets_group import GroupWidget


def get_time(string):
    """ String format : [[hours:]minutes:]seconds[.tenths]
        Return time in seconds """
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


class Ascii:
    def __init__(self, filename):
        self.file = filename
        self.basename = self.file.get_basename() if filename else ""
        self.modified = False

        self.default_time = App().settings.get_double("default-time")

    def load(self):
        self.basename = self.file.get_basename()
        self.default_time = App().settings.get_double("default-time")
        try:
            status, contents, _etag_out = self.file.load_contents(None)

            if not status:
                print("Error")
                return

            contents = contents.decode("iso-8859-1")

            file_io = StringIO(contents)

            readlines = file_io.readlines()

            flag_seq = False
            in_cue = False
            flag_patch = False
            flag_master = False
            flag_group = False
            flag_preset = False

            type_seq = "Normal"
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

                line = line.replace("\r", "")
                line = line.replace("\n", "")

                # Marker for end of file
                if line[:7].upper() == "ENDDATA":
                    break

                if line[:7].upper() == "CONSOLE":
                    console = line[8:]

                if line[:9].upper() == "CLEAR ALL":
                    # Clear All
                    del App().memories[:]
                    del App().chasers[:]
                    del App().groups[:]
                    del App().masters[:]
                    for page in range(2):
                        for i in range(20):
                            App().masters.append(
                                Master(
                                    page + 1, i + 1, 0, 0, App().groups, App().chasers,
                                )
                            )
                    App().patch.patch_empty()
                    App().sequence = Sequence(1, App().patch, text="Main Playback")
                    del App().sequence.steps[1:]
                    App().sequence.window = App().window

                if line[:9].upper() == "$SEQUENCE":
                    p = line[10:].split(" ")
                    if int(p[0]) < 2 and not playback:
                        playback = True
                        type_seq = "Normal"
                    else:
                        type_seq = "Chaser"
                        index_seq = int(p[0])
                        App().chasers.append(
                            Sequence(index_seq, App().patch, type_seq=type_seq)
                        )
                        del App().chasers[-1].steps[1:]
                    flag_seq = True
                    flag_patch = False
                    flag_master = False
                    flag_group = False
                    flag_preset = False

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

                if flag_seq and type_seq == "Normal":
                    if line[:0] == "!":
                        flag_seq = False
                        print(line)
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
                            if len(p.split(" ")) == 2:
                                delay = p.split(" ")[1]
                            else:
                                delay = "0"

                            t_out = get_time(time)
                            if t_out == 0:
                                t_out = self.default_time

                            d_out = get_time(delay)

                        if line[:2].upper() == "UP":
                            p = line[3:]
                            time = p.split(" ")[0]
                            if len(p.split(" ")) == 2:
                                delay = p.split(" ")[1]
                            else:
                                delay = "0"

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

                if line[:11].upper() == "CLEAR PATCH":
                    flag_seq = False
                    flag_patch = True
                    flag_master = False
                    flag_group = False
                    flag_preset = False
                    App().patch.patch_empty()  # Empty patch
                    App().window.flowbox.invalidate_filter()
                if flag_patch:
                    if line[:0] == "!":
                        flag_patch = False
                if line[:7].upper() == "PATCH 1":
                    for p in line[8:].split(" "):
                        q = p.split("<")
                        if q[0]:
                            r = q[1].split("@")
                            channel = int(q[0])
                            output = int(r[0])
                            univ = int((output - 1) / 512)
                            out = output - (512 * univ)
                            level = int(r[1])
                            # print(channel, univ, out, level)
                            if univ < NB_UNIVERSES:
                                if channel < MAX_CHANNELS:
                                    App().patch.add_output(channel, out, univ, level)
                                    App().window.flowbox.invalidate_filter()
                                else:
                                    print("Plus de", MAX_CHANNELS, "Circuits")
                            else:
                                print("Plus de", NB_UNIVERSES, "univers")

                if line[:5].upper() == "GROUP" and console == "CONGO":
                    # On Congo, Preset not in sequence
                    flag_seq = False
                    flag_patch = False
                    flag_master = False
                    flag_group = False
                    flag_preset = True
                    channels = array.array("B", [0] * MAX_CHANNELS)
                    preset_nb = float(line[6:])
                if line[:7].upper() == "$PRESET" and (console in ("DLIGHT", "VLC")):
                    # On DLight, Preset not in sequence
                    flag_seq = False
                    flag_patch = False
                    flag_master = False
                    flag_group = False
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

                if line[:5].upper() == "GROUP" and console != "CONGO":
                    flag_seq = False
                    flag_patch = False
                    flag_master = False
                    flag_preset = False
                    flag_group = True
                    channels = array.array("B", [0] * MAX_CHANNELS)
                    group_nb = float(line[6:])
                if line[:6].upper() == "$GROUP":
                    flag_seq = False
                    flag_patch = False
                    flag_master = False
                    flag_preset = False
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
                            int(item[0]),
                            int(item[1]),
                            item[2],
                            item[3],
                            App().groups,
                            App().chasers,
                            channels=channels,
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
                        flag_master = True
                        channels = array.array("B", [0] * MAX_CHANNELS)
                    # Only 20 Masters per pages
                    elif int(item[1]) <= 20:
                        index = int(item[1]) - 1 + ((int(item[0]) - 1) * 20)
                        App().masters[index] = Master(
                            int(item[0]),
                            int(item[1]),
                            item[2],
                            item[3],
                            App().groups,
                            App().chasers,
                        )

            # Add Empty Step at the end
            cue = Cue(0, 0.0)
            step = Step(1, cue=cue)
            App().sequence.add_step(step)

            # Set main window's title with the file name
            App().window.header.set_title(self.basename)
            # Set main window's subtitle
            subtitle = (
                "Mem. : 0 - Next Mem. : "
                + str(App().sequence.steps[0].cue.memory)
                + " "
                + App().sequence.steps[0].cue.text
            )
            App().window.header.set_subtitle(subtitle)

            # Redraw crossfade :
            # On se place au début de la séquence
            App().sequence.position = 0
            # On récupère les temps de la mémoire suivante
            t_in = App().sequence.steps[1].time_in
            t_out = App().sequence.steps[1].time_out
            d_in = App().sequence.steps[1].delay_in
            d_out = App().sequence.steps[1].delay_out
            t_wait = App().sequence.steps[1].wait
            t_total = App().sequence.steps[1].total_time
            App().window.sequential.time_in = t_in
            App().window.sequential.time_out = t_out
            App().window.sequential.wait = t_wait
            App().window.sequential.delay_in = d_in
            App().window.sequential.delay_out = d_out
            App().window.sequential.total_time = t_total

            # On met à jour la liste des mémoires
            App().window.cues_liststore1.clear()
            App().window.cues_liststore2.clear()
            # 2 lignes vides au début
            App().window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
            )
            App().window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )
            for i in range(App().sequence.last):
                # Si on a des entiers, on les affiche comme tels
                if App().sequence.steps[i].wait.is_integer():
                    wait = str(int(App().sequence.steps[i].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(App().sequence.steps[i].wait)
                if App().sequence.steps[i].time_out.is_integer():
                    t_out = int(App().sequence.steps[i].time_out)
                else:
                    t_out = App().sequence.steps[i].time_out
                if App().sequence.steps[i].delay_out.is_integer():
                    d_out = str(int(App().sequence.steps[i].delay_out))
                else:
                    d_out = str(App().sequence.steps[i].delay_out)
                if d_out == "0":
                    d_out = ""
                if App().sequence.steps[i].time_in.is_integer():
                    t_in = int(App().sequence.steps[i].time_in)
                else:
                    t_in = App().sequence.steps[i].time_in
                if App().sequence.steps[i].delay_in.is_integer():
                    d_in = str(int(App().sequence.steps[i].delay_in))
                else:
                    d_in = str(App().sequence.steps[i].delay_in)
                if d_in == "0":
                    d_in = ""
                channel_time = str(len(App().sequence.steps[i].channel_time))
                if channel_time == "0":
                    channel_time = ""
                if i == 0:
                    background = "#997004"
                elif i == 1:
                    background = "#555555"
                else:
                    background = "#232729"
                # Actual and Next Cue in Bold
                if i in (0, 1):
                    weight = Pango.Weight.HEAVY
                else:
                    weight = Pango.Weight.NORMAL
                if i in (0, App().sequence.last - 1):
                    App().window.cues_liststore1.append(
                        [
                            str(i),
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            background,
                            Pango.Weight.NORMAL,
                            99,
                        ]
                    )
                    App().window.cues_liststore2.append(
                        [str(i), "", "", "", "", "", "", "", ""]
                    )
                else:
                    App().window.cues_liststore1.append(
                        [
                            str(i),
                            str(App().sequence.steps[i].cue.memory),
                            str(App().sequence.steps[i].text),
                            wait,
                            d_out,
                            str(t_out),
                            d_in,
                            str(t_in),
                            channel_time,
                            background,
                            weight,
                            99,
                        ]
                    )
                    App().window.cues_liststore2.append(
                        [
                            str(i),
                            str(App().sequence.steps[i].cue.memory),
                            str(App().sequence.steps[i].text),
                            wait,
                            d_out,
                            str(t_out),
                            d_in,
                            str(t_in),
                            channel_time,
                        ]
                    )

            App().window.step_filter1 = App().window.cues_liststore1.filter_new()
            App().window.step_filter1.set_visible_func(App().window.step_filter_func1)

            App().window.step_filter2 = App().window.cues_liststore2.filter_new()
            App().window.step_filter2.set_visible_func(App().window.step_filter_func2)

            App().window.treeview1.set_model(App().window.step_filter1)
            App().window.treeview2.set_model(App().window.step_filter2)

            App().window.step_filter1.refilter()
            App().window.step_filter2.refilter()

            path = Gtk.TreePath.new_from_indices([0])
            App().window.treeview1.set_cursor(path, None, False)
            App().window.treeview2.set_cursor(path, None, False)

            App().window.seq_grid.queue_draw()

            # Redraw Group Tab if exist
            if App().group_tab:
                # Remove Old Groups
                del App().group_tab.grps[:]
                App().group_tab.scrolled2.remove(App().group_tab.flowbox2)
                App().group_tab.flowbox2.destroy()
                # New FlowBox
                App().group_tab.flowbox2 = Gtk.FlowBox()
                App().group_tab.flowbox2.set_valign(Gtk.Align.START)
                App().group_tab.flowbox2.set_max_children_per_line(20)
                App().group_tab.flowbox2.set_homogeneous(True)
                App().group_tab.flowbox2.set_activate_on_single_click(True)
                App().group_tab.flowbox2.set_selection_mode(Gtk.SelectionMode.SINGLE)
                App().group_tab.flowbox2.set_filter_func(
                    App().group_tab.filter_groups, None
                )
                App().group_tab.scrolled2.add(App().group_tab.flowbox2)
                # Add Groups to FlowBox
                for i, _ in enumerate(App().groups):
                    App().group_tab.grps.append(
                        GroupWidget(
                            i,
                            App().groups[i].index,
                            App().groups[i].text,
                            App().group_tab.grps,
                        )
                    )
                    App().group_tab.flowbox2.add(App().group_tab.grps[i])
                App().group_tab.flowbox1.invalidate_filter()
                App().group_tab.flowbox2.invalidate_filter()
                App().window.show_all()

            # Redraw Sequences Tab if exist
            if App().sequences_tab:
                App().sequences_tab.liststore1.clear()

                App().sequences_tab.liststore1.append(
                    [
                        App().sequence.index,
                        App().sequence.type_seq,
                        App().sequence.text,
                    ]
                )

                for chaser in App().chasers:
                    App().sequences_tab.liststore1.append(
                        [chaser.index, chaser.type_seq, chaser.text]
                    )

                App().sequences_tab.treeview1.set_model(App().sequences_tab.liststore1)
                path = Gtk.TreePath.new_first()
                App().sequences_tab.treeview1.set_cursor(path, None, False)
                # TODO: List of steps of selected sequence
                selection = App().sequences_tab.treeview1.get_selection()
                App().sequences_tab.on_sequence_changed(selection)

            # Redraw Patch Outputs Tab if exist
            if App().patch_outputs_tab:
                App().patch_outputs_tab.flowbox.queue_draw()

            # Redraw Patch Channels Tab if exist
            if App().patch_channels_tab:
                App().patch_channels_tab.flowbox.queue_draw()

            # Redraw List of Memories Tab if exist
            if App().memories_tab:
                App().memories_tab.liststore.clear()
                for mem in App().memories:
                    channels = 0
                    for chan in range(MAX_CHANNELS):
                        if mem.channels[chan]:
                            channels += 1
                    App().memories_tab.liststore.append(
                        [str(mem.memory), mem.text, channels]
                    )
                App().memories_tab.flowbox.invalidate_filter()

            # Redraw Masters if Virtual Console is open
            if App().virtual_console:
                if App().virtual_console.props.visible:
                    for page in range(2):
                        for master in App().masters:
                            if master.page == page + 1:
                                App().virtual_console.flashes[
                                    master.number - 1 + (page * 20)
                                ].label = master.text
                                App().virtual_console.flashes[
                                    master.number - 1 + (page * 20)
                                ].queue_draw()

            # Redraw Edit Masters Tab if exist
            if App().masters_tab:
                App().masters_tab.liststore.clear()
                for page in range(2):
                    for i in range(20):
                        index = i + (page * 20)

                        # Type : None
                        if App().masters[index].content_type == 0:
                            App().masters_tab.liststore.append([index + 1, "", "", ""])

                        # Type : Preset
                        elif App().masters[index].content_type == 1:
                            content_value = str(App().masters[index].content_value)
                            App().masters_tab.liststore.append(
                                [index + 1, "Preset", content_value, ""]
                            )

                        # Type : Channels
                        elif App().masters[index].content_type == 2:
                            nb_chan = 0
                            for chan in range(MAX_CHANNELS):
                                if App().masters[index].channels[chan]:
                                    nb_chan += 1
                            App().masters_tab.liststore.append(
                                [index + 1, "Channels", str(nb_chan), ""]
                            )

                        # Type : Sequence
                        elif App().masters[index].content_type == 3:
                            if App().masters[index].content_value.is_integer():
                                content_value = str(
                                    int(App().masters[index].content_value)
                                )
                            else:
                                content_value = str(App().masters[index].content_value)
                            App().masters_tab.liststore.append(
                                [index + 1, "Sequence", content_value, ""]
                            )

                        # Type : Group
                        elif App().masters[index].content_type == 13:
                            if App().masters[index].content_value.is_integer():
                                content_value = str(
                                    int(App().masters[index].content_value)
                                )
                            else:
                                content_value = str(App().masters[index].content_value)
                            App().masters_tab.liststore.append(
                                [index + 1, "Group", content_value, "Exclusif"]
                            )

                        # Type : Unknown
                        else:
                            App().masters_tab.liststore.append(
                                [index + 1, "Unknown", "", ""]
                            )

                App().masters_tab.flowbox.invalidate_filter()

            # TODO: Redraw Track Channels Tab if exist

        except GObject.GError as e:
            print("Error: " + str(e))

        self.modified = False

    def save(self):
        """ Save ASCII File """

        stream = self.file.replace("", False, Gio.FileCreateFlags.NONE, None)

        # TODO: to import Fx and Masters in dlight :
        # MANUFACTURER NICOBATS or AVAB
        # CONSOLE      DLIGHT   or CONGO
        # TODO: Masters dans Dlight sont en Time et pas Flash
        stream.write(bytes("IDENT 3:0\n", "utf8"))
        stream.write(bytes("MANUFACTURER MIKA\n", "utf8"))
        stream.write(bytes("CONSOLE OLC\n\n", "utf8"))
        stream.write(bytes("CLEAR ALL\n\n", "utf8"))

        # Main Sequence
        stream.write(
            bytes(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
                "utf8",
            )
        )
        stream.write(bytes("! Main sequence\n\n", "utf8"))
        stream.write(bytes("$SEQUENCE 1 0\n\n", "utf8"))
        for step, _ in enumerate(App().sequence.steps):
            if int(App().sequence.steps[step].cue.memory) != 0:
                # Save integers as integers
                if App().sequence.steps[step].time_out.is_integer():
                    time_out = str(int(App().sequence.steps[step].time_out))
                else:
                    time_out = str(App().sequence.steps[step].time_out)
                if App().sequence.steps[step].delay_out.is_integer():
                    delay_out = str(int(App().sequence.steps[step].delay_out))
                else:
                    delay_out = str(App().sequence.steps[step].delay_out)
                if App().sequence.steps[step].time_in.is_integer():
                    time_in = str(int(App().sequence.steps[step].time_in))
                else:
                    time_in = str(App().sequence.steps[step].time_in)
                if App().sequence.steps[step].delay_in.is_integer():
                    delay_in = str(int(App().sequence.steps[step].delay_in))
                else:
                    delay_in = str(App().sequence.steps[step].delay_in)
                if App().sequence.steps[step].wait.is_integer():
                    wait = str(int(App().sequence.steps[step].wait))
                else:
                    wait = str(App().sequence.steps[step].wait)
                stream.write(
                    bytes(
                        "CUE " + str(App().sequence.steps[step].cue.memory) + "\n",
                        "utf8",
                    )
                )
                stream.write(
                    bytes("DOWN " + time_out + " " + delay_out + "\n", "utf8",)
                )
                stream.write(bytes("UP " + time_in + " " + delay_in + "\n", "utf8",))
                stream.write(bytes("$$WAIT " + wait + "\n", "utf8",))
                #  Chanel Time if any
                for chan in App().sequence.steps[step].channel_time.keys():
                    if App().sequence.steps[step].channel_time[chan].delay.is_integer():
                        delay = str(
                            int(App().sequence.steps[step].channel_time[chan].delay)
                        )
                    else:
                        delay = str(App().sequence.steps[step].channel_time[chan].delay)
                    if App().sequence.steps[step].channel_time[chan].time.is_integer():
                        time = str(
                            int(App().sequence.steps[step].channel_time[chan].time)
                        )
                    else:
                        time = str(App().sequence.steps[step].channel_time[chan].time)
                    stream.write(
                        bytes("$$PARTTIME " + delay + " " + time + "\n", "utf8",)
                    )
                    stream.write(bytes("$$PARTTIMECHAN " + str(chan) + "\n", "utf8"))
                stream.write(
                    bytes(
                        "TEXT " + App().sequence.steps[step].text + "\n", "iso-8859-1"
                    )
                )
                stream.write(
                    bytes(
                        "$$TEXT " + ascii(App().sequence.steps[step].text)[1:-1] + "\n",
                        "ascii",
                    )
                )
                channels = ""
                i = 1
                for chan, _ in enumerate(App().sequence.steps[step].cue.channels):
                    level = App().sequence.steps[step].cue.channels[chan]
                    if level != 0:
                        level = "H" + format(level, "02X")
                        channels += " " + str(chan + 1) + "/" + level
                        # 6 Channels per line
                        if not i % 6 and channels != "":
                            stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                            channels = ""
                        i += 1
                if channels != "":
                    stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                stream.write(bytes("\n", "utf8"))

        # Chasers
        stream.write(bytes("! Additional Sequences\n\n", "utf8"))

        for chaser, _ in enumerate(App().chasers):
            stream.write(
                bytes("$SEQUENCE " + str(App().chasers[chaser].index) + "\n", "utf8")
            )
            stream.write(bytes("TEXT " + App().chasers[chaser].text + "\n\n", "utf8"))
            for step, _ in enumerate(App().chasers[chaser].steps):
                if int(App().chasers[chaser].steps[step].cue.memory) != 0:
                    # Save integers as integers
                    if App().chasers[chaser].steps[step].time_out.is_integer():
                        time_out = str(int(App().chasers[chaser].steps[step].time_out))
                    else:
                        time_out = str(App().chasers[chaser].steps[step].time_out)
                    if App().chasers[chaser].steps[step].delay_out.is_integer():
                        delay_out = str(
                            int(App().chasers[chaser].steps[step].delay_out)
                        )
                    else:
                        delay_out = str(App().chasers[chaser].steps[step].delay_out)
                    if App().chasers[chaser].steps[step].time_in.is_integer():
                        time_in = str(int(App().chasers[chaser].steps[step].time_in))
                    else:
                        time_in = str(App().chasers[chaser].steps[step].time_in)
                    if App().chasers[chaser].steps[step].delay_in.is_integer():
                        delay_in = str(int(App().chasers[chaser].steps[step].delay_in))
                    else:
                        delay_in = str(App().chasers[chaser].steps[step].delay_in)
                    if App().chasers[chaser].steps[step].wait.is_integer():
                        wait = str(int(App().chasers[chaser].steps[step].wait))
                    else:
                        wait = str(App().chasers[chaser].steps[step].wait)
                    stream.write(
                        bytes(
                            "$CUE "
                            + str(App().chasers[chaser].index)
                            + " "
                            + str(App().chasers[chaser].steps[step].cue.memory)
                            + "\n",
                            "utf8",
                        )
                    )
                    stream.write(
                        bytes("DOWN " + time_out + " " + delay_out + "\n", "utf8",)
                    )
                    stream.write(
                        bytes("UP " + time_in + " " + delay_in + "\n", "utf8",)
                    )
                    stream.write(bytes("$$WAIT " + wait + "\n", "utf8",))
                    channels = ""
                    i = 1
                    for chan, _ in enumerate(
                        App().chasers[chaser].steps[step].cue.channels
                    ):
                        level = App().chasers[chaser].steps[step].cue.channels[chan]
                        if level != 0:
                            level = "H" + format(level, "02X")
                            channels += " " + str(chan + 1) + "/" + level
                            # 6 channels per line
                            if not i % 6 and channels != "":
                                stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                                channels = ""
                            i += 1
                    if channels != "":
                        stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                    stream.write(bytes("\n", "utf8"))

        # Groups
        stream.write(
            bytes(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
                "utf8",
            )
        )
        stream.write(bytes("! Groups (presets not in sequence)\n", "utf8"))
        stream.write(bytes("! GROUP  Standard ASCII Light Cues\n", "utf8"))
        stream.write(bytes("! CHAN   Standard ASCII Light Cues\n", "utf8"))
        stream.write(bytes("! TEXT   Standard ASCII Light Cues\n", "utf8"))
        stream.write(
            bytes("! $$TEXT  Unicode encoded version of the same text\n", "utf8")
        )

        for group, _ in enumerate(App().groups):
            stream.write(
                bytes("GROUP " + str(App().groups[group].index) + "\n", "utf8")
            )
            stream.write(
                bytes("TEXT " + ascii(App().groups[group].text)[1:-1] + "\n", "utf8")
                .decode("utf8")
                .encode("ascii")
            )
            stream.write(bytes("$$TEXT " + App().groups[group].text + "\n", "utf8"))
            channels = ""
            i = 1
            for chan, _ in enumerate(App().groups[group].channels):
                level = App().groups[group].channels[chan]
                if level != 0:
                    level = "H" + format(level, "02X")
                    channels += " " + str(chan + 1) + "/" + level
                    # 6 channels per line
                    if not i % 6 and channels != "":
                        stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                        channels = ""
                    i += 1
            if channels != "":
                stream.write(bytes("CHAN" + channels + "\n", "utf8"))
            stream.write(bytes("\n", "utf8"))

        # Congo Groups
        stream.write(
            bytes(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
                "utf8",
            )
        )
        stream.write(bytes("! Congo Groups\n", "utf8"))
        stream.write(bytes("! $GROUP  Group number\n", "utf8"))
        stream.write(bytes("! CHAN    Standard ASCII Light Cues\n", "utf8"))
        stream.write(bytes("! TEXT    Standard ASCII Light Cues\n", "utf8"))
        stream.write(
            bytes("! $$TEXT  Unicode encoded version of the same text\n", "utf8")
        )
        stream.write(bytes("CLEAR $GROUP\n\n", "utf8"))

        for group, _ in enumerate(App().groups):
            stream.write(
                bytes("$GROUP " + str(App().groups[group].index) + "\n", "utf8")
            )
            stream.write(
                bytes("TEXT " + ascii(App().groups[group].text)[1:-1] + "\n", "utf8")
                .decode("utf8")
                .encode("ascii")
            )
            stream.write(bytes("$$TEXT " + App().groups[group].text + "\n", "utf8"))
            channels = ""
            i = 1
            for chan, _ in enumerate(App().groups[group].channels):
                level = App().groups[group].channels[chan]
                if level != 0:
                    level = "H" + format(level, "02X")
                    channels += " " + str(chan + 1) + "/" + level
                    # 6 channels per line
                    if not i % 6 and channels != "":
                        stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                        channels = ""
                    i += 1
            if channels != "":
                stream.write(bytes("CHAN" + channels + "\n", "utf8"))
            stream.write(bytes("\n", "utf8"))

        # Masters
        stream.write(
            bytes(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
                "utf8",
            )
        )
        stream.write(bytes("! Master Pages\n", "utf8"))
        stream.write(bytes("! $MASTPAGE     Master page number\n", "utf8"))
        stream.write(bytes("! TEXT          Master page text\n", "utf8"))
        stream.write(
            bytes("! $TEXT         Unicode encoded version of the same text\n", "utf8")
        )
        stream.write(bytes("! $MASTPAGEITEM Page number, Master number,\n", "utf8"))
        stream.write(
            bytes("!               Content type (2 = Channels, 3 = Chaser,\n", "utf8")
        )
        stream.write(
            bytes(
                "!               13 = Group), Content value (Chaser#, Group#),\n",
                "utf8",
            )
        )
        stream.write(bytes("!               Time In, Wait time, Time Out,\n", "utf8"))
        stream.write(bytes("!               Flash level (0-255)\n", "utf8"))
        stream.write(bytes("CLEAR $MASTPAGE\n\n", "utf8"))
        stream.write(bytes("$MASTPAGE 1 0 0 0\n", "utf8"))
        page = 1
        for master, _ in enumerate(App().masters):
            if App().masters[master].page != page:
                page = App().masters[master].page
                stream.write(bytes("\n$MASTPAGE " + str(page) + " 0 0 0\n", "utf8"))
            # MASTPAGEITEM :
            # page, sub, type, content, timeIn, autotime, timeOut, target,,,,,,
            stream.write(
                bytes(
                    "$MASTPAGEITEM "
                    + str(App().masters[master].page)
                    + " "
                    + str(App().masters[master].number)
                    + " "
                    + str(App().masters[master].content_type)
                    + " "
                    + str(App().masters[master].content_value)
                    + " 5 0 5 255\n",
                    "utf8",
                )
            )
            # Master of Channels, save them
            if App().masters[master].content_type == 2:
                channels = ""
                i = 1
                for chan, _ in enumerate(App().masters[master].channels):
                    level = App().masters[master].channels[chan]
                    if level != 0:
                        level = "H" + format(level, "02X")
                        channels += " " + str(chan + 1) + "/" + level
                        # 6 channels per line
                        if not i % 6 and channels != "":
                            stream.write(bytes("CHAN" + channels + "\n", "utf8"))
                            channels = ""
                        i += 1
                if channels != "":
                    stream.write(bytes("CHAN" + channels + "\n", "utf8"))
        stream.write(bytes("\n", "utf8"))

        # Patch
        stream.write(
            bytes(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
                "utf8",
            )
        )
        stream.write(bytes("! Patch\n", "utf8"))
        stream.write(bytes("CLEAR PATCH\n\n", "utf8"))
        patch = ""
        i = 1
        for universe in range(NB_UNIVERSES):
            for output in range(512):
                if App().patch.outputs[universe][output][0]:
                    patch += (
                        " "
                        + str(App().patch.outputs[universe][output][0])
                        + "<"
                        + str(output + 1 + (512 * universe))
                        + "@"
                        + str(App().patch.outputs[universe][output][1])
                    )
                    if not i % 4 and patch != "":
                        stream.write(bytes("PATCH 1" + patch + "\n", "utf8"))
                        patch = ""
                    i += 1
        if patch != "":
            stream.write(bytes("PATCH 1" + patch + "\n", "utf8"))

        stream.write(bytes("\nENDDATA\n", "utf8"))

        stream.close()

        self.modified = False
        App().window.header.set_title(self.basename)

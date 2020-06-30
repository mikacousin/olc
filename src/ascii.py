import array
from io import StringIO
from gi.repository import Gio, Gtk, GObject, Pango

from olc.define import MAX_CHANNELS, NB_UNIVERSES
from olc.cue import Cue
from olc.step import Step
from olc.channel_time import ChannelTime
from olc.sequence import Sequence
from olc.group import Group
from olc.master import Master
from olc.widgets_group import GroupWidget


class Ascii:
    def __init__(self, filename):
        self.file = filename
        if filename:
            self.basename = self.file.get_basename()
        else:
            self.basename = ""
        self.modified = False

        self.default_time = Gio.Application.get_default().settings.get_double(
            "default-time"
        )

        self.app = Gio.Application.get_default()

    def load(self):
        self.basename = self.file.get_basename()
        self.default_time = Gio.Application.get_default().settings.get_double(
            "default-time"
        )
        try:
            status, contents, etag_out = self.file.load_contents(None)

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
            Playback = False
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
                    del self.app.memories[:]
                    del self.app.chasers[:]
                    del self.app.groups[:]
                    del self.app.masters[:]
                    for page in range(2):
                        for i in range(20):
                            self.app.masters.append(
                                Master(
                                    page + 1,
                                    i + 1,
                                    0,
                                    0,
                                    self.app.groups,
                                    self.app.chasers,
                                )
                            )
                    self.app.patch.patch_empty()
                    self.app.sequence = Sequence(
                        1, self.app.patch, text="Main Playback"
                    )
                    del self.app.sequence.steps[1:]
                    self.app.sequence.window = self.app.window

                if line[:9].upper() == "$SEQUENCE":
                    p = line[10:].split(" ")
                    if int(p[0]) < 2 and not Playback:
                        Playback = True
                        type_seq = "Normal"
                    else:
                        type_seq = "Chaser"
                        index_seq = int(p[0])
                        self.app.chasers.append(
                            Sequence(index_seq, self.app.patch, type_seq=type_seq)
                        )
                        del self.app.chasers[-1].steps[1:]
                    flag_seq = True
                    flag_patch = False
                    flag_master = False
                    flag_group = False
                    flag_preset = False

                if flag_seq and type_seq == "Chaser":
                    if line[:4].upper() == "TEXT":
                        self.app.chasers[-1].text = line[5:]

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

                            t_out = self.get_time(time)
                            if t_out == 0:
                                t_out = self.default_time

                            d_out = self.get_time(delay)

                        if line[:2].upper() == "UP":
                            p = line[3:]
                            time = p.split(" ")[0]
                            delay = p.split(" ")[1]

                            t_in = self.get_time(time)
                            if t_in == 0:
                                t_in = self.default_time

                            d_in = self.get_time(delay)

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

                            self.app.chasers[-1].add_step(step)

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
                        if line[:4].upper() == "TEXT" and not txt:
                            txt = line[5:]
                        if line[:6].upper() == "$$TEXT":
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

                            t_out = self.get_time(time)
                            if t_out == 0:
                                t_out = self.default_time

                            d_out = self.get_time(delay)

                        if line[:2].upper() == "UP":
                            p = line[3:]
                            time = p.split(" ")[0]
                            if len(p.split(" ")) == 2:
                                delay = p.split(" ")[1]
                            else:
                                delay = "0"

                            t_in = self.get_time(time)
                            if t_in == 0:
                                t_in = self.default_time

                            d_in = self.get_time(delay)

                        if line[:6].upper() == "$$WAIT":
                            time = line[7:].split(" ")[0]
                            wait = self.get_time(time)

                        if line[:11].upper() == "$$PARTTIME ":
                            p = line[11:]
                            d = p.split(" ")[0]
                            if d == ".":
                                d = 0
                            delay = float(d)
                            time_str = p.split(" ")[1]
                            time = self.get_time(time_str)

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
                            self.app.memories.append(cue)
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
                            self.app.sequence.add_step(step)
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
                    self.app.patch.patch_empty()  # Empty patch
                    self.app.window.flowbox.invalidate_filter()
                if flag_patch:
                    if line[:0] == "!":
                        flag_patch = False
                if line[:7].upper() == "PATCH 1":
                    for p in line[8:-1].split(" "):
                        q = p.split("<")
                        if q[0]:
                            r = q[1].split("@")
                            channel = int(q[0])
                            output = int(r[0])
                            univ = int(output / 512)
                            out = output - (512 * univ)
                            level = int(r[1])
                            # print(channel, univ, out, level)
                            if univ < NB_UNIVERSES:
                                if channel < MAX_CHANNELS:
                                    self.app.patch.add_output(channel, out, univ, level)
                                    self.app.window.flowbox.invalidate_filter()
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
                        for i, _ in enumerate(self.app.memories):
                            if self.app.memories[i].memory > preset_nb:
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
                        self.app.memories.insert(i, cue)
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
                        for grp in self.app.groups:
                            if group_nb == grp.index:
                                group_exist = True
                        if not group_exist:
                            self.app.groups.append(Group(group_nb, channels, txt))
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
                        self.app.masters[index] = Master(
                            int(item[0]),
                            int(item[1]),
                            item[2],
                            item[3],
                            self.app.groups,
                            self.app.chasers,
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
                        self.app.masters[index] = Master(
                            int(item[0]),
                            int(item[1]),
                            item[2],
                            item[3],
                            self.app.groups,
                            self.app.chasers,
                        )

            # Add Empty Step at the end
            cue = Cue(0, 0.0)
            step = Step(1, cue=cue)
            self.app.sequence.add_step(step)

            # Set main window's title with the file name
            self.app.window.header.set_title(self.basename)
            # Set main window's subtitle
            subtitle = (
                "Mem. : 0 - Next Mem. : "
                + str(self.app.sequence.steps[0].cue.memory)
                + " "
                + self.app.sequence.steps[0].cue.text
            )
            self.app.window.header.set_subtitle(subtitle)

            # Redraw crossfade :
            # On se place au début de la séquence
            self.app.sequence.position = 0
            # On récupère les temps de la mémoire suivante
            t_in = self.app.sequence.steps[1].time_in
            t_out = self.app.sequence.steps[1].time_out
            d_in = self.app.sequence.steps[1].delay_in
            d_out = self.app.sequence.steps[1].delay_out
            t_wait = self.app.sequence.steps[1].wait
            t_total = self.app.sequence.steps[1].total_time
            self.app.window.sequential.time_in = t_in
            self.app.window.sequential.time_out = t_out
            self.app.window.sequential.wait = t_wait
            self.app.window.sequential.delay_in = d_in
            self.app.window.sequential.delay_out = d_out
            self.app.window.sequential.total_time = t_total

            # On met à jour la liste des mémoires
            self.app.window.cues_liststore1.clear()
            self.app.window.cues_liststore2.clear()
            # 2 lignes vides au début
            self.app.window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 0]
            )
            self.app.window.cues_liststore1.append(
                ["", "", "", "", "", "", "", "", "", "#232729", 0, 1]
            )
            for i in range(self.app.sequence.last):
                # Si on a des entiers, on les affiche comme tels
                if self.app.sequence.steps[i].wait.is_integer():
                    wait = str(int(self.app.sequence.steps[i].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.app.sequence.steps[i].wait)
                if self.app.sequence.steps[i].time_out.is_integer():
                    t_out = int(self.app.sequence.steps[i].time_out)
                else:
                    t_out = self.app.sequence.steps[i].time_out
                if self.app.sequence.steps[i].delay_out.is_integer():
                    d_out = str(int(self.app.sequence.steps[i].delay_out))
                else:
                    d_out = str(self.app.sequence.steps[i].delay_out)
                if d_out == "0":
                    d_out = ""
                if self.app.sequence.steps[i].time_in.is_integer():
                    t_in = int(self.app.sequence.steps[i].time_in)
                else:
                    t_in = self.app.sequence.steps[i].time_in
                if self.app.sequence.steps[i].delay_in.is_integer():
                    d_in = str(int(self.app.sequence.steps[i].delay_in))
                else:
                    d_in = str(self.app.sequence.steps[i].delay_in)
                if d_in == "0":
                    d_in = ""
                channel_time = str(len(self.app.sequence.steps[i].channel_time))
                if channel_time == "0":
                    channel_time = ""
                if i == 0:
                    bg = "#997004"
                elif i == 1:
                    bg = "#555555"
                else:
                    bg = "#232729"
                # Actual and Next Cue in Bold
                if i in (0, 1):
                    weight = Pango.Weight.HEAVY
                else:
                    weight = Pango.Weight.NORMAL
                if i in (0, self.app.sequence.last - 1):
                    self.app.window.cues_liststore1.append(
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
                            bg,
                            Pango.Weight.NORMAL,
                            99,
                        ]
                    )
                    self.app.window.cues_liststore2.append(
                        [str(i), "", "", "", "", "", "", "", ""]
                    )
                else:
                    self.app.window.cues_liststore1.append(
                        [
                            str(i),
                            str(self.app.sequence.steps[i].cue.memory),
                            str(self.app.sequence.steps[i].text),
                            wait,
                            d_out,
                            str(t_out),
                            d_in,
                            str(t_in),
                            channel_time,
                            bg,
                            weight,
                            99,
                        ]
                    )
                    self.app.window.cues_liststore2.append(
                        [
                            str(i),
                            str(self.app.sequence.steps[i].cue.memory),
                            str(self.app.sequence.steps[i].text),
                            wait,
                            d_out,
                            str(t_out),
                            d_in,
                            str(t_in),
                            channel_time,
                        ]
                    )

            self.app.window.step_filter1 = self.app.window.cues_liststore1.filter_new()
            self.app.window.step_filter1.set_visible_func(
                self.app.window.step_filter_func1
            )

            self.app.window.step_filter2 = self.app.window.cues_liststore2.filter_new()
            self.app.window.step_filter2.set_visible_func(
                self.app.window.step_filter_func2
            )

            self.app.window.treeview1.set_model(self.app.window.step_filter1)
            self.app.window.treeview2.set_model(self.app.window.step_filter2)

            self.app.window.step_filter1.refilter()
            self.app.window.step_filter2.refilter()

            path = Gtk.TreePath.new_from_indices([0])
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)

            self.app.window.seq_grid.queue_draw()

            # Redraw Group Tab if exist
            if self.app.group_tab:
                # Remove Old Groups
                del self.app.group_tab.grps[:]
                self.app.group_tab.scrolled2.remove(self.app.group_tab.flowbox2)
                self.app.group_tab.flowbox2.destroy()
                # New FlowBox
                self.app.group_tab.flowbox2 = Gtk.FlowBox()
                self.app.group_tab.flowbox2.set_valign(Gtk.Align.START)
                self.app.group_tab.flowbox2.set_max_children_per_line(20)
                self.app.group_tab.flowbox2.set_homogeneous(True)
                self.app.group_tab.flowbox2.set_activate_on_single_click(True)
                self.app.group_tab.flowbox2.set_selection_mode(Gtk.SelectionMode.SINGLE)
                self.app.group_tab.flowbox2.set_filter_func(
                    self.app.group_tab.filter_groups, None
                )
                self.app.group_tab.scrolled2.add(self.app.group_tab.flowbox2)
                # Add Groups to FlowBox
                for i, _ in enumerate(self.app.groups):
                    self.app.group_tab.grps.append(
                        GroupWidget(
                            i,
                            self.app.groups[i].index,
                            self.app.groups[i].text,
                            self.app.group_tab.grps,
                        )
                    )
                    self.app.group_tab.flowbox2.add(self.app.group_tab.grps[i])
                self.app.group_tab.flowbox1.invalidate_filter()
                self.app.group_tab.flowbox2.invalidate_filter()
                self.app.window.show_all()

            # Redraw Sequences Tab if exist
            if self.app.sequences_tab:
                self.app.sequences_tab.liststore1.clear()

                self.app.sequences_tab.liststore1.append(
                    [
                        self.app.sequence.index,
                        self.app.sequence.type_seq,
                        self.app.sequence.text,
                    ]
                )

                for chaser in self.app.chasers:
                    self.app.sequences_tab.liststore1.append(
                        [chaser.index, chaser.type_seq, chaser.text]
                    )

                self.app.sequences_tab.treeview1.set_model(
                    self.app.sequences_tab.liststore1
                )
                path = Gtk.TreePath.new_first()
                self.app.sequences_tab.treeview1.set_cursor(path, None, False)
                # TODO: List of steps of selected sequence
                selection = self.app.sequences_tab.treeview1.get_selection()
                self.app.sequences_tab.on_sequence_changed(selection)

            # Redraw Patch Outputs Tab if exist
            if self.app.patch_outputs_tab:
                self.app.patch_outputs_tab.flowbox.queue_draw()

            # Redraw Patch Channels Tab if exist
            if self.app.patch_channels_tab:
                self.app.patch_channels_tab.flowbox.queue_draw()

            # Redraw List of Memories Tab if exist
            if self.app.memories_tab:
                self.app.memories_tab.liststore.clear()
                for mem in self.app.memories:
                    channels = 0
                    for chan in range(MAX_CHANNELS):
                        if mem.channels[chan]:
                            channels += 1
                    self.app.memories_tab.liststore.append(
                        [str(mem.memory), mem.text, channels]
                    )
                self.app.memories_tab.flowbox.invalidate_filter()

            # Redraw Masters if Virtual Console is open
            if self.app.virtual_console:
                if self.app.virtual_console.props.visible:
                    for page in range(2):
                        for master in self.app.masters:
                            if master.page == page + 1:
                                self.app.virtual_console.flashes[
                                    master.number - 1 + (page * 20)
                                ].label = master.text
                                self.app.virtual_console.flashes[
                                    master.number - 1 + (page * 20)
                                ].queue_draw()

            # Redraw Edit Masters Tab if exist
            if self.app.masters_tab:
                self.app.masters_tab.liststore.clear()
                for page in range(2):
                    for i in range(20):
                        index = i + (page * 20)

                        # Type : None
                        if self.app.masters[index].content_type == 0:
                            self.app.masters_tab.liststore.append(
                                [index + 1, "", "", ""]
                            )

                        # Type : Preset
                        elif self.app.masters[index].content_type == 1:
                            content_value = str(self.app.masters[index].content_value)
                            self.app.masters_tab.liststore.append(
                                [index + 1, "Preset", content_value, ""]
                            )

                        # Type : Channels
                        elif self.app.masters[index].content_type == 2:
                            nb_chan = 0
                            for chan in range(MAX_CHANNELS):
                                if self.app.masters[index].channels[chan]:
                                    nb_chan += 1
                            self.app.masters_tab.liststore.append(
                                [index + 1, "Channels", str(nb_chan), ""]
                            )

                        # Type : Sequence
                        elif self.app.masters[index].content_type == 3:
                            if self.app.masters[index].content_value.is_integer():
                                content_value = str(
                                    int(self.app.masters[index].content_value)
                                )
                            else:
                                content_value = str(
                                    self.app.masters[index].content_value
                                )
                            self.app.masters_tab.liststore.append(
                                [index + 1, "Sequence", content_value, ""]
                            )

                        # Type : Group
                        elif self.app.masters[index].content_type == 13:
                            if self.app.masters[index].content_value.is_integer():
                                content_value = str(
                                    int(self.app.masters[index].content_value)
                                )
                            else:
                                content_value = str(
                                    self.app.masters[index].content_value
                                )
                            self.app.masters_tab.liststore.append(
                                [index + 1, "Group", content_value, "Exclusif"]
                            )

                        # Type : Unknown
                        else:
                            self.app.masters_tab.liststore.append(
                                [index + 1, "Unknown", "", ""]
                            )

                self.app.masters_tab.flowbox.invalidate_filter()

            # TODO: Redraw Track Channels Tab if exist

        except GObject.GError as e:
            print("Error: " + str(e))

        self.modified = False

    def save(self):
        """ Save ASCII File """

        # TODO: Rewrite all this function
        print("Don't save for now !!!")
        return False

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
        for cue, _ in enumerate(self.app.sequence.steps):
            if self.app.sequence.steps[cue].cue.memory != "0":
                stream.write(
                    bytes(
                        "CUE " + self.app.sequence.steps[cue].cue.memory + "\n", "utf8"
                    )
                )
                stream.write(
                    bytes(
                        "DOWN " + str(self.app.sequence.steps[cue].time_out) + "\n",
                        "utf8",
                    )
                )
                stream.write(
                    bytes(
                        "UP " + str(self.app.sequence.steps[cue].time_in) + "\n", "utf8"
                    )
                )
                stream.write(
                    bytes(
                        "$$WAIT " + str(self.app.sequence.steps[cue].wait) + "\n",
                        "utf8",
                    )
                )
                #  Chanel Time if any
                for chan in self.app.sequence.steps[cue].channel_time.keys():
                    stream.write(
                        bytes(
                            "$$PARTTIME "
                            + str(self.app.sequence.steps[cue].channel_time[chan].delay)
                            + " "
                            + str(self.app.sequence.steps[cue].channel_time[chan].time)
                            + "\n",
                            "utf8",
                        )
                    )
                    stream.write(bytes("$$PARTTIMECHAN " + str(chan) + "\n", "utf8"))
                stream.write(
                    bytes(
                        "TEXT " + ascii(self.app.sequence.steps[cue].text)[1:-1] + "\n",
                        "utf8",
                    )
                    .decode("utf8")
                    .encode("ascii")
                )
                stream.write(
                    bytes("$$TEXT " + self.app.sequence.steps[cue].text + "\n", "utf8")
                )
                channels = ""
                i = 1
                for chan, _ in enumerate(self.app.sequence.steps[cue].cue.channels):
                    level = self.app.sequence.steps[cue].cue.channels[chan]
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

        for chaser, _ in enumerate(self.app.chasers):
            stream.write(
                bytes("$SEQUENCE " + str(self.app.chasers[chaser].index) + "\n", "utf8")
            )
            stream.write(
                bytes("TEXT " + self.app.chasers[chaser].text + "\n\n", "utf8")
            )
            for cue, _ in enumerate(self.app.chasers[chaser].steps):
                if self.app.chasers[chaser].steps[cue].cue.memory != "0":
                    stream.write(
                        bytes(
                            "$CUE "
                            + str(self.app.chasers[chaser].index)
                            + " "
                            + self.app.chasers[chaser].steps[cue].cue.memory
                            + "\n",
                            "utf8",
                        )
                    )
                    stream.write(
                        bytes(
                            "DOWN "
                            + str(self.app.chasers[chaser].steps[cue].time_out)
                            + "\n",
                            "utf8",
                        )
                    )
                    stream.write(
                        bytes(
                            "UP "
                            + str(self.app.chasers[chaser].steps[cue].time_in)
                            + "\n",
                            "utf8",
                        )
                    )
                    stream.write(
                        bytes(
                            "$$WAIT "
                            + str(self.app.chasers[chaser].steps[cue].wait)
                            + "\n",
                            "utf8",
                        )
                    )
                    channels = ""
                    i = 1
                    for chan, _ in enumerate(
                        self.app.chasers[chaser].steps[cue].channels
                    ):
                        level = self.app.chasers[chaser].steps[cue].cue.channels[chan]
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

        for group, _ in enumerate(self.app.groups):
            stream.write(
                bytes("GROUP " + str(self.app.groups[group].index) + "\n", "utf8")
            )
            stream.write(
                bytes("TEXT " + ascii(self.app.groups[group].text)[1:-1] + "\n", "utf8")
                .decode("utf8")
                .encode("ascii")
            )
            stream.write(bytes("$$TEXT " + self.app.groups[group].text + "\n", "utf8"))
            channels = ""
            i = 1
            for chan, _ in enumerate(self.app.groups[group].channels):
                level = self.app.groups[group].channels[chan]
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

        for group, _ in enumerate(self.app.groups):
            stream.write(
                bytes("$GROUP " + str(self.app.groups[group].index) + "\n", "utf8")
            )
            stream.write(
                bytes("TEXT " + ascii(self.app.groups[group].text)[1:-1] + "\n", "utf8")
                .decode("utf8")
                .encode("ascii")
            )
            stream.write(bytes("$$TEXT " + self.app.groups[group].text + "\n", "utf8"))
            channels = ""
            i = 1
            for chan, _ in enumerate(self.app.groups[group].channels):
                level = self.app.groups[group].channels[chan]
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
        for master, _ in enumerate(self.app.masters):
            if self.app.masters[master].page != page:
                page = self.app.masters[master].page
                stream.write(bytes("\n$MASTPAGE " + str(page) + " 0 0 0\n", "utf8"))
            # MASTPAGEITEM :
            # page, sub, type, content, timeIn, autotime, timeOut, target,,,,,,
            stream.write(
                bytes(
                    "$MASTPAGEITEM "
                    + self.app.masters[master].page
                    + " "
                    + self.app.masters[master].number
                    + " "
                    + str(self.app.masters[master].content_type)
                    + " "
                    + str(self.app.masters[master].content_value)
                    + " 5 0 5 255\n",
                    "utf8",
                )
            )
            # Master of Channels, save them
            if self.app.masters[master].content_type == 2:
                channels = ""
                i = 1
                for chan, _ in enumerate(self.app.masters[master].channels):
                    level = self.app.masters[master].channels[chan]
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
        # TODO: More than 1 Univers
        # TODO: Prise en charge du niveau de l'output
        patch = ""
        i = 1
        for output, _ in enumerate(self.app.patch.outputs):
            if self.app.patch.outputs[output] != 0:
                patch += (
                    " "
                    + str(self.app.patch.outputs[output])
                    + "<"
                    + str(output + 1)
                    + "@100"
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
        self.app.window.header.set_title(self.basename)

    def get_time(self, string):
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

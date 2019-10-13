import array
from gi.repository import Gio, Gtk, GObject, Pango

from olc.cue import Cue, ChannelTime
from olc.sequence import Sequence
from olc.group import Group
from olc.master import Master
from olc.customwidgets import GroupWidget

class Ascii(object):
    def __init__(self, filename):
        self.file = filename
        if filename != None:
            self.basename = self.file.get_basename()
        else:
            self.basename = ""
        self.modified = False

        self.default_time = Gio.Application.get_default().settings.get_double('default-time')

        self.app = Gio.Application.get_default()

    def load(self):
        self.basename = self.file.get_basename()
        self.default_time = Gio.Application.get_default().settings.get_double('default-time')
        try:
            fstream = self.file.read(None)
            dstream = Gio.DataInputStream.new(fstream)

            flag_seq = False
            in_cue = False
            flag_patch = False
            flag_master = False
            flag_group = False

            type_seq = "Normal"
            txt = False
            t_in = False
            t_out = False
            wait = False
            channels = False
            mem = False
            chan_t = False
            channel_time = {}

            console = ""

            while True:

                line, size = dstream.read_line(None)
                if console == "CONGO":
                    line = line.decode('iso-8859-1').encode('utf8')
                    line = str(line, 'utf8')
                else:
                    line = str(line)[2:-1]
                line = line.replace('\\t', '\t')
                line = line.replace('\\r', '')

                # Marker for end of file
                if "ENDDATA" in line:
                    break

                if line[:7] == "CONSOLE":
                    console = line[8:]

                if line[:9] == "CLEAR ALL":
                    # Clear All
                    del(self.app.chasers[:])
                    del(self.app.groups[:])
                    del(self.app.masters[:])
                    self.app.patch.patch_empty()
                    self.app.sequence = Sequence(1, self.app.patch, text="Main Playback")
                    self.app.sequence.window = self.app.window

                if line[:9] == "$SEQUENCE" or line[:9] == "$Sequence":
                    p = line[10:].split(" ")
                    if int(p[0]) < 2:
                        type_seq = "Normal"
                    else:
                        type_seq = "Chaser"
                        index_seq = int(p[0])
                        self.app.chasers.append(Sequence(index_seq, self.app.patch, type_seq = type_seq))
                    """
                    try:
                        test_type = p[1]
                        print("try:", p[1])
                        if p[1] == "0":
                            type_seq = "Normal"
                        elif p[1] == "1":
                            type_seq = "Chaser"
                            index_seq = int(p[0])
                            self.chasers.append(Sequence(index_seq, self.patch))
                            #print ("Sequence :", index_seq, "Type :", type_seq)
                    except:
                        print("except:", p[0])
                        if p[0] == "0":
                            type_seq = "Normal"
                        else:
                            type_seq = "Chaser"
                            index_seq = int(p[0])
                            self.chasers.append(Sequence(index_seq, self.patch))
                    """
                    #print ("Sequence :", p[0], "Type :", type_seq)
                    i = 1
                    flag_seq = True
                    flag_patch = False
                    flag_master = False
                    flag_group = False

                if flag_seq and type_seq == "Chaser":
                    if line[:4] == 'TEXT':
                        self.app.chasers[-1].text = line[5:]

                    if line[:4] == "$CUE":
                        in_cue = True
                        channels = array.array('B', [0] * 512)
                        i += 1
                        p = line[5:].split(" ")
                        seq = p[0]
                        mem = float(p[1])
                        #print ("CUE in Sequence", seq, "Memory", mem)

                    if in_cue:
                        if line[:4] == 'DOWN':
                            p = line[5:]
                            time = p.split(" ")[0]
                            delay = p.split(" ")[1]
                            if ":" in time:
                                t_out = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_out = float(time)
                            if t_out == 0:
                                t_out = self.default_time
                            if ":" in delay:
                                d_out = float(delay.split(":")[0])*60 + float(delay.split(":")[1])
                            else:
                                d_out = float(delay)
                            # print("Time Out:", t_out)
                            # print("Delay Out:", d_out)
                        if line[:2] == 'UP':
                            p = line[3:]
                            time = p.split(" ")[0]
                            delay = p.split(" ")[1]
                            if ":" in time:
                                t_in = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_in = float(time)
                            if t_in == 0:
                                t_in = default_time
                            if ":" in delay:
                                d_in = float(delay.split(":")[0])*60 + float(delay.split(":")[1])
                            else:
                                d_in = float(delay)
                            # print("Time In:", t_in)
                            # print("Delay In:", d_in)
                        if line[:4] == 'CHAN':
                            #print ("        Chanels :")
                            p = line[5:].split(" ")
                            for q in p:
                                r = q.split("/")
                                if r[0] != "":
                                    channel = int(r[0])
                                    level = int(r[1][1:], 16)
                                    channels[channel-1] = level
                                    #print ("            ", r[0], "@", int(r[1][1:], 16))

                        if line == "":
                            #print("Fin de la Cue")

                            if not wait:
                                wait = 0.0
                            if not txt:
                                txt = ""
                            if not t_out:
                                t_out = 5.0
                            if not t_in:
                                t_in = 5.0
                            cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, delay_out=d_out, delay_in=d_in, wait=wait, text=txt)

                            self.app.chasers[-1].add_cue(cue)

                            in_cue = False
                            t_out = False
                            t_in = False
                            channels = False

                if flag_seq and type_seq == "Normal":
                    if line[:0] == "!":
                        flag_seq = False
                        print(line)
                    if line[:3] == "CUE":
                        in_cue = True
                        channels = array.array('B', [0] * 512)
                        i += 1
                        #print ("        Mémoire :", line[4:])
                        mem = line[4:]
                    if line[:4] == "$CUE":
                        in_cue = True
                        channels = array.array('B', [0] * 512)
                        i += 1
                        #print ("        Mémoire :", line[5:])
                        mem = line[5:]

                    if in_cue:
                        if line[:4] == "TEXT":
                            #print ("        Text :", line[5:])
                            txt = line[5:]
                        if line[:6] == "$$TEXT" and not txt:
                            #print ("        $$Text :", line[7:])
                            txt = line[7:]
                        if (line[:12] == "$$PRESETTEXT" or line[:12] == "$$PresetText") and not txt:
                            #print ("        $$PrestText :", line[13:])
                            txt = line[13:]
                        if line[:4] == 'DOWN':
                            #print ("        Time Out :", line[5:])
                            p = line[5:]
                            time = p.split(" ")[0]
                            delay = p.split(" ")[1]
                            # Si on a un tps avec ":" on est en minutes
                            if ":" in time:
                                t_out = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_out = float(time)
                            if t_out == 0:
                                t_out = self.default_time
                            if ":" in delay:
                                d_out = float(delay.split(":")[0])*60 + float(delay.split(":")[1])
                            else:
                                d_out = float(delay)
                        if line[:2] == 'UP':
                            #print ("        Time In :", line[3:])
                            p = line[3:]
                            time = p.split(" ")[0]
                            delay = p.split(" ")[1]
                            # Si on a un tps avec ":" on est en minutes
                            if ":" in time:
                                t_in = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_in = float(time)
                            if t_in == 0:
                                t_in = self.default_time
                            if ":" in delay:
                                d_in = float(delay.split(":")[0])*60 + float(delay.split(":")[1])
                            else:
                                d_in = float(delay)
                        if line[:6] == '$$WAIT' or line[:6] == '$$Wait':
                            #print ("        Wait :", line[7:])
                            #wait = float(line[7:].split(" ")[0])
                            time = line[7:].split(" ")[0]
                            # Si on a un tps avec ":" on est en minutes
                            if ":" in time:
                                wait = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                wait = float(time)
                        if line[:11] == '$$PARTTIME ':
                            #print("Channel Time")
                            p = line[11:]
                            delay = float(p.split(" ")[0])
                            # Times with ":" are in minutes
                            time_str = p.split(" ")[1]
                            if ':' in time_str:
                                time = float(time_str.split(':')[0])*60 + float(time_str.split(':')[1])
                            else:
                                time = float(time_str)
                            #print("Temps:", time, "Delay:", delay)
                        if line[:14] == '$$PARTTIMECHAN':
                            p = line[15:].split(' ')
                            # We could have several channels
                            for chan in p:
                                if chan.isdigit():
                                    #print("PARTTIMECHAN: Channel N°", chan)
                                    channel_time[int(chan)] = ChannelTime(delay, time)
                        if line[:4] == 'CHAN':
                            #print ("        Chanels :")
                            #p = line[5:-1].split(" ")
                            p = line[5:].split(" ")
                            for q in p:
                                r = q.split("/")
                                #print ("            ", r[0], "@", int(r[1][1:], 16))
                                if r[0] != "":
                                    channel = int(r[0])
                                    # For now, ignore channels greater than 512
                                    if channel < 512:
                                        level = int(r[1][1:], 16)
                                        channels[channel-1] = level
                        #if txt and t_out and t_in and channels:
                        if line == "":
                            #print("Fin Cue", mem)
                            if not wait:
                                wait = 0.0
                            if not txt:
                                txt = ""
                            if not t_out:
                                t_out = 5.0
                            if not t_in:
                                t_in = 5.0
                            cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, delay_in=d_in, delay_out=d_out, wait=wait, text=txt, channel_time=channel_time)

                            # print("StepId :", cue.index, "Memory :", cue.memory)
                            # print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
                            # print("Delay In :", cue.delay_in, "\nDelay Out :", cue.delay_out)
                            # print("Text :", cue.text)
                            # for channel in channel_time.keys():
                            #     print("Channel Time :", channel, channel_time[channel].delay, channel_time[channel].time)
                            # print("")
                            # for channel in range(512):
                            #     print("Channel :", channel+1, "@", cue.channels[channel])

                            self.app.sequence.add_cue(cue)
                            in_cue = False
                            txt = False
                            t_out = False
                            t_in = False
                            wait = False
                            mem = False
                            channels = False
                            chan_t = False
                            channel_time = {}

                if line[:11] == 'CLEAR PATCH':
                    flag_seq = False
                    flag_patch = True
                    flag_master = False
                    flag_group = False
                    #print ("\nPatch :")
                    self.app.patch.patch_empty()    # Empty patch
                    self.app.window.flowbox.invalidate_filter()
                if flag_patch:
                    if line[:0] == "!":
                        flag_patch = False
                if line[:7] == 'PATCH 1':
                    for p in line[8:-1].split(" "):
                        q = p.split("<")
                        if q[0]:
                            r = q[1].split("@")
                            if int(q[0]) <= 512 and int(r[0]) <=512:
                                #print ("Chanel :", q[0], "-> Output :", r[0], "@", r[1])
                                self.app.patch.add_output(int(q[0]), int(r[0]))
                                self.app.window.flowbox.invalidate_filter()
                            else:
                                print("Attention ! PLusieurs univers !!!")

                if line[:6] == '$GROUP':
                    flag_seq = False
                    flag_patch = False
                    flag_master = False
                    flag_group = True
                    #print ("Group :", line[7:])
                    channels = array.array('B', [0] * 512)
                    group_nb = float(line[7:])
                if line[:5] == 'GROUP':
                    flag_seq = False
                    flag_patch = False
                    flag_master = False
                    flag_group = True
                    #print ("Group :", line[6:])
                    channels = array.array('B', [0] * 512)
                    # TODO: Le numéro du groupe peut etre un float
                    group_nb = float(line[6:])
                if flag_group:
                    if line[:1] == "!":
                        flag_group = False
                    if line[:4] == 'TEXT':
                        txt = line[5:]
                    if line[:6] == '$$TEXT':
                        #print ("    Text :", line[5:])
                        txt = line[7:]
                    if line[:4] == 'CHAN':
                        #print ("    Chanels :")
                        p = line[5:].split(" ")
                        for q in p:
                            r = q.split("/")
                            #print ("        ", r[0], "@", int(r[1][1:], 16))
                            if r[0] != "":
                                channel = int(r[0])
                                level = int(r[1][1:], 16)
                                if channel <= 512:
                                    channels[channel-1] = level
                    if line == "":
                        #print("Group", group_nb, txt, "channels", channels)
                        # We don't create a group who already exist
                        master_exist = False
                        for grp in range(len(self.app.groups)):
                            if group_nb == self.app.groups[grp].index:
                                #print("Le groupe", txt, "existe déjà")
                                master_exist = True
                        if not master_exist:
                            self.app.groups.append(Group(group_nb, channels, txt))
                        flag_group = False
                        txt = ""

                if line[:13] == '$MASTPAGEITEM':
                    # TODO: DLight use Type "2" for Groups
                    #print("Master!")
                    item = line[14:].split(" ")
                    #print("Page :", p[0], "Master :", p[1], "Type :", p[2], "Contient :", p[3])
                    if item[2] == "2":
                        flag_seq = False
                        flag_patch = False
                        flag_group = False
                        flag_master = True
                        channels = array.array('B', [0] * 512)
                    else:
                        self.app.masters.append(Master(item[0], item[1], item[2], item[3], self.app.groups, self.app.chasers))
                if flag_master:
                    if line[:1] == "!":
                        flag_master = False
                    if line[:4] == 'CHAN':
                        p = line[5:].split(" ")
                        for q in p:
                            r = q.split("/")
                            if r[0] != "":
                                channel = int(r[0])
                                level = int(r[1][1:], 16)
                                if channel <= 512:
                                    channels[channel-1] = level
                    if line == "":
                        self.app.masters.append(Master(item[0], item[1], item[2], item[3], self.app.groups, self.app.chasers, channels=channels))
                        flag_master = False


            fstream.close()


            # Set main window's title with the file name
            self.app.window.header.set_title(self.basename)
            # Set main window's subtitle
            subtitle = "Mem. : 0 - Next Mem. : "+self.app.sequence.cues[1].memory+" "+self.app.sequence.cues[1].text
            self.app.window.header.set_subtitle(subtitle)

            # Add an empty cue at the end
            cue = Cue(self.app.sequence.last+1, "0", text="End")
            self.app.sequence.add_cue(cue)

            # Redraw crossfade :
            # On se place au début de la séquence
            self.app.sequence.position = 0
            # On récupère les temps de la mémoire suivante
            t_in = self.app.sequence.cues[1].time_in
            t_out = self.app.sequence.cues[1].time_out
            t_wait = self.app.sequence.cues[1].wait
            t_total = self.app.sequence.cues[1].total_time
            self.app.window.sequential.time_in = t_in
            self.app.window.sequential.time_out = t_out
            self.app.window.sequential.wait = t_wait
            self.app.window.sequential.total_time = t_total

            # On met à jour la liste des mémoires
            self.app.window.cues_liststore1.clear()
            self.app.window.cues_liststore2.clear()
            # 2 lignes vides au début
            #for i in range(2):
            #    self.app.win_seq.cues_liststore.append(["", "", "", "", "", "", ""])
            for i in range(self.app.sequence.last):
                # Si on a des entiers, on les affiche comme tels
                if self.app.sequence.cues[i].wait.is_integer():
                    wait = str(int(self.app.sequence.cues[i].wait))
                    if wait == "0":
                        wait = ""
                else:
                    wait = str(self.app.sequence.cues[i].wait)
                if self.app.sequence.cues[i].time_out.is_integer():
                    t_out = int(self.app.sequence.cues[i].time_out)
                else:
                    t_out = self.app.sequence.cues[i].time_out
                if self.app.sequence.cues[i].delay_out.is_integer():
                    d_out = str(int(self.app.sequence.cues[i].delay_out))
                else:
                    d_out = str(self.app.sequence.cues[i].delay_out)
                if d_out == "0":
                    d_out = ""
                if self.app.sequence.cues[i].time_in.is_integer():
                    t_in = int(self.app.sequence.cues[i].time_in)
                else:
                    t_in = self.app.sequence.cues[i].time_in
                if self.app.sequence.cues[i].delay_in.is_integer():
                    d_in = str(int(self.app.sequence.cues[i].delay_in))
                else:
                    d_in = str(self.app.sequence.cues[i].delay_in)
                if d_in == "0":
                    d_in = ""
                channel_time = str(len(self.app.sequence.cues[i].channel_time))
                if channel_time == "0":
                    channel_time = ""
                if i == 0:
                    bg = "#997004"
                else:
                    bg = "#232729"
                # Next Cue in Bold
                if i == 1:
                    weight = Pango.Weight.ULTRAHEAVY
                else:
                    weight = Pango.Weight.NORMAL
                self.app.window.cues_liststore1.append([str(i), str(self.app.sequence.cues[i].memory),
                    str(self.app.sequence.cues[i].text), wait, d_out, str(t_out), d_in, str(t_in), channel_time, bg, weight])
                self.app.window.cues_liststore2.append([str(i), str(self.app.sequence.cues[i].memory),
                    str(self.app.sequence.cues[i].text), wait, d_out, str(t_out), d_in, str(t_in), channel_time])

            self.app.window.step_filter1 = self.app.window.cues_liststore1.filter_new()
            self.app.window.step_filter1.set_visible_func(self.app.window.step_filter_func1)

            self.app.window.step_filter2 = self.app.window.cues_liststore2.filter_new()
            self.app.window.step_filter2.set_visible_func(self.app.window.step_filter_func2)

            self.app.window.treeview1.set_model(self.app.window.step_filter1)
            self.app.window.treeview2.set_model(self.app.window.step_filter2)

            self.app.window.step_filter1.refilter()
            self.app.window.step_filter2.refilter()

            path = Gtk.TreePath.new_from_indices([0])
            self.app.window.treeview1.set_cursor(path, None, False)
            self.app.window.treeview2.set_cursor(path, None, False)

            self.app.window.seq_grid.queue_draw()

            # Redraw Group Tab if exist
            if self.app.group_tab != None:
                # Remove Old Groups
                del(self.app.group_tab.grps[:])
                self.app.group_tab.scrolled2.remove(self.app.group_tab.flowbox2)
                self.app.group_tab.flowbox2.destroy()
                # New FlowBox
                self.app.group_tab.flowbox2 = Gtk.FlowBox()
                self.app.group_tab.flowbox2.set_valign(Gtk.Align.START)
                self.app.group_tab.flowbox2.set_max_children_per_line(20)
                self.app.group_tab.flowbox2.set_homogeneous(True)
                self.app.group_tab.flowbox2.set_activate_on_single_click(True)
                self.app.group_tab.flowbox2.set_selection_mode(Gtk.SelectionMode.NONE)
                self.app.group_tab.flowbox2.set_filter_func(self.app.group_tab.filter_groups, None)
                self.app.group_tab.scrolled2.add(self.app.group_tab.flowbox2)
                # Add Groups to FlowBox
                for i in range(len(self.app.groups)):
                    self.app.group_tab.grps.append(GroupWidget(self.app.window, self.app.groups[i].index,
                        self.app.groups[i].text, self.app.group_tab.grps))
                    self.app.group_tab.flowbox2.add(self.app.group_tab.grps[i])
                self.app.group_tab.flowbox1.invalidate_filter()
                self.app.group_tab.flowbox2.invalidate_filter()
                self.app.window.show_all()

            # Redraw Masters Tab if exist
            if self.app.master_tab != None:
                del(self.app.master_tab.scale[:])
                del(self.app.master_tab.ad[:])
                del(self.app.master_tab.flash[:])
                for i in range(len(self.app.masters)):
                    if Gio.Application.get_default().settings.get_boolean('percent'):
                        self.app.master_tab.ad.append(Gtk.Adjustment(0, 0, 100, 1, 10, 0))
                    else:
                        self.app.master_tab.ad.append(Gtk.Adjustment(0, 0, 255, 1, 10, 0))
                    self.app.master_tab.scale.append(Gtk.Scale(orientation=Gtk.Orientation.VERTICAL,
                        adjustment=self.app.master_tab.ad[i]))
                    self.app.master_tab.scale[i].set_digits(0)
                    self.app.master_tab.scale[i].set_vexpand(True)
                    self.app.master_tab.scale[i].set_value_pos(Gtk.PositionType.BOTTOM)
                    self.app.master_tab.scale[i].set_inverted(True)
                    self.app.master_tab.scale[i].connect("value-changed", self.app.master_tab.scale_moved)
                    # Button to flash Master
                    self.app.master_tab.flash.append(Gtk.Button.new_with_label(self.app.masters[i].text))
                    self.app.master_tab.flash[i].connect("button-press-event", self.app.master_tab.flash_on)
                    self.app.master_tab.flash[i].connect("button-release-event", self.app.master_tab.flash_off)
                    # Place Masters in Window
                    if i == 0:
                        self.app.master_tab.attach(self.app.master_tab.scale[i], 0, 0, 1, 1)
                        self.app.master_tab.attach_next_to(self.app.master_tab.flash[i],
                                self.app.master_tab.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
                    elif not i % 4:
                        self.app.master_tab.attach_next_to(self.app.master_tab.scale[i],
                                self.app.master_tab.flash[i-4], Gtk.PositionType.BOTTOM, 1, 1)
                        self.app.master_tab.attach_next_to(self.app.master_tab.flash[i],
                                self.app.master_tab.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
                    else:
                        self.app.master_tab.attach_next_to(self.app.master_tab.scale[i],
                                self.app.master_tab.scale[i-1], Gtk.PositionType.RIGHT, 1, 1)
                        self.app.master_tab.attach_next_to(self.app.master_tab.flash[i],
                                self.app.master_tab.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
                self.app.window.show_all()

            # Redraw Sequences Tab if exist
            if self.app.sequences_tab != None:
                self.app.sequences_tab.liststore1.clear()

                self.app.sequences_tab.liststore1.append([self.app.sequence.index, self.app.sequence.type_seq,
                    self.app.sequence.text])

                for chaser in range(len(self.app.chasers)):
                    self.app.sequences_tab.liststore1.append([self.app.chasers[chaser].index,
                        self.app.chasers[chaser].type_seq, self.app.chasers[chaser].text])

                self.app.sequences_tab.treeview1.set_model(self.app.sequences_tab.liststore1)
                path = Gtk.TreePath.new()
                self.app.window.treeview1.set_cursor(path, None, False)

            # Redraw Patch Tab if exist
            if self.app.patch_tab != None:
                self.app.patch_tab.flowbox.queue_draw()

        except GObject.GError as e:
            print("Error: " + e.message)

        self.modified = False

    def save(self):
        """ Save ASCII File """

        stream = self.file.replace('', False, Gio.FileCreateFlags.NONE, None)

        # TODO: to import Fx and Masters in dlight :
        # MANUFACTURER NICOBATS or AVAB
        # CONSOLE      DLIGHT   or CONGO
        # TODO: Masters dans Dlight sont en Time et pas Flash
        stream.write(bytes('IDENT 3:0\n', 'utf8'))
        stream.write(bytes('MANUFACTURER MIKA\n', 'utf8'))
        stream.write(bytes('CONSOLE OLC\n\n', 'utf8'))
        stream.write(bytes('CLEAR ALL\n\n', 'utf8'))

        # Main Sequence
        stream.write(bytes('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n', 'utf8'))
        stream.write(bytes('! Main sequence\n\n', 'utf8'))
        stream.write(bytes('$SEQUENCE 1 0\n\n', 'utf8'))
        for cue in range(len(self.app.sequence.cues)):
            if self.app.sequence.cues[cue].memory != '0':
                stream.write(bytes('CUE ' + self.app.sequence.cues[cue].memory + '\n', 'utf8'))
                stream.write(bytes('DOWN ' + str(self.app.sequence.cues[cue].time_out) + '\n', 'utf8'))
                stream.write(bytes('UP ' + str(self.app.sequence.cues[cue].time_in) + '\n', 'utf8'))
                stream.write(bytes('$$WAIT ' + str(self.app.sequence.cues[cue].wait) + '\n', 'utf8'))
                #  Chanel Time if any
                for chan in self.app.sequence.cues[cue].channel_time.keys():
                    stream.write(bytes('$$PARTTIME ' + str(self.app.sequence.cues[cue].channel_time[chan].delay) +
                        ' ' + str(self.app.sequence.cues[cue].channel_time[chan].time) + '\n', 'utf8'))
                    stream.write(bytes('$$PARTTIMECHAN ' + str(chan) + '\n', 'utf8'))
                stream.write(bytes('TEXT ' + ascii(self.app.sequence.cues[cue].text)[1:-1] +
                    '\n', 'utf8').decode('utf8').encode('ascii'))
                stream.write(bytes('$$TEXT ' + self.app.sequence.cues[cue].text + '\n', 'utf8'))
                channels = ""
                i = 1
                for chan in range(len(self.app.sequence.cues[cue].channels)):
                    level = self.app.sequence.cues[cue].channels[chan]
                    if level != 0:
                        level = 'H' + format(level, '02X')
                        channels += " " + str(chan+1) + "/" + level
                        # 6 Channels per line
                        if not i % 6 and channels != "":
                            stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                            channels = ""
                        i += 1
                if channels != "":
                    stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                stream.write(bytes('\n', 'utf8'))

        # Chasers
        stream.write(bytes('! Additional Sequences\n\n', 'utf8'))

        for chaser in range(len(self.app.chasers)):
            stream.write(bytes('$SEQUENCE ' + str(self.app.chasers[chaser].index) + '\n', 'utf8'))
            stream.write(bytes('TEXT ' + self.app.chasers[chaser].text + '\n\n', 'utf8'))
            for cue in range(len(self.app.chasers[chaser].cues)):
                if self.app.chasers[chaser].cues[cue].memory != '0':
                    stream.write(bytes('$CUE ' + str(self.app.chasers[chaser].index) + ' ' + self.app.chasers[chaser].cues[cue].memory + '\n', 'utf8'))
                    stream.write(bytes('DOWN ' + str(self.app.chasers[chaser].cues[cue].time_out) + '\n', 'utf8'))
                    stream.write(bytes('UP ' + str(self.app.chasers[chaser].cues[cue].time_in) + '\n', 'utf8'))
                    stream.write(bytes('$$WAIT ' + str(self.app.chasers[chaser].cues[cue].wait) + '\n', 'utf8'))
                    channels = ""
                    i = 1
                    for chan in range(len(self.app.chasers[chaser].cues[cue].channels)):
                        level = self.app.chasers[chaser].cues[cue].channels[chan]
                        if level != 0:
                            level = 'H' + format(level, '02X')
                            channels += " " + str(chan+1) + "/" + level
                            # 6 channels per line
                            if not i % 6 and channels != "":
                                stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                                channels = ""
                            i += 1
                    if channels != "":
                        stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                    stream.write(bytes('\n', 'utf8'))

        # Groups
        stream.write(bytes('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n', 'utf8'))
        stream.write(bytes('! Groups (presets not in sequence)\n', 'utf8'))
        stream.write(bytes('! GROUP  Standard ASCII Light Cues\n', 'utf8'))
        stream.write(bytes('! CHAN   Standard ASCII Light Cues\n', 'utf8'))
        stream.write(bytes('! TEXT   Standard ASCII Light Cues\n', 'utf8'))
        stream.write(bytes('! $$TEXT  Unicode encoded version of the same text\n', 'utf8'))

        for group in range(len(self.app.groups)):
            stream.write(bytes('GROUP ' + str(self.app.groups[group].index) + '\n', 'utf8'))
            stream.write(bytes('TEXT ' + ascii(self.app.groups[group].text)[1:-1] +
                '\n', 'utf8').decode('utf8').encode('ascii'))
            stream.write(bytes('$$TEXT ' + self.app.groups[group].text + '\n', 'utf8'))
            channels = ""
            i = 1
            for chan in range(len(self.app.groups[group].channels)):
                level = self.app.groups[group].channels[chan]
                if level != 0:
                    level = 'H' + format(level, '02X')
                    channels += " " + str(chan+1) + "/" + level
                    # 6 channels per line
                    if not i % 6 and channels != "":
                        stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                        channels = ""
                    i += 1
            if channels != "":
                stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
            stream.write(bytes('\n', 'utf8'))

        # Congo Groups
        stream.write(bytes('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n', 'utf8'))
        stream.write(bytes('! Congo Groups\n', 'utf8'))
        stream.write(bytes('! $GROUP  Group number\n', 'utf8'))
        stream.write(bytes('! CHAN    Standard ASCII Light Cues\n', 'utf8'))
        stream.write(bytes('! TEXT    Standard ASCII Light Cues\n', 'utf8'))
        stream.write(bytes('! $$TEXT  Unicode encoded version of the same text\n', 'utf8'))
        stream.write(bytes('CLEAR $GROUP\n\n', 'utf8'))

        for group in range(len(self.app.groups)):
            stream.write(bytes('$GROUP ' + str(self.app.groups[group].index) + '\n', 'utf8'))
            stream.write(bytes('TEXT ' + ascii(self.app.groups[group].text)[1:-1] +
                '\n', 'utf8').decode('utf8').encode('ascii'))
            stream.write(bytes('$$TEXT ' + self.app.groups[group].text + '\n', 'utf8'))
            channels = ""
            i = 1
            for chan in range(len(self.app.groups[group].channels)):
                level = self.app.groups[group].channels[chan]
                if level != 0:
                    level = 'H' + format(level, '02X')
                    channels += " " + str(chan+1) + "/" + level
                    # 6 channels per line
                    if not i % 6 and channels != "":
                        stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                        channels = ""
                    i += 1
            if channels != "":
                stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
            stream.write(bytes('\n', 'utf8'))

        # Masters
        stream.write(bytes('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n', 'utf8'))
        stream.write(bytes('! Master Pages\n', 'utf8'))
        stream.write(bytes('! $MASTPAGE     Master page number\n', 'utf8'))
        stream.write(bytes('! TEXT          Master page text\n', 'utf8'))
        stream.write(bytes('! $TEXT         Unicode encoded version of the same text\n', 'utf8'))
        stream.write(bytes('! $MASTPAGEITEM Page number, Master number,\n', 'utf8'))
        stream.write(bytes('!               Content type (2 = Channels, 3 = Chaser,\n', 'utf8'))
        stream.write(bytes('!               13 = Group), Content value (Chaser#, Group#),\n', 'utf8'))
        stream.write(bytes('!               Time In, Wait time, Time Out,\n', 'utf8'))
        stream.write(bytes('!               Flash level (0-255)\n', 'utf8'))
        stream.write(bytes('CLEAR $MASTPAGE\n\n', 'utf8'))
        stream.write(bytes('$MASTPAGE 1 0 0 0\n', 'utf8'))
        page = 1
        for master in range(len(self.app.masters)):
            if self.app.masters[master].page != page:
                page = self.app.masters[master].page
                stream.write(bytes('\n$MASTPAGE ' + str(page) + ' 0 0 0\n', 'utf8'))
            # MASTPAGEITEM : page, sub, type, content, timeIn, autotime, timeOut, target,,,,,,
            stream.write(bytes('$MASTPAGEITEM ' + self.app.masters[master].page +
                ' ' + self.app.masters[master].number +
                ' ' + str(self.app.masters[master].content_type) +
                ' ' + str(self.app.masters[master].content_value) +
                ' 5 0 5 255\n', 'utf8'))
            # Master of Channels, save them
            if self.app.masters[master].content_type == 2:
                channels = ""
                i = 1
                for chan in range(len(self.app.masters[master].channels)):
                    level = self.app.masters[master].channels[chan]
                    if level != 0:
                        level = 'H' + format(level, '02X')
                        channels += " " + str(chan+1) + "/" + level
                        # 6 channels per line
                        if not i % 6 and channels != "":
                            stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
                            channels = ""
                        i += 1
                if channels != "":
                    stream.write(bytes('CHAN' + channels + '\n', 'utf8'))
        stream.write(bytes('\n', 'utf8'))

        # Patch
        stream.write(bytes('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n', 'utf8'))
        stream.write(bytes('! Patch\n', 'utf8' ))
        stream.write(bytes('CLEAR PATCH\n\n', 'utf8'))
        # TODO: More than 1 Univers
        # TODO: Prise en charge du niveau de l'output
        patch = ""
        i = 1
        for output in range(len(self.app.patch.outputs)):
            if self.app.patch.outputs[output] != 0:
                patch += " " + str(self.app.patch.outputs[output]) + "<" + str(output+1) + "@100"
                if not i % 4 and patch != "":
                    stream.write(bytes('PATCH 1' + patch + '\n', 'utf8'))
                    patch = ""
                i += 1
        if patch != "":
            stream.write(bytes('PATCH 1' + patch + '\n', 'utf8'))

        stream.write(bytes('\nENDDATA\n', 'utf8'))

        stream.close()

        self.modified = False
        self.app.window.header.set_title(self.basename)

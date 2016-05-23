import array
from gi.repository import Gio, Gtk, GObject

from olc.cue import Cue
from olc.sequence import Sequence
from olc.group import Group
from olc.master import Master
from olc.customwidgets import GroupWidget

class Ascii(object):
    def __init__(self, filename):
        self.file = filename
        self.basename = self.file.get_basename()
        self.modify = False

        self.app = Gio.Application.get_default()

    def load(self):
        try:
            fstream = self.file.read(None)
            dstream = Gio.DataInputStream.new(fstream)

            flag_seq = False
            in_cue = False
            flag_patch = False
            flag_group = False

            type_seq = "Normal"
            txt = False
            t_in = False
            t_out = False
            wait = False
            channels = False
            mem = False

            while True:

                line, size = dstream.read_line(None)
                line = str(line)[2:-1]
                line = line.replace('\\t', '\t')
                line = line.replace('\\r', '')

                # Marker for end of file
                if "ENDDATA" in line:
                    break

                if line[:9] == "CLEAR ALL":
                    # Clear All
                    del(self.app.chasers[:])
                    del(self.app.groups[:])
                    del(self.app.masters[:])
                    self.app.patch.patch_empty()
                    self.app.sequence = Sequence(1, self.app.patch)
                    self.app.sequence.window = self.app.win_seq

                if line[:9] == "$SEQUENCE" or line[:9] == "$Sequence":
                    p = line[10:].split(" ")
                    if int(p[0]) < 2:
                        type_seq = "Normal"
                    else:
                        type_seq = "Chaser"
                        index_seq = int(p[0])
                        self.app.chasers.append(Sequence(index_seq, self.app.patch))
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
                        mem = p[1]
                        #print ("CUE in Sequence", seq, "Memory", mem)

                    if in_cue:
                        if line[:4] == 'DOWN':
                            p = line[5:]
                            time = p.split(" ")[0]
                            if ":" in time:
                                t_out = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_out = float(time)
                            if t_out == 0:
                                t_out = 0.1
                            #print("Time Out:", t_out)
                        if line[:2] == 'UP':
                            p = line[3:]
                            time = p.split(" ")[0]
                            if ":" in time:
                                t_in = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_in = float(time)
                            if t_in == 0:
                                t_in = 0.1
                            #print("Time In:", t_in)
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
                            cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, wait=wait, text=txt)

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
                            # Si on a un tps avec ":" on est en minutes
                            if ":" in time:
                                t_out = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_out = float(time)
                            if t_out == 0:
                                t_out = 0.1
                        if line[:2] == 'UP':
                            #print ("        Time In :", line[3:])
                            p = line[3:]
                            time = p.split(" ")[0]
                            # Si on a un tps avec ":" on est en minutes
                            if ":" in time:
                                t_in = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                t_in = float(time)
                            if t_in == 0:
                                t_in = 0.1
                        if line[:6] == '$$WAIT' or line[:6] == '$$Wait':
                            #print ("        Wait :", line[7:])
                            #wait = float(line[7:].split(" ")[0])
                            time = line[7:].split(" ")[0]
                            # Si on a un tps avec ":" on est en minutes
                            if ":" in time:
                                wait = float(time.split(":")[0])*60 + float(time.split(":")[1])
                            else:
                                wait = float(time)
                        if line[:4] == 'CHAN':
                            #print ("        Chanels :")
                            #p = line[5:-1].split(" ")
                            p = line[5:].split(" ")
                            for q in p:
                                r = q.split("/")
                                #print ("            ", r[0], "@", int(r[1][1:], 16))
                                if r[0] != "":
                                    channel = int(r[0])
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
                            cue = Cue(i, mem, channels, time_in=t_in, time_out=t_out, wait=wait, text=txt)

                            #print("StepId :", cue.index, "Memory :", cue.memory)
                            #print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
                            #print("Text :", cue.text)
                            #print("")
                            #for channel in range(512):
                            #    print("Channel :", channel+1, "@", cue.channels[channel])

                            self.app.sequence.add_cue(cue)
                            in_cue = False
                            txt = False
                            t_out = False
                            t_in = False
                            wait = False
                            mem = False
                            channels = False

                if line[:11] == 'CLEAR PATCH':
                    flag_seq = False
                    flag_patch = True
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
                    flag_group = True
                    #print ("Group :", line[7:])
                    channels = array.array('B', [0] * 512)
                    group_nb = int(line[7:])
                if line[:5] == 'GROUP':
                    flag_seq = False
                    flag_patch = False
                    flag_group = True
                    #print ("Group :", line[6:])
                    channels = array.array('B', [0] * 512)
                    group_nb = int(line[6:])
                if flag_group:
                    if line[:1] == "!":
                        flag_group = False
                    if line[:4] == 'TEXT':
                        #print ("    Text :", line[5:])
                        txt = line[5:]
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
                        self.app.groups.append(Group(group_nb, channels, txt))
                        flag_group = False
                        txt = ""

                if line[:13] == '$MASTPAGEITEM':
                    #print("Master!")
                    p = line[14:].split(" ")
                    #print("Page :", p[0], "Master :", p[1], "Type :", p[2], "Contient :", p[3])
                    self.app.masters.append(Master(p[0], p[1], p[2], p[3], self.app.groups, self.app.chasers))

            fstream.close()


            # Set main window's title with the file name
            self.app.window.header.set_title(self.basename)
            # Set main window's subtitle
            subtitle = "Mem. : 0 - Next Mem. : "+self.app.sequence.cues[1].memory+" "+self.app.sequence.cues[1].text
            self.app.window.header.set_subtitle(subtitle)

            # Add an empty cue at the end
            cue = Cue(self.app.sequence.last+1, "0", text="Last Cue")
            self.app.sequence.add_cue(cue)

            # Redraw crossfade :
            # On se place au début de la séquence
            self.app.sequence.position = 0
            # On récupère les temps de la mémoire suivante
            t_in = self.app.sequence.cues[1].time_in
            t_out = self.app.sequence.cues[1].time_out
            t_wait = self.app.sequence.cues[1].wait
            self.app.win_seq.sequential.time_in = t_in
            self.app.win_seq.sequential.time_out = t_out
            self.app.win_seq.sequential.wait = t_wait

            # On met à jour la liste des mémoires
            self.app.win_seq.cues_liststore = Gtk.ListStore(str, str, str, str, str, str, str)
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
                if self.app.sequence.cues[i].time_in.is_integer():
                    t_in = int(self.app.sequence.cues[i].time_in)
                else:
                    t_in = self.app.sequence.cues[i].time_in
                self.app.win_seq.cues_liststore.append([str(i), str(self.app.sequence.cues[i].memory),
                        str(self.app.sequence.cues[i].text), wait,
                        str(t_out), str(t_in),
                        ""])
            self.app.win_seq.step_filter = self.app.win_seq.cues_liststore.filter_new()
            self.app.win_seq.step_filter.set_visible_func(self.app.win_seq.step_filter_func)

            self.app.win_seq.treeview.set_model(self.app.win_seq.cues_liststore)
            #self.app.win_seq.treeview.set_model(self.app.win_seq.step_filter)
            #self.app.win_seq.step_filter.refilter()

            path = Gtk.TreePath.new_from_indices([0])
            self.app.win_seq.treeview.set_cursor(path, None, False)

            self.app.win_seq.grid.queue_draw()

            # Redraw Groups Window
            del(self.app.win_groups.grps[:])
            for i in range(len(self.app.groups)):
                #print(self.app.groups[i].index, self.app.groups[i].text, self.app.groups[i].channels)
                self.app.win_groups.grps.append(GroupWidget(self.app.win_groups, self.app.groups[i].index,
                    self.app.groups[i].text, self.app.win_groups.grps))
                self.app.win_groups.flowbox2.add(self.app.win_groups.grps[i])
            self.app.win_groups.flowbox1.invalidate_filter()
            # TODO: pas bon, ouvre la fenetre si fermée
            self.app.win_groups.show_all()

            # Redraw Masters Window if exist
            try:
                del(self.app.win_masters.scale[:])
                del(self.app.win_masters.ad[:])
                del(self.app.win_masters.flash[:])
                for i in range(len(self.app.masters)):
                    if Gio.Application.get_default().settings.get_boolean('percent'):
                        self.app.win_masters.ad.append(Gtk.Adjustment(0, 0, 100, 1, 10, 0))
                    else:
                        self.app.win_masters.ad.append(Gtk.Adjustment(0, 0, 255, 1, 10, 0))
                    self.app.win_masters.scale.append(Gtk.Scale(orientation=Gtk.Orientation.VERTICAL,
                        adjustment=self.app.win_masters.ad[i]))
                    self.app.win_masters.scale[i].set_digits(0)
                    self.app.win_masters.scale[i].set_vexpand(True)
                    self.app.win_masters.scale[i].set_value_pos(Gtk.PositionType.BOTTOM)
                    self.app.win_masters.scale[i].set_inverted(True)
                    self.app.win_masters.scale[i].connect("value-changed", self.app.win_masters.scale_moved)
                    # Button to flash Master
                    self.app.win_masters.flash.append(Gtk.Button.new_with_label(self.app.masters[i].text))
                    self.app.win_masters.flash[i].connect("button-press-event", self.app.win_masters.flash_on)
                    self.app.win_masters.flash[i].connect("button-release-event", self.app.win_masters.flash_off)
                    # Place Masters in Window
                    if i == 0:
                        self.app.win_masters.grid.attach(self.app.win_masters.scale[i], 0, 0, 1, 1)
                        self.app.win_masters.grid.attach_next_to(self.app.win_masters.flash[i],
                                self.app.win_masters.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
                    elif not i % 10:
                        self.app.win_masters.grid.attach_next_to(self.app.win_masters.scale[i],
                                self.app.win_masters.flash[i-10], Gtk.PositionType.BOTTOM, 1, 1)
                        self.app.win_masters.grid.attach_next_to(self.app.win_masters.flash[i],
                                self.app.win_masters.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
                    else:
                        self.app.win_masters.grid.attach_next_to(self.app.win_masters.scale[i],
                                self.app.win_masters.scale[i-1], Gtk.PositionType.RIGHT, 1, 1)
                        self.app.win_masters.grid.attach_next_to(self.app.win_masters.flash[i],
                                self.app.win_masters.scale[i], Gtk.PositionType.BOTTOM, 1, 1)
                self.app.win_masters.show_all()
            except:
                pass

            # TODO: Redraw Patch Window if exist

        except GObject.GError as e:
            print("Error: " + e.message)

        self.modify = False

    def save(self):
        print("Save ASCII")
        self.modify = False
        self.app.window.header.set_title(self.basename)

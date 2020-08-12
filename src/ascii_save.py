"""ASCII file: Save functions"""

from olc.define import NB_UNIVERSES, App


def save_main_playback(stream):
    """Save Main Sequence"""
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
                    "CUE " + str(App().sequence.steps[step].cue.memory) + "\n", "utf8",
                )
            )
            stream.write(bytes("DOWN " + time_out + " " + delay_out + "\n", "utf8",))
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
                    time = str(int(App().sequence.steps[step].channel_time[chan].time))
                else:
                    time = str(App().sequence.steps[step].channel_time[chan].time)
                stream.write(bytes("$$PARTTIME " + delay + " " + time + "\n", "utf8",))
                stream.write(bytes("$$PARTTIMECHAN " + str(chan) + "\n", "utf8"))
            stream.write(
                bytes("TEXT " + App().sequence.steps[step].text + "\n", "iso-8859-1")
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


def save_chasers(stream):
    """Save Chasers"""
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
                    delay_out = str(int(App().chasers[chaser].steps[step].delay_out))
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
                stream.write(bytes("UP " + time_in + " " + delay_in + "\n", "utf8",))
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


def save_groups(stream):
    """Save Groups"""
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
    stream.write(bytes("! $$TEXT  Unicode encoded version of the same text\n", "utf8"))

    for group, _ in enumerate(App().groups):
        stream.write(bytes("GROUP " + str(App().groups[group].index) + "\n", "utf8"))
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


def save_congo_groups(stream):
    """Save Congo Groups"""
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
    stream.write(bytes("! $$TEXT  Unicode encoded version of the same text\n", "utf8"))
    stream.write(bytes("CLEAR $GROUP\n\n", "utf8"))

    for group, _ in enumerate(App().groups):
        stream.write(bytes("$GROUP " + str(App().groups[group].index) + "\n", "utf8"))
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


def save_masters(stream):
    """Save Masters"""
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
            "!               13 = Group), Content value (Chaser#, Group#),\n", "utf8",
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


def save_patch(stream):
    """Save Patch"""
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

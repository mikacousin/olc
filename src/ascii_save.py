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
    for step in App().sequence.steps:
        if int(step.cue.memory) != 0:
            # Save integers as integers
            time_out = (
                str(int(step.time_out))
                if step.time_out.is_integer()
                else str(step.time_out)
            )
            delay_out = (
                str(int(step.delay_out))
                if step.delay_out.is_integer()
                else str(step.delay_out)
            )
            time_in = (
                str(int(step.time_in))
                if step.time_in.is_integer()
                else str(step.time_in)
            )
            delay_in = (
                str(int(step.delay_in))
                if step.delay_in.is_integer()
                else str(step.delay_in)
            )
            wait = str(int(step.wait)) if step.wait.is_integer() else str(step.wait)
            stream.write(bytes("CUE " + str(step.cue.memory) + "\n", "utf8",))
            stream.write(bytes("DOWN " + time_out + " " + delay_out + "\n", "utf8",))
            stream.write(bytes("UP " + time_in + " " + delay_in + "\n", "utf8",))
            stream.write(bytes("$$WAIT " + wait + "\n", "utf8",))
            #  Chanel Time if any
            for chan in step.channel_time.keys():
                delay = (
                    str(int(step.channel_time[chan].delay))
                    if step.channel_time[chan].delay.is_integer()
                    else str(step.channel_time[chan].delay)
                )
                time = (
                    str(int(step.channel_time[chan].time))
                    if step.channel_time[chan].time.is_integer()
                    else str(step.channel_time[chan].time)
                )
                stream.write(bytes("$$PARTTIME " + delay + " " + time + "\n", "utf8",))
                stream.write(bytes("$$PARTTIMECHAN " + str(chan) + "\n", "utf8"))
            stream.write(bytes("TEXT " + step.text + "\n", "iso-8859-1"))
            stream.write(bytes("$$TEXT " + ascii(step.text)[1:-1] + "\n", "ascii",))
            _save_channels(stream, step.cue.channels)
            stream.write(bytes("\n", "utf8"))


def save_chasers(stream):
    """Save Chasers"""
    stream.write(bytes("! Additional Sequences\n\n", "utf8"))

    for chaser in App().chasers:
        stream.write(bytes("$SEQUENCE " + str(chaser.index) + "\n", "utf8"))
        stream.write(bytes("TEXT " + chaser.text + "\n\n", "utf8"))
        for step in chaser.steps:
            if int(step.cue.memory) != 0:
                # Save integers as integers
                time_out = (
                    str(int(step.time_out))
                    if step.time_out.is_integer()
                    else str(step.time_out)
                )
                delay_out = (
                    str(int(step.delay_out))
                    if step.delay_out.is_integer()
                    else str(step.delay_out)
                )
                time_in = (
                    str(int(step.time_in))
                    if step.time_in.is_integer()
                    else str(step.time_in)
                )
                delay_in = (
                    str(int(step.delay_in))
                    if step.delay_in.is_integer()
                    else str(step.delay_in)
                )
                wait = str(int(step.wait)) if step.wait.is_integer() else str(step.wait)
                stream.write(
                    bytes(
                        "$CUE " + str(chaser.index) + " " + str(step.cue.memory) + "\n",
                        "utf8",
                    )
                )
                stream.write(
                    bytes("DOWN " + time_out + " " + delay_out + "\n", "utf8",)
                )
                stream.write(bytes("UP " + time_in + " " + delay_in + "\n", "utf8",))
                stream.write(bytes("$$WAIT " + wait + "\n", "utf8",))
                _save_channels(stream, step.cue.channels)
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

    for group in App().groups:
        stream.write(bytes("GROUP " + str(group.index) + "\n", "utf8"))
        stream.write(
            bytes("TEXT " + ascii(group.text)[1:-1] + "\n", "utf8")
            .decode("utf8")
            .encode("ascii")
        )
        stream.write(bytes("$$TEXT " + group.text + "\n", "utf8"))
        _save_channels(stream, group.channels)
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

    for group in App().groups:
        stream.write(bytes("$GROUP " + str(group.index) + "\n", "utf8"))
        stream.write(
            bytes("TEXT " + ascii(group.text)[1:-1] + "\n", "utf8")
            .decode("utf8")
            .encode("ascii")
        )
        stream.write(bytes("$$TEXT " + group.text + "\n", "utf8"))
        _save_channels(stream, group.channels)
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
    for master in App().masters:
        if master.page != page:
            page = master.page
            stream.write(bytes("\n$MASTPAGE " + str(page) + " 0 0 0\n", "utf8"))
        # MASTPAGEITEM :
        # page, sub, type, content, timeIn, autotime, timeOut, target,,,,,,
        stream.write(
            bytes(
                "$MASTPAGEITEM "
                + str(master.page)
                + " "
                + str(master.number)
                + " "
                + str(master.content_type)
                + " "
                + str(master.content_value)
                + " 5 0 5 255\n",
                "utf8",
            )
        )
        # Master of Channels, save them
        if master.content_type == 2:
            _save_channels(stream, master.channels)

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


def _save_channels(stream, channels_array):
    """Save channels"""
    channels = ""
    i = 1
    for chan, level in enumerate(channels_array):
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

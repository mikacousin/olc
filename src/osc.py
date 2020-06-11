import sys
import liblo
from gi.repository import Gio


class OscClient:
    def __init__(self):
        # Port to send data to the client
        self.port = Gio.Application.get_default().settings.get_int("osc-client-port")
        # client's IP address
        self.host = Gio.Application.get_default().settings.get_string("osc-host")

        try:
            self.target = liblo.Address(self.host, self.port)
        except liblo.AddressError as err:
            print(err)
            sys.exit()

    def send(self, path, *arg):
        liblo.send(self.target, path, *arg)


class OscServer(liblo.ServerThread):
    def __init__(self, window):

        self.app = Gio.Application.get_default()
        self.percent_view = Gio.Application.get_default().settings.get_boolean(
            "percent"
        )

        # Main Window
        self.window = window
        # Port to listen data from the client
        self.serv_port = Gio.Application.get_default().settings.get_int(
            "osc-server-port"
        )

        # Create Thread server
        liblo.ServerThread.__init__(self, self.serv_port)

        # Create Client
        self.client = OscClient()

        # Add methods (strings the server will respond)
        self.add_method("/seq/go", "i", self.seqgo_cb)  # Go
        self.add_method("/seq/plus", "i", self.seqplus_cb)  # Seq +
        self.add_method("/seq/moins", "i", self.seqless_cb)  # Seq -
        self.add_method("/pad/1", None, self.pad1_cb)
        self.add_method("/pad/2", None, self.pad2_cb)
        self.add_method("/pad/3", None, self.pad3_cb)
        self.add_method("/pad/4", None, self.pad4_cb)
        self.add_method("/pad/5", None, self.pad5_cb)
        self.add_method("/pad/6", None, self.pad6_cb)
        self.add_method("/pad/7", None, self.pad7_cb)
        self.add_method("/pad/8", None, self.pad8_cb)
        self.add_method("/pad/9", None, self.pad9_cb)
        self.add_method("/pad/0", None, self.pad0_cb)
        self.add_method("/pad/dot", None, self.paddot_cb)
        self.add_method("/pad/channel", None, self.padchannel_cb)  # Channel
        self.add_method("/pad/all", None, self.padall_cb)
        self.add_method("/pad/level", None, self.padlevel_cb)  # Level
        self.add_method("/pad/ff", None, self.padfull_cb)  # Full
        self.add_method("/pad/thru", None, self.padthru_cb)  # Thru
        self.add_method("/pad/plus", None, self.padplus_cb)  # +
        self.add_method("/pad/moins", None, self.padminus_cb)  # -
        # + %
        self.add_method("/pad/pluspourcent", None, self.padpluspourcent_cb)
        # - %
        self.add_method("/pad/moinspourcent", None, self.padminuspourcent_cb)
        self.add_method("/pad/clear", None, self.padclear_cb)  # Clear

        # For DiLuz :
        # Open Masters page
        self.add_method("/sub/launch", None, self.sub_launch_cb)
        # Flash Master (master number, level)
        self.add_method("/subStick/flash", "ii", self.sub_flash_cb)
        # Master level (master number, level)
        self.add_method("/subStick/level", "ii", self.sub_level_cb)

        # For TouchOSC :
        # Master 1 (float entre 0 et 255)
        self.add_method("/sub/1/level", "f", self.sub1_level_cb)
        # Master 2 (float entre 0 et 255)
        self.add_method("/sub/2/level", "f", self.sub2_level_cb)
        # Master 3 (float entre 0 et 255)
        self.add_method("/sub/3/level", "f", self.sub3_level_cb)
        # Master 4 (float entre 0 et 255)
        self.add_method("/sub/4/level", "f", self.sub4_level_cb)
        # Master 5 (float entre 0 et 255)
        self.add_method("/sub/5/level", "f", self.sub5_level_cb)
        # Master 6 (float entre 0 et 255)
        self.add_method("/sub/6/level", "f", self.sub6_level_cb)
        # Master 7 (float entre 0 et 255)
        self.add_method("/sub/7/level", "f", self.sub7_level_cb)
        # Master 8 (float entre 0 et 255)
        self.add_method("/sub/8/level", "f", self.sub8_level_cb)
        # Master 9 (float entre 0 et 255)
        self.add_method("/sub/9/level", "f", self.sub9_level_cb)
        # Master 10 (float entre 0 et 255)
        self.add_method("/sub/10/level", "f", self.sub10_level_cb)
        # Master 1A (float entre 0 et 255)
        self.add_method("/sub/11/level", "f", self.sub11_level_cb)
        # Master 12 (float entre 0 et 255)
        self.add_method("/sub/12/level", "f", self.sub12_level_cb)

        # TODO :
        self.add_method("/pad/enter", None, self.fallback)  # Enter
        self.add_method("/pad/blackout", None, self.fallback)  # Blackout (1 ou 0)
        self.add_method("/pad/freeze", None, self.fallback)  # Freeze (1 ou 0)
        self.add_method("/pad/scene", None, self.fallback)  # X1

        self.add_method("/seq/pause", None, self.fallback)  # Pause
        self.add_method("/seq/goback", None, self.fallback)  # Go Back
        self.add_method("/seq/fadeX1", None, self.fallback)  # (float entre 0 et 255)
        self.add_method("/seq/fadeX2", None, self.fallback)  # (float entre 0 et 255)

        # Register a fallback for unhandled messages
        self.add_method(None, None, self.fallback)

        # Launch server
        self.start()

    def fallback(self, path, args, types, src):
        print("Got unknown message '%s' from '%s'" % (path, src.url))
        for a, t in zip(args, types):
            print("received argument %s of type %s" % (a, t))

    def seqgo_cb(self, path, args, types):
        """ Go """
        for a, t in zip(args, types):
            if a == 1:
                self.client.send("/seq/go", self.window.keystring)
                self.window.keypress_space()

    def seqplus_cb(self, path, args, types):
        """ Seq + """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Down()

    def seqless_cb(self, path, args, types):
        """ Seq - """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Up()

    def pad1_cb(self, path, args, types):
        """ Pad 1 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "1"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad2_cb(self, path, args, types):
        """ Pad 2 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "2"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad3_cb(self, path, args, types):
        """ Pad 3 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "3"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad4_cb(self, path, args, types):
        """ Pad 4 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "4"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad5_cb(self, path, args, types):
        """ Pad 5 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "5"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad6_cb(self, path, args, types):
        """ Pad 6 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "6"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad7_cb(self, path, args, types):
        """ Pad 7 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "7"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad8_cb(self, path, args, types):
        """ Pad 8 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "8"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad9_cb(self, path, args, types):
        """ Pad 9 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "9"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def pad0_cb(self, path, args, types):
        """ Pad 0 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "0"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def paddot_cb(self, path, args, types):
        """ Pad . """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "."
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def padchannel_cb(self, path, args, types):
        """ Pad Channel """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_c()
                self.client.send("/pad/saisieText", "")

    def padall_cb(self, path, args, types):
        """ Pad All """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_a()
                self.client.send("/pad/saisieText", "")

    def padlevel_cb(self, path, args, types):
        """ Pad @ """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_equal()
                self.client.send("/pad/saisieText", "")

    def padfull_cb(self, path, args, types):
        """ Pad Full """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "255"
                self.window.keypress_equal()
                self.client.send("/pad/saisieText", "")

    def padthru_cb(self, path, args, types):
        """ Pad Thru """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_greater()
                self.client.send("/pad/saisieText", "")

    def padplus_cb(self, path, args, types):
        """ Pad + """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_plus()
                self.client.send("/pad/saisieText", "")

    def padminus_cb(self, path, args, types):
        """ Pad - """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_minus()
                self.client.send("/pad/saisieText", "")

    def padpluspourcent_cb(self, path, args, types):
        """ Pad +% """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Right()
                self.client.send("/pad/saisieText", "")

    def padminuspourcent_cb(self, path, args, types):
        """ Pad -% """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Left()
                self.client.send("/pad/saisieText", "")

    def padclear_cb(self, path, args, types):
        """ Pad Clear """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Escape()
                self.client.send("/pad/saisieText", "")

    def sub_launch_cb(self, path, args, types):
        """ Launch Sub page """
        for i in range(10):
            self.client.send(
                "/subStick/text", ("i", i + 1), ("s", self.app.masters[i].text)
            )

    def sub_flash_cb(self, path, args, types):
        """ Flash Master """
        flash, level = args
        if self.percent_view:
            lvl = int(round((level / 255) * 100))
        self.app.win_masters.scale[flash - 1].set_value(lvl)
        self.client.send("/subStick/level", ("i", flash), ("i", level))

    def sub_level_cb(self, path, args, types):
        """ Master Level """
        flash, level = args
        if self.percent_view:
            lvl = int(round((level / 255) * 100))
        self.app.win_masters.scale[flash - 1].set_value(lvl)
        self.client.send("/subStick/level", ("i", flash), ("i", level))

    def sub1_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[0].set_value(int(level[0]))

    def sub2_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[1].set_value(int(level[0]))

    def sub3_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[2].set_value(int(level[0]))

    def sub4_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[3].set_value(int(level[0]))

    def sub5_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[4].set_value(int(level[0]))

    def sub6_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[5].set_value(int(level[0]))

    def sub7_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[6].set_value(int(level[0]))

    def sub8_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[7].set_value(int(level[0]))

    def sub9_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[8].set_value(int(level[0]))

    def sub10_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[9].set_value(int(level[0]))

    def sub11_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[10].set_value(int(level[0]))

    def sub12_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[11].set_value(int(level[0]))

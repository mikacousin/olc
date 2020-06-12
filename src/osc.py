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
        self.add_method("/seq/go", "i", self._seqgo_cb)  # Go
        self.add_method("/seq/plus", "i", self._seqplus_cb)  # Seq +
        self.add_method("/seq/moins", "i", self._seqless_cb)  # Seq -
        self.add_method("/pad/1", None, self._pad1_cb)
        self.add_method("/pad/2", None, self._pad2_cb)
        self.add_method("/pad/3", None, self._pad3_cb)
        self.add_method("/pad/4", None, self._pad4_cb)
        self.add_method("/pad/5", None, self._pad5_cb)
        self.add_method("/pad/6", None, self._pad6_cb)
        self.add_method("/pad/7", None, self._pad7_cb)
        self.add_method("/pad/8", None, self._pad8_cb)
        self.add_method("/pad/9", None, self._pad9_cb)
        self.add_method("/pad/0", None, self._pad0_cb)
        self.add_method("/pad/dot", None, self._paddot_cb)
        self.add_method("/pad/channel", None, self._padchannel_cb)  # Channel
        self.add_method("/pad/all", None, self._padall_cb)
        self.add_method("/pad/level", None, self._padlevel_cb)  # Level
        self.add_method("/pad/ff", None, self._padfull_cb)  # Full
        self.add_method("/pad/thru", None, self._padthru_cb)  # Thru
        self.add_method("/pad/plus", None, self._padplus_cb)  # +
        self.add_method("/pad/moins", None, self._padminus_cb)  # -
        # + %
        self.add_method("/pad/pluspourcent", None, self._padpluspourcent_cb)
        # - %
        self.add_method("/pad/moinspourcent", None, self._padminuspourcent_cb)
        self.add_method("/pad/clear", None, self._padclear_cb)  # Clear

        # For DiLuz :
        # Open Masters page
        self.add_method("/sub/launch", None, self._sub_launch_cb)
        # Flash Master (master number, level)
        self.add_method("/subStick/flash", "ii", self._sub_flash_cb)
        # Master level (master number, level)
        self.add_method("/subStick/level", "ii", self._sub_level_cb)

        # For TouchOSC :
        # Master 1 (float entre 0 et 255)
        self.add_method("/sub/1/level", "f", self._sub1_level_cb)
        # Master 2 (float entre 0 et 255)
        self.add_method("/sub/2/level", "f", self._sub2_level_cb)
        # Master 3 (float entre 0 et 255)
        self.add_method("/sub/3/level", "f", self._sub3_level_cb)
        # Master 4 (float entre 0 et 255)
        self.add_method("/sub/4/level", "f", self._sub4_level_cb)
        # Master 5 (float entre 0 et 255)
        self.add_method("/sub/5/level", "f", self._sub5_level_cb)
        # Master 6 (float entre 0 et 255)
        self.add_method("/sub/6/level", "f", self._sub6_level_cb)
        # Master 7 (float entre 0 et 255)
        self.add_method("/sub/7/level", "f", self._sub7_level_cb)
        # Master 8 (float entre 0 et 255)
        self.add_method("/sub/8/level", "f", self._sub8_level_cb)
        # Master 9 (float entre 0 et 255)
        self.add_method("/sub/9/level", "f", self._sub9_level_cb)
        # Master 10 (float entre 0 et 255)
        self.add_method("/sub/10/level", "f", self._sub10_level_cb)
        # Master 1A (float entre 0 et 255)
        self.add_method("/sub/11/level", "f", self._sub11_level_cb)
        # Master 12 (float entre 0 et 255)
        self.add_method("/sub/12/level", "f", self._sub12_level_cb)

        # TODO :
        self.add_method("/pad/enter", None, self._fallback)  # Enter
        self.add_method("/pad/blackout", None, self._fallback)  # Blackout (1 ou 0)
        self.add_method("/pad/freeze", None, self._fallback)  # Freeze (1 ou 0)
        self.add_method("/pad/scene", None, self._fallback)  # X1

        self.add_method("/seq/pause", None, self._fallback)  # Pause
        self.add_method("/seq/goback", None, self._fallback)  # Go Back
        self.add_method("/seq/fadeX1", None, self._fallback)  # (float entre 0 et 255)
        self.add_method("/seq/fadeX2", None, self._fallback)  # (float entre 0 et 255)

        # Register a fallback for unhandled messages
        self.add_method(None, None, self._fallback)

        # Launch server
        self.start()

    def _fallback(self, path, args, types, src):
        print("Got unknown message '%s' from '%s'" % (path, src.url))
        for a, t in zip(args, types):
            print("received argument %s of type %s" % (a, t))

    def _seqgo_cb(self, path, args, types):
        """ Go """
        for a, _t in zip(args, types):
            if a == 1:
                self.client.send("/seq/go", self.window.keystring)
                self.window.keypress_space()

    def _seqplus_cb(self, path, args, types):
        """ Seq + """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_Down()

    def _seqless_cb(self, path, args, types):
        """ Seq - """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_Up()

    def _pad1_cb(self, path, args, types):
        """ Pad 1 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "1"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad2_cb(self, path, args, types):
        """ Pad 2 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "2"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad3_cb(self, path, args, types):
        """ Pad 3 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "3"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad4_cb(self, path, args, types):
        """ Pad 4 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "4"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad5_cb(self, path, args, types):
        """ Pad 5 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "5"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad6_cb(self, path, args, types):
        """ Pad 6 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "6"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad7_cb(self, path, args, types):
        """ Pad 7 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "7"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad8_cb(self, path, args, types):
        """ Pad 8 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "8"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad9_cb(self, path, args, types):
        """ Pad 9 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "9"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _pad0_cb(self, path, args, types):
        """ Pad 0 """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "0"
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _paddot_cb(self, path, args, types):
        """ Pad . """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "."
                self.client.send("/pad/saisieText", self.window.keystring)
                # print("keystring :", self.window.keystring)

    def _padchannel_cb(self, path, args, types):
        """ Pad Channel """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_c()
                self.client.send("/pad/saisieText", "")

    def _padall_cb(self, path, args, types):
        """ Pad All """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_a()
                self.client.send("/pad/saisieText", "")

    def _padlevel_cb(self, path, args, types):
        """ Pad @ """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_equal()
                self.client.send("/pad/saisieText", "")

    def _padfull_cb(self, path, args, types):
        """ Pad Full """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keystring += "255"
                self.window.keypress_equal()
                self.client.send("/pad/saisieText", "")

    def _padthru_cb(self, path, args, types):
        """ Pad Thru """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_greater()
                self.client.send("/pad/saisieText", "")

    def _padplus_cb(self, path, args, types):
        """ Pad + """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_plus()
                self.client.send("/pad/saisieText", "")

    def _padminus_cb(self, path, args, types):
        """ Pad - """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_minus()
                self.client.send("/pad/saisieText", "")

    def _padpluspourcent_cb(self, path, args, types):
        """ Pad +% """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_Right()
                self.client.send("/pad/saisieText", "")

    def _padminuspourcent_cb(self, path, args, types):
        """ Pad -% """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_Left()
                self.client.send("/pad/saisieText", "")

    def _padclear_cb(self, path, args, types):
        """ Pad Clear """
        for a, _t in zip(args, types):
            if a == 1:
                self.window.keypress_Escape()
                self.client.send("/pad/saisieText", "")

    def _sub_launch_cb(self, path, args, types):
        """ Launch Sub page """
        for i in range(10):
            self.client.send(
                "/subStick/text", ("i", i + 1), ("s", self.app.masters[i].text)
            )

    def _sub_flash_cb(self, path, args, types):
        """ Flash Master """
        flash, level = args
        if self.percent_view:
            lvl = int(round((level / 255) * 100))
        self.app.win_masters.scale[flash - 1].set_value(lvl)
        self.client.send("/subStick/level", ("i", flash), ("i", level))

    def _sub_level_cb(self, path, args, types):
        """ Master Level """
        flash, level = args
        if self.percent_view:
            lvl = int(round((level / 255) * 100))
        self.app.win_masters.scale[flash - 1].set_value(lvl)
        self.client.send("/subStick/level", ("i", flash), ("i", level))

    def _sub1_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[0].set_value(int(level[0]))

    def _sub2_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[1].set_value(int(level[0]))

    def _sub3_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[2].set_value(int(level[0]))

    def _sub4_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[3].set_value(int(level[0]))

    def _sub5_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[4].set_value(int(level[0]))

    def _sub6_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[5].set_value(int(level[0]))

    def _sub7_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[6].set_value(int(level[0]))

    def _sub8_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[7].set_value(int(level[0]))

    def _sub9_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[8].set_value(int(level[0]))

    def _sub10_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[9].set_value(int(level[0]))

    def _sub11_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[10].set_value(int(level[0]))

    def _sub12_level_cb(self, path, args, types):
        level = args
        self.app.win_masters.scale[11].set_value(int(level[0]))

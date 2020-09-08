"""OSC client / server"""

import sys

import liblo
from gi.repository import Gdk, GLib
from olc.define import App


class OscClient:
    """OSC client"""

    def __init__(self):
        # Port to send data to the client
        self.port = App().settings.get_int("osc-client-port")
        # client's IP address
        self.host = App().settings.get_string("osc-host")

        try:
            self.target = liblo.Address(self.host, self.port)
        except liblo.AddressError as err:
            print(err)
            sys.exit()

    def send(self, path, *arg):
        """Send OSC message to the client"""
        liblo.send(self.target, path, *arg)


class OscServer(liblo.ServerThread):
    """OSC server"""

    def __init__(self):
        # Port to listen data from the client
        self.serv_port = App().settings.get_int("osc-server-port")

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
        self.add_method("/subStick/flash", "ii", self._sub_level_cb)
        # Master level (master number, level)
        self.add_method("/subStick/level", "ii", self._sub_level_cb)

        # TODO :
        self.add_method("/pad/enter", None, self._fallback)  # Enter
        self.add_method("/pad/blackout", None, self._fallback)  # Blackout (1 ou 0)
        self.add_method("/pad/freeze", None, self._fallback)  # Freeze (1 ou 0)
        self.add_method("/pad/scene", None, self._fallback)  # X1

        self.add_method("/seq/pause", None, self._fallback)  # Pause
        self.add_method("/seq/goback", None, self._fallback)  # Go Back
        self.add_method("/seq/fadeX1", None, self._fallback)  # (float entre 0 et 255)
        self.add_method("/seq/fadeX2", None, self._fallback)  # (float entre 0 et 255)

        # For TouchOSC :
        # Master 1 (float entre 0 et 255)
        self.add_method("/sub/1/level", "f", self._fallback)
        # Master 2 (float entre 0 et 255)
        self.add_method("/sub/2/level", "f", self._fallback)
        # Master 3 (float entre 0 et 255)
        self.add_method("/sub/3/level", "f", self._fallback)
        # Master 4 (float entre 0 et 255)
        self.add_method("/sub/4/level", "f", self._fallback)
        # Master 5 (float entre 0 et 255)
        self.add_method("/sub/5/level", "f", self._fallback)
        # Master 6 (float entre 0 et 255)
        self.add_method("/sub/6/level", "f", self._fallback)
        # Master 7 (float entre 0 et 255)
        self.add_method("/sub/7/level", "f", self._fallback)
        # Master 8 (float entre 0 et 255)
        self.add_method("/sub/8/level", "f", self._fallback)
        # Master 9 (float entre 0 et 255)
        self.add_method("/sub/9/level", "f", self._fallback)
        # Master 10 (float entre 0 et 255)
        self.add_method("/sub/10/level", "f", self._fallback)
        # Master 1A (float entre 0 et 255)
        self.add_method("/sub/11/level", "f", self._fallback)
        # Master 12 (float entre 0 et 255)
        self.add_method("/sub/12/level", "f", self._fallback)

        # Register a fallback for unhandled messages
        self.add_method(None, None, self._fallback)

        # Launch server
        self.start()

    def _fallback(self, path, args, types, src):
        print("Got unknown message '%s' from '%s'" % (path, src.url))
        for a, t in zip(args, types):
            print("received argument %s of type %s" % (a, t))

    def _seqgo_cb(self, path, args, types):
        """Go"""
        for a, _t in zip(args, types):
            if a == 1:
                self.client.send("/seq/go", App().window.keystring)
                GLib.idle_add(App().sequence.do_go, None, None)

    def _seqplus_cb(self, path, args, types):
        """Seq +"""
        for a, _t in zip(args, types):
            if a == 1:
                GLib.idle_add(App().sequence.sequence_plus)

    def _seqless_cb(self, path, args, types):
        """Seq -"""
        for a, _t in zip(args, types):
            if a == 1:
                GLib.idle_add(App().sequence.sequence_minus)

    def _pad1_cb(self, path, args, types):
        """Pad 1"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "1"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad2_cb(self, path, args, types):
        """Pad 2"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "2"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad3_cb(self, path, args, types):
        """Pad 3"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "3"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad4_cb(self, path, args, types):
        """Pad 4"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "4"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad5_cb(self, path, args, types):
        """Pad 5"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "5"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad6_cb(self, path, args, types):
        """Pad 6"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "6"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad7_cb(self, path, args, types):
        """Pad 7"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "7"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad8_cb(self, path, args, types):
        """Pad 8"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "8"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad9_cb(self, path, args, types):
        """Pad 9"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "9"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _pad0_cb(self, path, args, types):
        """Pad 0"""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "0"
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _paddot_cb(self, path, args, types):
        """Pad ."""
        for a, _t in zip(args, types):
            if a == 1:
                App().window.keystring += "."
                App().window.channels_view.statusbar.push(
                    App().window.channels_view.context_id, App().window.keystring
                )
                self.client.send("/pad/saisieText", App().window.keystring)

    def _padchannel_cb(self, path, args, types):
        """Pad Channel"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_c
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padall_cb(self, path, args, types):
        """Pad All"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_a
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padlevel_cb(self, path, args, types):
        """Pad @"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_equal
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padfull_cb(self, path, args, types):
        """Pad Full"""
        for a, _t in zip(args, types):
            if a == 1:
                if App().settings.get_boolean("percent"):
                    App().window.keystring = "100"
                else:
                    App().window.keystring = "255"
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_equal
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padthru_cb(self, path, args, types):
        """Pad Thru"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_greater
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padplus_cb(self, path, args, types):
        """Pad +"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_plus
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padminus_cb(self, path, args, types):
        """Pad -"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_minus
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padpluspourcent_cb(self, path, args, types):
        """Pad +%"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_exclam
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padminuspourcent_cb(self, path, args, types):
        """Pad -%"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_colon
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _padclear_cb(self, path, args, types):
        """Pad Clear"""
        for a, _t in zip(args, types):
            if a == 1:
                event = Gdk.EventKey()
                event.keyval = Gdk.KEY_BackSpace
                App().window.on_key_press_event(None, event)
                self.client.send("/pad/saisieText", "")

    def _sub_launch_cb(self, path, args, types):
        """ Launch Sub page """
        for i in range(10):
            self.client.send(
                "/subStick/text", ("i", i + 1), ("s", App().masters[i].text)
            )

    def _sub_level_cb(self, _path, args, _types):
        """Master Level"""
        master_index, level = args
        if App().virtual_console:
            GLib.idle_add(
                App().virtual_console.masters[master_index - 1].set_value, level
            )
            GLib.idle_add(
                App().virtual_console.master_moved,
                App().virtual_console.masters[master_index - 1],
            )
        else:
            page = int((master_index - 1) / 20) + 1
            number = master_index if page == 1 else int(master_index / 2)
            master = None
            for master in App().masters:
                if master.page == page and master.number == number:
                    break
            master.set_level(level)
        self.client.send("/subStick/level", ("i", master_index), ("i", level))

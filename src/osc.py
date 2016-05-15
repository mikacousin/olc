import liblo
from gi.repository import Gio

from olc.window import Window

class OscClient(object):
    def __init__(self, host="localhost", port=9000):
        self.port = port
        self.host = host

        try:
            self.target = liblo.Address(self.host, self.port)
        except (liblo.AddressError, err):
            print(str(err))
            sys.exit()

    def send(self, path, arg):
        liblo.send(self.target, path, arg)

class OscServer(liblo.ServerThread):
    def __init__(self, window, port=7000):
        self.window = window
        self.host = Gio.Application.get_default().settings.get_string('osc-host')

        # Create Thread server
        liblo.ServerThread.__init__(self, port)

        # Create Client
        # TODO: Paramètre pour l'adresse IP
        #self.client = OscClient(host='10.0.0.3')
        self.client = OscClient(self.host)

        # Add methods (strings the server will respond)
        self.add_method('/seq/go', 'i', self.seqgo_cb)
        self.add_method('/seq/plus', 'i', self.seqplus_cb)
        self.add_method('/seq/moins', 'i', self.seqless_cb)
        self.add_method('/pad/1', None, self.pad1_cb)
        self.add_method('/pad/2', None, self.pad2_cb)
        self.add_method('/pad/3', None, self.pad3_cb)
        self.add_method('/pad/4', None, self.pad4_cb)
        self.add_method('/pad/5', None, self.pad5_cb)
        self.add_method('/pad/6', None, self.pad6_cb)
        self.add_method('/pad/7', None, self.pad7_cb)
        self.add_method('/pad/8', None, self.pad8_cb)
        self.add_method('/pad/9', None, self.pad9_cb)
        self.add_method('/pad/0', None, self.pad0_cb)
        self.add_method('/pad/dot', None, self.paddot_cb)
        self.add_method('/pad/channel', None, self.padchannel_cb)
        self.add_method('/pad/all', None, self.padall_cb)
        self.add_method('/pad/level', None, self.padlevel_cb) # Level
        self.add_method('/pad/ff', None, self.padfull_cb) # Full
        self.add_method('/pad/thru', None, self.padthru_cb) # Thru
        self.add_method('/pad/plus', None, self.padplus_cb) # +
        self.add_method('/pad/moins', None, self.padminus_cb) # -
        self.add_method('/pad/pluspourcent', None, self.padpluspourcent_cb) # + %
        self.add_method('/pad/moinspourcent', None, self.padminuspourcent_cb) # - %
        self.add_method('/pad/clear', None, self.padclear_cb) # Clear

        #TODO
        self.add_method('/pad/enter', None, self.fallback) # Enter
        self.add_method('/pad/blackout', None, self.fallback) # Blackout (1 ou 0)
        self.add_method('/pad/freeze', None, self.fallback) # Freeze (1 ou 0)
        self.add_method('/pad/scene', None, self.fallback) # X1

        self.add_method('/seq/pause', None, self.fallback) # Pause
        self.add_method('/seq/goback', None, self.fallback) # Go Back
        self.add_method('/seq/fadeX1', None, self.fallback) # (float entre 0 et 255)
        self.add_method('/seq/fadeX2', None, self.fallback) # (float entre 0 et 255)

        self.add_method('/sub/1/level', None, self.fallback) # Master 1 (float entre 0 et 255)
        self.add_method('/sub/2/level', None, self.fallback) # Master 2 (float entre 0 et 255)

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
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad2_cb(self, path, args, types):
        """ Pad 2 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "2"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad3_cb(self, path, args, types):
        """ Pad 3 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "3"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad4_cb(self, path, args, types):
        """ Pad 4 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "4"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad5_cb(self, path, args, types):
        """ Pad 5 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "5"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad6_cb(self, path, args, types):
        """ Pad 6 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "6"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad7_cb(self, path, args, types):
        """ Pad 7 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "7"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad8_cb(self, path, args, types):
        """ Pad 8 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "8"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad9_cb(self, path, args, types):
        """ Pad 9 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "9"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def pad0_cb(self, path, args, types):
        """ Pad 0 """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "0"
                self.client.send('/pad/saisieText', self.window.keystring)
                #print("keystring :", self.window.keystring)

    def paddot_cb(self, path, args, types):
        """ Pad . """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "."
                self.client.send('/pad/saisieText', self.window.keystring)
                print("keystring :", self.window.keystring)

    def padchannel_cb(self, path, args, types):
        """ Pad Channel """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_c()
                self.client.send('/pad/saisieText', '')

    def padall_cb(self, path, args, types):
        """ Pad All """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_a()
                self.client.send('/pad/saisieText', '')

    def padlevel_cb(self, path, args, types):
        """ Pad @ """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_equal()
                self.client.send('/pad/saisieText', '')

    def padfull_cb(self, path, args, types):
        """ Pad Full """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keystring += "255"
                self.window.keypress_equal()
                self.client.send('/pad/saisieText', '')

    def padthru_cb(self, path, args, types):
        """ Pad Thru """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_greater()
                self.client.send('/pad/saisieText', '')

    def padplus_cb(self, path, args, types):
        """ Pad + """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_plus()
                self.client.send('/pad/saisieText', '')

    def padminus_cb(self, path, args, types):
        """ Pad - """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_minus()
                self.client.send('/pad/saisieText', '')

    def padpluspourcent_cb(self, path, args, types):
        """ Pad +% """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Right()
                self.client.send('/pad/saisieText', '')

    def padminuspourcent_cb(self, path, args, types):
        """ Pad -% """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Left()
                self.client.send('/pad/saisieText', '')

    def padclear_cb(self, path, args, types):
        """ Pad Clear """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_Escape()
                self.client.send('/pad/saisieText', '')

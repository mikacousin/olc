import liblo

from olc.window import Window

class OscServer(liblo.ServerThread):
    def __init__(self, window, port=7000):
        self.window = window

        # Create Thread server
        liblo.ServerThread.__init__(self, port)

        # Add methods (strings the server will respond)
        self.add_method('/seq/go', None, self.seqgo_cb)
        self.add_method('/seq/plus', 'i', self.seqplus_cb)
        self.add_method('/seq/less', 'i', self.seqless_cb)
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
        self.add_method('/pad/channel', None, self.padchannel_cb)
        self.add_method('/pad/all', None, self.padall_cb)
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
        #for a, t in zip(args, types):
        #    if a == 1:
        #        self.window.keypress_space()
        self.window.keypress_space()

    def seqplus_cb(self, path, args, types):
        """ Seq + """
        self.window.keypress_Down()

    def seqless_cb(self, path, args, types):
        """ Seq - """
        self.window.keypress_Up()

    def pad1_cb(self, path, args, types):
        """ Pad 1 """
        self.window.keystring += "1"
        print("keystring :", self.window.keystring)

    def pad2_cb(self, path, args, types):
        """ Pad 2 """
        self.window.keystring += "2"
        print("keystring :", self.window.keystring)

    def pad3_cb(self, path, args, types):
        """ Pad 3 """
        self.window.keystring += "3"
        print("keystring :", self.window.keystring)

    def pad4_cb(self, path, args, types):
        """ Pad 4 """
        self.window.keystring += "4"
        print("keystring :", self.window.keystring)

    def pad5_cb(self, path, args, types):
        """ Pad 5 """
        self.window.keystring += "5"
        print("keystring :", self.window.keystring)

    def pad6_cb(self, path, args, types):
        """ Pad 6 """
        self.window.keystring += "6"
        print("keystring :", self.window.keystring)

    def pad7_cb(self, path, args, types):
        """ Pad 7 """
        self.window.keystring += "7"
        print("keystring :", self.window.keystring)

    def pad8_cb(self, path, args, types):
        """ Pad 8 """
        self.window.keystring += "8"
        print("keystring :", self.window.keystring)

    def pad9_cb(self, path, args, types):
        """ Pad 9 """
        self.window.keystring += "9"
        print("keystring :", self.window.keystring)

    def pad0_cb(self, path, args, types):
        """ Pad 0 """
        self.window.keystring += "0"
        print("keystring :", self.window.keystring)

    def padchannel_cb(self, path, args, types):
        """ Pad Channel """
        print("keystring :", self.window.keystring)
        self.window.keypress_c()

    def padall_cb(self, path, args, types):
        """ Pad All """
        self.window.keypress_a()

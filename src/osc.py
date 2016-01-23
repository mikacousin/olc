import liblo

from olc.window import Window

class OscServer(liblo.ServerThread):
    def __init__(self, window, port=7000):
        self.window = window

        # Create Thread server
        liblo.ServerThread.__init__(self, port)

        # Add methods (strings the server will respond)
        self.add_method('/seq/go', 'i', self.seqgo_cb)
        self.add_method('/seq/plus', 'i', self.seqplus_cb)
        self.add_method('/seq/less', 'i', self.seqless_cb)

        # Launch server
        self.start()

    def seqgo_cb(self, path, args, types):
        """ Go """
        for a, t in zip(args, types):
            if a == 1:
                self.window.keypress_space()

    def seqplus_cb(self, path, args, types):
        """ Seq + """
        self.window.keypress_Down()

    def seqless_cb(self, path, args, types):
        """ Seq - """
        self.window.keypress_Up()

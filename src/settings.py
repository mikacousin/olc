from gi.repository import Gio

class Settings(Gio.Settings):
    def __init__(self):

        Gio.Settings.__init__(self)

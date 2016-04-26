from gi.repository import Gio

class Settings(Gio.Settings):
    def __init__(self):

        Gio.Settings.__init__(self)

    def new():

        settings = Gio.Settings.new('org.gnome.olc')
        settings.__class__ = Settings
        return settings

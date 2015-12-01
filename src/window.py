#import gi
#gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class Window(Gtk.ApplicationWindow):

    def __init__(self, app):
        Gtk.Window.__init__(self, title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1000)

        # create a label
        label = Gtk.Label()
        # set the text of the label
        label.set_text("Hello GNOME!")
        # add the label to the window
        self.add(label)

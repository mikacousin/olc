from gi.repository import Gtk

from olc.dmx import PatchDmx

class PatchWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Patch")
        self.set_border_width(10)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.add(self.grid)

        self.patch_liststore = Gtk.ListStore(int, int, str)
        for i in range(len(patch.chanels)):
            self.patch_liststore.append([i+1, patch.chanels[i], ""])

if __name__ == "__main__":
    
    patch = PatchDmx()

    win = PatchWindow()

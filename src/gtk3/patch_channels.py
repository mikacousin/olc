# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Device-centric and channel-centric DMX patch view for GTK3."""

from __future__ import annotations

import typing
from typing import Callable, Optional

from gi.repository import Gdk, Gtk

from olc.define import MAX_CHANNELS, UNIVERSES
from olc.devices.builtin import populate_builtin_library
from olc.devices.gdtf import GdtfImporter
from olc.gtk3.dialogs.patch_device import AddDeviceDialog, FixtureExchangeDialog
from olc.gtk3.widgets.patch_channels import PatchChannelHeader, PatchChannelWidget

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    import olc.gtk3.patch_channels
    from olc.core.backends import DMXBackend
    from olc.core.commandline import CoreCommandLine
    from olc.core.lightshow import LightShow
    from olc.devices.device import LightingDevice
    from olc.devices.fixture import FixtureDefinition, FixtureLibrary
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.patch import DMXPatch

# Column indices for the devices ListStore
COL_ID = 0
COL_NAME = 1
COL_TYPE = 2
COL_UNIVERSE = 3
COL_ADDRESS = 4
COL_FOOTPRINT = 5
COL_MODE = 6
COL_CURVE = 7


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class PatchChannelsTab(Gtk.Box):
    """Tab to patch lighting devices and channels."""

    app: Application
    patch: DMXPatch
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    backend: DMXBackend
    commandline: CoreCommandLine
    last_chan_selected: str
    flowbox: Gtk.FlowBox
    channels: list[PatchChannelWidget]
    scrollable: Gtk.ScrolledWindow
    fixture_library: FixtureLibrary
    sort_mode: str
    devices_store: Gtk.ListStore
    devices_treeview: Gtk.TreeView
    view_stack: Gtk.Stack

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(self, app: Application) -> None:
        self.app = app
        self.patch = app.core.lightshow.patch
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.backend = (
            app.core.backend
            if app.core.backend is not None
            else typing.cast(typing.Any, None)
        )
        self.commandline = app.core.commandline
        self.last_chan_selected = ""
        self.fixture_library = (
            getattr(self.lightshow, "fixture_library", None)
            or populate_builtin_library()
        )
        self.sort_mode = "logical"

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self._setup_toolbar()
        self._setup_views()
        self.populate_devices_store()

    def _setup_toolbar(self) -> None:
        """Create top action toolbar for device patch management."""
        self.toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.toolbar.set_margin_start(6)
        self.toolbar.set_margin_end(6)
        self.toolbar.set_margin_top(4)

        self.sort_toggle_btn = Gtk.ToggleButton(label="Sort: Logical (ID)")
        self.sort_toggle_btn.connect("toggled", self._on_sort_toggled)
        self.toolbar.pack_start(self.sort_toggle_btn, False, False, 0)

        self.add_device_btn = Gtk.Button(label="Add Device")
        self.add_device_btn.connect("clicked", self._on_add_device_clicked)
        self.toolbar.pack_start(self.add_device_btn, False, False, 0)

        self.remove_device_btn = Gtk.Button(label="Remove Device")
        self.remove_device_btn.connect("clicked", self._on_remove_device_clicked)
        self.toolbar.pack_start(self.remove_device_btn, False, False, 0)

        self.exchange_btn = Gtk.Button(label="Fixture Exchange")
        self.exchange_btn.connect("clicked", self._on_exchange_clicked)
        self.toolbar.pack_start(self.exchange_btn, False, False, 0)

        self.import_gdtf_btn = Gtk.Button(label="Import .gdtf")
        self.import_gdtf_btn.connect("clicked", self._on_import_gdtf_clicked)
        self.toolbar.pack_start(self.import_gdtf_btn, False, False, 0)

        self.legacy_toggle_btn = Gtk.ToggleButton(label="Channel Grid")
        self.legacy_toggle_btn.connect("toggled", self._on_view_mode_toggled)
        self.toolbar.pack_end(self.legacy_toggle_btn, False, False, 0)

        self.pack_start(self.toolbar, False, False, 2)

    def _setup_views(self) -> None:
        """Create the Stack holding the Devices TreeView and Legacy Channel FlowBox."""
        self.view_stack = Gtk.Stack()
        self.view_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Modern Devices Table View
        self.devices_store = Gtk.ListStore(
            int,  # COL_ID
            str,  # COL_NAME
            str,  # COL_TYPE
            int,  # COL_UNIVERSE
            int,  # COL_ADDRESS
            int,  # COL_FOOTPRINT
            str,  # COL_MODE
            str,  # COL_CURVE
        )
        self.devices_treeview = Gtk.TreeView(model=self.devices_store)
        self.devices_treeview.set_enable_search(True)
        self.devices_treeview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)

        columns_spec = [
            ("ID", COL_ID, 60),
            ("Label / Name", COL_NAME, 180),
            ("Type", COL_TYPE, 120),
            ("Universe", COL_UNIVERSE, 80),
            ("Address", COL_ADDRESS, 80),
            ("Footprint", COL_FOOTPRINT, 80),
            ("Patch / Footprint", COL_MODE, 140),
            ("Curve", COL_CURVE, 100),
        ]
        for title, col_idx, min_width in columns_spec:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_idx)
            column.set_min_width(min_width)
            column.set_resizable(True)
            self.devices_treeview.append_column(column)

        devices_scroll = Gtk.ScrolledWindow()
        devices_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        devices_scroll.add(self.devices_treeview)
        self.view_stack.add_named(devices_scroll, "devices")

        # 2. Legacy Channels FlowBox View (retained for backward compatibility)
        legacy_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = PatchChannelHeader()
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(1)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        self.channels = []
        for channel in range(MAX_CHANNELS):
            self.channels.append(
                PatchChannelWidget(
                    channel + 1,
                    self.app,
                    typing.cast("olc.gtk3.patch_channels.PatchChannelsTab", self),
                )
            )
            self.flowbox.add(self.channels[channel])

        self.scrollable = Gtk.ScrolledWindow()
        self.scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrollable.add(self.flowbox)

        legacy_box.pack_start(header, False, False, 2)
        legacy_box.pack_start(self.scrollable, True, True, 0)
        self.view_stack.add_named(legacy_box, "legacy")

        self.pack_start(self.view_stack, True, True, 0)
        self.view_stack.set_visible_child_name("devices")

        child = self.flowbox.get_child_at_index(0)
        if child is not None:
            self.flowbox.select_child(child)
            self.last_chan_selected = "0"

    # -------------------------------------------------------------------------
    # Device Table Data & Sorting
    # -------------------------------------------------------------------------

    def populate_devices_store(self) -> None:
        """Populate the devices ListStore from PatchManager, sorted by sort_mode."""
        self.devices_store.clear()
        devices = list(self.patch.devices.values())

        if self.sort_mode == "physical":
            devices.sort(key=lambda d: (d.universe, d.address, d.device_id))
        else:
            devices.sort(key=lambda d: d.device_id)

        for dev in devices:
            curve_str = "Linear" if dev.curve_id == 0 else f"Curve #{dev.curve_id}"
            self.devices_store.append(
                [
                    dev.device_id,
                    dev.label or f"Device {dev.device_id}",
                    dev.fixture_type.value.upper(),
                    dev.universe,
                    dev.address,
                    dev.channel_count(),
                    dev.patch_summary(),
                    curve_str,
                ]
            )

    def set_sort_mode(self, mode: str) -> None:
        """Set device table sort mode ('logical' or 'physical')."""
        if mode not in ("logical", "physical"):
            raise ValueError(f"Unsupported sort mode: {mode}")
        self.sort_mode = mode
        is_phys = mode == "physical"
        if self.sort_toggle_btn.get_active() != is_phys:
            self.sort_toggle_btn.set_active(is_phys)
        self.sort_toggle_btn.set_label(
            "Sort: Physical (Univ:Addr)" if is_phys else "Sort: Logical (ID)"
        )
        self.populate_devices_store()

    def toggle_sort_mode(self) -> str:
        """Toggle between logical and physical sort modes and return the new mode."""
        new_mode = "physical" if self.sort_mode == "logical" else "logical"
        self.set_sort_mode(new_mode)
        return new_mode

    def get_selected_device_id(self) -> Optional[int]:
        """Return currently selected device_id in the devices TreeView, or None."""
        selection = self.devices_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            return int(model[treeiter][COL_ID])
        return None

    # -------------------------------------------------------------------------
    # Device Patch Operations (Programmatic & Interactive)
    # -------------------------------------------------------------------------

    def add_patched_device(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_id: int,
        fixture_key: str,
        universe: int,
        address: int,
        mode_name: Optional[str] = None,
        label: str = "",
        curve_id: int = 0,
        force: bool = False,
    ) -> LightingDevice:
        """Patch a new LightingDevice from the fixture library and refresh display."""
        fdef = self.fixture_library.get_by_key(fixture_key)
        if fdef is None:
            raise KeyError(f"Fixture profile '{fixture_key}' not found in library")

        dev = self.patch.patch_device(
            device_id=device_id,
            fixture_def=fdef,
            universe=universe,
            address=address,
            mode_name=mode_name,
            label=label,
            force=force,
        )
        if curve_id > 0:
            dev.set_curve_id(curve_id)
        self.lightshow.set_modified()
        self.refresh()
        self.app.core.emit("patch.changed")
        return dev

    def remove_patched_device(self, device_id: int) -> bool:
        """Unpatch a device by ID and refresh the table."""
        removed = self.patch.unpatch_device(device_id)
        if removed is not None:
            self.lightshow.set_modified()
            self.refresh()
            self.app.core.emit("patch.changed")
            return True
        self.refresh()
        return False

    def exchange_device_fixture(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_id: int,
        new_fixture_key: str,
        new_mode_name: Optional[str] = None,
        universe: Optional[int] = None,
        address: Optional[int] = None,
        force: bool = False,
    ) -> LightingDevice:
        """Replace the fixture definition for an existing device (Fixture Exchange)."""
        fdef = self.fixture_library.get_by_key(new_fixture_key)
        if fdef is None:
            raise KeyError(f"Fixture profile '{new_fixture_key}' not found in library")

        dev = self.patch.exchange_fixture(
            device_id=device_id,
            new_fixture_def=fdef,
            new_mode_name=new_mode_name,
            universe=universe,
            address=address,
            force=force,
        )
        self.lightshow.set_modified()
        self.refresh()
        self.app.core.emit("patch.changed")
        return dev

    def import_gdtf(self, file_path: str) -> FixtureDefinition:
        """Import a .gdtf file and register it in the local fixture library."""
        importer = GdtfImporter()
        fdef = importer.load(file_path)
        self.fixture_library.register(fdef)
        return fdef

    # -------------------------------------------------------------------------
    # Toolbar Callbacks
    # -------------------------------------------------------------------------

    def _on_sort_toggled(self, button: Gtk.ToggleButton) -> None:
        mode = "physical" if button.get_active() else "logical"
        if self.sort_mode != mode:
            self.set_sort_mode(mode)

    def _on_view_mode_toggled(self, button: Gtk.ToggleButton) -> None:
        if button.get_active():
            self.view_stack.set_visible_child_name("legacy")
        else:
            self.view_stack.set_visible_child_name("devices")

    def _on_add_device_clicked(self, _button: Gtk.Button) -> None:
        next_id = 1
        while next_id <= MAX_CHANNELS and self.patch.is_patched(next_id):
            next_id += 1
        if next_id > MAX_CHANNELS:
            next_id = 1
        dialog = AddDeviceDialog(
            parent=self.window,
            patch=self.patch,
            library=self.fixture_library,
            default_device_id=next_id,
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            vals = dialog.get_values()
            try:
                self.add_patched_device(
                    device_id=vals["device_id"],
                    fixture_key=vals["fixture_key"],
                    universe=vals["universe"],
                    address=vals["address"],
                    mode_name=vals["mode_name"],
                    label=vals["label"],
                    curve_id=vals["curve_id"],
                    force=vals["force"],
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        dialog.destroy()

    def _on_remove_device_clicked(self, _button: Gtk.Button) -> None:
        dev_id = self.get_selected_device_id()
        if dev_id is not None:
            self.remove_patched_device(dev_id)

    def _on_exchange_clicked(self, _button: Gtk.Button) -> None:
        dev_id = self.get_selected_device_id()
        if dev_id is None:
            return
        dialog = FixtureExchangeDialog(
            parent=self.window,
            patch=self.patch,
            library=self.fixture_library,
            device_id=dev_id,
        )
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            vals = dialog.get_values()
            try:
                self.exchange_device_fixture(
                    device_id=vals["device_id"],
                    new_fixture_key=vals["fixture_key"],
                    new_mode_name=vals["mode_name"],
                    universe=vals["universe"],
                    address=vals["address"],
                    force=vals["force"],
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        dialog.destroy()

    def _on_import_gdtf_clicked(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserDialog(
            title="Import GDTF Fixture File",
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )
        file_filter = Gtk.FileFilter()
        file_filter.set_name("GDTF files (*.gdtf)")
        file_filter.add_pattern("*.gdtf")
        chooser.add_filter(file_filter)

        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
            if filename:
                try:
                    self.import_gdtf(filename)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        chooser.destroy()

    def refresh(self) -> None:
        """Refresh display."""
        self.populate_devices_store()
        self.flowbox.queue_draw()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked."""
        self.tabs.close("patch_channels")

    def on_key_press_event(
        self, _widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool:
        """Key press events.

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        widget = self.window.get_focus()
        if widget and widget.get_path().is_type(Gtk.Entry):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.app.core.action_registry.execute("commandline.append_char", keyname)

        if keyname in (
            "KP_1",
            "KP_2",
            "KP_3",
            "KP_4",
            "KP_5",
            "KP_6",
            "KP_7",
            "KP_8",
            "KP_9",
            "KP_0",
        ):
            self.app.core.action_registry.execute(
                "commandline.append_char", keyname[3:]
            )

        if keyname == "period":
            self.app.core.action_registry.execute("commandline.append_char", ".")

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_backspace(self) -> None:
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_down(self) -> None:
        """Select Next Channel."""
        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            if child is not None:
                self.flowbox.select_child(child)
                self.last_chan_selected = "0"
        elif int(self.last_chan_selected) < MAX_CHANNELS - 1:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) + 1)
            if child is not None:
                self.flowbox.select_child(child)
                self.last_chan_selected = str(int(self.last_chan_selected) + 1)

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_up(self) -> None:
        """Select Previous Channel."""
        if self.last_chan_selected == "":
            child = self.flowbox.get_child_at_index(0)
            if child is not None:
                self.flowbox.select_child(child)
                self.last_chan_selected = "0"
        elif int(self.last_chan_selected) > 0:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(int(self.last_chan_selected) - 1)
            if child is not None:
                self.flowbox.select_child(child)
                self.last_chan_selected = str(int(self.last_chan_selected) - 1)

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_c(self) -> None:
        """Select Channel."""
        self.flowbox.unselect_all()

        keystring = self.commandline.get_string()
        if keystring != "" and "." not in keystring:
            channel = int(keystring) - 1
            if 0 <= channel < MAX_CHANNELS:
                child = self.flowbox.get_child_at_index(channel)
                if child is not None:
                    self.flowbox.select_child(child)
                    self.last_chan_selected = str(channel)

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_kp_divide(self) -> None:
        """Thru."""
        self.thru()

    def _keypress_greater(self) -> None:
        """Thru."""
        self.thru()

    def thru(self) -> None:
        """Thru."""
        selected = self.flowbox.get_selected_children()
        if len(selected) == 1:
            child_widget = selected[0].get_child()
            if child_widget is not None:
                patchwidget = typing.cast("PatchChannelWidget", child_widget)
                channel = patchwidget.channel - 1
                self.last_chan_selected = str(channel)

        if not self.last_chan_selected:
            return

        to_chan = int(self.commandline.get_string())

        if to_chan > int(self.last_chan_selected):
            for chan in range(int(self.last_chan_selected), to_chan):
                child = self.flowbox.get_child_at_index(chan)
                if child is not None:
                    self.flowbox.select_child(child)
        else:
            for chan in range(to_chan - 1, int(self.last_chan_selected)):
                child = self.flowbox.get_child_at_index(chan)
                if child is not None:
                    self.flowbox.select_child(child)
        self.last_chan_selected = str(to_chan - 1)

        self.app.core.action_registry.execute("commandline.clear")

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def _keypress_m(self) -> None:
        """Modify Output."""
        sel = self.flowbox.get_selected_children()
        several = len(sel) > 1
        channel: int = 0
        for i, flowboxchild in enumerate(sel):
            child_widget = flowboxchild.get_child()
            if child_widget is None:
                continue
            widget = typing.cast("PatchChannelWidget", child_widget)
            channel = widget.channel

            keystring = self.commandline.get_string()
            if keystring in ["", "0"]:
                items = list(self.patch.channels[channel])
                for item in items:
                    output = item[0]
                    universe = item[1]
                    if output is not None and universe is not None:
                        self.window.app.core.action_registry.execute(
                            "patch.unpatch_output", output, universe
                        )
                self.channels[channel].queue_draw()

                widget_chan = self.window.live_view.channels_view.get_channel_widget(
                    channel
                )
                if widget_chan is not None:
                    widget_chan.level = 0
                    widget_chan.queue_draw()
                self.window.live_view.channels_view.update()
            else:
                if "." in keystring:
                    if keystring[0] == ".":
                        output = self.patch.channels[channel][0][0]
                        universe = int(keystring[1:])
                        several = False
                    else:
                        split = keystring.split(".")
                        output = int(split[0])
                        universe = int(split[1])
                else:
                    output = int(keystring)
                    universe = UNIVERSES[0]

                if output is not None and universe is not None:
                    if 0 < output + i <= 512:
                        self._unpatch_channel(channel)
                        out_val = output + i if several else output
                        self.window.app.core.action_registry.execute(
                            "patch.add_output", channel, out_val, universe
                        )
                        self.channels[channel - 1].queue_draw()

                    index = UNIVERSES.index(universe)
                    level = self.backend.dmx.frame[index][output]
                    widget_chan = (
                        self.window.live_view.channels_view.get_channel_widget(channel)
                    )
                    if widget_chan is not None:
                        widget_chan.level = level
                        widget_chan.queue_draw()
                    self.window.live_view.channels_view.update()

        if sel and channel < MAX_CHANNELS:
            self.flowbox.unselect_all()
            child = self.flowbox.get_child_at_index(channel)
            if child is not None:
                self.flowbox.select_child(child)
                self.last_chan_selected = str(channel)

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_i(self) -> None:
        """Insert Output."""
        keystring = self.commandline.get_string()
        if keystring in ["", "0"]:
            return
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            child_widget = flowboxchild.get_child()
            if child_widget is None:
                continue
            widget = typing.cast("PatchChannelWidget", child_widget)
            channel = widget.channel

            if "." in keystring:
                if keystring[0] == ".":
                    output = self.patch.channels[channel][0][0]
                    universe = int(keystring[1:])
                else:
                    split = keystring.split(".")
                    output = int(split[0])
                    universe = int(split[1])
            else:
                output = int(keystring)
                universe = UNIVERSES[0]

            if output is not None and universe is not None:
                if 0 < output <= 512:
                    self.window.app.core.action_registry.execute(
                        "patch.add_output", channel, output, universe
                    )
                    self.channels[channel - 1].queue_draw()

                    widget_chan = (
                        self.window.live_view.channels_view.get_channel_widget(channel)
                    )
                    if widget_chan is not None:
                        widget_chan.queue_draw()
                    self.window.live_view.channels_view.update()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_r(self) -> None:
        """Remove Output."""
        keystring = self.commandline.get_string()
        if keystring in ["", "0"]:
            return
        sel = self.flowbox.get_selected_children()
        for flowboxchild in sel:
            child_widget = flowboxchild.get_child()
            if child_widget is None:
                continue
            widget = typing.cast("PatchChannelWidget", child_widget)
            channel = widget.channel
            if "." in keystring:
                if keystring[0] != ".":
                    split = keystring.split(".")
                    output = int(split[0])
                    universe = int(split[1])
                else:
                    return
            else:
                output = int(keystring)
                universe = UNIVERSES[0]

            if output is not None and universe is not None:
                if (
                    0 < output <= 512
                    and [output, universe] in self.patch.channels[channel]
                ):
                    self.window.app.core.action_registry.execute(
                        "patch.unpatch_output", output, universe
                    )
                    self.channels[channel - 1].queue_draw()

                widget_chan = self.window.live_view.channels_view.get_channel_widget(
                    channel
                )
                if widget_chan is not None:
                    widget_chan.queue_draw()
                self.window.live_view.channels_view.update()

        self.app.core.action_registry.execute("commandline.clear")

    def _unpatch(self, output: int, universe: int) -> None:
        if universe in self.patch.outputs and output in self.patch.outputs[universe]:
            self.window.app.core.action_registry.execute(
                "patch.unpatch_output", output, universe
            )

    def _unpatch_channel(self, channel: int) -> None:
        if channel in self.patch.channels:
            items = list(self.patch.channels[channel])
            for item in items:
                output = item[0]
                universe = item[1]
                if output is not None and universe is not None:
                    self.window.app.core.action_registry.execute(
                        "patch.unpatch_output", output, universe
                    )

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
from __future__ import annotations

import typing
from typing import Callable

from gi.repository import Gdk, Gio, GLib, Gtk
from olc.cue import Cue
from olc.define import MAX_CHANNELS, UNIVERSES, string_to_time, time_to_string
from olc.gtk3.widgets.main_fader import MainFaderWidget
from olc.gtk3.window_channels import LiveView
from olc.gtk3.window_playback import MainPlaybackView
from olc.step import Step

if typing.TYPE_CHECKING:
    import olc.gtk3.window
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs


# pylint: disable=too-few-public-methods
class CommandLineWidget:
    """Display keyboard entries in GTK UI using a Gtk.Statusbar."""

    def __init__(self, app: Application) -> None:
        """Initialize the CommandLine widget.

        Args:
            app: The main application instance.
        """
        self.app = app
        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("keypress")
        self.widget = Gtk.Grid()
        label = Gtk.Label(label="Input : ")
        self.widget.add(label)
        self.widget.attach_next_to(self.statusbar, label, Gtk.PositionType.RIGHT, 1, 1)

        self.app.core.subscribe("commandline.changed", self.on_changed)

    def on_changed(self, keystring: str) -> None:
        """Callback triggered when the logical command line changes.

        Args:
            keystring: The new command line string.
        """
        GLib.idle_add(self._update_ui, keystring)

    def _update_ui(self, keystring: str) -> bool:
        self.statusbar.push(self.context_id, keystring)
        return False


# pylint: disable=too-many-instance-attributes
class Window(Gtk.ApplicationWindow):
    """Main Window"""

    @property
    def app(self) -> Application:
        """Get parent application instance safely."""
        app = self.get_application()
        return typing.cast("Application", app)

    def __init__(self, app: Gtk.Application, tabs: Tabs) -> None:
        # Full screen
        self.full = False
        self.tabs_manager = tabs

        super().__init__(title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1080)
        self.set_name("olc")
        self.connect("delete-event", self.app.exit)

        # Header Bar
        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("")
        self.header.props.show_close_button = True
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Main Fader viewer
        self.main_fader = MainFaderWidget(self.app.backend)
        box.add(self.main_fader)
        # Menu button
        button = Gtk.MenuButton()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)
        box.add(button)
        popover = Gtk.Popover.new_from_model(button, self.app.setup_app_menu())
        button.set_popover(popover)
        self.header.pack_end(box)
        self.set_titlebar(self.header)

        # Paned
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(800)

        # Channels
        self.live_view = LiveView(
            typing.cast("olc.gtk3.window.Window", self), self.tabs_manager
        )
        paned_chan = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned_chan.set_position(1100)
        paned_chan.pack1(self.live_view, resize=True, shrink=False)
        # Gtk.Statusbar to display keyboard's keys
        self.commandline_widget = CommandLineWidget(self.app)
        paned_chan.pack2(self.commandline_widget.widget, resize=True, shrink=False)
        paned.pack1(paned_chan, resize=True, shrink=False)

        # Main Playback
        self.playback = MainPlaybackView(self.app)
        paned.pack2(self.playback, resize=True, shrink=False)

        self.add(paned)

        self.set_icon_name("olc")

    def get_active_tab(self) -> Gtk.Paned:
        """Get active tab

        Returns:
            Active tab
        """
        widget = self.get_focus()
        while widget:
            if widget in (self.live_view, self.playback):
                break
            widget = widget.get_parent()
        any_widget = typing.cast(typing.Any, widget)
        return any_widget.get_nth_page(any_widget.get_current_page())

    def toggle_focus(self) -> None:
        """Toggle focus Left/Right"""
        focus = self.get_focus()
        if focus is self.live_view:
            self.playback.grab_focus()
        else:
            self.live_view.grab_focus()

    def fullscreen_toggle(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        """Toggle full screen"""
        if self.full:
            self.unfullscreen()
            self.full = False
        else:
            self.fullscreen()
            self.full = True

    def move_tab(self) -> None:
        """Move focused tab on next notebook"""
        focus = typing.cast(typing.Any, self.get_focus())
        page = focus.get_current_page()
        child = focus.get_nth_page(page)
        label = focus.get_tab_label(child)
        if focus is self.live_view:
            self.live_view.detach_tab(child)
            self.playback.append_page(child, label)
            self.playback.set_current_page(-1)
        else:
            self.playback.detach_tab(child)
            self.live_view.append_page(child, label)
            self.live_view.set_current_page(-1)

    def update_channels_display(self, step: int) -> None:
        """Update Channels levels display

        Args:
            step: Step
        """
        step_obj = self.app.core.lightshow.main_playback.steps[step]
        cue = step_obj.cue
        next_step_obj = self.app.core.lightshow.main_playback.steps[step + 1]
        next_cue = next_step_obj.cue

        for channel in range(1, MAX_CHANNELS + 1):
            level = cue.channels.get(channel, 0) if cue is not None else 0
            next_level = (
                next_cue.channels.get(channel, 0) if next_cue is not None else 0
            )
            widget = self.live_view.channels_view.get_channel_widget(channel)
            if widget is not None:
                widget.level = level
                widget.next_level = next_level
                widget.queue_draw()

    def on_key_press_event(
        self, _widget: Gtk.Widget | None, event: Gdk.EventKey
    ) -> Callable | bool:
        """Executed on key press event

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.app.core.commandline.add_string(keyname)

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
            self.app.core.commandline.add_string(keyname[3:])

        if keyname == "period":
            self.app.core.commandline.add_string(".")

        # Channels View
        self.live_view.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_exclam(self) -> None:
        """Level + (% level) of selected channels"""
        self.live_view.channels_view.level_plus()

    def _keypress_colon(self) -> None:
        """Level - (% level) of selected channels"""
        self.live_view.channels_view.level_minus()

    def _keypress_kp_enter(self) -> None:
        """@ Level"""
        self._keypress_equal()

    def _keypress_equal(self) -> None:
        """@ Level"""
        self.live_view.channels_view.at_level()
        self.app.core.commandline.set_string("")

    def _keypress_backspace(self) -> None:
        """Empty keys buffer"""
        self.app.core.commandline.set_string("")

    def _keypress_escape(self) -> None:
        """Deselect all channels"""
        self.live_view.channels_view.flowbox.unselect_all()
        self.live_view.channels_view.last_selected_channel = ""
        if self.app.tabs is not None:
            track_channels = typing.cast(
                typing.Any, self.app.tabs.tabs["track_channels"]
            )
            if track_channels:
                track_channels.update_display()

    def _keypress_q(self) -> None:
        """Seq -"""
        self.app.core.action_registry.execute("playback.sequence_minus")
        self.app.core.commandline.set_string("")

    def _keypress_w(self) -> None:
        """Seq +"""
        self.app.core.action_registry.execute("playback.sequence_plus")
        self.app.core.commandline.set_string("")

    def _keypress_g(self) -> None:
        """Goto"""
        self.app.core.lightshow.main_playback.goto(
            self.app.core.commandline.get_string()
        )
        self.app.core.commandline.set_string("")

    def _keypress_r(self) -> None:
        """Record new Step and new Preset"""
        found = False
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            # Find next free Cue
            position = self.app.core.lightshow.main_playback.position
            mem = self.app.core.lightshow.main_playback.get_next_cue(step=position)
            step = position + 1
        else:
            # Use given number
            mem = float(keystring)
            found, step = self.app.core.lightshow.main_playback.get_step(cue=mem)

        if mem is not None:
            if not found:
                self._create_preset(mem, step)
            else:  # Update Preset
                self._update_preset(mem)

        # Update Sequential edition Tabs
        if self.app.tabs is not None and self.app.tabs.tabs["sequences"]:
            sequences_tab = typing.cast(typing.Any, self.app.tabs.tabs["sequences"])
            # Main Playback selected ?
            path, _focus_column = sequences_tab.treeview1.get_cursor()
            if path:
                selected = path.get_indices()[0]
                sequence = sequences_tab.liststore1[selected][0]
                if sequence == self.app.core.lightshow.main_playback.index:
                    # Yes, update it
                    sequences_tab.on_sequence_changed()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _create_preset(self, mem: float, step: int) -> None:
        """Create new Preset component"""
        channels = {}
        if self.app.backend is not None and self.app.backend.dmx is not None:
            for channel, outputs in self.app.core.lightshow.patch.channels.items():
                if not self.app.core.lightshow.patch.is_patched(channel):
                    continue
                for values in outputs:
                    output = values[0]
                    univ = values[1]
                    if univ is not None and output is not None:
                        index = UNIVERSES.index(univ)
                        if level := self.app.backend.dmx.frame[index][output - 1]:
                            channels[channel] = level
        cue = Cue(1, mem, channels)
        self.app.core.lightshow.cues.insert(step - 1, cue)

        # Update Presets Tab if exist
        if self.app.tabs is not None and self.app.tabs.tabs["memories"]:
            memories_tab = typing.cast(typing.Any, self.app.tabs.tabs["memories"])
            nb_chan = len(channels)
            memories_tab.liststore.insert(step - 1, [str(mem), "", nb_chan])

        self.app.core.lightshow.main_playback.position = step

        # Create Step
        step_object = Step(1, cue=cue)
        self.app.core.lightshow.main_playback.insert_step(step, step_object)

        # Update Main Playback
        self.playback.update_sequence_display()
        self.playback.update_xfade_display(step)
        self.update_channels_display(step)

    def _update_preset(self, mem: float) -> None:
        """Update existing Preset component"""
        # Find Preset position
        i = 0
        for item in self.app.core.lightshow.cues:
            if item.number > mem:
                break
            i += 1
        i -= 1

        if self.app.backend is not None and self.app.backend.dmx is not None:
            for univ in UNIVERSES:
                for output in range(512):
                    channel = self.app.core.lightshow.patch.outputs[univ][output + 1][0]
                    index = UNIVERSES.index(univ)
                    level = self.app.backend.dmx.frame[index][output]

                    self.app.core.lightshow.cues[i].channels[channel] = level

        # Update Presets Tab if exist
        if self.app.tabs is not None and self.app.tabs.tabs["memories"]:
            memories_tab = typing.cast(typing.Any, self.app.tabs.tabs["memories"])
            nb_chan = sum(
                bool(self.app.core.lightshow.cues[i].channels.get(chan, 0))
                for chan in range(1, MAX_CHANNELS + 1)
            )

            treeiter = memories_tab.liststore.get_iter(i)
            memories_tab.liststore.set_value(treeiter, 2, nb_chan)
            memories_tab.channels_view.update()

    def _keypress_u(self) -> None:
        """Update Cue"""
        position = self.app.core.lightshow.main_playback.position
        step_obj = self.app.core.lightshow.main_playback.steps[position]
        cue = step_obj.cue
        if cue is None:
            return

        number = cue.number

        # Confirmation Dialog
        dialog = Dialog(self, number)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            for channel, outputs in self.app.core.lightshow.patch.channels.items():
                if not self.app.core.lightshow.patch.is_patched(channel):
                    continue
                if channel not in self.app.core.lightshow.independents.channels:
                    out = outputs[0][0]
                    univ = outputs[0][1]
                    if out is not None and univ is not None:
                        output = out - 1
                        index = UNIVERSES.index(univ)
                        if (
                            self.app.backend is not None
                            and self.app.backend.dmx is not None
                        ):
                            level = self.app.backend.dmx.frame[index][output]
                            cue.channels[channel] = level

            # Tag filename as modified
            self.app.core.lightshow.set_modified()

        dialog.destroy()

    def _keypress_t(self) -> None:
        """Change Time In and Time Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_time(time)
        self.playback.cues_liststore1[position + 3][5] = string
        self.playback.cues_liststore1[position + 3][7] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_in
        self.playback.sequential.time_out = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_out
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _keypress_i(self) -> None:
        """Change Time In of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_time_in(time)
        self.playback.cues_liststore1[position + 3][7] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_in
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _keypress_o(self) -> None:
        """Change Time Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_time_out(time)
        self.playback.cues_liststore1[position + 3][5] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_out = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_out
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _keypress_x(self) -> None:
        """Change Wait Time of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_wait(time)
        self.playback.cues_liststore1[position + 3][3] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.wait = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].wait
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _keypress_d(self) -> None:
        """Change Delay In and Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_delay(time)
        self.playback.cues_liststore1[position + 3][4] = string
        self.playback.cues_liststore1[position + 3][6] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].delay_in
        self.playback.sequential.delay_out = (
            self.app.core.lightshow.main_playback.steps[position + 1].delay_out
        )
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _keypress_k(self) -> None:
        """Change Delay In of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_delay_in(time)
        self.playback.cues_liststore1[position + 3][6] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].delay_in
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")

    def _keypress_l(self) -> None:
        """Change Delay Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_delay_out(time)
        self.playback.cues_liststore1[position + 3][4] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_out = (
            self.app.core.lightshow.main_playback.steps[position + 1].delay_out
        )
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.commandline.set_string("")


class Dialog(Gtk.Dialog):
    """Confirmation dialog when updating a Cue."""

    def __init__(self, parent: Gtk.Window, number: float) -> None:
        super().__init__(title="", transient_for=parent)
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )

        self.set_default_size(150, 100)

        label = Gtk.Label(label=f"Update cue {number} ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()

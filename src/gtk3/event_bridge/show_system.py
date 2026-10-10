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
"""GUI event bridge handler for show life cycle, tabs, preferences, and windows."""

from __future__ import annotations

import typing

from gi.repository import Gio, Gtk

from olc.gtk3.history import HistoryTab
from olc.gtk3.patch_outputs import PatchOutputsTab
from olc.gtk3.widgets.channel import ChannelWidget
from olc.gtk3.widgets.channels_view import ChannelsView

from .base import BaseEventBridgeHandler

if typing.TYPE_CHECKING:
    from olc.settings import SettingsTab


# pylint: disable=too-few-public-methods
class ShowSystemBridgeHandler(BaseEventBridgeHandler):
    """Handles show life cycle, tabs, windows, preferences, OSC, and MIDI events."""

    def register(self) -> None:
        """Subscribe to Core events for show, tabs, windows, and system settings."""
        self.app.core.subscribe(
            "show.new",
            lambda: self._run_idle(self._safe_on_show_new),
        )
        self.app.core.subscribe(
            "show.loaded",
            lambda path: self._run_idle(self._safe_on_show_loaded, path),
        )
        self.app.core.subscribe(
            "show.imported",
            lambda *args: self._run_idle(self._safe_on_show_imported),
        )
        self.app.core.subscribe(
            "gui.zoom_changed",
            lambda level: self._run_idle(self._on_zoom_changed, level),
        )
        self.app.core.subscribe(
            "gui.tab_opened",
            lambda tab_name, nb_id: self._run_idle(
                self._on_tab_opened, tab_name, nb_id
            ),
        )
        self.app.core.subscribe(
            "gui.tab_opened_at",
            lambda tab_name, nb_id, index: self._run_idle(
                self._on_tab_opened_at, tab_name, nb_id, index
            ),
        )
        self.app.core.subscribe(
            "gui.tab_closed",
            lambda tab_name, nb_id: self._run_idle(
                self._on_tab_closed, tab_name, nb_id
            ),
        )
        self.app.core.subscribe(
            "gui.active_tab_changed",
            lambda tab_name, nb_id: self._run_idle(
                self._on_active_tab_changed, tab_name, nb_id
            ),
        )
        self.app.core.subscribe(
            "gui.tab_moved",
            lambda tab_name, from_nb, to_nb, index: self._run_idle(
                self._on_tab_moved, tab_name, from_nb, to_nb, index
            ),
        )
        self.app.core.subscribe(
            "history.changed",
            lambda data: self._run_idle(self._on_history_changed, data),
        )
        self.app.core.subscribe(
            "osc.config_changed",
            lambda host, client_port, server_port: self._run_idle(
                self._on_osc_config_changed, host, client_port, server_port
            ),
        )
        self.app.core.subscribe(
            "osc.toggled",
            lambda state: self._run_idle(self._on_osc_toggled, state),
        )
        self.app.core.subscribe(
            "midi.port_toggled",
            lambda port_name, enable: self._run_idle(
                self._on_midi_port_toggled, port_name, enable
            ),
        )
        self.app.core.subscribe(
            "midi.port_mode_changed",
            lambda port_name, mode: self._run_idle(
                self._on_midi_port_mode_changed, port_name, mode
            ),
        )
        self.app.core.subscribe(
            "gui.virtual_console_requested",
            lambda: self._run_idle(self._on_virtual_console_requested),
        )
        self.app.core.subscribe(
            "gui.fullscreen_toggle_requested",
            lambda: self._run_idle(self._on_fullscreen_toggle_requested),
        )
        self.app.core.subscribe(
            "gui.shortcuts_requested",
            lambda: self._run_idle(self._on_shortcuts_requested),
        )
        self.app.core.subscribe(
            "gui.about_requested",
            lambda: self._run_idle(self._on_about_requested),
        )
        self.app.core.subscribe(
            "gui.theme_changed",
            lambda dark_theme: self._run_idle(self._on_theme_changed, dark_theme),
        )
        self.app.core.subscribe(
            "gui.percent_display_changed",
            lambda percent: self._run_idle(self._on_percent_display_changed, percent),
        )
        self.app.core.subscribe(
            "gui.default_time_changed",
            lambda default_time: self._run_idle(
                self._on_default_time_changed, default_time
            ),
        )

    def _safe_on_show_new(self) -> bool:
        """Handle show.new event in GUI main thread.

        Returns:
            Always False.
        """
        if self.app.window is not None:
            if self.app.window.live_view is not None:
                self.app.window.live_view.channels_view.flowbox.unselect_all()
                self.app.window.live_view.channels_view.last_selected_channel = ""
            if self.app.window.playback is not None:
                self.app.window.playback.update_sequence_display()
                self.app.window.playback.update_xfade_display(
                    self.app.core.lightshow.main_playback.position
                )
            self.app.window.update_channels_display(
                self.app.core.lightshow.main_playback.position
            )
            if self.app.window.header is not None:
                self.app.window.header.set_subtitle("")
            if (
                hasattr(self.app.window, "main_fader")
                and self.app.window.main_fader is not None
            ):
                self.app.window.main_fader.queue_draw()
        if self.app.tabs is not None:
            self.app.tabs.refresh_all()
        return False

    def _safe_on_show_loaded(self, _path: str) -> bool:
        """Handle show.loaded event in GUI main thread.

        Args:
            _path: Show file path.

        Returns:
            Always False.
        """
        if self.app.window is not None:
            if self.app.window.live_view is not None:
                self.app.window.live_view.channels_view.update()
                self.app.window.live_view.channels_view.flowbox.unselect_all()
                self.app.window.live_view.channels_view.last_selected_channel = ""
            if self.app.window.playback is not None:
                self.app.window.playback.update_xfade_display(0)
                self.app.window.playback.update_sequence_display()
            if self.app.window.header is not None:
                steps = self.app.core.lightshow.main_playback.steps
                if len(steps) > 1 and steps[1].cue is not None:
                    cue = steps[1].cue
                    number = cue.number
                    text = cue.text
                    subtitle = f"Mem. : 0.0 - Next Mem. : {number} {text}"
                else:
                    subtitle = ""
                self.app.window.header.set_subtitle(subtitle)
            if (
                hasattr(self.app.window, "main_fader")
                and self.app.window.main_fader is not None
            ):
                self.app.window.main_fader.queue_draw()
        if self.app.tabs is not None:
            self.app.tabs.refresh_all()
        if (
            self.app.midi
            and self.app.midi.messages
            and getattr(self.app.midi.messages, "lcd", None)
        ):
            self.app.midi.messages.lcd.show_faders()
        return False

    def _safe_on_show_imported(self) -> bool:
        """Handle show.imported event in GUI main thread.

        Returns:
            Always False.
        """
        return self._safe_on_show_loaded("")

    def _on_zoom_changed(self, level: float) -> bool:
        """Handle zoom change event in the active tab/view.

        Args:
            level: Zoom scale factor.

        Returns:
            Always False.
        """
        if not self.app.window:
            return False
        tab = self.app.window.get_active_tab()
        if not tab:
            return False

        view = None
        if isinstance(tab, (ChannelsView, PatchOutputsTab)):
            view = tab
        else:
            for child in tab.get_children():
                if isinstance(child, ChannelsView):
                    view = child

        if view:
            for flowboxchild in view.flowbox.get_children():
                flowbox_child = typing.cast(Gtk.FlowBoxChild, flowboxchild)
                child_widget = flowbox_child.get_child()
                if child_widget and isinstance(child_widget, ChannelWidget):
                    child_widget.scale = level
                    flowboxchild.queue_draw()
        return False

    def _on_tab_opened(self, tab_name: str, notebook_id: str) -> bool:
        """Handle physical tab opening.

        Args:
            tab_name: Name of tab.
            notebook_id: Notebook ID.

        Returns:
            Always False.
        """
        if not self.app.window or not self.app.tabs:
            return False

        with self.app.window.blocking_switch_page():
            app = typing.cast(typing.Any, self.app)
            mapping = {
                "patch_outputs": app.open_patch_outputs,
                "patch_channels": app.open_patch_channels,
                "track_channels": app.open_track_channels,
                "memories": app.open_memories,
                "sequences": app.open_sequences,
                "groups": app.open_groups,
                "indes": app.open_independents,
                "curves": app.open_curves,
                "faders": app.open_faders,
                "settings": app.open_settings,
                "history": app.open_history,
            }

            if tab_name in mapping:
                original_default = self.app.tabs.default_notebook_id
                self.app.tabs.default_notebook_id = notebook_id
                try:
                    mapping[tab_name]()
                finally:
                    self.app.tabs.default_notebook_id = original_default
        return False

    def _on_tab_opened_at(self, tab_name: str, notebook_id: str, index: int) -> bool:
        """Handle physical tab opening at a specific index.

        Args:
            tab_name: Name of tab.
            notebook_id: Notebook ID.
            index: Target tab index.

        Returns:
            Always False.
        """
        if not self.app.window:
            return False
        with self.app.window.blocking_switch_page():
            self._on_tab_opened(tab_name, notebook_id)
            if self.app.tabs:
                self.app.tabs.move(tab_name, notebook_id, notebook_id, index)
        return False

    def _on_tab_closed(self, tab_name: str, _notebook_id: str) -> bool:
        """Handle physical tab closing.

        Args:
            tab_name: Name of tab.
            _notebook_id: Notebook ID.

        Returns:
            Always False.
        """
        if not self.app.window:
            return False
        with self.app.window.blocking_switch_page():
            if self.app.tabs:
                self.app.tabs.close_physically(tab_name)
        return False

    def _on_active_tab_changed(self, tab_name: str, notebook_id: str) -> bool:
        """Handle active tab change event by switching active tab page.

        Args:
            tab_name: Name of tab.
            notebook_id: Notebook ID.

        Returns:
            Always False.
        """
        if not self.app.window:
            return False

        with self.app.window.blocking_switch_page():
            is_dyn = tab_name not in ("playback", "channels")
            if self.app.tabs and is_dyn and self.app.tabs.tabs[tab_name] is None:
                self._on_tab_opened(tab_name, notebook_id)
            else:
                if tab_name == "playback":
                    tab = self.app.window.playback.grid
                elif tab_name == "channels":
                    tab = self.app.window.live_view.channels_view
                else:
                    tab = self.app.tabs.tabs[tab_name] if self.app.tabs else None

                if tab:
                    parent = tab.get_parent()
                    if isinstance(parent, Gtk.Notebook):
                        page = parent.page_num(tab)
                        parent.set_current_page(page)
                        parent.grab_focus()
        return False

    def _on_tab_moved(
        self, tab_name: str, from_nb: str, to_nb: str, index: int
    ) -> bool:
        """Handle physical tab movement.

        Args:
            tab_name: Name of tab.
            from_nb: Source notebook ID.
            to_nb: Destination notebook ID.
            index: Target index.

        Returns:
            Always False.
        """
        if not self.app.window:
            return False
        with self.app.window.blocking_switch_page():
            if self.app.tabs:
                self.app.tabs.move(tab_name, from_nb, to_nb, index)
        return False

    def _on_history_changed(self, data: dict[str, bool]) -> bool:
        """Handle history changed event by refreshing history tab UI.

        Args:
            data: Dictionary containing can_undo and can_redo flags.

        Returns:
            Always False.
        """
        if undo_action := self.app.lookup_action("undo"):
            if isinstance(undo_action, Gio.SimpleAction):
                undo_action.set_enabled(data.get("can_undo", False))
        if redo_action := self.app.lookup_action("redo"):
            if isinstance(redo_action, Gio.SimpleAction):
                redo_action.set_enabled(data.get("can_redo", False))
        if not self.app.tabs:
            return False
        history_tab = self.app.tabs.tabs.get("history")
        if history_tab:
            typing.cast(HistoryTab, history_tab).refresh()
        return False

    def _on_osc_config_changed(
        self, host: str, client_port: int, server_port: int
    ) -> bool:
        """Handle OSC config change to update Settings tab if open.

        Args:
            host: OSC server host name.
            client_port: OSC client port.
            server_port: OSC server port.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            settings_tab.update_osc_config(host, client_port, server_port)
        return False

    def _on_osc_toggled(self, state: bool) -> bool:
        """Handle OSC toggle change to update Settings tab if open.

        Args:
            state: True if OSC enabled.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            settings_tab.update_osc_toggle(state)
        return False

    def _on_midi_port_toggled(self, port_name: str, enable: bool) -> bool:
        """Handle MIDI port toggle to update Settings tab if open.

        Args:
            port_name: MIDI port name.
            enable: Port enabled state.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            settings_tab.update_midi_port_toggle(port_name, enable)
        return False

    def _on_midi_port_mode_changed(self, port_name: str, mode: str) -> bool:
        """Handle MIDI port mode change to update Settings tab if open.

        Args:
            port_name: MIDI port name.
            mode: Port mode string.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            settings_tab.update_midi_port_mode(port_name, mode)
        return False

    def _on_virtual_console_requested(self) -> bool:
        """Handle request to open or present virtual console window.

        Returns:
            Always False.
        """
        if hasattr(self.app, "open_virtual_console"):
            self.app.open_virtual_console()
        return False

    def _on_fullscreen_toggle_requested(self) -> bool:
        """Handle request to toggle window full screen.

        Returns:
            Always False.
        """
        if self.app.window:
            self.app.window.fullscreen_toggle()
        return False

    def _on_shortcuts_requested(self) -> bool:
        """Handle request to open shortcuts window.

        Returns:
            Always False.
        """
        if hasattr(self.app, "open_shortcuts"):
            self.app.open_shortcuts()
        return False

    def _on_about_requested(self) -> bool:
        """Handle request to open about dialog.

        Returns:
            Always False.
        """
        if hasattr(self.app, "open_about"):
            self.app.open_about()
        return False

    def _on_theme_changed(self, dark_theme: bool) -> bool:
        """Handle application theme change event.

        Args:
            dark_theme: True if dark theme requested.

        Returns:
            Always False.
        """
        if settings := Gtk.Settings.get_default():
            settings.set_property("gtk-application-prefer-dark-theme", dark_theme)
        return False

    def _on_percent_display_changed(self, percent: bool) -> bool:
        """Handle percentage display toggle event.

        Args:
            percent: True if percentages should be displayed.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            if hasattr(settings_tab, "update_percent_ui"):
                settings_tab.update_percent_ui(percent)

        if self.app.window is not None and self.app.window.live_view:
            self.app.window.live_view.channels_view.update()

        if self.app.tabs:
            for tab_key in ("sequences", "groups", "memories"):
                tab_obj = self.app.tabs.tabs.get(tab_key)
                if tab_obj is not None:
                    channels_view = getattr(tab_obj, "channels_view", None)
                    if channels_view is not None and hasattr(channels_view, "update"):
                        channels_view.update()
        return False

    def _on_default_time_changed(self, default_time: float) -> bool:
        """Handle default cue transfer time change event.

        Args:
            default_time: Default time value in seconds.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            if hasattr(settings_tab, "update_default_time_ui"):
                settings_tab.update_default_time_ui(default_time)
        return False

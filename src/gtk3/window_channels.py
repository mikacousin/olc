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

from gi.repository import Gdk, Gtk
from olc.define import UNIVERSES
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window


class LiveView(Gtk.Notebook):
    """Live Channels View"""

    def __init__(self, window: Window, tabs: Tabs) -> None:
        self.window = window
        self.tabs = tabs
        super().__init__()
        self.set_group_name("olc")

        self.channels_view = LiveChannelsView(window, tabs)

        self.append_page(self.channels_view, Gtk.Label(label="Channels"))
        self.set_tab_reorderable(self.channels_view, True)
        self.set_tab_detachable(self.channels_view, True)

        self.connect("key_press_event", self.on_key_press_event)

    @property
    def app(self) -> Application:
        """Get parent application instance safely."""
        return self.window.app

    def update_channel_widget(self, channel: int, next_level: int) -> None:
        """Update display of channel widget

        Args:
            channel: Index of channel (from 1 to MAX_CHANNELS)
            next_level: Channel next level (from 0 to 255)
        """
        widget = self.channels_view.get_channel_widget(channel)
        if not widget:
            return
        if self.app.backend is None:
            return
        channel -= 1
        level, color_level = self.app.backend.dmx.get_composite_level(channel)

        # Apply Main Fader for visual display
        level = round(level * self.app.backend.dmx.main_fader.value)
        next_level = round(next_level * self.app.backend.dmx.main_fader.value)

        widget.color_level = color_level
        widget.level = level
        widget.next_level = next_level
        widget.queue_draw()

    def on_key_press_event(
        self, widget: Gtk.Widget, event: Gdk.EventKey
    ) -> Callable | bool | None:
        """On key press event

        Args:
            widget: Gtk Widget
            event: Gdk.EventKey

        Returns:
            function() to handle keys pressed
        """
        keyname = Gdk.keyval_name(event.keyval)
        if self.app.window is not None:
            if keyname == "Tab":
                return self.app.window.toggle_focus()
            if keyname == "ISO_Left_Tab":
                return self.app.window.move_tab()
        # Find open page in notebook to send keyboard events
        page = self.get_current_page()
        child = self.get_nth_page(page)
        if (
            self.app.tabs is not None
            and child in self.app.tabs.tabs.values()
            and child is not None
            and hasattr(child, "on_key_press_event")
        ):
            return typing.cast(typing.Any, child).on_key_press_event(widget, event)
        if self.app.window is not None:
            return self.app.window.on_key_press_event(widget, event)
        return False


class LiveChannelsView(ChannelsView):
    """Channels View"""

    def __init__(self, window: Window, tabs: Tabs) -> None:
        super().__init__(app=window.app, window=window, tabs=tabs)

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Filter channels to display

        Args:
            child: Parent of Channel Widget

        Returns:
            True or False
        """
        channel_widget = typing.cast(typing.Any, child.get_child())
        if channel_widget is None:
            return False
        channel = child.get_index() + 1
        channel_widget.next_level = self.get_next_level(channel, channel_widget)
        if self.view_mode == VIEW_MODES["Active"]:
            visible = bool(
                channel_widget.level or channel_widget.next_level or child.is_selected()
            )
            child.set_visible(visible)
            return visible

        if self.view_mode == VIEW_MODES["Patched"]:
            patched = self.app.core.lightshow.patch.is_patched(channel)
            child.set_visible(patched)
            return patched
        if not self.app.core.lightshow.patch.is_patched(channel):
            channel_widget.level = 0
        child.set_visible(True)
        return True

    def get_next_level(self, channel: int, channel_widget: Gtk.Widget) -> int:
        """Get Channel next level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            channel_widget: Channel widget

        Returns:
            Channel next level (0 - 255)
        """
        position = self.app.core.lightshow.main_playback.position
        if (
            self.app.core.lightshow.main_playback.last > 1
            and position < self.app.core.lightshow.main_playback.last - 1
            and self.app.core.lightshow.main_playback.last
            <= len(self.app.core.lightshow.main_playback.steps)
        ):
            cue = self.app.core.lightshow.main_playback.steps[position + 1].cue
            next_level = cue.channels.get(channel, 0) if cue is not None else 0
        elif self.app.core.lightshow.main_playback.last:
            cue = self.app.core.lightshow.main_playback.steps[0].cue
            next_level = cue.channels.get(channel, 0) if cue is not None else 0
        else:
            next_level = typing.cast(typing.Any, channel_widget).level
        return next_level

    def set_channel_level(self, channel: int, level: int) -> None:
        """Set channel level using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.set_level", channel, level)

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change patched channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down
        """
        if self.app.backend is None:
            return
        level = 0
        channels = self.get_selected_channels()
        for channel in channels:
            if not self.app.core.lightshow.patch.is_patched(channel):
                continue
            for output in self.app.core.lightshow.patch.channels[channel]:
                out = output[0]
                univ = output[1]
                if out is not None and univ is not None:
                    index = UNIVERSES.index(univ)
                    level = self.app.backend.dmx.frame[index][out - 1]
                    if direction == Gdk.ScrollDirection.UP:
                        self.app.backend.dmx.levels["user"][channel - 1] = min(
                            level + step, 255
                        )
                    elif direction == Gdk.ScrollDirection.DOWN:
                        self.app.backend.dmx.levels["user"][channel - 1] = max(
                            level - step, 0
                        )
            next_level = self.app.core.lightshow.main_playback.get_next_channel_level(
                channel, level
            )
            if self.app.window is not None:
                self.app.window.live_view.update_channel_widget(channel, next_level)
        self.app.backend.dmx.set_levels()

    def select_channel(self) -> None:
        """Select one channel using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.select_active")

    def select_plus(self) -> None:
        """Add channel to selection using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.select_add")

    def select_thru(self) -> None:
        """Select Channel Thru using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.select_thru")

    def select_minus(self) -> None:
        """Remove channel from selection using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.select_remove")

    def select_all(self) -> None:
        """Select all active channels using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.select_all")

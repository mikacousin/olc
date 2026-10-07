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
"""GUI event bridge handler for channel levels and selection."""

from __future__ import annotations

import typing

from .base import BaseEventBridgeHandler

if typing.TYPE_CHECKING:
    from olc.gtk3.track_channels import TrackChannelsTab


# pylint: disable=too-few-public-methods
class ChannelBridgeHandler(BaseEventBridgeHandler):
    """Handles channel level changes and selection synchronization to GUI."""

    def register(self) -> None:
        """Subscribe to Core events for channel levels and selection."""
        self.app.core.subscribe(
            "channel.level_changed",
            lambda c, level: self._run_idle(self._on_channel_level_ui, c, level),
        )
        self.app.core.subscribe(
            "channels.selected_changed",
            lambda selected: self._run_idle(
                self._on_channels_selected_changed, selected
            ),
        )
        self.app.core.subscribe(
            "show.user_levels_reset",
            lambda: self._run_idle(self._on_user_levels_reset),
        )
        self.app.core.subscribe(
            "show.user_levels_restored",
            lambda: self._run_idle(self._on_user_levels_reset),
        )

    def _on_channel_level_ui(self, channel: int, level: int) -> bool:
        """Safely update a channel widget in the GTK main thread.

        Args:
            channel: Channel number.
            level: DMX level.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.update_channel_widget(channel, level)
        return False

    def _on_channels_selected_changed(self, selected_channels: list[int]) -> bool:
        """Synchronize the logical channel selection to the GUI's FlowBox."""
        if self.app.window and self.app.window.live_view:
            channels_view = self.app.window.live_view.channels_view
            channels_view.sync_selection_to_gui(selected_channels)

            # Update Track Channels if opened
            if self.app.tabs and self.app.tabs.tabs.get("track_channels") is not None:
                track_channels = typing.cast(
                    "TrackChannelsTab", self.app.tabs.tabs["track_channels"]
                )
                track_channels.update_display()
        return False

    def _on_user_levels_reset(self) -> bool:
        """Handle user levels reset event to refresh channels view."""
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.channels_view.update()
        return False

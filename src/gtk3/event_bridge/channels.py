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

from olc.gtk3.widgets.channels_view import VIEW_MODES

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
            lambda c, _lvl=None: self._run_idle(self._on_channel_level_ui, c),
        )
        self.app.core.subscribe(
            "channels.updated",
            lambda channels: self._run_idle(self._on_channels_updated_ui, channels),
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
        self.app.core.subscribe(
            "device.parameters_changed",
            lambda channels: self._run_idle(self._on_device_changed_ui, channels),
        )
        self.app.core.subscribe(
            "device.color_changed",
            lambda channels, _color=None: self._run_idle(
                self._on_device_changed_ui, channels
            ),
        )
        self.app.core.subscribe(
            "palette.applied",
            lambda _cat, _num, channels: self._run_idle(
                self._on_device_changed_ui, channels
            ),
        )
        self.app.core.subscribe(
            "palette.renamed",
            lambda *_args: self._run_idle(self._on_palette_metadata_changed_ui),
        )
        self.app.core.subscribe(
            "palette.updated",
            lambda *_args: self._run_idle(self._on_palette_metadata_changed_ui),
        )
        self.app.core.subscribe(
            "palette.deleted",
            lambda *_args: self._run_idle(self._on_palette_metadata_changed_ui),
        )
        self.app.core.subscribe(
            "palettes.changed",
            lambda *_args: self._run_idle(self._on_palette_metadata_changed_ui),
        )
        self.app.core.subscribe(
            "effect.applied",
            lambda _num, channels: self._run_idle(self._on_device_changed_ui, channels),
        )
        self.app.core.subscribe(
            "effect.stopped",
            lambda _num, channels: self._run_idle(self._on_device_changed_ui, channels),
        )
        self.app.core.subscribe(
            "effect.changed",
            lambda *_args: self._run_idle(self._on_palette_metadata_changed_ui),
        )
        self.app.core.subscribe(
            "live.state_changed",
            lambda channels=None: self._run_idle(
                self._on_device_changed_ui, channels or []
            ),
        )
        self.app.core.subscribe(
            "park.channel_parked",
            lambda ch, _lvl=None: self._run_idle(self._on_channel_level_ui, ch),
        )
        self.app.core.subscribe(
            "park.channel_unparked",
            lambda ch: self._run_idle(self._on_channel_level_ui, ch),
        )
        self.app.core.subscribe(
            "park.changed",
            lambda *_args: self._run_idle(self._on_park_changed_ui),
        )

    def _on_device_changed_ui(self, channels: list[int]) -> bool:
        """Queue affected channel widgets for ~30 fps coalesced redraw."""
        if self.app.window and self.app.window.live_view:
            channels_view = self.app.window.live_view.channels_view
            channels_view.mark_channels_dirty(channels or [])
            if channels_view.view_mode == VIEW_MODES["Manual"]:
                channels_view.refresh_filter()
        return False

    def _on_palette_metadata_changed_ui(self) -> bool:
        """Invalidate snapshots and coalesce redraw on palette label/edit."""
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.channels_view.mark_channels_dirty(None)
        if self.app.tabs:
            for tab_key in ("sequences",):
                tab_obj = self.app.tabs.tabs.get(tab_key)
                if tab_obj is not None:
                    cv = getattr(tab_obj, "channels_view", None)
                    if cv is not None and hasattr(cv, "mark_channels_dirty"):
                        cv.mark_channels_dirty(None)
        return False

    def _on_park_changed_ui(self) -> bool:
        """Invalidate snapshots and coalesce redraw on bulk park/unpark."""
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.channels_view.mark_channels_dirty(None)
        return False

    def _on_channel_level_ui(self, channel: int) -> bool:
        """Safely update a channel widget in the GTK main thread.

        Args:
            channel: Channel number.

        Returns:
            Always False (required for GLib.idle_add to remove the callback).
        """
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.update_channel_widget(channel, coalesce=True)
            channels_view = self.app.window.live_view.channels_view
            if channels_view.view_mode in (VIEW_MODES["Active"], VIEW_MODES["Manual"]):
                channels_view.refresh_filter()
        return False

    def _on_channels_updated_ui(self, channels: list[int]) -> bool:
        """Batch update channel widgets in the GTK main thread."""
        if self.app.window and self.app.window.live_view:
            live_view = self.app.window.live_view
            channels_view = live_view.channels_view
            curr_res, prev_res, next_lvls = channels_view.get_frame_tracking_context()
            is_active_mode = channels_view.view_mode == VIEW_MODES["Active"]
            is_manual_mode = channels_view.view_mode == VIEW_MODES["Manual"]
            filter_dirty = bool(is_manual_mode and channels)
            for ch in channels or []:
                old_active = False
                if is_active_mode:
                    w_old = channels_view.get_channel_widget(ch)
                    if w_old is not None:
                        old_active = bool(w_old.level or w_old.next_level)
                next_lvl = (
                    float(next_lvls[ch - 1])
                    if next_lvls is not None and 1 <= ch <= len(next_lvls)
                    else None
                )
                live_view.update_channel_widget(
                    ch,
                    next_level=next_lvl,
                    coalesce=True,
                    resolved_step=curr_res,
                    prev_resolved=prev_res,
                )
                if is_active_mode:
                    w_new = channels_view.get_channel_widget(ch)
                    if w_new is not None:
                        new_active = bool(w_new.level or w_new.next_level)
                        if new_active != old_active:
                            filter_dirty = True
            if filter_dirty:
                channels_view.refresh_filter()
            if self.app.tabs and self.app.tabs.tabs.get("track_channels") is not None:
                track_channels = typing.cast(
                    "TrackChannelsTab", self.app.tabs.tabs["track_channels"]
                )
                track_channels.update_display()
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

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

from gi.repository import Gdk, Gtk

from olc.core.channel_snapshot import build_live_channel_snapshot
from olc.core.tracking import TrackingEngine, classify_channel_tracking_state
from olc.define import MAX_CHANNELS, is_int
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    from olc.core.channel_snapshot import ChannelDisplaySnapshot
    from olc.core.tracking import ResolvedState
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window


class LiveView(Gtk.Notebook):
    """Live Channels View"""

    channels_view: LiveChannelsView

    def __init__(self, window: Window, tabs: Tabs) -> None:
        self.window = window
        self.tabs = tabs
        super().__init__()
        self.set_group_name("olc")
        self.set_scrollable(True)

        self.channels_view = LiveChannelsView(window, tabs)

        self.append_page(self.channels_view, Gtk.Label(label="Channels"))
        self.set_tab_reorderable(self.channels_view, True)
        self.set_tab_detachable(self.channels_view, True)

    @property
    def app(self) -> Application:
        """Get parent application instance safely."""
        return self.window.app

    def update_channel_widget(
        self,
        channel: int,
        next_level: float | None = None,
        *,
        coalesce: bool = True,
        resolved_step: ResolvedState | None = None,
        prev_resolved: ResolvedState | None = None,
    ) -> None:
        """Update display state of one channel widget.

        Widget ``level``, ``color_level``, and ``next_level`` are updated
        synchronously; Cairo redraws and snapshot rebuilds are coalesced via
        ``mark_channels_dirty`` unless ``coalesce=False``.

        Args:
            channel: Channel number (from 1 to MAX_CHANNELS).
            next_level: Normalized level in next cue, or None to query core.
            coalesce: Queue redraw through ~30 fps coalescer when True.
            resolved_step: Optional pre-resolved current step state.
            prev_resolved: Optional pre-resolved previous step state.
        """
        widget = self.channels_view.get_channel_widget(channel)
        if not widget:
            return
        if self.app.core.backend is None:
            return
        channel_idx = channel - 1
        level, color_level = self.app.core.get_channel_composite_level(
            channel_idx,
            curr_resolved=resolved_step,
            prev_resolved=prev_resolved,
        )

        main_fader_val = self.app.core.get_main_fader_value()
        gm_exempt_arr = getattr(
            getattr(self.app.core.backend, "dmx", None), "levels", {}
        ).get("faders_gm_exempt")
        gm_lvl = (
            float(gm_exempt_arr[channel_idx])
            if gm_exempt_arr is not None and 0 <= channel_idx < len(gm_exempt_arr)
            else 0.0
        )
        level = max(level * main_fader_val, gm_lvl)
        if next_level is None:
            main_pb = self._get_main_sequence()
            if main_pb is not None and hasattr(main_pb, "get_next_channel_level"):
                _, seq_lvl = classify_channel_tracking_state(
                    main_pb,
                    getattr(main_pb, "position", 0),
                    channel,
                    curr_resolved=resolved_step,
                    prev_resolved=prev_resolved,
                )
                next_level = main_pb.get_next_channel_level(channel, seq_lvl)
            else:
                next_level = 0.0
        next_level = float(next_level) * main_fader_val

        widget.color_level = color_level
        widget.level = level
        widget.next_level = next_level
        self.channels_view.invalidate_channel_snapshot(channel)
        if coalesce:
            self.channels_view.mark_channels_dirty([channel])
        else:
            widget.queue_draw()

    def _get_main_sequence(self) -> typing.Any:  # noqa: ANN401
        """Return the active Main Sequence from PlaybackEngine (fallback Seq 1)."""
        engine = getattr(self.app.core, "playback_engine", None)
        if engine is not None:
            seq = engine.main_sequence
            if seq is not None:
                return seq
        return getattr(self.app.core.lightshow, "main_playback", None)

    def refresh_all_channels(self, step: int | None = None) -> None:
        """Synchronize all channel widgets using one shared step resolution."""
        from olc.core.tracking import (  # pylint: disable=import-outside-toplevel
            get_tracking_color,
        )

        main_pb = self._get_main_sequence()
        if main_pb is None:
            return
        patch = getattr(self.app.core.lightshow, "patch", None)
        pos = getattr(main_pb, "position", 0)
        target_step = pos if step is None else int(step)
        steps = getattr(main_pb, "steps", ())
        tracking_mode = bool(getattr(main_pb, "tracking_mode", False))

        curr_resolved: ResolvedState | None = None
        prev_resolved: ResolvedState | None = None
        if isinstance(steps, list) and 0 <= target_step < len(steps):
            curr_resolved = TrackingEngine.resolve_step_state(
                main_pb, target_step, tracking_mode=tracking_mode, patch=patch
            )
        if isinstance(steps, list) and target_step > 1 and target_step - 1 < len(steps):
            prev_resolved = TrackingEngine.resolve_step_state(
                main_pb, target_step - 1, tracking_mode=tracking_mode, patch=patch
            )

        all_next_levels: list[float] | None = None
        if hasattr(main_pb, "get_all_next_channel_levels"):
            all_next_levels = main_pb.get_all_next_channel_levels()

        main_fader_val = self.app.core.get_main_fader_value()
        has_backend = self.app.core.backend is not None
        gm_exempt_arr = (
            getattr(getattr(self.app.core.backend, "dmx", None), "levels", {}).get(
                "faders_gm_exempt"
            )
            if has_backend
            else None
        )

        for channel in range(1, MAX_CHANNELS + 1):
            state, level = classify_channel_tracking_state(
                main_pb,
                target_step,
                channel,
                curr_resolved=curr_resolved,
                prev_resolved=prev_resolved,
            )
            color_level = get_tracking_color(state)
            if (step is None or target_step == pos) and has_backend:
                comp_level, comp_color = self.app.core.get_channel_composite_level(
                    channel - 1,
                    curr_resolved=curr_resolved,
                    prev_resolved=prev_resolved,
                )
                if (
                    step is None
                    or comp_level > 0.0
                    or self.app.core.get_user_channel_level(channel - 1) >= 0.0
                ):
                    level = comp_level
                    color_level = comp_color
            gm_lvl = (
                float(gm_exempt_arr[channel - 1])
                if gm_exempt_arr is not None
                and 1 <= channel <= len(gm_exempt_arr)
                and (step is None or target_step == pos)
                else 0.0
            )
            level = max(float(level) * main_fader_val, gm_lvl)
            if all_next_levels is not None and 1 <= channel <= len(all_next_levels):
                next_lvl = float(all_next_levels[channel - 1]) * main_fader_val
            else:
                next_lvl = float(level)

            widget = self.channels_view.get_channel_widget(channel)
            if widget is not None:
                widget.color_level = color_level
                widget.level = level
                widget.next_level = next_lvl

        self.channels_view.mark_channels_dirty(None, invalidate_step=True)
        if self.channels_view.view_mode in (VIEW_MODES["Active"], VIEW_MODES["Manual"]):
            self.channels_view.refresh_filter()


class LiveChannelsView(ChannelsView):
    """Live Channels View with frame-level snapshot cache."""

    is_live_view: bool = True
    _batch_next_levels: list[float] | None = None

    def __init__(self, window: Window, tabs: Tabs) -> None:
        self._batch_next_levels = None
        self._frame_step_key: tuple[float, int, bool, bool, int] | None = None
        self._frame_resolved_step: ResolvedState | None = None
        self._frame_prev_resolved: ResolvedState | None = None
        self._frame_next_levels: list[float] | None = None
        super().__init__(app=window.app, window=window, tabs=tabs)

    def _get_main_sequence(self) -> typing.Any:  # noqa: ANN401
        """Return the active Main Sequence from PlaybackEngine (fallback Seq 1)."""
        engine = getattr(self.app.core, "playback_engine", None)
        if engine is not None:
            seq = engine.main_sequence
            if seq is not None:
                return seq
        return getattr(self.app.core.lightshow, "main_playback", None)

    def _invalidate_step_cache(self) -> None:
        self._frame_step_key = None
        self._frame_resolved_step = None
        self._frame_prev_resolved = None
        self._frame_next_levels = None
        self._batch_next_levels = None

    def get_frame_tracking_context(
        self,
    ) -> tuple[ResolvedState | None, ResolvedState | None, list[float] | None]:
        """Resolve and cache step states once per frame across all visible channels."""
        main_pb = self._get_main_sequence()
        if main_pb is None:
            return None, None, None
        steps = getattr(main_pb, "steps", None)
        if not isinstance(steps, list) or not steps:
            return None, None, None
        pos = int(getattr(main_pb, "position", 0))
        tracking_mode = bool(getattr(main_pb, "tracking_mode", False))
        mib_enabled = bool(getattr(main_pb, "mib_enabled", True))
        seq_idx = float(getattr(main_pb, "index", 1.0))
        key = (seq_idx, pos, tracking_mode, mib_enabled, len(steps))
        if self._frame_step_key != key:
            patch = getattr(self.app.core.lightshow, "patch", None)
            if 0 <= pos < len(steps):
                self._frame_resolved_step = TrackingEngine.resolve_step_state(
                    main_pb, pos, tracking_mode=tracking_mode, patch=patch
                )
            else:
                self._frame_resolved_step = None
            if pos > 1 and pos - 1 < len(steps):
                self._frame_prev_resolved = TrackingEngine.resolve_step_state(
                    main_pb, pos - 1, tracking_mode=tracking_mode, patch=patch
                )
            else:
                self._frame_prev_resolved = None
            self._frame_next_levels = (
                main_pb.get_all_next_channel_levels()
                if hasattr(main_pb, "get_all_next_channel_levels")
                else None
            )
            self._frame_step_key = key
        return (
            self._frame_resolved_step,
            self._frame_prev_resolved,
            self._frame_next_levels,
        )

    def get_channel_snapshot(self, channel: int) -> ChannelDisplaySnapshot | None:
        """Return cached or freshly built live ChannelDisplaySnapshot for *channel*."""
        if not 1 <= channel <= MAX_CHANNELS:
            return None
        cached = self._snapshot_cache.get(channel)
        if cached is not None:
            return cached
        curr_res, prev_res, next_lvls = self.get_frame_tracking_context()
        snap = build_live_channel_snapshot(
            self.app.core,
            channel,
            resolved_step=curr_res,
            prev_resolved=prev_res,
            next_levels=next_lvls,
        )
        self._snapshot_cache[channel] = snap
        return snap

    def update(self) -> None:
        """Update channels display with batched next cue levels."""
        self.invalidate_all_snapshots()
        _, _, next_lvls = self.get_frame_tracking_context()
        self._batch_next_levels = next_lvls
        try:
            super().update()
        finally:
            self._batch_next_levels = None

    def is_manual_channel(self, channel: int) -> bool:
        """Return True if *channel* has a manual live intensity or attribute edit."""
        if not 1 <= channel <= MAX_CHANNELS:
            return False
        if self.app.core.get_user_channel_level(channel - 1) >= 0.0:
            return True
        live_state = getattr(self.app.core, "live_state", None)
        return bool(live_state is not None and live_state.is_channel_manual(channel))

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
        if self.view_mode == VIEW_MODES["Devices"]:
            visible = self.is_device_channel(channel)
            child.set_visible(visible)
            return visible
        if self.view_mode == VIEW_MODES["Selected"]:
            visible = self.is_selected_channel(channel, child)
            child.set_visible(visible)
            return visible
        if self.view_mode == VIEW_MODES["Manual"]:
            visible = self.is_manual_channel(channel)
            child.set_visible(visible)
            return visible
        if not self.app.core.lightshow.patch.is_patched(channel):
            channel_widget.level = 0
        child.set_visible(True)
        return True

    def get_next_level(self, channel: int, channel_widget: Gtk.Widget) -> float:
        """Get Channel next level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            channel_widget: Channel widget

        Returns:
            Channel next normalized level (0.0 - 1.0)
        """
        if self._batch_next_levels is not None and 1 <= channel <= len(
            self._batch_next_levels
        ):
            return float(self._batch_next_levels[channel - 1])
        current_level = float(typing.cast(typing.Any, channel_widget).level)
        main_pb = self._get_main_sequence()
        if main_pb is None:
            return 0.0
        return main_pb.get_next_channel_level(channel, current_level)

    def set_channel_level(self, channel: int, level: int | float) -> None:
        """Set channel level using the unified core ActionRegistry."""
        self.app.core.action_registry.execute("channel.set_level", channel, level)

    def at_level(self) -> None:
        """Channels at level using the unified core ActionRegistry."""
        if not self.settings:
            return
        keystring = self.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if self.settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        channels_dict = {channel: level for channel in channels}
        if channels_dict:
            self.app.core.action_registry.execute(
                "channel.set_multi_levels", channels_dict
            )

    def level_plus(self) -> None:
        """Channels +% using the unified core ActionRegistry."""
        if not self.settings:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                channels_dict[channel] = new_level
        if channels_dict:
            self.app.core.action_registry.execute(
                "channel.set_multi_levels", channels_dict
            )

    def level_minus(self) -> None:
        """Channels -% using the unified core ActionRegistry."""
        if not self.settings:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                channels_dict[channel] = new_level
        if channels_dict:
            self.app.core.action_registry.execute(
                "channel.set_multi_levels", channels_dict
            )

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change patched channels level with a wheel using the unified core
        ActionRegistry.

        Args:
            step: Step level
            direction: Up or Down
        """
        if self.app.core.backend is None:
            return
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if not self.app.core.lightshow.patch.is_patched(channel):
                continue
            level = None
            dev = self.app.core.lightshow.patch.get_device(channel)
            if dev is not None:
                patch_universes = self.app.core.lightshow.patch.universes
                for ch in dev.channels:
                    out = ch.address
                    univ = ch.universe
                    if univ in patch_universes:
                        index = patch_universes.index(univ)
                        level = self.app.core.get_dmx_frame_level(index, out - 1)
            if level is not None:
                if direction == Gdk.ScrollDirection.UP:
                    new_level = min(level + step, 255)
                elif direction == Gdk.ScrollDirection.DOWN:
                    new_level = max(level - step, 0)
                else:
                    continue
                channels_dict[channel] = new_level
        if channels_dict:
            self.app.core.action_registry.execute(
                "channel.set_multi_levels", channels_dict
            )

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

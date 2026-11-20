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
"""Channels view for the Sequence playback tab."""

from __future__ import annotations

import time
import typing
from typing import Optional

from gi.repository import Gdk, Gtk

from olc.core.channel_snapshot import build_step_channel_snapshot
from olc.core.tracking import (
    TrackingEngine,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.define import MAX_CHANNELS, is_int
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView

if typing.TYPE_CHECKING:
    from olc.core.channel_snapshot import ChannelDisplaySnapshot
    from olc.core.tracking import ResolvedState
    from olc.gtk3.application import Application
    from olc.gtk3.sequence import SequenceTab
    from olc.gtk3.widgets.channel import ChannelWidget
    from olc.show.sequence import Sequence


class SeqChannelsView(ChannelsView):
    """Channels View isolated to the selected Sequence step."""

    is_live_view: bool = False

    def __init__(self, app: Application) -> None:
        self._cache_time: float = 0.0
        self._cached_sequence: Sequence | None = None
        self._cached_step: int | None = None
        self._cached_resolved_step: ResolvedState | None = None
        self._cached_prev_resolved: ResolvedState | None = None
        self._snapshot_step_key: tuple[float, int, bool, bool, int] | None = None
        super().__init__(app=app)

    def _invalidate_step_cache(self) -> None:
        self._cache_time = 0.0
        self._cached_resolved_step = None
        self._cached_prev_resolved = None
        self._snapshot_step_key = None

    def _get_cached_selection(self) -> tuple[Optional[Sequence], Optional[int]]:
        """Get cached selected sequence and step to avoid heavy GTK calls."""
        now = time.time()
        if now - self._cache_time > 0.05:
            if self.tabs is not None and self.tabs.tabs.get("sequences") is not None:
                tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
                seq = tab.get_selected_sequence()
                step = tab.get_selected_step()
            else:
                seq = None
                step = None
            self._cached_sequence = seq
            self._cached_step = step
            self._cache_time = now
            self._refresh_resolved_step_cache(seq, step)
        return self._cached_sequence, self._cached_step

    def _refresh_resolved_step_cache(
        self, seq: Optional[Sequence], step: Optional[int]
    ) -> tuple[ResolvedState | None, ResolvedState | None]:
        """Resolve step states once when selection or tracking flags change."""
        if (
            seq is None
            or step is None
            or step < 0
            or step >= len(getattr(seq, "steps", ()))
            or self.lightshow is None
        ):
            self._cached_resolved_step = None
            self._cached_prev_resolved = None
            self._snapshot_step_key = None
            return None, None
        key = (
            float(seq.index),
            int(step),
            bool(getattr(seq, "tracking_mode", False)),
            bool(getattr(seq, "mib_enabled", True)),
            len(seq.steps),
        )
        if self._snapshot_step_key != key:
            patch = getattr(self.lightshow, "patch", None)
            tracking_mode = bool(getattr(seq, "tracking_mode", False))
            self._cached_resolved_step = TrackingEngine.resolve_step_state(
                seq, step, tracking_mode=tracking_mode, patch=patch
            )
            if step > 1:
                self._cached_prev_resolved = TrackingEngine.resolve_step_state(
                    seq, step - 1, tracking_mode=tracking_mode, patch=patch
                )
            else:
                self._cached_prev_resolved = None
            self._snapshot_cache.clear()
            self._snapshot_step_key = key
        return self._cached_resolved_step, self._cached_prev_resolved

    def get_channel_snapshot(self, channel: int) -> ChannelDisplaySnapshot | None:
        """Build or retrieve an isolated snapshot for *channel* at selected step."""
        if self.lightshow is None or not 1 <= channel <= MAX_CHANNELS:
            return None
        sequence, step = self._get_cached_selection()
        if sequence is None or step is None or step < 0 or step >= len(sequence.steps):
            return None
        curr_res, prev_res = self._refresh_resolved_step_cache(sequence, step)
        cached = self._snapshot_cache.get(channel)
        if cached is not None:
            return cached
        cue = sequence.steps[step].cue
        override_level: float | None = None
        if cue is not None:
            raw_override = self.lightshow.cues.cue_editor.get_levels(
                cue.number, cue.sequence
            )[channel - 1]
            if raw_override >= 0.0:
                override_level = float(raw_override)
        snap = build_step_channel_snapshot(
            self.lightshow,
            sequence,
            step,
            channel,
            resolved_step=curr_res,
            prev_resolved=prev_res,
            override_level=override_level,
        )
        self._snapshot_cache[channel] = snap
        return snap

    def set_channel_level(self, channel: int, level: int | float) -> None:
        """Set channel level"""
        if self.tabs is not None:
            tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
            seq = tab.get_selected_sequence()
            step_idx = tab.get_selected_step()
            if seq and step_idx is not None:
                step = seq.steps[step_idx]
                if step.cue and self.window is not None:
                    self.window.app.core.action_registry.execute(
                        "cue.set_temp_channels",
                        step.cue.number,
                        step.cue.sequence,
                        {channel: level},
                    )

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel using a group action."""
        if self.tabs is None or self.lightshow is None or self.window is None:
            return
        tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step_obj = seq.steps[step_idx]
        if step_obj.cue is None:
            return

        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if direction == Gdk.ScrollDirection.UP:
                    level = min(level + step, 255)
                elif direction == Gdk.ScrollDirection.DOWN:
                    level = max(level - step, 0)
                channels_dict[channel] = level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step_obj.cue.number,
                step_obj.cue.sequence,
                channels_dict,
            )

    def at_level(self) -> None:
        """Channels at level using a group action."""
        if (
            not self.window
            or not self.settings
            or self.tabs is None
            or self.lightshow is None
        ):
            return
        tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step = seq.steps[step_idx]
        if step.cue is None:
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
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step.cue.number,
                step.cue.sequence,
                channels_dict,
            )

    def level_plus(self) -> None:
        """Channels +% using a group action."""
        if (
            not self.settings
            or self.tabs is None
            or self.lightshow is None
            or self.window is None
        ):
            return
        tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step = seq.steps[step_idx]
        if step.cue is None:
            return

        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                channels_dict[channel] = new_level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step.cue.number,
                step.cue.sequence,
                channels_dict,
            )

    def level_minus(self) -> None:
        """Channels -% using a group action."""
        if (
            not self.settings
            or self.tabs is None
            or self.lightshow is None
            or self.window is None
        ):
            return
        tab = typing.cast("SequenceTab", self.tabs.tabs["sequences"])
        seq = tab.get_selected_sequence()
        step_idx = tab.get_selected_step()
        if seq is None or step_idx is None:
            return
        step = seq.steps[step_idx]
        if step.cue is None:
            return

        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        channels_dict = {}
        for channel in channels:
            if channel_widget := self.get_channel_widget(channel):
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                channels_dict[channel] = new_level

        if channels_dict:
            self.window.app.core.action_registry.execute(
                "cue.set_temp_channels",
                step.cue.number,
                step.cue.sequence,
                channels_dict,
            )

    def is_manual_channel(self, channel: int) -> bool:
        """Return True if *channel* has an uncommitted cue-editor override on step."""
        if self.lightshow is None or not 1 <= channel <= MAX_CHANNELS:
            return False
        sequence, step = self._get_cached_selection()
        if sequence is None or step is None or not 0 <= step < len(sequence.steps):
            return False
        cue = sequence.steps[step].cue
        if cue is None:
            return False
        return (
            self.lightshow.cues.cue_editor.get_levels(cue.number, cue.sequence)[
                channel - 1
            ]
            >= 0.0
        )

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Filter channels to display and apply tracking color coding."""
        if not self.tabs or not self.tabs.tabs["sequences"]:
            child.set_visible(False)
            return False
        sequence, step = self._get_cached_selection()
        if not sequence or step is None or step >= len(sequence.steps) or step < 0:
            child.set_visible(False)
            return False
        channel = child.get_index() + 1
        curr_res, prev_res = self._refresh_resolved_step_cache(sequence, step)
        tracking_state, resolved_level = classify_channel_tracking_state(
            sequence,
            step,
            channel,
            curr_resolved=curr_res,
            prev_resolved=prev_res,
        )
        widget = child.get_child()
        if widget is not None:
            channel_widget = typing.cast("ChannelWidget", widget)
            channel_widget.color_level = get_tracking_color(tracking_state)

        cue = sequence.steps[step].cue
        if getattr(sequence, "tracking_mode", False):
            channel_level = resolved_level
        else:
            channel_level = cue.channels.get(channel, 0) if cue is not None else 0

        if self.view_mode == VIEW_MODES["Active"]:
            return self._filter_active(child, channel_level)
        if self.view_mode == VIEW_MODES["Patched"]:
            return self._filter_patched(child, channel_level)
        if self.view_mode == VIEW_MODES["Devices"] and not self.is_device_channel(
            channel
        ):
            child.set_visible(False)
            return False
        if self.view_mode == VIEW_MODES["Selected"] and not self.is_selected_channel(
            channel, child
        ):
            child.set_visible(False)
            return False
        if self.view_mode == VIEW_MODES["Manual"] and not self.is_manual_channel(
            channel
        ):
            child.set_visible(False)
            return False
        return self._filter_all(child, channel_level)

    def _filter_active(
        self, child: Gtk.FlowBoxChild, channel_level: int | float
    ) -> bool:
        """Filter in Active mode"""
        channel_index = child.get_index()
        widget = child.get_child()
        if widget is None:
            return False
        channel_widget = typing.cast("ChannelWidget", widget)
        assert self.tabs is not None
        assert self.lightshow is not None

        seq, step_idx = self._get_cached_selection()
        if seq and step_idx is not None:
            cue = seq.steps[step_idx].cue
            if cue:
                user_channel = self.lightshow.cues.cue_editor.get_levels(
                    cue.number, cue.sequence
                )[channel_index]
            else:
                user_channel = -1
        else:
            user_channel = -1

        if channel_level or child.is_selected():
            if user_channel == -1:
                channel_widget.level = channel_level
                channel_widget.next_level = channel_level
            else:
                channel_widget.level = user_channel
                channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        if user_channel != -1:
            channel_widget.level = user_channel
            channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(False)
        return False

    def _filter_patched(
        self, child: Gtk.FlowBoxChild, channel_level: int | float
    ) -> bool:
        """Filter in Patched mode"""
        channel = child.get_index() + 1
        assert self.lightshow is not None
        if not self.lightshow.patch.is_patched(channel):
            child.set_visible(False)
            return False
        return self._filter_all(child, channel_level)

    def _filter_all(self, child: Gtk.FlowBoxChild, channel_level: int | float) -> bool:
        """Filter in All channels mode"""
        channel_index = child.get_index()
        widget = child.get_child()
        if widget is None:
            return False
        channel_widget = typing.cast("ChannelWidget", widget)
        assert self.tabs is not None
        assert self.lightshow is not None

        seq, step_idx = self._get_cached_selection()
        if seq and step_idx is not None:
            cue = seq.steps[step_idx].cue
            if cue:
                user_channel = self.lightshow.cues.cue_editor.get_levels(
                    cue.number, cue.sequence
                )[channel_index]
            else:
                user_channel = -1
        else:
            user_channel = -1

        if channel_level or child.is_selected():
            if user_channel == -1:
                channel_widget.level = channel_level
                channel_widget.next_level = channel_level
            else:
                channel_widget.level = user_channel
                channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        if user_channel != -1:
            channel_widget.level = user_channel
            channel_widget.next_level = user_channel
            child.set_visible(True)
            return True
        channel_widget.level = 0
        channel_widget.next_level = 0
        child.set_visible(True)
        return True


__all__ = ["SeqChannelsView"]

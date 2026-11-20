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
from typing import Any, Callable, Iterable, Optional

from gi.repository import Gdk, GLib, Gtk

from olc.core.selection import (
    SelectActiveAction,
    SelectAddAction,
    SelectAllAction,
    SelectionManager,
    SelectNoneAction,
    SelectRemoveAction,
    SelectThruAction,
)
from olc.define import MAX_CHANNELS, is_int, is_non_nul_int
from olc.devices.channel import ChannelType
from olc.gtk3.widgets.channel import ChannelWidget
from olc.gtk3.widgets.channels_table_view import (
    ChannelsTableView,
    normalize_expand_family,
)

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.channel_snapshot import ChannelDisplaySnapshot
    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow

VIEW_MODES: dict[str, int] = {
    "All": 0,
    "Patched": 1,
    "Active": 2,
    "Devices": 3,
    "Selected": 4,
    "Manual": 5,
}
DISPLAY_FORMATS: tuple[str, ...] = ("Compact", "Summary+", "Table")
READOUT_MODES: tuple[str, ...] = ("Auto", "Label", "Ref", "Percent", "DMX")
REDRAW_COALESCE_INTERVAL_MS: int = 33


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class ChannelsView(Gtk.Box):
    """Channels view

    This class must be subclassed and filter_channels, wheel_level, set_channel_level
    implemented
    """

    is_live_view: bool = False
    view_mode: int
    display_format: str
    readout_mode: str
    show_labels: bool
    last_selected_channel: str
    header: Gtk.HeaderBar
    format_combo: Gtk.ComboBoxText
    readout_combo: Gtk.ComboBoxText
    labels_btn: Gtk.ToggleButton
    expand_box: Gtk.Box
    expand_focus_btn: Gtk.ToggleButton
    expand_color_btn: Gtk.ToggleButton
    expand_beam_btn: Gtk.ToggleButton
    combo: Gtk.ComboBoxText
    content_stack: Gtk.Stack
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox
    table_view: ChannelsTableView
    app: Application
    window: Window | None
    commandline: CoreCommandLine
    lightshow: LightShow | None
    settings: Gio.Settings | None
    tabs: Tabs | None
    updating_selection: bool
    selection_manager: SelectionManager

    def __init__(
        self,
        app: Application,
        *args: Any,  # noqa: ANN401
        window: Window | None = None,
        tabs: Tabs | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        kwargs.setdefault("orientation", Gtk.Orientation.VERTICAL)
        super().__init__(*args, **kwargs)
        self.app = app
        self.window = window if window is not None else app.window
        self.commandline = app.core.commandline
        self.lightshow = app.core.lightshow
        self.settings = app.settings
        self.tabs = tabs if tabs is not None else app.tabs

        self.view_mode = VIEW_MODES.get("All", 0)
        self.display_format = DISPLAY_FORMATS[0]
        self.readout_mode = READOUT_MODES[0]
        self.show_labels = True
        self.last_selected_channel = ""
        self.updating_selection = False
        self._updating_expand_btn = False
        self._updating_labels_btn = False
        self._last_ref_readout: str = "Auto"
        self._snapshot_cache: dict[int, ChannelDisplaySnapshot] = {}
        self._dirty_channels: set[int] = set()
        self._dirty_all: bool = False
        self._redraw_timer_id: int | None = None
        self._redraw_interval_ms: int = REDRAW_COALESCE_INTERVAL_MS
        self._on_dirty_flushed_callbacks: list[Callable[[set[int] | None], None]] = []

        if self.__class__.__name__ == "LiveChannelsView":
            self.selection_manager = app.core.live_selection
        else:
            self.selection_manager = SelectionManager(
                commandline=app.core.commandline,
                on_changed_callback=self.sync_selection_to_gui,
                history_manager=app.core.history,
                get_level_callback=self._get_channel_level_for_select,
            )

        self.header = Gtk.HeaderBar()
        self.format_combo = Gtk.ComboBoxText()
        self.format_combo.set_entry_text_column(0)
        for fmt in DISPLAY_FORMATS:
            self.format_combo.append_text(fmt)
        self.format_combo.set_active(0)
        self.format_combo.set_tooltip_text(
            "Display format (Compact / Summary+ / Table) (Alt+Shift+F)"
        )
        self.format_combo.connect("changed", self._on_display_format_changed)
        self.header.pack_start(self.format_combo)

        self.readout_combo = Gtk.ComboBoxText()
        self.readout_combo.set_entry_text_column(0)
        for readout in READOUT_MODES:
            self.readout_combo.append_text(readout)
        self.readout_combo.set_active(0)
        self.readout_combo.set_tooltip_text(
            "Parameter readout (Auto / Label / Ref / Percent / DMX) (Alt+Shift+D)"
        )
        self.readout_combo.connect("changed", self._on_readout_mode_changed)
        self.header.pack_start(self.readout_combo)

        self.labels_btn = Gtk.ToggleButton(label="Labels")
        self.labels_btn.set_active(True)
        self.labels_btn.set_tooltip_text("Show or hide fixture labels (Alt+Shift+L)")
        self.labels_btn.connect("toggled", self._on_labels_btn_toggled)
        self.header.pack_start(self.labels_btn)

        self.expand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.expand_box.get_style_context().add_class("linked")
        self.expand_focus_btn = Gtk.ToggleButton(label="F")
        self.expand_focus_btn.set_tooltip_text("Expand Focus columns (Pan / Tilt)")
        self.expand_focus_btn.connect("toggled", self._on_expand_btn_toggled, "focus")
        self.expand_color_btn = Gtk.ToggleButton(label="C")
        self.expand_color_btn.set_tooltip_text("Expand Color columns (R/G/B/C/M/Y/…)")
        self.expand_color_btn.connect("toggled", self._on_expand_btn_toggled, "color")
        self.expand_beam_btn = Gtk.ToggleButton(label="B")
        self.expand_beam_btn.set_tooltip_text(
            "Expand Beam columns (Zoom / Gobo / Shutter / …)"
        )
        self.expand_beam_btn.connect("toggled", self._on_expand_btn_toggled, "beam")
        self.expand_box.pack_start(self.expand_focus_btn, False, False, 0)
        self.expand_box.pack_start(self.expand_color_btn, False, False, 0)
        self.expand_box.pack_start(self.expand_beam_btn, False, False, 0)
        self.expand_box.set_no_show_all(True)
        self.expand_box.set_visible(False)
        self.header.pack_start(self.expand_box)

        self.combo = Gtk.ComboBoxText()
        self.combo.set_entry_text_column(0)
        for mode in VIEW_MODES:
            self.combo.append_text(mode)
        self.combo.set_active(0)
        self.combo.set_tooltip_text(
            "Flexi filter (All/Patched/Active/Devices/Selected/Manual) (Ctrl+F)"
        )
        self.combo.connect("changed", self._on_view_mode_changed)
        self.header.pack_end(self.combo)
        self.pack_start(self.header, False, False, 0)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(20)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_filter_func(self.filter_channels, None)
        if self.lightshow and self.settings and self.window and self.tabs:
            for i in range(MAX_CHANNELS):
                self.flowbox.add(
                    ChannelWidget(
                        i + 1,
                        0,
                        0,
                        self.app,
                        window=self.window,
                        tabs=self.tabs,
                        channels_view=typing.cast(typing.Any, self),
                    )
                )
        self.scrolled.add(self.flowbox)

        self.table_view = ChannelsTableView(channels_view=typing.cast(typing.Any, self))
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.content_stack.add_named(self.scrolled, "tiles")
        self.content_stack.add_named(self.table_view, "table")
        self.content_stack.set_visible_child_name("tiles")

        self.pack_start(self.content_stack, True, True, 0)
        self.combo.set_active(0)
        self.connect("destroy", self._on_destroy_cleanup)

    def _on_destroy_cleanup(self, *_args: object) -> None:
        """Cancel any pending coalesced redraw timer on widget destruction."""
        if self._redraw_timer_id is not None:
            GLib.source_remove(self._redraw_timer_id)
            self._redraw_timer_id = None
        self._dirty_channels.clear()
        self._dirty_all = False

    def get_channel_snapshot(self, channel: int) -> ChannelDisplaySnapshot | None:
        """Return consolidated ChannelDisplaySnapshot for *channel*, if supported."""
        _ = channel
        return None

    def invalidate_channel_snapshot(self, channel: int) -> None:
        """Invalidate the cached display snapshot for a single *channel*."""
        self._snapshot_cache.pop(int(channel), None)

    def _invalidate_step_cache(self) -> None:
        """Invalidate any step/cue-level resolved tracking cache in subclasses."""

    def invalidate_all_snapshots(self) -> None:
        """Invalidate all cached channel snapshots and step resolution caches."""
        self._snapshot_cache.clear()
        self._invalidate_step_cache()

    def register_dirty_flush_listener(
        self, callback: Callable[[set[int] | None], None]
    ) -> None:
        """Register a listener notified whenever coalesced dirty channels flush."""
        if callback not in self._on_dirty_flushed_callbacks:
            self._on_dirty_flushed_callbacks.append(callback)

    def unregister_dirty_flush_listener(
        self, callback: Callable[[set[int] | None], None]
    ) -> None:
        """Unregister a dirty-flush listener."""
        if callback in self._on_dirty_flushed_callbacks:
            self._on_dirty_flushed_callbacks.remove(callback)

    def mark_channels_dirty(
        self,
        channels: Iterable[int] | None = None,
        *,
        invalidate_step: bool = False,
    ) -> None:
        """Queue *channels* (or all channels when None) for coalesced ~30 fps redraw."""
        if invalidate_step:
            self._invalidate_step_cache()
        if channels is None:
            self._dirty_all = True
            self._snapshot_cache.clear()
        else:
            added = False
            for raw_ch in channels:
                ch = int(raw_ch)
                if 1 <= ch <= MAX_CHANNELS:
                    self._dirty_channels.add(ch)
                    self._snapshot_cache.pop(ch, None)
                    added = True
            if not added and not self._dirty_all:
                return
        if self._redraw_timer_id is None:
            self._redraw_timer_id = GLib.timeout_add(
                self._redraw_interval_ms, self._on_redraw_timer
            )

    def _on_redraw_timer(self) -> bool:
        """One-shot GLib timer callback flushing queued channel redraws."""
        self._redraw_timer_id = None
        self.flush_dirty_channels()
        return False

    def flush_dirty_channels(self) -> int:
        """Invalidate snapshots and trigger targeted queue_draw on visible widgets."""
        if self._redraw_timer_id is not None:
            GLib.source_remove(self._redraw_timer_id)
            self._redraw_timer_id = None

        dirty_all = self._dirty_all
        dirty = set(self._dirty_channels)
        self._dirty_all = False
        self._dirty_channels.clear()

        if not dirty_all and not dirty:
            return 0

        is_table = self.display_format == "Table"
        drawn = 0
        if dirty_all:
            self._snapshot_cache.clear()
            self._invalidate_step_cache()
            if not is_table:
                for child in self.flowbox.get_children():
                    fb_child = typing.cast(Gtk.FlowBoxChild, child)
                    if fb_child.get_visible():
                        widget = fb_child.get_child()
                        if widget is not None:
                            widget.queue_draw()
                            drawn += 1
        else:
            for ch in dirty:
                self._snapshot_cache.pop(ch, None)
                if not is_table:
                    fb_child = self.flowbox.get_child_at_index(ch - 1)
                    if fb_child is not None and fb_child.get_visible():
                        widget = fb_child.get_child()
                        if widget is not None:
                            widget.queue_draw()
                            drawn += 1

        flushed_arg: set[int] | None = None if dirty_all else dirty
        for callback in list(self._on_dirty_flushed_callbacks):
            callback(flushed_arg)
        return drawn

    def get_display_format(self) -> str:
        """Return active format ('Compact', 'Summary+', or 'Table')."""
        return self.display_format

    def set_display_format(self, fmt: str) -> None:
        """Set display format ('Compact', 'Summary+', 'Table') case-insensitively."""
        target = str(fmt).strip().lower()
        matched_idx: int | None = None
        for idx, candidate in enumerate(DISPLAY_FORMATS):
            if candidate.lower() == target:
                matched_idx = idx
                break
        if matched_idx is None:
            return
        matched = DISPLAY_FORMATS[matched_idx]
        if self.format_combo.get_active() != matched_idx:
            self.format_combo.set_active(matched_idx)
        elif self.display_format != matched:
            self._apply_display_format(matched)

    def toggle_display_format(self) -> None:
        """Cycle to the next display format."""
        cur = self.format_combo.get_active()
        nxt = (cur + 1) % len(DISPLAY_FORMATS)
        self.format_combo.set_active(nxt)

    def _on_display_format_changed(self, combo: Gtk.ComboBoxText) -> None:
        text = combo.get_active_text()
        if text in DISPLAY_FORMATS:
            self._apply_display_format(text)
        self.grab_focus()

    def _expand_button_for_family(self, family: str) -> Gtk.ToggleButton | None:
        if family == "focus":
            return self.expand_focus_btn
        if family == "color":
            return self.expand_color_btn
        if family == "beam":
            return self.expand_beam_btn
        return None

    def get_expanded_families(self) -> dict[str, bool]:
        """Return copy of {'focus': bool, 'color': bool, 'beam': bool} state."""
        return dict(self.table_view.expanded_families)

    def set_family_expanded(self, family: str, expanded: bool) -> None:
        """Expand or collapse dynamic Table sub-columns for *family*."""
        norm = normalize_expand_family(family)
        btn = self._expand_button_for_family(norm)
        target = bool(expanded)
        if btn is not None and btn.get_active() != target:
            self._updating_expand_btn = True
            try:
                btn.set_active(target)
            finally:
                self._updating_expand_btn = False
        self.table_view.set_family_expanded(norm, target)
        self._persist_tab_setting(
            "expanded_families", dict(self.table_view.expanded_families)
        )

    def toggle_family_expanded(self, family: str) -> bool:
        """Toggle Table column expansion for *family* and return the new state."""
        norm = normalize_expand_family(family)
        new_state = not self.table_view.expanded_families.get(norm, False)
        self.set_family_expanded(norm, new_state)
        return new_state

    def _on_expand_btn_toggled(self, btn: Gtk.ToggleButton, family: str) -> None:
        if not self._updating_expand_btn:
            self.table_view.set_family_expanded(family, btn.get_active())
            self._persist_tab_setting(
                "expanded_families", dict(self.table_view.expanded_families)
            )
        self.grab_focus()

    def get_visible_channels(self) -> list[int]:
        """Evaluate filter_channels across children and return visible channel IDs."""
        visible: list[int] = []
        for idx, child in enumerate(self.flowbox.get_children()):
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            try:
                is_vis = bool(self.filter_channels(fb_child, None))
            except NotImplementedError:
                is_vis = fb_child.get_visible()
            if is_vis:
                visible.append(idx + 1)
        return visible

    def refresh_filter(self) -> None:
        """Invalidate channel filter and keep Table rows synced when visible."""
        self.flowbox.invalidate_filter()
        if self.display_format == "Table":
            self.table_view.rebuild_rows()

    def _apply_display_format(self, fmt: str) -> None:
        self.display_format = fmt
        self._snapshot_cache.clear()
        if fmt == "Table":
            self.expand_box.set_visible(True)
            self.expand_focus_btn.show()
            self.expand_color_btn.show()
            self.expand_beam_btn.show()
            self.table_view.show_all()
            self.content_stack.set_visible_child_name("table")
            self.table_view.rebuild_rows(force=True)
        else:
            self.expand_box.set_visible(False)
            for child in self.flowbox.get_children():
                fb_child = typing.cast(Gtk.FlowBoxChild, child)
                widget = fb_child.get_child()
                if widget is not None and isinstance(widget, ChannelWidget):
                    widget.set_display_format(fmt)
            self.content_stack.set_visible_child_name("tiles")
            self.flowbox.queue_resize()
        self._persist_tab_setting("display_format", fmt)
        for callback in list(self._on_dirty_flushed_callbacks):
            if fmt != "Table":
                callback(None)

    def get_readout_mode(self) -> str:
        """Return active readout mode ('Auto', 'Label', 'Ref', 'Percent', 'DMX')."""
        return self.readout_mode

    def set_readout_mode(self, mode: str) -> None:
        """Set parameter readout mode case-insensitively."""
        target = str(mode).strip().lower()
        matched_idx: int | None = None
        for idx, candidate in enumerate(READOUT_MODES):
            if candidate.lower() == target:
                matched_idx = idx
                break
        if matched_idx is None:
            return
        matched = READOUT_MODES[matched_idx]
        if self.readout_combo.get_active() != matched_idx:
            self.readout_combo.set_active(matched_idx)
        elif self.readout_mode != matched:
            self._apply_readout_mode(matched)

    def toggle_readout_mode(self) -> None:
        """Cycle to the next readout mode."""
        cur = self.readout_combo.get_active()
        nxt = (cur + 1) % len(READOUT_MODES)
        self.readout_combo.set_active(nxt)

    def toggle_data_mode(self) -> str:
        """Toggle between reference/label readout and raw value readout (Data key)."""
        if self.readout_mode in ("Percent", "DMX"):
            self.set_readout_mode(self._last_ref_readout)
        else:
            use_percent = self.settings is None or self.settings.get_boolean("percent")
            self.set_readout_mode("Percent" if use_percent else "DMX")
        return self.readout_mode

    def _on_readout_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        text = combo.get_active_text()
        if text in READOUT_MODES:
            self._apply_readout_mode(text)
        self.grab_focus()

    def _apply_readout_mode(self, mode: str) -> None:
        self.readout_mode = mode
        if mode in ("Auto", "Label", "Ref"):
            self._last_ref_readout = mode
        is_table = self.display_format == "Table"
        for child in self.flowbox.get_children():
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            widget = fb_child.get_child()
            if widget is not None and isinstance(widget, ChannelWidget):
                if is_table or not fb_child.get_visible():
                    widget.readout_mode = mode
                else:
                    widget.set_readout_mode(mode)
        self._persist_tab_setting("readout_mode", mode)
        for callback in list(self._on_dirty_flushed_callbacks):
            callback(None)

    def get_show_labels(self) -> bool:
        """Return whether fixture labels are shown in tiles and Table view."""
        return self.show_labels

    def set_show_labels(self, show: bool) -> None:
        """Show or hide fixture labels in tiles and Table view."""
        target = bool(show)
        if self.labels_btn.get_active() != target:
            self._updating_labels_btn = True
            try:
                self.labels_btn.set_active(target)
            finally:
                self._updating_labels_btn = False
        self._apply_show_labels(target)

    def toggle_show_labels(self) -> bool:
        """Toggle fixture label visibility and return the new state."""
        new_state = not self.show_labels
        self.set_show_labels(new_state)
        return new_state

    def _on_labels_btn_toggled(self, btn: Gtk.ToggleButton) -> None:
        if not self._updating_labels_btn:
            self._apply_show_labels(btn.get_active())
        self.grab_focus()

    def _apply_show_labels(self, show: bool) -> None:
        target = bool(show)
        self.show_labels = target
        is_table = self.display_format == "Table"
        for child in self.flowbox.get_children():
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            widget = fb_child.get_child()
            if widget is not None and isinstance(widget, ChannelWidget):
                if is_table or not fb_child.get_visible():
                    widget.show_labels = target
                else:
                    widget.set_show_labels(target)
        self.table_view.set_show_labels(target)
        self._persist_tab_setting("show_labels", target)

    def _persist_tab_setting(self, key: str, value: object) -> None:
        """Persist a per-tab ChannelsView setting into lightshow.workspace."""
        tab_name = self.get_tab_name()
        if tab_name and self.lightshow and hasattr(self.lightshow, "workspace"):
            tab_settings = self.lightshow.workspace.setdefault("tab_settings", {})
            tab_settings.setdefault(tab_name, {})[key] = value

    def _get_channel_level_for_select(self, channel: int) -> int | float:
        """Helper callback to read the level from a ChannelWidget."""
        widget = self.get_channel_widget(channel)
        return widget.level if widget else 0

    def sync_selection_to_gui(self, selected_channels: list[int]) -> None:
        """Synchronize logical selection from selection_manager to tiles & table."""
        self.updating_selection = True
        try:
            self.flowbox.unselect_all()
            for ch in selected_channels:
                if 1 <= ch <= MAX_CHANNELS:
                    flowboxchild = self.flowbox.get_child_at_index(ch - 1)
                    if flowboxchild:
                        self.flowbox.select_child(flowboxchild)
            if self.selection_manager.last_selected_channel is not None:
                self.last_selected_channel = str(
                    self.selection_manager.last_selected_channel
                )
            else:
                self.last_selected_channel = ""
            self.flowbox.invalidate_filter()
            if self.display_format == "Table":
                if self.view_mode in (VIEW_MODES["Active"], VIEW_MODES["Selected"]):
                    self.table_view.rebuild_rows()
                self.table_view.sync_selection(selected_channels)
        finally:
            self.updating_selection = False

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Display channels

        Args:
            child: Parent of Channel Widget

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """Change channels level with a wheel

        Args:
            step: Step level
            direction: Up or Down

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def set_channel_level(self, channel: int, level: int | float) -> None:
        """Channel at level

        Args:
            channel: Channel number (1 - MAX_CHANNELS)
            level: DMX level (0 - 255)

        Raises:
            NotImplementedError: Must be implemented in subclass
        """
        raise NotImplementedError

    def update(self) -> None:
        """Update channels display."""
        self.invalidate_all_snapshots()
        self.flowbox.invalidate_filter()
        if self.display_format == "Table":
            self.table_view.rebuild_rows(force=True)
        else:
            self.flowbox.queue_draw()

    def get_channel_widget(self, channel: int) -> Optional[ChannelWidget]:
        """Get ChannelWidget of channel number

        Args:
            channel: Channel (1-MAX_CHANNELS)

        Returns:
            Channel widget
        """
        if 0 < channel <= MAX_CHANNELS:
            flowboxchild = self.flowbox.get_child_at_index(channel - 1)
            if flowboxchild:
                channelwidget = typing.cast("ChannelWidget", flowboxchild.get_child())
                return channelwidget
        return None

    def get_tab_name(self) -> str | None:
        """Find the logical tab name this channels view belongs to."""
        if self.__class__.__name__ == "LiveChannelsView":
            return "channels"
        tabs_mgr = self.tabs
        if tabs_mgr and hasattr(tabs_mgr, "tabs"):
            for name, widget in tabs_mgr.tabs.items():
                if widget is not None:
                    if widget is self or getattr(widget, "channels_view", None) is self:
                        return name
        return None

    def get_view_mode_name(self) -> str:
        """Get the current view mode as a string name."""
        for name, idx in VIEW_MODES.items():
            if idx == self.view_mode:
                return name
        return "All"

    def set_view_mode_by_name(self, name: str) -> None:
        """Set view mode by string name case-insensitively."""
        target = str(name).strip().lower()
        for mode_name, idx in VIEW_MODES.items():
            if mode_name.lower() == target:
                self.combo.set_active(idx)
                return

    def is_device_channel(self, channel: int) -> bool:
        """Return True if *channel* is patched to a fixture with F/C/B attributes."""
        if not self.lightshow:
            return False
        dev = self.lightshow.patch.devices.get(int(channel))
        if dev is None:
            return False
        return any(
            ch.channel_type != ChannelType.INTENSITY
            for ch in getattr(dev, "channels", ())
        )

    def is_selected_channel(
        self, channel: int, child: Gtk.FlowBoxChild | None = None
    ) -> bool:
        """Return True if *channel* is currently selected in this view."""
        if int(channel) in self.selection_manager.selected_channels:
            return True
        return bool(child is not None and child.is_selected())

    def is_manual_channel(self, channel: int) -> bool:
        """Return True if *channel* carries manual overrides (subclasses override)."""
        _ = channel
        return False

    def _on_view_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        """Change View Mode

        Args:
            combo: Widget to change mode
        """
        text = combo.get_active_text()
        if text is not None:
            index = VIEW_MODES.get(text, 0)
            self.view_mode = index
            self.flowbox.invalidate_filter()
            if self.display_format == "Table":
                self.table_view.rebuild_rows(force=True)
            self._persist_tab_setting("view_mode", text)
        self.grab_focus()

    def toggle_view_mode(self) -> None:
        """Select next View Mode"""
        index = self.view_mode + 1
        if index not in VIEW_MODES.values():
            index = 0
        self.combo.set_active(index)

    def _focus_channel(self, channel: int) -> None:
        """Focus or scroll to *channel* in the active view (tiles or table)."""
        if not self.window:
            return
        if self.display_format == "Table":
            self.table_view.scroll_to_channel(channel)
            return
        if flowboxchild := self.flowbox.get_child_at_index(channel - 1):
            self.window.set_focus(flowboxchild)

    def select_channel(self) -> None:
        """Select one channel, or clear selection if commandline is empty or zero."""
        if not self.window or not self.commandline:
            return
        cmd = self.commandline.get_string()
        if not cmd or cmd == "0":
            self.selection_manager.execute_action(SelectNoneAction)
            return
        self.selection_manager.execute_action(SelectActiveAction)
        if self.selection_manager.last_selected_channel:
            self._focus_channel(self.selection_manager.last_selected_channel)

    def select_plus(self) -> None:
        """Add channel to selection"""
        if not self.window or not self.commandline:
            return

        self.selection_manager.execute_action(SelectAddAction)
        if self.selection_manager.last_selected_channel:
            self._focus_channel(self.selection_manager.last_selected_channel)

    def select_minus(self) -> None:
        """Remove channel from selection"""
        if not self.window or not self.commandline:
            return

        self.selection_manager.execute_action(SelectRemoveAction)
        if self.selection_manager.last_selected_channel:
            self._focus_channel(self.selection_manager.last_selected_channel)

    def select_next(self) -> None:
        """Select next channel"""
        if not self.window:
            return
        if self.last_selected_channel and not is_non_nul_int(
            self.last_selected_channel
        ):
            return
        if self.view_mode in (
            VIEW_MODES["Active"],
            VIEW_MODES["Devices"],
            VIEW_MODES["Selected"],
            VIEW_MODES["Manual"],
        ):
            target_ch = self._get_filtered_next_channel()
            if target_ch is None:
                return
            target_channel = target_ch
        elif self.view_mode == VIEW_MODES["Patched"]:
            target_channel = self._get_next_patched_index() + 1
        else:
            channel_index = (
                int(self.last_selected_channel) if self.last_selected_channel else 0
            )
            if channel_index > MAX_CHANNELS - 1:
                channel_index = 0
            target_channel = channel_index + 1

        self.selection_manager.execute_action(SelectActiveAction, target_channel)
        self.last_selected_channel = str(target_channel)
        self._focus_channel(target_channel)

    def _current_selection_anchor(self) -> int | None:
        """Return the active 1-based channel anchor for step navigation."""
        if (
            self.selection_manager.selected_channels
            and self.selection_manager.last_selected_channel is not None
        ):
            return int(self.selection_manager.last_selected_channel)
        if self.last_selected_channel and is_non_nul_int(self.last_selected_channel):
            return int(self.last_selected_channel)
        return None

    def _get_filtered_next_channel(self) -> int | None:
        """Return next visible channel ID (1-based) in filtered modes, or None."""
        visible = self.get_visible_channels()
        if not visible:
            return None
        cur = self._current_selection_anchor()
        if cur is None:
            return visible[0]
        for ch in visible:
            if ch > cur:
                return ch
        return visible[0]

    def _get_next_patched_index(self) -> int:
        """Get next patched channel index"""
        if not self.lightshow:
            return 0
        start = (
            int(self.last_selected_channel)
            if self.last_selected_channel
            else self.lightshow.patch.get_first_patched_channel() - 1
        )

        channel_index = start
        found = False
        for idx in range(start, MAX_CHANNELS):
            if self.lightshow.patch.is_patched(idx + 1):
                channel_index = idx
                found = True
                break
        if not found:
            channel_index = self.lightshow.patch.get_first_patched_channel() - 1
        return channel_index

    def select_previous(self) -> None:
        """Select previous channel"""
        if not self.window:
            return
        if self.last_selected_channel and not is_non_nul_int(
            self.last_selected_channel
        ):
            return
        if self.view_mode in (
            VIEW_MODES["Active"],
            VIEW_MODES["Devices"],
            VIEW_MODES["Selected"],
            VIEW_MODES["Manual"],
        ):
            target_ch = self._get_filtered_previous_channel()
            if target_ch is None:
                return
            target_channel = target_ch
        elif self.view_mode == VIEW_MODES["Patched"]:
            target_channel = self._get_previous_patched_index() + 1
        else:
            channel_index = (
                int(self.last_selected_channel) - 2 if self.last_selected_channel else 0
            )
            if channel_index < 0:
                channel_index = MAX_CHANNELS - 1
            target_channel = channel_index + 1

        self.selection_manager.execute_action(SelectActiveAction, target_channel)
        self.last_selected_channel = str(target_channel)
        self._focus_channel(target_channel)

    def _get_filtered_previous_channel(self) -> int | None:
        """Return previous visible channel ID (1-based) in filtered modes, or None."""
        visible = self.get_visible_channels()
        if not visible:
            return None
        cur = self._current_selection_anchor()
        if cur is None:
            return visible[-1]
        for ch in reversed(visible):
            if ch < cur:
                return ch
        return visible[-1]

    def _get_previous_patched_index(self) -> int:
        """Get previous patched channel index"""
        if not self.lightshow:
            return 0
        start = (
            int(self.last_selected_channel) - 2
            if self.last_selected_channel
            else self.lightshow.patch.get_last_patched_channel()
        )

        channel_index = start
        found = False
        for idx in range(start, -1, -1):
            if self.lightshow.patch.is_patched(idx + 1):
                channel_index = idx
                found = True
                break
        if not found:
            channel_index = self.lightshow.patch.get_last_patched_channel() - 1
        return channel_index

    def select_all(self) -> None:
        """Select all channel with a level > 0"""

        self.selection_manager.execute_action(SelectAllAction)

    def select_thru(self) -> None:
        """Select Channel Thru"""
        if not self.window or not self.commandline:
            return

        self.selection_manager.execute_action(SelectThruAction)
        if self.selection_manager.last_selected_channel:
            self._focus_channel(self.selection_manager.last_selected_channel)

    def at_level(self) -> None:
        """Channels at level"""
        if not self.window or not self.settings or not self.commandline:
            return
        keystring = self.commandline.get_string()
        if not is_int(keystring):
            return
        level = int(keystring)
        if self.settings.get_boolean("percent"):
            level = int(round((level / 100) * 255))
        level = min(level, 255)
        channels = self.get_selected_channels()
        for channel in channels:
            self.set_channel_level(channel, level)

    def level_plus(self) -> None:
        """Channels +%"""
        if not self.settings:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) + step_level
                    new_level = min(round((percent_level / 100) * 256), 255)
                else:
                    new_level = min(level + step_level, 255)
                self.set_channel_level(channel, new_level)

    def level_minus(self) -> None:
        """Channels -%"""
        if not self.settings:
            return
        step_level = self.settings.get_int("percent-level")
        channels = self.get_selected_channels()
        for channel in channels:
            channel_widget = self.get_channel_widget(channel)
            if channel_widget:
                level = channel_widget.level
                if self.settings.get_boolean("percent"):
                    percent_level = round((level / 256) * 100) - step_level
                    new_level = max(round((percent_level / 100) * 256), 0)
                else:
                    new_level = max(level - step_level, 0)
                self.set_channel_level(channel, new_level)

    def get_selected_channels(self) -> list[int]:
        """Return selected channels

        Returns:
            Selected channels
        """
        return list(self.selection_manager.selected_channels)

    def grab_focus(self) -> None:
        """Grab focus to active Tab"""
        parent = self.get_parent()
        if not self.window or not parent:
            return
        if self.window and parent in (self.window.live_view, self.window.playback):
            parent.grab_focus()
        elif parent:
            if grandparent := parent.get_parent():
                grandparent.grab_focus()

    def on_key_press(self, keyname: str | None) -> Callable | None:
        """Processes common keyboard methods of Channels View

        Args:
            keyname: Gdk Name of the pressed key

        Returns:
            method or None
        """
        if keyname in {
            "f",
            "Page_Up",
            "Page_Down",
            "a",
            "c",
            "KP_Divide",
            "greater",
            "KP_Add",
            "plus",
            "KP_Subtract",
            "minus",
        }:
            if func := getattr(self, f"_keypress_{keyname.lower()}", None):
                return func()
        return None

    def _keypress_f(self) -> None:
        """Toggle display mode"""
        self.toggle_view_mode()
        self.grab_focus()

    def _keypress_a(self) -> None:
        """All Channels"""
        self.select_all()
        self.grab_focus()

    def _keypress_page_up(self) -> None:
        """Next Channel"""
        self.select_next()
        self.grab_focus()
        if self.commandline:
            self.app.core.action_registry.execute("commandline.clear")

    def _keypress_page_down(self) -> None:
        """Previous Channel"""
        self.select_previous()
        self.grab_focus()
        if self.commandline:
            self.app.core.action_registry.execute("commandline.clear")

    def _keypress_c(self) -> None:
        """Channel"""
        self.select_channel()
        self.grab_focus()
        if self.commandline:
            self.app.core.action_registry.execute("commandline.clear")

    def _keypress_kp_divide(self) -> None:
        self._keypress_greater()

    def _keypress_greater(self) -> None:
        """Channel Thru"""
        self.select_thru()
        self.grab_focus()
        if self.commandline:
            self.app.core.action_registry.execute("commandline.clear")

    def _keypress_kp_add(self) -> None:
        self._keypress_plus()

    def _keypress_plus(self) -> None:
        """Channel +"""
        self.select_plus()
        self.grab_focus()
        if self.commandline:
            self.app.core.action_registry.execute("commandline.clear")

    def _keypress_kp_subtract(self) -> None:
        self._keypress_minus()

    def _keypress_minus(self) -> None:
        """Channel -"""
        self.select_minus()
        self.grab_focus()
        if self.commandline:
            self.app.core.action_registry.execute("commandline.clear")

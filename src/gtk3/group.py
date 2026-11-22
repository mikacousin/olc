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
from gettext import gettext as _

from gi.repository import GLib, Gtk, Pango

from olc.core.selection import SelectionAction, SelectNoneAction
from olc.define import is_non_nul_float
from olc.gtk3.widgets.channel import ChannelWidget
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView
from olc.gtk3.widgets.group import (
    GroupWidget,
    format_channel_summary,
    format_group_number,
)
from olc.show.group import Group

if typing.TYPE_CHECKING:
    from gi.repository import Gdk, Gio

    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow


class _SelectOrderedChannelsAction(SelectionAction):
    """SelectionAction preserving explicit channel order (used by Group Ctrl+A)."""

    name = "select.ordered"

    def __init__(self, manager: typing.Any) -> None:  # noqa: ANN401
        super().__init__(manager)
        self.channels: list[int] = []

    def configure(self, channels: list[int]) -> None:
        """Configure ordered channel selection list."""
        self.channels = list(dict.fromkeys(int(ch) for ch in channels))

    def execute(self) -> None:
        self._save_previous()
        self.manager.selected_channels = list(self.channels)
        self.manager.last_selected_channel = (
            self.channels[-1] if self.channels else None
        )
        self.manager.commandline.set_string("")


class GroupChannelsView(ChannelsView):
    """Channels View displaying ordered group membership without intensity levels."""

    is_membership_view: bool = True

    def __init__(self, app: Application) -> None:
        self._group_order_map: dict[int, int] = {}
        self._synced_group_id: float | None = None
        self._synced_channels: list[int] = []
        super().__init__(app=app)
        for widget in self._channel_widgets:
            widget.membership_mode = True
            widget.membership_order = None
            widget.level = 0.0
            widget.next_level = 0.0
        # Hide level/attribute readout controls not applicable to pure selections
        self.readout_combo.set_no_show_all(True)
        self.readout_combo.set_visible(False)
        self.expand_box.set_no_show_all(True)
        self.expand_box.set_visible(False)

    def invalidate_cache(self) -> None:
        """Reset cached order mapping so the next update refreshes from active group."""
        self._synced_group_id = None
        self._synced_channels = []
        self._group_order_map = {}

    def _get_selected_group(self) -> Group | None:
        """Return currently selected Group directly via model/tab state."""
        if not self.lightshow:
            return None
        target_nb: float | None = None
        if self.tabs:
            groups_tab = self.tabs.tabs.get("groups")
            if groups_tab is not None:
                target_nb = getattr(groups_tab, "selected_group_number", None)
        if target_nb is None:
            target_nb = getattr(self.app.core, "selected_group", None)
        if target_nb is None:
            return None
        return self.lightshow.groups.get(float(target_nb))

    def _sync_order_map(self, group: Group | None) -> None:
        """Ensure O(1) channel -> 1-based rank map matches *group.channels*."""
        if group is None:
            if self._synced_group_id is not None or self._group_order_map:
                self._synced_group_id = None
                self._synced_channels = []
                self._group_order_map = {}
            return
        if (
            self._synced_group_id != group.index
            or self._synced_channels != group.channels
        ):
            self._synced_group_id = group.index
            self._synced_channels = list(group.channels)
            self._group_order_map = {
                int(ch): idx + 1 for idx, ch in enumerate(self._synced_channels)
            }

    def update(self) -> None:
        """Synchronize membership ranks and redraw channels view."""
        group = self._get_selected_group()
        self._sync_order_map(group)
        super().update()

    def toggle_view_mode(self) -> None:
        """Cycle Flexi filter modes while skipping 'Manual' (empty in Groups)."""
        index = self.view_mode + 1
        if index == VIEW_MODES.get("Manual", 5):
            index += 1
        if index not in VIEW_MODES.values():
            index = 0
        self.combo.set_active(index)

    def _get_channel_level_for_select(self, channel: int) -> int | float:
        """Return membership presence for SelectAllAction fallbacks."""
        return 1.0 if int(channel) in self._group_order_map else 0.0

    def select_all(self) -> None:
        """Select all group member channels in the group's exact ordered sequence."""
        group = self._get_selected_group()
        self._sync_order_map(group)
        if group is not None and group.channels:
            self.selection_manager.execute_action(
                _SelectOrderedChannelsAction, list(group.channels)
            )
        else:
            self.selection_manager.execute_action(SelectNoneAction)

    def set_channel_level(self, channel: int, level: int | float) -> None:
        """No-op: groups store pure channel selections without intensity levels."""
        _ = (channel, level)

    def wheel_level(self, step: int, direction: Gdk.ScrollDirection) -> None:
        """No-op: groups store pure channel selections without intensity levels."""
        _ = (step, direction)

    def at_level(self) -> None:
        """No-op: groups store pure channel selections without intensity levels."""

    def level_plus(self) -> None:
        """No-op: groups store pure channel selections without intensity levels."""

    def level_minus(self) -> None:
        """No-op: groups store pure channel selections without intensity levels."""

    def _apply_membership_to_widget(
        self, child: Gtk.FlowBoxChild, channel: int
    ) -> ChannelWidget:
        """Attach rank metadata to *child*'s ChannelWidget with level fixed at 0.0."""
        channel_widget = typing.cast(ChannelWidget, child.get_child())
        channel_widget.membership_mode = True
        channel_widget.membership_order = self._group_order_map.get(channel)
        channel_widget.level = 0.0
        channel_widget.next_level = 0.0
        return channel_widget

    def filter_channels(self, child: Gtk.FlowBoxChild, _user_data: object) -> bool:
        """Filter channels to display and assign group order ranks."""
        group = self._get_selected_group()
        self._sync_order_map(group)
        channel = child.get_index() + 1
        channel_widget = self._apply_membership_to_widget(child, channel)
        if not group:
            channel_widget.membership_order = None
            child.set_visible(False)
            return False

        if self.view_mode == VIEW_MODES["Active"]:
            if channel in self._group_order_map or child.is_selected():
                child.set_visible(True)
                return True
            child.set_visible(False)
            return False

        if self.view_mode == VIEW_MODES["Patched"]:
            if self.lightshow and not self.lightshow.patch.is_patched(channel):
                child.set_visible(False)
                return False
            child.set_visible(True)
            return True

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

        if self.view_mode == VIEW_MODES["Manual"]:
            child.set_visible(False)
            return False

        child.set_visible(True)
        return True


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class GroupTab(Gtk.Box):
    """Groups edition and Direct Select tab."""

    app: Application
    lightshow: LightShow
    tabs: Tabs
    window: Window
    settings: Gio.Settings
    commandline: CoreCommandLine
    last_group_selected: str
    selected_group_number: float | None
    channels_view: GroupChannelsView
    paned: Gtk.Paned
    scrolled: Gtk.ScrolledWindow
    flowbox: Gtk.FlowBox
    details_label: Gtk.Label
    direct_select_toggle: Gtk.ToggleButton
    btn_select_live: Gtk.Button
    btn_record: Gtk.Button
    btn_update: Gtk.Button
    btn_reverse: Gtk.Button
    btn_sort: Gtk.Button
    btn_clear: Gtk.Button
    btn_rename: Gtk.Button
    btn_delete: Gtk.Button
    _updating_selection: bool

    def __init__(self, app: Application) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_border_width(4)

        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs if app.tabs is not None else typing.cast(typing.Any, None)
        self.window = (
            app.window if app.window is not None else typing.cast(typing.Any, None)
        )
        self.settings = app.settings
        self.commandline = app.core.commandline
        self.last_group_selected = ""
        self.selected_group_number = None
        self._updating_selection = False
        self._selection_idle_id: int | None = None

        # Top toolbar aligned with PalettesTab
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.direct_select_toggle = Gtk.ToggleButton(label=_("Direct Select"))
        self.direct_select_toggle.set_tooltip_text(
            _(
                "When active, clicking a group tile immediately selects its "
                "channels in Live"
            )
        )
        toolbar.pack_start(self.direct_select_toggle, False, False, 0)

        self.btn_select_live = Gtk.Button(label=_("Select Live"))
        self.btn_select_live.set_tooltip_text(
            _(
                "Recall the selected group into Live channel selection "
                "(or double-click tile)"
            )
        )
        self.btn_select_live.connect(
            "clicked", lambda *_: self.select_selected_in_live()
        )
        toolbar.pack_start(self.btn_select_live, False, False, 0)

        spacer = Gtk.Box()
        toolbar.pack_start(spacer, True, True, 0)

        self.btn_record = Gtk.Button(label=_("Record"))
        self.btn_record.set_tooltip_text(
            _("Create a group from selection (optional number in command line)")
        )
        self.btn_record.connect("clicked", lambda *_: self.record_group())
        toolbar.pack_start(self.btn_record, False, False, 0)

        self.btn_update = Gtk.Button(label=_("Update"))
        self.btn_update.set_tooltip_text(
            _("Replace selected group channels from local or Live selection")
        )
        self.btn_update.connect("clicked", lambda *_: self.update_selected_channels())
        toolbar.pack_start(self.btn_update, False, False, 0)

        toolbar.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2
        )

        self.btn_reverse = Gtk.Button(label=_("Reverse"))
        self.btn_reverse.set_tooltip_text(
            _("Reverse channel selection order in the selected group")
        )
        self.btn_reverse.connect("clicked", lambda *_: self.reverse_selected_order())
        toolbar.pack_start(self.btn_reverse, False, False, 0)

        self.btn_sort = Gtk.Button(label=_("Sort"))
        self.btn_sort.set_tooltip_text(
            _("Sort group channels in ascending numerical order")
        )
        self.btn_sort.connect("clicked", lambda *_: self.sort_selected_order())
        toolbar.pack_start(self.btn_sort, False, False, 0)

        self.btn_clear = Gtk.Button(label=_("Clear"))
        self.btn_clear.set_tooltip_text(
            _("Remove all channels from the selected group")
        )
        self.btn_clear.connect("clicked", lambda *_: self.clear_selected_channels())
        toolbar.pack_start(self.btn_clear, False, False, 0)

        toolbar.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2
        )

        self.btn_rename = Gtk.Button(label=_("Rename"))
        self.btn_rename.set_tooltip_text(_("Rename selected group (F2)"))
        self.btn_rename.connect("clicked", lambda *_: self.rename_selected())
        toolbar.pack_start(self.btn_rename, False, False, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.set_tooltip_text(_("Delete selected group (Delete)"))
        self.btn_delete.connect("clicked", lambda *_: self.delete_selected())
        toolbar.pack_start(self.btn_delete, False, False, 0)

        self.pack_start(toolbar, False, False, 0)

        # Vertical split: channels view on top, group cards on bottom
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(450)

        self.channels_view = GroupChannelsView(app=self.app)
        self.paned.add1(self.channels_view)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(12)
        self.flowbox.set_column_spacing(6)
        self.flowbox.set_row_spacing(6)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_activate_on_single_click(False)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.connect("selected-children-changed", self.on_selection_changed)
        self.flowbox.connect("child-activated", self._on_child_activated)
        self.scrolled.add(self.flowbox)
        self.paned.add2(self.scrolled)
        self.pack_start(self.paned, True, True, 0)

        # Bottom details bar
        self.details_label = Gtk.Label()
        self.details_label.set_halign(Gtk.Align.START)
        self.details_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.pack_start(self.details_label, False, False, 0)

        self.connect("destroy", self._on_destroy_cleanup)
        self.populate_tab()
        self._update_details_and_sensitivity()

    def set_position(self, position: int) -> None:
        """Set position of the inner paned separator."""
        self.paned.set_position(position)

    def get_position(self) -> int:
        """Get position of the inner paned separator."""
        return self.paned.get_position()

    def _on_destroy_cleanup(self, *_args: object) -> None:
        """Cancel pending idle selection updates when closing the tab."""
        if self._selection_idle_id is not None:
            source = GLib.MainContext.default().find_source_by_id(
                self._selection_idle_id
            )
            if source is not None and not source.is_destroyed():
                GLib.source_remove(self._selection_idle_id)
            self._selection_idle_id = None

    def populate_tab(self) -> None:
        """Populate group tiles into FlowBox."""
        for child in list(self.flowbox.get_children()):
            self.flowbox.remove(child)
            child.destroy()
        for grp in self.lightshow.groups:
            self.flowbox.add(
                GroupWidget(
                    grp.index,
                    grp.text,
                    channels=list(grp.channels),
                    lightshow=self.lightshow,
                    tabs=self.tabs,
                    window=self.window,
                    group_tab=typing.cast(typing.Any, self),
                )
            )
        self.flowbox.show_all()

    def get_selected_tile(self) -> GroupWidget | None:
        """Return currently selected GroupWidget, if any."""
        selected = self.flowbox.get_selected_children()
        if not selected:
            return None
        widget = selected[0].get_child()
        return widget if isinstance(widget, GroupWidget) else None

    def get_selected_group(self) -> Group | None:
        """Return currently selected Group model object, if any."""
        tile = self.get_selected_tile()
        if tile is not None:
            return self.lightshow.groups.get(tile.number)
        if self.selected_group_number is not None:
            return self.lightshow.groups.get(self.selected_group_number)
        return None

    def _update_details_and_sensitivity(self) -> None:
        group = self.get_selected_group()
        has_sel = group is not None
        has_channels = bool(group and group.channels)

        self.btn_select_live.set_sensitive(has_channels)
        self.btn_update.set_sensitive(has_sel)
        self.btn_reverse.set_sensitive(
            has_channels and len(group.channels) > 1 if group else False
        )
        self.btn_sort.set_sensitive(
            has_channels and len(group.channels) > 1 if group else False
        )
        self.btn_clear.set_sensitive(has_channels)
        self.btn_rename.set_sensitive(has_sel)
        self.btn_delete.set_sensitive(has_sel)
        self.btn_record.set_sensitive(True)

        if group is None:
            if len(self.lightshow.groups) > 0:
                self.details_label.set_text(
                    _("Select a group tile (double-click or Direct Select to recall)")
                )
            else:
                self.details_label.set_text(
                    _("No groups yet. Click Record or run RECORD GROUP <n>.")
                )
            self.details_label.set_tooltip_text(None)
            return

        num_str = format_group_number(group.index)
        title = f"Group {num_str}" + (f" \u2014 {group.text}" if group.text else "")
        count_txt = f"{len(group.channels)} ch"
        if group.channels:
            full_order = ", ".join(str(ch) for ch in group.channels)
            summary = format_channel_summary(group.channels, max_tokens=12)
            text = f"{title} ({count_txt})  |  Order: {summary}"
            self.details_label.set_tooltip_text(
                f"{title} ({count_txt})\nOrder: {full_order}"
            )
        else:
            text = f"{title} (empty)"
            self.details_label.set_tooltip_text(None)
        self.details_label.set_text(text)

    def on_selection_changed(self, flowbox: Gtk.FlowBox) -> None:
        """Called when user selection changes on flowbox."""
        if self._updating_selection:
            return

        if self._selection_idle_id is not None:
            source = GLib.MainContext.default().find_source_by_id(
                self._selection_idle_id
            )
            if source is not None and not source.is_destroyed():
                GLib.source_remove(self._selection_idle_id)
            self._selection_idle_id = None

        self._selection_idle_id = GLib.idle_add(self._apply_selection_changed, flowbox)

    def _apply_selection_changed(self, flowbox: Gtk.FlowBox) -> bool:
        self._selection_idle_id = None
        selected = flowbox.get_selected_children()
        if selected:
            child = selected[0]
            group_widget = typing.cast(GroupWidget, child.get_child())
            group_nb: float | None = group_widget.number
            self.last_group_selected = str(child.get_index())
        else:
            group_nb = None
            self.last_group_selected = ""
        self.selected_group_number = group_nb
        if self.app.core.selected_group != group_nb:
            self.app.core.action_registry.execute("group.select", group_nb)
        self.channels_view.update()
        self._update_details_and_sensitivity()
        return False

    def _on_child_activated(
        self, _flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild
    ) -> None:
        widget = child.get_child()
        if isinstance(widget, GroupWidget):
            self.select_group_in_live(widget.number)

    def select_group_graphically(self, group_nb: float | None) -> None:
        """Update the graphical group selection from the logical state."""
        self._updating_selection = True
        try:
            self.flowbox.unselect_all()
            if group_nb is not None:
                for child in self.flowbox.get_children():
                    fb_child = typing.cast(Gtk.FlowBoxChild, child)
                    group_widget = typing.cast(GroupWidget, fb_child.get_child())
                    if group_widget and group_widget.number == group_nb:
                        self.flowbox.select_child(fb_child)
                        self.selected_group_number = group_nb
                        self.last_group_selected = str(fb_child.get_index())
                        break
            else:
                self.selected_group_number = None
                self.last_group_selected = ""
            self.channels_view.invalidate_cache()
            self.channels_view.update()
            self._update_details_and_sensitivity()
        finally:
            self._updating_selection = False

    def _select_flowbox_child(self, fb_child: Gtk.FlowBoxChild) -> None:
        """Select *fb_child* smoothly via arrow navigation without idle lag."""
        group_widget = typing.cast(GroupWidget, fb_child.get_child())
        self.selected_group_number = group_widget.number if group_widget else None
        self.last_group_selected = str(fb_child.get_index())
        self._updating_selection = True
        try:
            self.flowbox.select_child(fb_child)
        finally:
            self._updating_selection = False
        if self.app.core.selected_group != self.selected_group_number:
            self.app.core.action_registry.execute(
                "group.select", self.selected_group_number
            )
        self.channels_view.flowbox.unselect_all()
        self.channels_view.last_selected_channel = ""
        self.channels_view.update()
        self._update_details_and_sensitivity()

    def update_group_tile(self, group: Group) -> bool:
        """Update an existing GroupWidget tile in place without rebuilding FlowBox."""
        for child in self.flowbox.get_children():
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            widget = fb_child.get_child()
            if isinstance(widget, GroupWidget) and widget.number == group.index:
                widget.update_from_group(group)
                if self.selected_group_number == group.index:
                    self.channels_view.update()
                self._update_details_and_sensitivity()
                return True
        return False

    def refresh(self) -> None:
        """Rebuild Group tiles from LightShow.groups and preserve selection."""
        self.lightshow = self.app.core.lightshow
        self.populate_tab()

        restored = False
        self._updating_selection = True
        try:
            if self.selected_group_number is not None:
                for child in self.flowbox.get_children():
                    fb_child = typing.cast(Gtk.FlowBoxChild, child)
                    group_widget = typing.cast(GroupWidget, fb_child.get_child())
                    if (
                        group_widget
                        and group_widget.number == self.selected_group_number
                    ):
                        self.flowbox.select_child(fb_child)
                        self.last_group_selected = str(fb_child.get_index())
                        restored = True
                        break
            if not restored:
                self.selected_group_number = None
                self.last_group_selected = ""
            self.channels_view.invalidate_cache()
            self.channels_view.update()
            self._update_details_and_sensitivity()
        finally:
            self._updating_selection = False

    def _get_source_channels(self) -> list[int]:
        """Return ordered local channel selection if non-empty, else Live selection."""
        local = self.channels_view.get_selected_channels()
        if local:
            return local
        return list(self.app.core.selected_channels)

    def select_group_in_live(self, group_nb: float) -> list[int]:
        """Recall *group_nb*'s ordered channels into Live channel selection."""
        group = self.lightshow.groups.get(group_nb)
        if group is None:
            return []
        ordered = list(group.channels)
        last_sel = ordered[-1] if ordered else None
        self.app.core.action_registry.execute(
            "channel.select_channels",
            channels=ordered,
            last_selected=last_sel,
        )
        return ordered

    def select_selected_in_live(self) -> list[int]:
        """Recall currently selected group tile into Live channel selection."""
        group = self.get_selected_group()
        if group is None:
            return []
        return self.select_group_in_live(group.index)

    def record_group(self, group_nb: float | None = None) -> float | None:
        """Create (or overwrite) a group from local or Live channel selection."""
        if group_nb is None:
            raw = self.commandline.get_string().strip()
            if raw and is_non_nul_float(raw):
                target_nb = float(raw)
                self.app.core.action_registry.execute("commandline.clear")
            else:
                target_nb = self.lightshow.groups.get_next_index()
        else:
            target_nb = float(group_nb)

        channels = self._get_source_channels()
        self.selected_group_number = target_nb
        if self.lightshow.groups.get(target_nb) is not None:
            self.app.core.action_registry.execute(
                "group.update_channels", target_nb, channels
            )
        else:
            self.app.core.action_registry.execute("group.new", target_nb, channels)
        self.channels_view.flowbox.unselect_all()
        self.app.core.action_registry.execute("group.select", target_nb)
        self.refresh()
        return target_nb

    def update_selected_channels(self) -> None:
        """Update selected group channel list from local or Live selection."""
        group = self.get_selected_group()
        if group is None:
            return
        channels = self._get_source_channels()
        self.channels_view.flowbox.unselect_all()
        self.app.core.action_registry.execute(
            "group.update_channels", group.index, channels
        )
        self.update_group_tile(group)

    def reverse_selected_order(self) -> None:
        """Reverse the ordered channel sequence of the selected group."""
        group = self.get_selected_group()
        if group is None or len(group.channels) <= 1:
            return
        reversed_chs = list(reversed(group.channels))
        self.app.core.action_registry.execute(
            "group.update_channels", group.index, reversed_chs
        )
        self.update_group_tile(group)

    def sort_selected_order(self) -> None:
        """Sort channels of the selected group in ascending numerical order."""
        group = self.get_selected_group()
        if group is None or len(group.channels) <= 1:
            return
        sorted_chs = sorted(group.channels)
        self.app.core.action_registry.execute(
            "group.update_channels", group.index, sorted_chs
        )
        self.update_group_tile(group)

    def clear_selected_channels(self) -> None:
        """Clear all channels from the selected group."""
        group = self.get_selected_group()
        if group is None or not group.channels:
            return
        self.app.core.action_registry.execute("group.update_channels", group.index, [])
        self.update_group_tile(group)

    def rename_selected(self) -> None:
        """Open popover to rename the selected group."""
        if (tile := self.get_selected_tile()) is not None:
            tile.open_rename_popover()

    def delete_selected(self) -> None:
        """Delete the currently selected group."""
        group = self.get_selected_group()
        if group is None:
            return
        groups_list = list(self.lightshow.groups)
        next_group_number: float | None = None
        if len(groups_list) > 1 and group in groups_list:
            index = groups_list.index(group)
            if index + 1 == len(groups_list):
                next_group_number = groups_list[index - 1].index
            else:
                next_group_number = groups_list[index + 1].index

        self.selected_group_number = next_group_number
        self.app.core.action_registry.execute("group.delete", group.index)
        self.refresh()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab with the icon clicked."""
        self.tabs.close("groups")

    def _keypress_f2(self) -> None:
        """Rename selected Group."""
        self.rename_selected()

    def _keypress_q(self) -> None:
        """Previous Group."""
        self._keypress_left()

    def _keypress_w(self) -> None:
        """Next Group."""
        self._keypress_right()

    def _keypress_right(self) -> None:
        """Next Group."""
        if not self.last_group_selected:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        elif child := self.flowbox.get_child_at_index(
            int(self.last_group_selected) + 1
        ):
            self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))

    def _keypress_left(self) -> None:
        """Previous Group."""
        if not self.last_group_selected:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        elif int(self.last_group_selected) > 0:
            if child := self.flowbox.get_child_at_index(
                int(self.last_group_selected) - 1
            ):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))

    def _keypress_down(self) -> None:
        """Group on Next Line."""
        if not self.last_group_selected:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected))
            if child is not None:
                allocation = child.get_allocation()
                if next_child := self.flowbox.get_child_at_pos(
                    allocation.x, allocation.y + allocation.height + 4
                ):
                    self._select_flowbox_child(
                        typing.cast(Gtk.FlowBoxChild, next_child)
                    )

    def _keypress_up(self) -> None:
        """Group on Previous Line."""
        if not self.last_group_selected:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        else:
            child = self.flowbox.get_child_at_index(int(self.last_group_selected))
            if child is not None:
                allocation = child.get_allocation()
                y_pos = int(allocation.y - allocation.height / 2)
                if prev_child := self.flowbox.get_child_at_pos(allocation.x, y_pos):
                    self._select_flowbox_child(
                        typing.cast(Gtk.FlowBoxChild, prev_child)
                    )

    def _keypress_delete(self) -> None:
        """Delete selected group."""
        self.delete_selected()

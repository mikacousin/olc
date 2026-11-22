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

import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from olc.gtk3.widgets.common import (
    SystemFontManager,
    TextAnchor,
    create_pango_layout_for_widget,
    create_system_font_description,
    draw_cached_numeric_text,
    register_system_font_listener,
    rounded_rectangle,
    rounded_rectangle_fill,
)

if typing.TYPE_CHECKING:
    from olc.gtk3.group import GroupTab
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.group import Group
    from olc.show.lightshow import LightShow

_GROUP_ACCENT_RGB: tuple[float, float, float] = (0.38, 0.56, 0.94)


def format_group_number(number: float) -> str:
    """Format group index concisely (integers without .0, decimals compactly)."""
    val = float(number)
    return str(int(val)) if val.is_integer() else f"{val:g}"


def format_channel_summary(channels: typing.Sequence[int], max_tokens: int = 4) -> str:
    """Summarize ordered channels cleanly while preserving selection direction."""
    if not channels:
        return ""
    tokens: list[str] = []
    idx = 0
    total = len(channels)
    while idx < total:
        start = int(channels[idx])
        if idx + 1 < total:
            step = int(channels[idx + 1]) - start
            if step in (-1, 1):
                end_idx = idx + 1
                while (
                    end_idx + 1 < total
                    and int(channels[end_idx + 1]) - int(channels[end_idx]) == step
                ):
                    end_idx += 1
                if end_idx - idx >= 2:
                    tokens.append(f"{start}-{int(channels[end_idx])}")
                    idx = end_idx + 1
                    continue
        tokens.append(str(start))
        idx += 1
    if len(tokens) > max_tokens:
        return ", ".join(tokens[:max_tokens]) + ", \u2026"
    return ", ".join(tokens)


class GroupWidget(Gtk.Widget):
    """Clickable Cairo tile displaying a Group with inline rename."""

    __gtype_name__ = "GroupWidget"

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(
        self,
        number: float,
        name: str,
        *,
        channels: list[int] | None = None,
        lightshow: LightShow | None = None,
        tabs: Tabs | None = None,
        window: Window | None = None,
        group_tab: GroupTab | None = None,
    ) -> None:
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.group_tab = group_tab
        self.number = float(number)
        self.name = name
        self.channels: list[int] = list(channels) if channels is not None else []

        Gtk.Widget.__init__(self)
        self.set_size_request(116, 78)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)
        register_system_font_listener(self.queue_draw)
        self.connect("destroy", self._on_destroy)

        self.popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.rename_entry = Gtk.Entry()
        self.rename_entry.set_has_frame(False)
        self.rename_entry.set_text(name)
        self.rename_entry.connect("activate", self.on_edit)
        vbox.pack_start(self.rename_entry, False, True, 10)
        vbox.show_all()
        self.popover.add(vbox)
        self.popover.set_relative_to(self)
        self.popover.set_position(Gtk.PositionType.BOTTOM)

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        SystemFontManager.unregister_listener(self.queue_draw)

    def open_rename_popover(self) -> None:
        """Open inline rename popover focused on the current label."""
        self.rename_entry.set_text(self.name)
        self.popover.popup()
        self.rename_entry.grab_focus()
        self.rename_entry.select_region(0, -1)

    def update_from_group(self, group: Group) -> None:
        """Update tile label and channel list in place from *group*."""
        self.name = group.text
        self.channels = list(group.channels)
        self.rename_entry.set_text(self.name)
        self.queue_draw()

    def on_edit(self, widget: Gtk.Entry) -> None:
        """Edit Group text."""
        text = widget.get_text()
        core = None
        if self.group_tab is not None:
            core = self.group_tab.app.core
        elif self.window is not None:
            core = self.window.app.core
        if core is not None:
            core.action_registry.execute("group.rename", self.number, text)
        self.popover.popdown()

    def on_click(self, _tgt: Gtk.Widget, event: Gdk.Event) -> bool:
        """Select tile on click; recall in Live on Direct Select or double-click."""
        parent = self.get_parent()
        if isinstance(parent, Gtk.FlowBoxChild):
            flowbox = parent.get_parent()
            if isinstance(flowbox, Gtk.FlowBox):
                flowbox.unselect_all()
                flowbox.select_child(parent)

        ev_type = getattr(event, "type", None)
        if self.group_tab is not None:
            if (
                ev_type == Gdk.EventType.BUTTON_PRESS
                and self.group_tab.direct_select_toggle.get_active()
            ):
                self.group_tab.select_group_in_live(self.number)
                return True
            if (
                ev_type == Gdk.EventType(5)
                and not self.group_tab.direct_select_toggle.get_active()
            ):
                self.group_tab.select_group_in_live(self.number)
                return True
        return False

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Group card tile using Cairo and Pango."""
        allocation = self.get_allocation()
        width = float(allocation.width) if allocation.width > 0 else 116.0
        height = float(allocation.height) if allocation.height > 0 else 78.0

        # Theme background
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Selection state
        parent = self.get_parent()
        is_selected = (
            parent is not None and getattr(parent, "is_selected", lambda: False)()
        )

        # Tile card body
        if is_selected:
            cr.set_source_rgb(0.42, 0.30, 0.12)
        else:
            cr.set_source_rgb(0.24, 0.25, 0.27)
        area = (1.0, width - 1.0, 1.0, height - 1.0)
        rounded_rectangle_fill(cr, area, 8.0)

        # Top accent bar
        cr.set_source_rgb(*_GROUP_ACCENT_RGB)
        bar_area = (3.0, width - 3.0, 3.0, 10.0)
        rounded_rectangle_fill(cr, bar_area, 3.0)

        # Selection border
        if is_selected:
            cr.set_source_rgb(0.95, 0.72, 0.25)
            cr.set_line_width(1.6)
        else:
            cr.set_source_rgb(0.35, 0.37, 0.40)
            cr.set_line_width(1.0)
        rounded_rectangle(cr, area, 8.0)

        # Group badge ("G 1" / "G 1.5")
        cr.set_source_rgb(*_GROUP_ACCENT_RGB)
        badge_txt = f"G {format_group_number(self.number)}"
        num_layout = create_pango_layout_for_widget(cr, badge_txt)
        ndesc = create_system_font_description()
        ndesc.set_weight(Pango.Weight.BOLD)
        ndesc.set_size(10 * Pango.SCALE)
        num_layout.set_font_description(ndesc)
        cr.move_to(8.0, 11.0)
        PangoCairo.show_layout(cr, num_layout)

        # Channel count top right
        count_txt = f"{len(self.channels)} ch"
        cr.set_source_rgb(0.66, 0.70, 0.75)
        draw_cached_numeric_text(
            cr,
            width - 8.0,
            23.0,
            count_txt,
            8.0,
            weight=Pango.Weight.NORMAL,
            anchor=TextAnchor.BASELINE_RIGHT,
        )

        # Group label
        if self.name:
            cr.set_source_rgb(0.94, 0.94, 0.96)
            name_layout = create_pango_layout_for_widget(cr, self.name)
            mdesc = create_system_font_description()
            mdesc.set_weight(Pango.Weight.NORMAL)
            mdesc.set_size(int(9.5 * Pango.SCALE))
            name_layout.set_font_description(mdesc)
            name_layout.set_width(int(max(20.0, width - 16.0) * Pango.SCALE))
            name_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            name_layout.set_height(-2)
            name_layout.set_ellipsize(Pango.EllipsizeMode.END)
            cr.move_to(8.0, 30.0)
            PangoCairo.show_layout(cr, name_layout)

        # Compact channel order preview at bottom
        summary = format_channel_summary(self.channels) or "Empty"
        cr.set_source_rgb(0.62, 0.76, 0.86) if self.channels else cr.set_source_rgb(
            0.52, 0.55, 0.58
        )
        sum_layout = create_pango_layout_for_widget(cr, summary)
        sdesc = create_system_font_description()
        sdesc.set_weight(Pango.Weight.NORMAL)
        sdesc.set_size(int(8.0 * Pango.SCALE))
        sum_layout.set_font_description(sdesc)
        sum_layout.set_width(int(max(20.0, width - 16.0) * Pango.SCALE))
        sum_layout.set_ellipsize(Pango.EllipsizeMode.END)
        cr.move_to(8.0, height - 18.0)
        PangoCairo.show_layout(cr, sum_layout)
        return False

    def do_realize(self) -> None:
        """Realize widget"""
        allocation = self.get_allocation()
        attr = Gdk.WindowAttr()
        attr.window_type = Gdk.WindowType.CHILD
        attr.x = allocation.x
        attr.y = allocation.y
        attr.width = allocation.width
        attr.height = allocation.height
        attr.visual = self.get_visual()
        attr.event_mask = (
            self.get_events()
            | Gdk.EventMask.EXPOSURE_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.TOUCH_MASK
        )
        wat = Gdk.WindowAttributesType
        mask = wat.X | wat.Y | wat.VISUAL

        window = Gdk.Window(self.get_parent_window(), attr, mask)
        self.set_window(window)
        self.register_window(window)

        self.set_realized(True)
        window.set_background_pattern(None)

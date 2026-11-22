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
from gi.repository import Gdk, Gtk, Pango

from olc.core.channel_snapshot import AttributeFamilySnapshot, format_family_readout
from olc.core.selection import SelectAddAction, SelectRemoveAction, SelectThruAction
from olc.core.tracking import TrackingDisplayState, get_tracking_color
from olc.devices.device import (
    COLOR_CHANNEL_TYPES,
    POSITION_CHANNEL_TYPES,
    ChannelType,
    FixtureType,
)
from olc.gtk3.widgets.common import (
    TextAnchor,
    create_pango_layout_for_widget,
    create_system_font_description,
    draw_cached_numeric_text,
    draw_pango_layout_anchored,
    register_system_font_listener,
)

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.core.channel_snapshot import ChannelDisplaySnapshot
    from olc.core.commandline import CoreCommandLine
    from olc.devices.device import LightingDevice
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.widgets.channels_view import ChannelsView
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow

COMPACT_BASE_WIDTH: int = 80
COMPACT_BASE_HEIGHT: int = 80
SUMMARY_BASE_WIDTH: int = 128
SUMMARY_BASE_HEIGHT: int = 124

_PALETTE_CYAN: tuple[float, float, float] = (0.20, 0.88, 0.96)
_PALETTE_CYAN_TEXT: tuple[float, float, float] = (0.35, 0.92, 0.98)
_EFFECT_MAGENTA: tuple[float, float, float] = (0.85, 0.35, 0.95)
_MANUAL_CORAL: tuple[float, float, float] = (0.95, 0.35, 0.35)
_MIB_AMBER: tuple[float, float, float] = (1.0, 0.65, 0.15)
_PARK_AMBER: tuple[float, float, float] = (1.0, 0.7, 0.0)
_MUTED_GREY: tuple[float, float, float] = (0.50, 0.54, 0.57)
_GROUP_MEMBER_FILL: tuple[float, float, float] = (0.16, 0.27, 0.36)
_GROUP_MEMBER_TEXT: tuple[float, float, float] = (0.45, 0.85, 1.0)

_COMPACT_COLOR_TYPES: frozenset[ChannelType] = COLOR_CHANNEL_TYPES | frozenset(
    {ChannelType.COLOR_TEMP, ChannelType.COLOR_WHEEL}
)
_COMPACT_BEAM_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.ZOOM,
        ChannelType.FOCUS,
        ChannelType.IRIS,
        ChannelType.STROBE,
        ChannelType.GOBO_WHEEL,
        ChannelType.FROST,
        ChannelType.PRISM,
    }
)


# pylint: disable=too-many-instance-attributes
class ChannelWidget(Gtk.DrawingArea):
    """Channel tile widget supporting Compact and Summary+ (tombstone) formats."""

    __gtype_name__ = "ChannelWidget"

    app: Application
    lightshow: LightShow
    settings: Gio.Settings
    window: Window | None
    tabs: Tabs | None
    channels_view: ChannelsView | None
    commandline: CoreCommandLine
    level: int | float
    next_level: int | float
    display_format: str
    readout_mode: str
    show_labels: bool
    membership_mode: bool
    membership_order: int | None
    scale: float
    width: int
    height: int

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        channel: int,
        level: int | float,
        next_level: int | float,
        app: Application,
        window: Window | None = None,
        tabs: Tabs | None = None,
        channels_view: ChannelsView | None = None,
    ) -> None:
        super().__init__()
        self.app = app
        self.lightshow = app.core.lightshow
        self.settings = app.settings
        self.window = window if window is not None else app.window
        self.tabs = tabs if tabs is not None else app.tabs
        self.channels_view = channels_view
        self.commandline = app.core.commandline

        self.channel = str(channel)
        self.level = level
        self.next_level = next_level
        self.clicked = False
        self.color_level = {"red": 0.9, "green": 0.9, "blue": 0.9}
        self.display_format = (
            channels_view.display_format if channels_view is not None else "Compact"
        )
        self.readout_mode = (
            channels_view.readout_mode if channels_view is not None else "Auto"
        )
        self.show_labels = (
            bool(channels_view.show_labels) if channels_view is not None else True
        )
        self.membership_mode = False
        self.membership_order = None
        self.scale = 1.0
        base_w, base_h = self.get_base_dimensions()
        self.width = round(base_w * self.scale)
        self.height = round(base_h * self.scale)
        self._last_requested_size: tuple[int, int] = (self.width, self.height)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_click)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.connect("touch-event", self.on_click)
        self.set_size_request(self.width, self.height)
        register_system_font_listener(self.queue_draw)

    def _get_context(
        self, target: Gtk.Widget
    ) -> tuple[ChannelsView | None, Gtk.FlowBox | None, Gtk.FlowBoxChild | None]:
        """Find containing ChannelsView, FlowBox, and FlowBoxChild for target."""
        flowboxchild_raw = target.get_parent()
        if flowboxchild_raw is None:
            return None, None, None
        flowboxchild = typing.cast("Gtk.FlowBoxChild", flowboxchild_raw)
        flowbox_raw = flowboxchild.get_parent()
        if flowbox_raw is None:
            return None, None, None
        flowbox = typing.cast("Gtk.FlowBox", flowbox_raw)
        if self.channels_view is not None:
            return self.channels_view, flowbox, flowboxchild
        ancestor: Gtk.Widget | None = flowbox.get_parent()
        while ancestor is not None:
            if hasattr(ancestor, "selection_manager") and hasattr(ancestor, "flowbox"):
                return typing.cast("ChannelsView", ancestor), flowbox, flowboxchild
            ancestor = ancestor.get_parent()
        return None, None, None

    def on_click(self, target: Gtk.Widget, event: Gdk.EventButton) -> None:
        """Select clicked widget

        Args:
            target: Target
            event: Gdk.EventButton or Gdk.EventTouch
        """
        channels_view, flowbox, flowboxchild = self._get_context(target)
        if channels_view is None or flowbox is None or flowboxchild is None:
            return

        accel_mask = Gtk.accelerator_get_default_mod_mask()
        channel_num = int(self.channel)

        if event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
            channels_view.selection_manager.execute_action(
                SelectThruAction, channel_num
            )
        elif channel_num in channels_view.selection_manager.selected_channels:
            channels_view.selection_manager.execute_action(
                SelectRemoveAction, channel_num
            )
        else:
            channels_view.selection_manager.execute_action(SelectAddAction, channel_num)

    def get_base_dimensions(self) -> tuple[int, int]:
        """Return base (width, height) in unscaled pixels for the active format."""
        if self.display_format == "Summary+":
            return (SUMMARY_BASE_WIDTH, SUMMARY_BASE_HEIGHT)
        return (COMPACT_BASE_WIDTH, COMPACT_BASE_HEIGHT)

    def update_dimensions(self) -> bool:
        """Recompute pixel dimensions and call set_size_request only if changed."""
        base_w, base_h = self.get_base_dimensions()
        new_w = round(base_w * self.scale)
        new_h = round(base_h * self.scale)
        self.width = new_w
        self.height = new_h
        if (new_w, new_h) != self._last_requested_size:
            self._last_requested_size = (new_w, new_h)
            self.set_size_request(new_w, new_h)
            return True
        return False

    def set_display_format(self, fmt: str) -> None:
        """Switch tile display format ('Compact' or 'Summary+') and resize."""
        target = "Summary+" if str(fmt).strip().lower() == "summary+" else "Compact"
        changed = target != self.display_format
        self.display_format = target
        resized = self.update_dimensions()
        if changed or resized:
            self.queue_resize()
        self.queue_draw()

    def set_readout_mode(self, mode: str) -> None:
        """Switch parameter readout mode and redraw."""
        self.readout_mode = str(mode)
        self.queue_draw()

    def set_show_labels(self, show: bool) -> None:
        """Show or hide fixture label in tile header and redraw."""
        self.show_labels = bool(show)
        self.queue_draw()

    def set_scale(self, scale: float) -> None:
        """Update widget zoom scale cleanly within [0.5, 2.0]."""
        self.scale = max(0.5, min(2.0, float(scale)))
        if self.update_dimensions():
            self.queue_resize()
        self.queue_draw()

    def get_snapshot(self) -> ChannelDisplaySnapshot | None:
        """Return ChannelDisplaySnapshot from parent ChannelsView, if available."""
        if self.channels_view is None:
            return None
        return self.channels_view.get_channel_snapshot(int(self.channel))

    def _uses_non_live_snapshot(self) -> bool:
        return bool(
            self.channels_view is not None
            and not getattr(self.channels_view, "is_live_view", False)
        )

    def get_patched_device(self) -> LightingDevice | None:
        """Return the LightingDevice patched at this channel ID, if any."""
        return self.lightshow.patch.devices.get(int(self.channel))

    def has_color_capability(self) -> bool:
        """Return True if the channel/device has color mixing capability."""
        if self._uses_non_live_snapshot():
            if (snap := self.get_snapshot()) is not None:
                return snap.has_color
        dev = self.get_patched_device()
        if dev is None:
            return False
        if hasattr(dev, "has_color_capability"):
            return bool(dev.has_color_capability)
        return any(ch.channel_type in COLOR_CHANNEL_TYPES for ch in dev.channels)

    def get_preview_rgb(self) -> tuple[float, float, float] | None:
        """Return normalized (r, g, b) preview color (RGB and CMY)."""
        if self._uses_non_live_snapshot():
            if (snap := self.get_snapshot()) is not None:
                return snap.preview_rgb
        dev = self.get_patched_device()
        if dev is None or not self.has_color_capability():
            return None
        return dev.get_preview_rgb()

    def is_moving_head(self) -> bool:
        """Return True if the patched device is a moving head or has Pan/Tilt."""
        if self._uses_non_live_snapshot():
            if (snap := self.get_snapshot()) is not None:
                return snap.is_moving_head
        dev = self.get_patched_device()
        if dev is None:
            return False
        if dev.fixture_type == FixtureType.MOVING_HEAD:
            return True
        return any(
            ch.channel_type in (ChannelType.PAN, ChannelType.TILT)
            for ch in dev.channels
        )

    def _is_parked(self, snap: ChannelDisplaySnapshot | None) -> bool:
        if snap is not None:
            return snap.is_parked
        park_mgr = getattr(self.lightshow, "park", None)
        return bool(
            park_mgr is not None and park_mgr.is_channel_parked(int(self.channel))
        )

    def _normalized_level_for_bar(self, snap: ChannelDisplaySnapshot | None) -> float:
        lvl = float(self.level)
        if lvl <= 1.0:
            return max(0.0, lvl)
        if snap is not None and 0.0 <= snap.intensity <= 1.0:
            return snap.intensity
        return min(1.0, lvl / 255.0)

    @staticmethod
    def _get_family_status_rgb(
        family_snap: AttributeFamilySnapshot,
        *,
        is_mib_channel: bool = False,
    ) -> tuple[float, float, float]:
        if family_snap.effect_ref is not None:
            return _EFFECT_MAGENTA
        if family_snap.is_manual:
            return _MANUAL_CORAL
        if family_snap.palette_ref is not None:
            return _PALETTE_CYAN
        if is_mib_channel or family_snap.tracking_state == TrackingDisplayState.MIB:
            return _MIB_AMBER
        if family_snap.tracking_state != TrackingDisplayState.INACTIVE:
            col = get_tracking_color(family_snap.tracking_state)
            return (
                float(col.get("red", 0.9)),
                float(col.get("green", 0.9)),
                float(col.get("blue", 0.9)),
            )
        return _MUTED_GREY

    def _draw_ellipsized_text(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        cr: cairo.Context,
        x: float,
        y: float,
        max_width: float,
        text: str,
        font_size_pt: float,
        weight: Pango.Weight = Pango.Weight.NORMAL,
        anchor: TextAnchor = TextAnchor.BASELINE_LEFT,
    ) -> None:
        """Draw single-line text ellipsized cleanly within *max_width*."""
        if not text or max_width <= 2.0:
            return
        try:
            desc = create_system_font_description()
            desc.set_weight(weight)
            desc.set_size(int(max(4.0, font_size_pt) * Pango.SCALE))
            layout = create_pango_layout_for_widget(cr, text, font_desc=desc)
            layout.set_width(int(max(1.0, max_width) * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            draw_pango_layout_anchored(cr, layout, x, y, anchor=anchor)
        except TypeError:
            draw_cached_numeric_text(
                cr, x, y, text, font_size_pt, weight=weight, anchor=anchor
            )

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw widget in active format ('Compact' or 'Summary+')."""
        self.update_dimensions()
        allocation = self.get_allocation()
        percent_level = self.settings.get_boolean("percent")
        snap = self.get_snapshot()

        if self.display_format == "Summary+":
            self._draw_summary_plus(cr, allocation, percent_level, snap)
        else:
            self._draw_compact(cr, allocation, percent_level, snap)
        return False

    def _draw_compact(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        percent_level: bool,
        snap: ChannelDisplaySnapshot | None,
    ) -> None:
        """Draw compact 80x80 tile with live color preview and micro IFCB markers."""
        if self.membership_mode:
            self._draw_compact_membership(cr, allocation)
            return
        self._draw_background(cr, allocation, header_height=18 * self.scale)
        self._draw_channel_number(cr)
        self._draw_park_badge(cr, snap)
        self._draw_device_indicators(cr, allocation, snap)
        self._draw_compact_ifcb_markers(cr, allocation, snap)
        self._draw_level(cr, percent_level, snap)
        self._draw_level_bar(cr, allocation, snap)
        self._draw_next_level(cr, percent_level)

    def _draw_compact_membership(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
    ) -> None:
        """Draw compact 80x80 tile showing pure group membership and selection rank."""
        s = self.scale
        alloc_w = max(self.width, allocation.width)
        hdr_h = 18 * s
        self._draw_background(cr, allocation, header_height=hdr_h)
        if self.membership_order is not None:
            cr.rectangle(
                4, 4 + hdr_h, max(1.0, alloc_w - 8), max(1.0, self.height - 8 - hdr_h)
            )
            cr.set_source_rgb(*_GROUP_MEMBER_FILL)
            cr.fill()
        self._draw_channel_number(cr)
        if self.membership_order is not None:
            cr.set_source_rgb(*_GROUP_MEMBER_TEXT)
            draw_cached_numeric_text(
                cr,
                alloc_w / 2.0,
                52 * s,
                f"#{self.membership_order}",
                13.0 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_CENTER,
            )

    def _draw_summary_plus_membership(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
    ) -> None:
        """Draw Summary+ tombstone tile showing pure group membership and rank."""
        s = self.scale
        alloc_w = max(self.width, allocation.width)
        hdr_h = 20 * s
        self._draw_background(cr, allocation, header_height=hdr_h)

        if self.membership_order is not None:
            cr.rectangle(
                4,
                4 + hdr_h,
                max(1.0, alloc_w - 8),
                max(1.0, self.height - 8 - hdr_h),
            )
            cr.set_source_rgb(*_GROUP_MEMBER_FILL)
            cr.fill()

        self._set_channel_number_color(cr)
        ch_draw = draw_cached_numeric_text(
            cr,
            7 * s,
            17 * s,
            self.channel,
            10.5 * s,
            weight=Pango.Weight.BOLD,
            anchor=TextAnchor.BASELINE_LEFT,
        )
        ch_right_x = 7 * s + max(14 * s, float(ch_draw[2])) + 5 * s

        if self.show_labels:
            dev = self.get_patched_device()
            label = str(dev.label or dev.fixture_name) if dev is not None else ""
            if label:
                cr.set_source_rgb(0.78, 0.80, 0.82)
                self._draw_ellipsized_text(
                    cr,
                    ch_right_x,
                    16.5 * s,
                    alloc_w - 6 * s - ch_right_x - 3 * s,
                    label,
                    8.0 * s,
                    weight=Pango.Weight.NORMAL,
                )

        if self.membership_order is not None:
            cr.set_source_rgb(*_GROUP_MEMBER_TEXT)
            draw_cached_numeric_text(
                cr,
                alloc_w / 2.0,
                60 * s,
                f"#{self.membership_order}",
                16.0 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_CENTER,
            )
            cr.set_source_rgb(0.72, 0.84, 0.92)
            draw_cached_numeric_text(
                cr,
                alloc_w / 2.0,
                82 * s,
                "In Group",
                8.5 * s,
                weight=Pango.Weight.NORMAL,
                anchor=TextAnchor.BASELINE_CENTER,
            )

    def _draw_summary_plus(  # pylint: disable=too-many-locals, too-many-branches
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        percent_level: bool,
        snap: ChannelDisplaySnapshot | None,
    ) -> None:
        """Draw Summary+ tombstone tile (header, label, level, color strip, IFCB)."""
        if self.membership_mode:
            self._draw_summary_plus_membership(cr, allocation)
            return
        s = self.scale
        alloc_w = max(self.width, allocation.width)
        self._draw_background(cr, allocation, header_height=20 * s)

        # Header left: Channel number
        self._set_channel_number_color(cr)
        ch_draw = draw_cached_numeric_text(
            cr,
            7 * s,
            17 * s,
            self.channel,
            10.5 * s,
            weight=Pango.Weight.BOLD,
            anchor=TextAnchor.BASELINE_LEFT,
        )
        ch_right_x = 7 * s + max(14 * s, float(ch_draw[2])) + 5 * s

        # Header right badges: Park / Manual / MIB
        is_parked = self._is_parked(snap)
        badge_right_x = alloc_w - 6 * s
        if is_parked:
            cr.set_source_rgb(*_PARK_AMBER)
            res = draw_cached_numeric_text(
                cr,
                badge_right_x,
                16.5 * s,
                "P",
                8.5 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_RIGHT,
            )
            badge_right_x -= max(9 * s, float(res[2])) + 3 * s
        if snap is not None and snap.effect_ref is not None:
            cr.set_source_rgb(*_EFFECT_MAGENTA)
            res = draw_cached_numeric_text(
                cr,
                badge_right_x,
                16.5 * s,
                "FX",
                8.0 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_RIGHT,
            )
            badge_right_x -= max(14 * s, float(res[2])) + 3 * s
        if snap is not None and snap.is_manual:
            cr.set_source_rgb(*_MANUAL_CORAL)
            res = draw_cached_numeric_text(
                cr,
                badge_right_x,
                16.5 * s,
                "M",
                8.5 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_RIGHT,
            )
            badge_right_x -= max(10 * s, float(res[2])) + 3 * s
        elif snap is not None and snap.is_mib:
            cr.set_source_rgb(*_MIB_AMBER)
            res = draw_cached_numeric_text(
                cr,
                badge_right_x,
                16.5 * s,
                "MIB",
                7.5 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_RIGHT,
            )
            badge_right_x -= max(18 * s, float(res[2])) + 3 * s

        # Header center: fixture label or fixture model name
        label = ""
        if self.show_labels:
            if snap is not None:
                label = snap.device_label or snap.fixture_name
            else:
                dev = self.get_patched_device()
                if dev is not None:
                    label = str(dev.label or dev.fixture_name)
        if label:
            cr.set_source_rgb(0.78, 0.80, 0.82)
            self._draw_ellipsized_text(
                cr,
                ch_right_x,
                16.5 * s,
                badge_right_x - ch_right_x - 3 * s,
                label,
                8.0 * s,
                weight=Pango.Weight.NORMAL,
            )

        # Intensity body: large level + level bar + next level + intensity source/ref
        self._set_level_color(cr, is_parked)
        if self.level > 0.0 or self.next_level > 0.0:
            lvl_txt = self._format_intensity_text(self.level, percent_level)
            draw_cached_numeric_text(
                cr,
                8 * s,
                46 * s,
                lvl_txt,
                15.0 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_LEFT,
            )

        bar_fill = self._normalized_level_for_bar(snap)
        cr.rectangle(
            alloc_w - 10 * s,
            58 * s,
            5.5 * s,
            -(32.0 * s) * bar_fill,
        )
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()

        if int(self.channel) not in self.lightshow.independents.get_channels():
            if self.next_level < self.level:
                self._draw_summary_next_indicator(cr, percent_level, up=False)
            elif self.next_level > self.level:
                self._draw_summary_next_indicator(cr, percent_level, up=True)

        if snap is not None and (
            snap.intensity_ref is not None or snap.intensity_effect_ref is not None
        ):
            mode_low = self.readout_mode.strip().lower()
            parts: list[str] = []
            if snap.intensity_ref is not None:
                parts.append(
                    snap.intensity_ref.short_ref
                    if mode_low == "ref"
                    else (snap.intensity_ref.label or snap.intensity_ref.short_ref)
                )
            if snap.intensity_effect_ref is not None:
                parts.append(
                    snap.intensity_effect_ref.label
                    if (mode_low == "label" and snap.intensity_effect_ref.label)
                    else snap.intensity_effect_ref.short_ref
                )
            if snap.intensity_effect_ref is not None:
                cr.set_source_rgb(*_EFFECT_MAGENTA)
            elif (
                snap.intensity_source == "manual"
                or snap.intensity_state == TrackingDisplayState.MANUAL
            ):
                cr.set_source_rgb(*_MANUAL_CORAL)
            else:
                cr.set_source_rgb(*_PALETTE_CYAN_TEXT)
            self._draw_ellipsized_text(
                cr, 8 * s, 58 * s, alloc_w - 22 * s, " + ".join(parts), 7.5 * s
            )
        elif snap is not None and snap.intensity_source in (
            "park",
            "fader",
            "independent",
        ):
            src_map = {"park": "Park", "fader": "Sub", "independent": "Ind"}
            cr.set_source_rgb(0.68, 0.72, 0.74)
            draw_cached_numeric_text(
                cr,
                8 * s,
                58 * s,
                src_map[snap.intensity_source],
                7.5 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_LEFT,
            )

        # Full-width real-time color strip
        rgb = (
            snap.preview_rgb
            if self._uses_non_live_snapshot() and snap is not None
            else self.get_preview_rgb()
        )
        strip_x = 7 * s
        strip_y = 62 * s
        strip_w = alloc_w - 14 * s
        strip_h = 8 * s
        if rgb is not None:
            cr.rectangle(strip_x, strip_y, strip_w, strip_h)
            cr.set_source_rgb(rgb[0], rgb[1], rgb[2])
            cr.fill_preserve()
            has_col_ref = snap is not None and snap.color.palette_ref is not None
            is_col_manual = snap is not None and snap.color.is_manual
            if is_col_manual:
                cr.set_source_rgb(*_MANUAL_CORAL)
                cr.set_line_width(1.5)
            elif has_col_ref:
                cr.set_source_rgb(*_PALETTE_CYAN)
                cr.set_line_width(1.5)
            else:
                cr.set_source_rgb(0.55, 0.55, 0.55)
                cr.set_line_width(1.0)
            cr.stroke()
            if has_col_ref:
                cr.rectangle(strip_x, strip_y, max(2.5, 3.0 * s), strip_h)
                cr.set_source_rgb(*_PALETTE_CYAN)
                cr.fill()
        else:
            cr.set_source_rgb(0.27, 0.30, 0.32)
            cr.set_line_width(1.0)
            cr.move_to(strip_x, strip_y + 4 * s)
            cr.line_to(strip_x + strip_w, strip_y + 4 * s)
            cr.stroke()

        # IFCB footer slots (F, C, B)
        ifcb_rows: list[tuple[str, AttributeFamilySnapshot]] = []
        if snap is not None:
            for tag, fam in (("F", snap.focus), ("C", snap.color), ("B", snap.beam)):
                if fam.available:
                    ifcb_rows.append((tag, fam))

        if ifcb_rows:
            mode_low = self.readout_mode.strip().lower()
            for idx, (tag, fam) in enumerate(ifcb_rows[:3]):
                y_base = (83 + idx * 14) * s
                tag_rgb = self._get_family_status_rgb(
                    fam, is_mib_channel=snap.is_mib if snap else False
                )
                cr.set_source_rgb(*tag_rgb)
                draw_cached_numeric_text(
                    cr,
                    8 * s,
                    y_base,
                    tag,
                    8.0 * s,
                    weight=Pango.Weight.BOLD,
                    anchor=TextAnchor.BASELINE_LEFT,
                )

                val_txt = format_family_readout(fam, self.readout_mode)
                if val_txt:
                    if fam.effect_ref is not None and mode_low in (
                        "auto",
                        "label",
                        "ref",
                    ):
                        cr.set_source_rgb(*_EFFECT_MAGENTA)
                    elif fam.is_manual:
                        cr.set_source_rgb(*_MANUAL_CORAL)
                    elif fam.palette_ref is not None and mode_low in (
                        "auto",
                        "label",
                        "ref",
                    ):
                        cr.set_source_rgb(*_PALETTE_CYAN_TEXT)
                    elif fam.tracking_state not in (
                        TrackingDisplayState.INACTIVE,
                        TrackingDisplayState.MIB,
                    ):
                        cr.set_source_rgb(*tag_rgb)
                    else:
                        cr.set_source_rgb(0.78, 0.81, 0.84)
                    self._draw_ellipsized_text(
                        cr,
                        20 * s,
                        y_base,
                        alloc_w - 27 * s,
                        val_txt,
                        8.0 * s,
                    )
        elif snap is not None and snap.is_patched and snap.address_str:
            cr.set_source_rgb(0.60, 0.64, 0.67)
            self._draw_ellipsized_text(
                cr,
                8 * s,
                84 * s,
                alloc_w - 16 * s,
                f"Addr {snap.address_str}",
                8.0 * s,
            )

    def _draw_summary_next_indicator(
        self, cr: cairo.Context, percent_level: bool, *, up: bool
    ) -> None:
        """Draw compact next-cue up/down arrow and value inside Summary+ body."""
        s = self.scale
        base_x = 54 * s
        base_y = 43 * s
        if up:
            cr.move_to(base_x + 4 * s, base_y - 7 * s)
            cr.line_to(base_x, base_y)
            cr.line_to(base_x + 8 * s, base_y)
            cr.close_path()
            cr.set_source_rgb(0.9, 0.5, 0.5)
        else:
            cr.move_to(base_x + 4 * s, base_y)
            cr.line_to(base_x, base_y - 7 * s)
            cr.line_to(base_x + 8 * s, base_y - 7 * s)
            cr.close_path()
            cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.fill()
        next_txt = self._format_intensity_text(self.next_level, percent_level)
        draw_cached_numeric_text(
            cr,
            base_x + 11 * s,
            base_y,
            next_txt,
            9.5 * s,
            weight=Pango.Weight.NORMAL,
            anchor=TextAnchor.BASELINE_LEFT,
        )

    def _draw_compact_ifcb_markers(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        snap: ChannelDisplaySnapshot | None,
    ) -> None:
        """Draw compact right-edge F/C/B status letters for device tiles."""
        s = self.scale
        alloc_w = max(self.width, allocation.width)
        x_pos = alloc_w - 13 * s
        if snap is None:
            dev = self.get_patched_device()
            if dev is None:
                return
            has_focus = any(
                ch.channel_type in POSITION_CHANNEL_TYPES for ch in dev.channels
            )
            has_color = bool(getattr(dev, "has_color_capability", False)) or any(
                ch.channel_type in _COMPACT_COLOR_TYPES for ch in dev.channels
            )
            has_beam = any(
                ch.channel_type in _COMPACT_BEAM_TYPES for ch in dev.channels
            )
            fallback_slots = (
                ("F", has_focus, 33 * s),
                ("C", has_color, 45 * s),
                ("B", has_beam, 57 * s),
            )
            for tag, available, y_pos in fallback_slots:
                if not available:
                    continue
                cr.set_source_rgb(*_MUTED_GREY)
                draw_cached_numeric_text(
                    cr,
                    x_pos,
                    y_pos,
                    tag,
                    7.5 * s,
                    weight=Pango.Weight.BOLD,
                    anchor=TextAnchor.BASELINE_RIGHT,
                )
            return

        if not snap.has_device:
            return
        slots = (
            ("F", snap.focus, 33 * s),
            ("C", snap.color, 45 * s),
            ("B", snap.beam, 57 * s),
        )
        for tag, fam, y_pos in slots:
            if not fam.available:
                continue
            cr.set_source_rgb(
                *self._get_family_status_rgb(fam, is_mib_channel=snap.is_mib)
            )
            draw_cached_numeric_text(
                cr,
                x_pos,
                y_pos,
                tag,
                7.5 * s,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_RIGHT,
            )
            if fam.is_manual and fam.palette_ref is not None and fam.effect_ref is None:
                cr.new_sub_path()
                cr.arc(x_pos - 9.0 * s, y_pos - 3.0 * s, 1.5 * s, 0, 6.2831853)
                cr.set_source_rgb(*_PALETTE_CYAN)
                cr.fill()

    def _draw_device_indicators(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        snap: ChannelDisplaySnapshot | None = None,
    ) -> None:
        """Draw color preview dot and bottom strip if applicable."""
        rgb = (
            snap.preview_rgb
            if self._uses_non_live_snapshot() and snap is not None
            else self.get_preview_rgb()
        )
        is_parked = self._is_parked(snap)
        has_col_ref = snap is not None and snap.color.palette_ref is not None
        is_col_manual = snap is not None and snap.color.is_manual
        cx = (20 if is_parked else 11) * self.scale
        if rgb is not None:
            r, g, b = rgb
            cy = 13 * self.scale
            radius = 4.5 * self.scale
            cr.new_sub_path()
            cr.arc(cx, cy, radius, 0, 6.2831853)
            cr.set_source_rgb(r, g, b)
            cr.fill_preserve()
            if is_col_manual:
                cr.set_source_rgb(*_MANUAL_CORAL)
                cr.set_line_width(1.5)
            elif has_col_ref:
                cr.set_source_rgb(*_PALETTE_CYAN)
                cr.set_line_width(1.4)
            else:
                cr.set_source_rgb(0.75, 0.75, 0.75)
                cr.set_line_width(1.0)
            cr.stroke()

            # Bottom color strip
            alloc_w = max(self.width, allocation.width)
            strip_h = max(2.0, 3.0 * self.scale)
            strip_w = max(8.0, alloc_w - 14)
            strip_y = self.height - 4 - strip_h
            cr.rectangle(4, strip_y, strip_w, strip_h)
            cr.set_source_rgb(r, g, b)
            cr.fill()
            if is_col_manual:
                cr.set_source_rgb(*_MANUAL_CORAL)
                cr.set_line_width(1.3)
                cr.move_to(4, strip_y)
                cr.line_to(4 + strip_w, strip_y)
                cr.stroke()
                if has_col_ref:
                    cr.rectangle(4, strip_y, max(3.0, 4.0 * self.scale), strip_h)
                    cr.set_source_rgb(*_PALETTE_CYAN)
                    cr.fill()
            elif has_col_ref:
                cr.set_source_rgb(*_PALETTE_CYAN)
                cr.set_line_width(1.2)
                cr.move_to(4, strip_y)
                cr.line_to(4 + strip_w, strip_y)
                cr.stroke()

    def _draw_background(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        *,
        header_height: float | None = None,
    ) -> None:
        """Draw tile frame, selection border, body panel, and header strip."""
        alloc_w = max(self.width, allocation.width)
        alloc_h = max(self.height, allocation.height)
        bg_color = self.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        parent_raw = self.get_parent()
        parent = (
            typing.cast("Gtk.FlowBoxChild", parent_raw)
            if parent_raw is not None
            else None
        )
        is_sel = bool(parent is not None and parent.is_selected())
        if is_sel:
            cr.set_source_rgb(0.6, 0.4, 0.1)
        else:
            cr.set_source_rgba(
                bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha
            )
        cr.rectangle(0, 0, alloc_w, alloc_h)
        cr.fill()

        # Draw border rectangle
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(0, 0, alloc_w, alloc_h)
        cr.stroke()

        # Draw inner panel background
        background = Gdk.RGBA()
        background.parse("#33393B")
        cr.set_source_rgba(
            background.red, background.green, background.blue, background.alpha
        )
        cr.rectangle(4, 4, alloc_w - 8, self.height - 8)
        cr.fill()

        # Draw header bar background
        if is_sel:
            cr.set_source_rgb(0.4, 0.4, 0.4)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        hdr_h = header_height if header_height is not None else 18 * self.scale
        cr.rectangle(4, 4, alloc_w - 8, hdr_h)
        cr.fill()

    def _set_channel_number_color(self, cr: cairo.Context) -> None:
        ch_num = int(self.channel)
        cr.set_source_rgb(0.9, 0.6, 0.2)
        if ch_num in self.lightshow.independents.get_channels():
            cr.set_source_rgb(0.5, 0.5, 0.8)
        if not self.lightshow.patch.is_patched(ch_num):
            cr.set_source_rgb(0.5, 0.5, 0.5)

    def _draw_channel_number(self, cr: cairo.Context) -> None:
        """Draw channel number"""
        self._set_channel_number_color(cr)
        draw_cached_numeric_text(
            cr,
            50 * self.scale,
            15 * self.scale,
            self.channel,
            12 * self.scale,
            weight=Pango.Weight.BOLD,
            anchor=TextAnchor.BASELINE_LEFT,
        )

    def _draw_park_badge(
        self, cr: cairo.Context, snap: ChannelDisplaySnapshot | None = None
    ) -> None:
        """Draw 'P' badge if channel is parked."""
        if not self._is_parked(snap):
            return
        cr.set_source_rgb(*_PARK_AMBER)
        draw_cached_numeric_text(
            cr,
            6 * self.scale,
            15 * self.scale,
            "P",
            10 * self.scale,
            weight=Pango.Weight.BOLD,
            anchor=TextAnchor.BASELINE_LEFT,
        )

    def _set_level_color(self, cr: cairo.Context, is_parked: bool) -> None:
        if is_parked:
            cr.set_source_rgb(*_PARK_AMBER)
        else:
            cr.set_source_rgb(
                self.color_level.get("red", 0.0),
                self.color_level.get("green", 0.0),
                self.color_level.get("blue", 0.0),
            )

    @staticmethod
    def _format_intensity_text(raw_level: int | float, percent_level: bool) -> str:
        val = float(raw_level)
        if val > 1.0:
            # Handle legacy tests passing DMX 0..255 values into widget.level
            norm = min(1.0, val / 255.0)
            if percent_level:
                return "F" if norm >= 1.0 else str(round(norm * 100.0))
            return str(round(val))
        if percent_level:
            return "F" if val >= 1.0 else str(round(val * 100.0))
        return str(round(val * 255.0))

    def _draw_level(
        self,
        cr: cairo.Context,
        percent_level: bool,
        snap: ChannelDisplaySnapshot | None = None,
    ) -> None:
        """Draw level"""
        self._set_level_color(cr, self._is_parked(snap))
        if self.level > 0.0 or self.next_level > 0.0:
            txt = self._format_intensity_text(self.level, percent_level)
            draw_cached_numeric_text(
                cr,
                6 * self.scale,
                48 * self.scale,
                txt,
                13 * self.scale,
                weight=Pango.Weight.BOLD,
                anchor=TextAnchor.BASELINE_LEFT,
            )

    def _draw_level_bar(
        self,
        cr: cairo.Context,
        allocation: Gdk.Rectangle,
        snap: ChannelDisplaySnapshot | None = None,
    ) -> None:
        """Draw level bar"""
        alloc_w = max(self.width, allocation.width)
        bar_fill = self._normalized_level_for_bar(snap)
        cr.rectangle(
            alloc_w - 9,
            self.height - 4,
            6 * self.scale,
            -(50.0 * self.scale) * bar_fill,
        )
        cr.set_source_rgb(0.9, 0.6, 0.2)
        cr.fill()

    def _draw_next_level(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw next level indicator"""
        if int(self.channel) in self.lightshow.independents.get_channels():
            return
        if self.next_level < self.level:
            self._draw_down_icon(cr, percent_level)
        if self.next_level > self.level:
            self._draw_up_icon(cr, percent_level)

    def _draw_down_icon(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw down icon"""
        offset_x = 6 * self.scale
        offset_y = -6 * self.scale
        cr.move_to(
            offset_x + 11 * self.scale,
            offset_y + self.height - 6 * self.scale,
        )
        cr.line_to(
            offset_x + 6 * self.scale,
            offset_y + self.height - 16 * self.scale,
        )
        cr.line_to(
            offset_x + 16 * self.scale,
            offset_y + self.height - 16 * self.scale,
        )
        cr.close_path()
        cr.set_source_rgb(0.5, 0.5, 0.9)
        cr.fill()

        self._draw_next_level_text(
            cr,
            percent_level,
            offset_x + (24 * self.scale),
            offset_y + self.height - (6 * self.scale),
        )

    def _draw_up_icon(self, cr: cairo.Context, percent_level: bool) -> None:
        """Draw up icon"""
        offset_x = 6 * self.scale
        offset_y = 15 * self.scale
        cr.move_to(offset_x + 11 * self.scale, offset_y + 6 * self.scale)
        cr.line_to(offset_x + 6 * self.scale, offset_y + 16 * self.scale)
        cr.line_to(offset_x + 16 * self.scale, offset_y + 16 * self.scale)
        cr.close_path()
        cr.set_source_rgb(0.9, 0.5, 0.5)
        cr.fill()

        self._draw_next_level_text(
            cr,
            percent_level,
            offset_x + (24 * self.scale),
            offset_y + (16 * self.scale),
        )

    def _draw_next_level_text(
        self, cr: cairo.Context, percent_level: bool, x: float, y: float
    ) -> None:
        """Draw text for next level"""
        txt = self._format_intensity_text(self.next_level, percent_level)
        draw_cached_numeric_text(
            cr,
            x,
            y,
            txt,
            10 * self.scale,
            weight=Pango.Weight.NORMAL,
            anchor=TextAnchor.BASELINE_LEFT,
        )

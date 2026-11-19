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
"""GTK3 Palettes & Presets management tab."""

from __future__ import annotations

import typing
from gettext import gettext as _

import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from olc.actions.palette import format_palette_number
from olc.define import is_non_nul_float
from olc.gtk3.widgets.common import (
    SystemFontManager,
    create_pango_layout_for_widget,
    create_system_font_description,
    register_system_font_listener,
    rounded_rectangle,
    rounded_rectangle_fill,
)
from olc.show.palette import Palette, PaletteCategory

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.show.lightshow import LightShow

CATEGORY_SPECS: tuple[
    tuple[PaletteCategory, str, str, tuple[float, float, float]], ...
] = (
    (PaletteCategory.INTENSITY, "IP", _("Intensity"), (1.0, 0.72, 0.30)),
    (PaletteCategory.FOCUS, "FP", _("Focus"), (0.31, 0.76, 0.97)),
    (PaletteCategory.COLOR, "CP", _("Color"), (0.94, 0.38, 0.57)),
    (PaletteCategory.BEAM, "BP", _("Beam"), (0.41, 0.94, 0.68)),
    (PaletteCategory.PRESET, "PR", _("Presets"), (0.81, 0.58, 0.85)),
)

_SPEC_BY_CATEGORY: dict[
    PaletteCategory, tuple[str, str, tuple[float, float, float]]
] = {cat: (prefix, title, accent) for cat, prefix, title, accent in CATEGORY_SPECS}


def extract_palette_preview_rgb(
    palette: Palette,
) -> tuple[float, float, float] | None:
    """Return normalized RGB preview color from a Palette/Preset if present."""
    for vals in palette.device_values.values():
        if not isinstance(vals, dict):
            continue
        raw = vals.get("color", vals.get("colour"))
        if isinstance(raw, str) and raw.startswith("#") and len(raw) in (7, 9):
            try:
                return (
                    int(raw[1:3], 16) / 255.0,
                    int(raw[3:5], 16) / 255.0,
                    int(raw[5:7], 16) / 255.0,
                )
            except ValueError:
                continue
        if isinstance(raw, (list, tuple)) and len(raw) >= 3:
            if all(isinstance(c, (int, float)) for c in raw[:3]):
                r, g, b = float(raw[0]), float(raw[1]), float(raw[2])
                if r > 1.0 or g > 1.0 or b > 1.0:
                    r, g, b = r / 255.0, g / 255.0, b / 255.0
                return (
                    max(0.0, min(1.0, r)),
                    max(0.0, min(1.0, g)),
                    max(0.0, min(1.0, b)),
                )
    return None


class PaletteTileWidget(Gtk.Widget):  # pylint: disable=too-many-instance-attributes
    """Clickable Cairo tile displaying a Palette or Preset with inline rename."""

    __gtype_name__ = "PaletteTileWidget"

    def __init__(  # pylint: disable=too-many-arguments
        self,
        tab: PalettesTab,
        palette: Palette,
        *,
        prefix: str,
        accent_rgb: tuple[float, float, float],
    ) -> None:
        super().__init__()
        self.tab = tab
        self.category = palette.category
        self.number = float(palette.number)
        self.prefix = prefix
        self.name = palette.text
        self.channel_count = len(set(palette.channels) | set(palette.device_values))
        self.palette_ref_count = sum(
            len(refs) for refs in palette.palette_refs.values()
        )
        self.accent_rgb = accent_rgb
        self.preview_rgb = extract_palette_preview_rgb(palette)

        self.set_size_request(116, 78)
        self.connect("button-press-event", self.on_click)
        self.connect("touch-event", self.on_click)
        register_system_font_listener(self.queue_draw)
        self.connect("destroy", self._on_destroy)

        self.popover = Gtk.Popover()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.rename_entry = Gtk.Entry()
        self.rename_entry.set_has_frame(False)
        self.rename_entry.set_text(self.name)
        self.rename_entry.connect("activate", self.on_rename_activate)
        vbox.pack_start(self.rename_entry, False, True, 8)
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

    def on_rename_activate(self, widget: Gtk.Entry) -> None:
        """Rename the represented palette/preset when user confirms the Entry."""
        new_text = widget.get_text().strip()
        self.tab.app.core.action_registry.execute(
            "palette.rename",
            self.category,
            self.number,
            new_text,
        )
        self.popover.popdown()

    def on_click(self, _tgt: Gtk.Widget, event: Gdk.Event) -> bool:
        """Select tile on click and trigger recall when Direct Recall is active."""
        parent = self.get_parent()
        if isinstance(parent, Gtk.FlowBoxChild):
            flowbox = parent.get_parent()
            if isinstance(flowbox, Gtk.FlowBox):
                flowbox.unselect_all()
                flowbox.select_child(parent)

        ev_type = getattr(event, "type", None)
        if (
            ev_type == Gdk.EventType.BUTTON_PRESS
            and self.tab.direct_recall_toggle.get_active()
        ):
            self.tab.recall_palette(self.category, self.number)
            return True
        return False

    def do_draw(self, cr: cairo.Context) -> bool:  # pylint: disable=too-many-locals
        """Draw the palette/preset tile using Cairo and Pango."""
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

        # Top color/category bar
        bar_r, bar_g, bar_b = (
            self.preview_rgb if self.preview_rgb is not None else self.accent_rgb
        )
        cr.set_source_rgb(bar_r, bar_g, bar_b)
        bar_area = (3.0, width - 3.0, 3.0, 10.0)
        rounded_rectangle_fill(cr, bar_area, 3.0)

        # Selection border
        if is_selected:
            cr.set_source_rgb(1.0, 0.72, 0.25)
            cr.set_line_width(1.8)
            rounded_rectangle(cr, area, 8.0)
        else:
            cr.set_source_rgb(0.38, 0.40, 0.43)
            cr.set_line_width(1.0)
            rounded_rectangle(cr, area, 8.0)

        # Top-left badge (e.g. "CP 2", "PR 1")
        num_str = format_palette_number(self.number)
        badge_text = f"{self.prefix} {num_str}"
        cr.set_source_rgb(*self.accent_rgb)
        badge_layout = create_pango_layout_for_widget(cr, badge_text)
        bdesc = create_system_font_description()
        bdesc.set_weight(Pango.Weight.BOLD)
        bdesc.set_size(10 * Pango.SCALE)
        badge_layout.set_font_description(bdesc)
        cr.move_to(8.0, 14.0)
        PangoCairo.show_layout(cr, badge_layout)

        # Top-right channel count
        cnt_text = f"{self.channel_count} ch"
        cr.set_source_rgb(0.68, 0.72, 0.76)
        cnt_layout = create_pango_layout_for_widget(cr, cnt_text)
        cdesc = create_system_font_description()
        cdesc.set_size(8 * Pango.SCALE)
        cnt_layout.set_font_description(cdesc)
        _ink, clogical = cnt_layout.get_pixel_extents()
        cr.move_to(width - clogical.width - 8.0, 16.0)
        PangoCairo.show_layout(cr, cnt_layout)

        # Center/bottom label
        display_name = self.name or f"{self.prefix} {num_str}"
        cr.set_source_rgb(0.92, 0.94, 0.96)
        name_layout = create_pango_layout_for_widget(cr, display_name)
        ndesc = create_system_font_description()
        ndesc.set_weight(Pango.Weight.NORMAL if self.name else Pango.Weight.LIGHT)
        ndesc.set_size(9 * Pango.SCALE)
        name_layout.set_font_description(ndesc)
        name_layout.set_width(int(max(20.0, width - 16.0) * Pango.SCALE))
        name_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        name_layout.set_height(-2)
        name_layout.set_ellipsize(Pango.EllipsizeMode.END)
        cr.move_to(8.0, 36.0)
        PangoCairo.show_layout(cr, name_layout)

        return False

    def do_realize(self) -> None:
        """Create child Gdk.Window with pointer/touch masks."""
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


class PalettesTab(Gtk.Box):  # pylint: disable=too-many-instance-attributes
    """Tab displaying IFCB Palettes and Presets in category grids."""

    app: Application
    lightshow: LightShow
    tabs: Tabs | None

    def __init__(self, app: Application) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs
        self._updating_selection = False
        self._selected_numbers: dict[PaletteCategory, float | None] = {
            cat: None for cat, *_ in CATEGORY_SPECS
        }

        self.set_border_width(6)

        # Header / Action toolbar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack_switcher = Gtk.StackSwitcher()
        self.stack_switcher.set_stack(self.stack)
        header.pack_start(self.stack_switcher, False, False, 0)

        spacer = Gtk.Box()
        header.pack_start(spacer, True, True, 0)

        self.direct_recall_toggle = Gtk.ToggleButton(label=_("Direct Recall"))
        self.direct_recall_toggle.set_tooltip_text(
            _("When active, clicking a tile immediately recalls its palette/preset")
        )
        header.pack_start(self.direct_recall_toggle, False, False, 0)

        self.btn_recall = Gtk.Button(label=_("Recall"))
        self.btn_recall.connect("clicked", lambda *_: self.recall_selected())
        header.pack_start(self.btn_recall, False, False, 0)

        self.btn_record = Gtk.Button(label=_("Record"))
        self.btn_record.connect("clicked", lambda *_: self.record_palette())
        header.pack_start(self.btn_record, False, False, 0)

        self.btn_update = Gtk.Button(label=_("Update"))
        self.btn_update.connect("clicked", lambda *_: self.update_selected())
        header.pack_start(self.btn_update, False, False, 0)

        self.btn_rename = Gtk.Button(label=_("Rename"))
        self.btn_rename.connect("clicked", lambda *_: self.rename_selected())
        header.pack_start(self.btn_rename, False, False, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.connect("clicked", lambda *_: self.delete_selected())
        header.pack_start(self.btn_delete, False, False, 0)

        self.pack_start(header, False, False, 0)

        # Category stacks
        self.scrolled_windows: dict[PaletteCategory, Gtk.ScrolledWindow] = {}
        self.flowboxes: dict[PaletteCategory, Gtk.FlowBox] = {}
        self._flowbox_to_category: dict[Gtk.FlowBox, PaletteCategory] = {}

        for cat, _prefix, title, _accent in CATEGORY_SPECS:
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            fb = Gtk.FlowBox()
            fb.set_valign(Gtk.Align.START)
            fb.set_max_children_per_line(12)
            fb.set_column_spacing(6)
            fb.set_row_spacing(6)
            fb.set_homogeneous(True)
            fb.set_activate_on_single_click(False)
            fb.set_selection_mode(Gtk.SelectionMode.SINGLE)
            fb.connect("selected-children-changed", self._on_selection_changed)
            fb.connect("child-activated", self._on_child_activated)
            scrolled.add(fb)
            self.scrolled_windows[cat] = scrolled
            self.flowboxes[cat] = fb
            self._flowbox_to_category[fb] = cat
            self.stack.add_titled(scrolled, cat.value, title)

        self.stack.connect("notify::visible-child-name", self._on_category_changed)
        self.pack_start(self.stack, True, True, 0)

        # Bottom details bar
        self.details_label = Gtk.Label()
        self.details_label.set_halign(Gtk.Align.START)
        self.details_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.pack_start(self.details_label, False, False, 0)

        self.refresh()
        self.show_all()

    @property
    def current_category(self) -> PaletteCategory:
        """Return currently visible PaletteCategory."""
        name = self.stack.get_visible_child_name()
        if name:
            try:
                return PaletteCategory(name)
            except ValueError:
                pass
        return PaletteCategory.INTENSITY

    @property
    def flowbox(self) -> Gtk.FlowBox:
        """Return the FlowBox of the currently visible category."""
        return self.flowboxes[self.current_category]

    def set_active_category(self, category: PaletteCategory | str) -> None:
        """Switch the visible tab stack page to *category*."""
        cat = (
            category
            if isinstance(category, PaletteCategory)
            else PaletteCategory(str(category).lower())
        )
        self.stack.set_visible_child_name(cat.value)
        self._update_details_and_sensitivity()

    def get_selected_tile(
        self, category: PaletteCategory | None = None
    ) -> PaletteTileWidget | None:
        """Return the selected PaletteTileWidget in *category* (default active)."""
        cat = category or self.current_category
        fb = self.flowboxes[cat]
        selected = fb.get_selected_children()
        if not selected:
            return None
        widget = selected[0].get_child()
        return widget if isinstance(widget, PaletteTileWidget) else None

    def get_selected_palette(
        self, category: PaletteCategory | None = None
    ) -> Palette | None:
        """Return the selected Palette model object, if any."""
        tile = self.get_selected_tile(category)
        if tile is None:
            return None
        return self.lightshow.palettes.get(tile.category, tile.number)

    def _on_category_changed(self, _stack: Gtk.Stack, _param: object) -> None:
        self._update_details_and_sensitivity()

    def _on_selection_changed(self, flowbox: Gtk.FlowBox) -> None:
        if self._updating_selection:
            return
        cat = self._flowbox_to_category.get(flowbox)
        if cat is not None:
            selected = flowbox.get_selected_children()
            if selected:
                tile = selected[0].get_child()
                if isinstance(tile, PaletteTileWidget):
                    self._selected_numbers[cat] = tile.number
            else:
                self._selected_numbers[cat] = None
        self._update_details_and_sensitivity()

    def _on_child_activated(
        self, _flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild
    ) -> None:
        tile = child.get_child()
        if isinstance(tile, PaletteTileWidget):
            self.recall_palette(tile.category, tile.number)

    def refresh(self) -> None:
        """Rebuild all category FlowBoxes from LightShow.palettes."""
        self.lightshow = self.app.core.lightshow
        self._updating_selection = True
        try:
            for cat, prefix, title, accent in CATEGORY_SPECS:
                fb = self.flowboxes[cat]
                for child in list(fb.get_children()):
                    fb.remove(child)
                    child.destroy()

                items = self.lightshow.palettes.list_by_category(cat)
                self.stack.child_set_property(
                    self.scrolled_windows[cat],
                    "title",
                    f"{title} ({len(items)})",
                )

                target_num = self._selected_numbers.get(cat)
                restored_child: Gtk.FlowBoxChild | None = None
                for pal in items:
                    tile = PaletteTileWidget(
                        self,
                        pal,
                        prefix=prefix,
                        accent_rgb=accent,
                    )
                    fb.add(tile)
                    fb_child = tile.get_parent()
                    if (
                        isinstance(fb_child, Gtk.FlowBoxChild)
                        and target_num is not None
                        and float(pal.number) == float(target_num)
                    ):
                        restored_child = fb_child

                fb.show_all()
                if restored_child is not None:
                    fb.select_child(restored_child)
                else:
                    self._selected_numbers[cat] = None
        finally:
            self._updating_selection = False

        self._update_details_and_sensitivity()

    def _update_details_and_sensitivity(self) -> None:
        pal = self.get_selected_palette()
        has_sel = pal is not None
        self.btn_recall.set_sensitive(has_sel)
        self.btn_update.set_sensitive(has_sel)
        self.btn_rename.set_sensitive(has_sel)
        self.btn_delete.set_sensitive(has_sel)
        self.btn_record.set_sensitive(True)

        if pal is None:
            items = self.lightshow.palettes.list_by_category(self.current_category)
            if items:
                self.details_label.set_text(
                    _("Select a tile (double-click or Direct Recall to apply)")
                )
            else:
                self.details_label.set_text(
                    _(
                        "No entries in this category. Click Record or run "
                        "RECORD <CATEGORY> PALETTE <n>."
                    )
                )
            return

        prefix, _title, _accent = _SPEC_BY_CATEGORY[pal.category]
        num_str = format_palette_number(pal.number)
        title_part = f"{prefix} {num_str}" + (f" \u2014 {pal.text}" if pal.text else "")
        ch_count = len(set(pal.channels) | set(pal.device_values))
        attrs = sorted(
            {
                str(k)
                for dv in pal.device_values.values()
                if isinstance(dv, dict)
                for k in dv
            }
        )
        parts = [title_part, f"{ch_count} channel(s)"]
        if attrs:
            parts.append("params: " + ", ".join(attrs))
        if pal.palette_refs:
            ref_count = sum(len(refs) for refs in pal.palette_refs.values())
            parts.append(f"{ref_count} palette ref(s)")
        self.details_label.set_text("  |  ".join(parts))

    def recall_palette(self, category: PaletteCategory, number: float) -> None:
        """Apply *category* / *number* via Core ActionRegistry."""
        self.app.core.action_registry.execute("palette.apply", category, number)

    def recall_selected(self) -> None:
        """Apply the currently selected tile's palette or preset."""
        if (pal := self.get_selected_palette()) is not None:
            self.recall_palette(pal.category, pal.number)

    def record_palette(self, number: float | None = None, label: str = "") -> float:
        """Record live stage state into current category and return its number."""
        cat = self.current_category
        if number is None:
            raw = self.app.core.commandline.get_string().strip()
            if raw and is_non_nul_float(raw):
                target_num = float(raw)
                self.app.core.action_registry.execute("commandline.clear")
            else:
                existing = self.lightshow.palettes.list_by_category(cat)
                target_num = (
                    float(max(int(float(p.number)) for p in existing) + 1)
                    if existing
                    else 1.0
                )
        else:
            target_num = float(number)

        self._selected_numbers[cat] = target_num
        self.app.core.action_registry.execute(
            "palette.record", cat, target_num, label=label
        )
        self.refresh()
        return target_num

    def update_selected(self) -> None:
        """Update selected palette/preset with current live stage values."""
        if (pal := self.get_selected_palette()) is None:
            return
        self._selected_numbers[pal.category] = float(pal.number)
        self.app.core.action_registry.execute(
            "palette.update", pal.category, pal.number
        )
        self.refresh()

    def rename_selected(self) -> None:
        """Open rename popover on currently selected palette/preset tile."""
        if (tile := self.get_selected_tile()) is not None:
            tile.open_rename_popover()

    def delete_selected(self) -> None:
        """Delete the currently selected palette/preset with Undo support."""
        if (pal := self.get_selected_palette()) is None:
            return
        cat = pal.category
        items = self.lightshow.palettes.list_by_category(cat)
        next_num: float | None = None
        for idx, item in enumerate(items):
            if float(item.number) == float(pal.number):
                if len(items) <= 1:
                    next_num = None
                elif idx + 1 < len(items):
                    next_num = float(items[idx + 1].number)
                else:
                    next_num = float(items[idx - 1].number)
                break
        self._selected_numbers[cat] = next_num
        self.app.core.action_registry.execute("palette.delete", cat, pal.number)
        self.refresh()

    def _keypress_delete(self) -> None:
        self.delete_selected()

    def _keypress_f2(self) -> None:
        self.rename_selected()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close the Palettes tab."""
        if self.tabs:
            self.tabs.close("palettes")

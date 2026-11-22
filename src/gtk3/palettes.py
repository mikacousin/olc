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

import copy
import typing
from gettext import gettext as _

import cairo
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from olc.actions.palette import format_palette_number
from olc.define import is_non_nul_float
from olc.gtk3.widgets.channels_table_view import (
    PALETTE_CYAN_HEX,
    ColorSwatchCellRenderer,
)
from olc.gtk3.widgets.common import (
    SystemFontManager,
    create_pango_layout_for_widget,
    create_system_font_description,
    register_system_font_listener,
    rounded_rectangle,
    rounded_rectangle_fill,
)
from olc.gtk3.widgets.group import format_channel_summary
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

# Inspector ListStore column indices
INSP_COL_CH = 0
INSP_COL_FIXTURE = 1
INSP_COL_INTENSITY = 2
INSP_COL_HAS_COLOR = 3
INSP_COL_R = 4
INSP_COL_G = 5
INSP_COL_B = 6
INSP_COL_HAS_COLOR_REF = 7
INSP_COL_PARAMS = 8
INSP_COL_REFS = 9

_COLOR_REF_KEYS: frozenset[str] = frozenset(
    {"color", "colour", "red", "green", "blue", "cyan", "magenta", "yellow"}
)
_PERCENT_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "red",
        "green",
        "blue",
        "white",
        "amber",
        "lime",
        "cyan",
        "magenta",
        "yellow",
        "indigo",
        "frost",
        "prism",
        "iris",
        "color_wheel",
    }
)


def _norm_channel_component(value: typing.Any) -> float:  # noqa: ANN401
    num = float(value)
    if num > 1.0:
        num /= 255.0
    return max(0.0, min(1.0, num))


def extract_device_values_rgb(
    vals: typing.Mapping[str, typing.Any],
) -> tuple[float, float, float] | None:
    """Return normalized RGB preview color from a single device_values dict."""
    raw = vals.get("color", vals.get("colour"))
    if isinstance(raw, str) and raw.startswith("#") and len(raw) in (7, 9):
        try:
            return (
                int(raw[1:3], 16) / 255.0,
                int(raw[3:5], 16) / 255.0,
                int(raw[5:7], 16) / 255.0,
            )
        except ValueError:
            pass
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        if all(isinstance(c, (int, float)) for c in raw[:3]):
            return (
                _norm_channel_component(raw[0]),
                _norm_channel_component(raw[1]),
                _norm_channel_component(raw[2]),
            )

    if any(
        k in vals and isinstance(vals[k], (int, float))
        for k in ("cyan", "magenta", "yellow")
    ):
        c = _norm_channel_component(vals.get("cyan", 0.0))
        m = _norm_channel_component(vals.get("magenta", 0.0))
        y = _norm_channel_component(vals.get("yellow", 0.0))
        return (1.0 - c, 1.0 - m, 1.0 - y)

    if any(
        k in vals and isinstance(vals[k], (int, float))
        for k in ("red", "green", "blue")
    ):
        r = _norm_channel_component(vals.get("red", 0.0))
        g = _norm_channel_component(vals.get("green", 0.0))
        b = _norm_channel_component(vals.get("blue", 0.0))
        return (r, g, b)

    return None


def extract_palette_preview_rgb(
    palette: Palette,
) -> tuple[float, float, float] | None:
    """Return normalized RGB preview color from a Palette/Preset if present."""
    for vals in palette.device_values.values():
        if not isinstance(vals, typing.Mapping):
            continue
        rgb = extract_device_values_rgb(vals)
        if rgb is not None:
            return rgb
    return None


def _format_palette_param_value(key: str, val: typing.Any) -> str:  # noqa: ANN401
    """Format a stored device parameter value concisely for the Inspector table."""
    k = str(key).strip().lower()
    if k in ("pan", "tilt", "zoom") and isinstance(val, (int, float)):
        return f"{float(val):g}°"
    if k == "focus" and isinstance(val, (int, float)):
        return f"{float(val):.1f}m"
    if k == "strobe" and isinstance(val, (int, float)):
        return f"{float(val):.1f}Hz"
    if k in ("color", "colour") and isinstance(val, str):
        return val.upper()
    if k in ("cct", "color_temp", "colortemp") and isinstance(val, (int, float)):
        return f"{round(float(val))}K"
    if k in _PERCENT_PARAM_KEYS and isinstance(val, (int, float)):
        fval = float(val)
        pct = fval * 100.0 if fval <= 1.0 else (fval / 255.0) * 100.0
        return f"{round(max(0.0, min(100.0, pct)))}%"
    return str(val)


def _format_channel_params(dev_vals: typing.Mapping[str, typing.Any]) -> str:
    """Format stored device parameters (excluding intensity) for one channel."""
    parts = [
        f"{k}={_format_palette_param_value(str(k), v)}"
        for k, v in dev_vals.items()
        if str(k).lower() != "intensity"
    ]
    return ", ".join(parts)


def _format_channel_refs(
    lightshow: LightShow,
    refs: typing.Mapping[str, tuple[str, float]],
) -> str:
    """Format nested sub-palette references for one Preset channel row."""
    parts: list[str] = []
    for param, (cat_str, num) in refs.items():
        try:
            cat = PaletteCategory(str(cat_str).lower())
            prefix = _SPEC_BY_CATEGORY[cat][0]
            target = lightshow.palettes.get(cat, float(num))
        except ValueError:
            prefix = str(cat_str)[:2].upper() or "P"
            target = None
        num_str = format_palette_number(float(num))
        label_suffix = f" ({target.text})" if target is not None and target.text else ""
        parts.append(f"{param} \u2192 {prefix} {num_str}{label_suffix}")
    return ", ".join(parts)


def _format_stored_intensity(
    raw_val: float,
    *,
    percent_mode: bool,
) -> str:
    """Format stored 0..1 or 0..255 intensity for Inspector display."""
    val = float(raw_val)
    norm = max(0.0, min(1.0, val / 255.0 if val > 1.0 else val))
    if not percent_mode:
        return str(round(norm * 255.0))
    return "F" if norm >= 1.0 else f"{round(norm * 100.0)}%"


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
        self.channels: list[int] = sorted(
            set(palette.channels) | set(palette.device_values)
        )
        self.channel_count = len(self.channels)
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

    def update_from_palette(self, palette: Palette) -> None:
        """Update tile metadata, preview, and channel summary in place."""
        self.name = palette.text
        self.channels = sorted(set(palette.channels) | set(palette.device_values))
        self.channel_count = len(self.channels)
        self.palette_ref_count = sum(
            len(refs) for refs in palette.palette_refs.values()
        )
        self.preview_rgb = extract_palette_preview_rgb(palette)
        self.rename_entry.set_text(self.name)
        self.queue_draw()

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
        """Select tile on click; recall immediately on Direct Select or double-click."""
        parent = self.get_parent()
        if isinstance(parent, Gtk.FlowBoxChild):
            flowbox = parent.get_parent()
            if isinstance(flowbox, Gtk.FlowBox):
                flowbox.unselect_all()
                flowbox.select_child(parent)

        ev_type = getattr(event, "type", None)
        direct_active = self.tab.direct_select_toggle.get_active()
        if ev_type == Gdk.EventType.BUTTON_PRESS and direct_active:
            self.tab.recall_palette(self.category, self.number)
            return True
        if ev_type == Gdk.EventType(5) and not direct_active:
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
        cr.move_to(8.0, 11.0)
        PangoCairo.show_layout(cr, badge_layout)

        # Top-right channel count
        cnt_text = f"{self.channel_count} ch"
        cr.set_source_rgb(0.68, 0.72, 0.76)
        cnt_layout = create_pango_layout_for_widget(cr, cnt_text)
        cdesc = create_system_font_description()
        cdesc.set_size(8 * Pango.SCALE)
        cnt_layout.set_font_description(cdesc)
        _ink, clogical = cnt_layout.get_pixel_extents()
        cr.move_to(width - clogical.width - 8.0, 13.0)
        PangoCairo.show_layout(cr, cnt_layout)

        # Palette label (only drawn if non-empty; avoids duplicating top badge)
        if self.name:
            cr.set_source_rgb(0.92, 0.94, 0.96)
            name_layout = create_pango_layout_for_widget(cr, self.name)
            ndesc = create_system_font_description()
            ndesc.set_weight(Pango.Weight.NORMAL)
            ndesc.set_size(int(9.0 * Pango.SCALE))
            name_layout.set_font_description(ndesc)
            name_layout.set_width(int(max(20.0, width - 16.0) * Pango.SCALE))
            name_layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            name_layout.set_height(-2)
            name_layout.set_ellipsize(Pango.EllipsizeMode.END)
            cr.move_to(8.0, 30.0)
            PangoCairo.show_layout(cr, name_layout)

        # Compact channel preview at bottom
        summary = format_channel_summary(self.channels, max_tokens=3) or _("Empty")
        if self.channels:
            cr.set_source_rgb(0.62, 0.76, 0.86)
        else:
            cr.set_source_rgb(0.52, 0.55, 0.58)
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


class PalettesTab(Gtk.Box):  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Tab displaying IFCB Palettes and Presets with Direct Select & Inspector."""

    app: Application
    lightshow: LightShow
    tabs: Tabs | None
    direct_select_toggle: Gtk.ToggleButton
    direct_recall_toggle: Gtk.ToggleButton
    btn_recall: Gtk.Button
    btn_select_live: Gtk.Button
    btn_record: Gtk.Button
    btn_update: Gtk.Button
    btn_rename: Gtk.Button
    btn_delete: Gtk.Button
    inspector_toggle: Gtk.ToggleButton
    paned: Gtk.Paned
    inspector_box: Gtk.Box
    inspector_title_label: Gtk.Label
    btn_inspector_select_ch: Gtk.Button
    btn_inspector_remove_ch: Gtk.Button
    inspector_store: Gtk.ListStore
    inspector_view: Gtk.TreeView
    inspector_selection: Gtk.TreeSelection

    def __init__(self, app: Application) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs
        self._updating_selection = False
        self._selected_numbers: dict[PaletteCategory, float | None] = {
            cat: None for cat, *_rest in CATEGORY_SPECS
        }
        self._last_selected_index: dict[PaletteCategory, int | None] = {
            cat: None for cat, *_rest in CATEGORY_SPECS
        }

        self.set_border_width(4)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack_switcher = Gtk.StackSwitcher()
        self.stack_switcher.set_stack(self.stack)

        # Row 1: Action toolbar aligned with GroupTab
        toolbar = self._build_toolbar()
        self.pack_start(toolbar, False, False, 0)

        # Row 2: Category selector
        switcher_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        switcher_bar.pack_start(self.stack_switcher, False, False, 0)
        self.pack_start(switcher_bar, False, False, 0)

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

        # Vertical Paned: Palette grid (top) | Collapsible Inspector (bottom)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_position(320)
        self.paned.pack1(self.stack, True, False)

        self._build_inspector_panel()
        self.paned.pack2(self.inspector_box, True, False)
        self.pack_start(self.paned, True, True, 0)

        # Bottom details bar
        self.details_label = Gtk.Label()
        self.details_label.set_halign(Gtk.Align.START)
        self.details_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.pack_start(self.details_label, False, False, 0)

        self.refresh()
        self.show_all()

    def _build_toolbar(self) -> Gtk.Box:
        """Build top action toolbar aligned with GroupTab."""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.direct_select_toggle = Gtk.ToggleButton(label=_("Direct Select"))
        self.direct_select_toggle.set_tooltip_text(
            _(
                "When active, clicking a tile immediately recalls its "
                "palette/preset in Live"
            )
        )
        self.direct_recall_toggle = self.direct_select_toggle
        toolbar.pack_start(self.direct_select_toggle, False, False, 0)

        self.btn_recall = Gtk.Button(label=_("Recall"))
        self.btn_recall.set_tooltip_text(
            _(
                "Apply the selected palette/preset to Live selection, or to all "
                "stored channels when nothing is selected (or double-click tile)"
            )
        )
        self.btn_recall.connect("clicked", lambda *_: self.recall_selected())
        toolbar.pack_start(self.btn_recall, False, False, 0)

        self.btn_select_live = Gtk.Button(label=_("Select Live"))
        self.btn_select_live.set_tooltip_text(
            _("Select all channels stored in the selected palette/preset in Live")
        )
        self.btn_select_live.connect(
            "clicked", lambda *_: self.select_selected_channels_in_live()
        )
        toolbar.pack_start(self.btn_select_live, False, False, 0)

        spacer = Gtk.Box()
        toolbar.pack_start(spacer, True, True, 0)

        self.btn_record = Gtk.Button(label=_("Record"))
        self.btn_record.set_tooltip_text(
            _("Record Live state into current category (optional number in CLI)")
        )
        self.btn_record.connect("clicked", lambda *_: self.record_palette())
        toolbar.pack_start(self.btn_record, False, False, 0)

        self.btn_update = Gtk.Button(label=_("Update"))
        self.btn_update.set_tooltip_text(
            _("Update selected palette/preset with current Live values")
        )
        self.btn_update.connect("clicked", lambda *_: self.update_selected())
        toolbar.pack_start(self.btn_update, False, False, 0)

        toolbar.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2
        )

        self.btn_rename = Gtk.Button(label=_("Rename"))
        self.btn_rename.set_tooltip_text(_("Rename selected palette/preset (F2)"))
        self.btn_rename.connect("clicked", lambda *_: self.rename_selected())
        toolbar.pack_start(self.btn_rename, False, False, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.set_tooltip_text(_("Delete selected palette/preset (Delete)"))
        self.btn_delete.connect("clicked", lambda *_: self.delete_selected())
        toolbar.pack_start(self.btn_delete, False, False, 0)

        toolbar.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2
        )

        self.inspector_toggle = Gtk.ToggleButton(label=_("Inspector"))
        self.inspector_toggle.set_tooltip_text(
            _("Show or hide the stored channels and values inspector panel")
        )
        self.inspector_toggle.set_active(True)
        self.inspector_toggle.connect("toggled", self._on_toggle_inspector)
        toolbar.pack_start(self.inspector_toggle, False, False, 0)

        return toolbar

    def _build_inspector_panel(self) -> None:
        """Build collapsible bottom panel inspecting channels inside selected entry."""
        self.inspector_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        insp_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.inspector_title_label = Gtk.Label()
        self.inspector_title_label.set_halign(Gtk.Align.START)
        self.inspector_title_label.set_ellipsize(Pango.EllipsizeMode.END)
        insp_hdr.pack_start(self.inspector_title_label, True, True, 0)

        self.btn_inspector_select_ch = Gtk.Button(label=_("Select Ch"))
        self.btn_inspector_select_ch.set_tooltip_text(
            _("Select highlighted channel(s) in Live")
        )
        self.btn_inspector_select_ch.connect(
            "clicked", lambda *_: self.select_inspector_channels_in_live()
        )
        insp_hdr.pack_start(self.btn_inspector_select_ch, False, False, 0)

        self.btn_inspector_remove_ch = Gtk.Button(label=_("Remove Ch"))
        self.btn_inspector_remove_ch.set_tooltip_text(
            _("Remove highlighted channel(s) from the selected palette/preset")
        )
        self.btn_inspector_remove_ch.connect(
            "clicked", lambda *_: self.remove_inspector_channels()
        )
        insp_hdr.pack_start(self.btn_inspector_remove_ch, False, False, 0)
        self.inspector_box.pack_start(insp_hdr, False, False, 0)

        self.inspector_store = Gtk.ListStore(
            int,  # INSP_COL_CH
            str,  # INSP_COL_FIXTURE
            str,  # INSP_COL_INTENSITY
            bool,  # INSP_COL_HAS_COLOR
            float,  # INSP_COL_R
            float,  # INSP_COL_G
            float,  # INSP_COL_B
            bool,  # INSP_COL_HAS_COLOR_REF
            str,  # INSP_COL_PARAMS
            str,  # INSP_COL_REFS
        )

        self.inspector_view = Gtk.TreeView(model=self.inspector_store)
        self.inspector_view.set_headers_visible(True)
        self.inspector_view.set_enable_search(False)
        self.inspector_view.set_grid_lines(Gtk.TreeViewGridLines.HORIZONTAL)
        self.inspector_selection = self.inspector_view.get_selection()
        self.inspector_selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.inspector_selection.connect(
            "changed", lambda *_: self._update_inspector_buttons()
        )
        self.inspector_view.connect("row-activated", self._on_inspector_row_activated)

        self._append_inspector_text_column(
            _("Ch"), INSP_COL_CH, bold=True, min_width=44
        )
        self._append_inspector_text_column(
            _("Fixture"), INSP_COL_FIXTURE, ellipsize=True, min_width=110
        )
        self._append_inspector_text_column(
            _("Int"), INSP_COL_INTENSITY, xalign=1.0, min_width=52
        )

        swatch_renderer = ColorSwatchCellRenderer()
        col_swatch = Gtk.TreeViewColumn(_("Color"), swatch_renderer)
        col_swatch.set_min_width(48)
        col_swatch.set_cell_data_func(
            typing.cast(Gtk.CellRendererPixbuf, swatch_renderer),
            self._inspector_color_data_func,
            None,
        )
        self.inspector_view.append_column(col_swatch)

        self._append_inspector_text_column(
            _("Parameters"), INSP_COL_PARAMS, ellipsize=True, min_width=180
        )
        self._append_inspector_text_column(
            _("Refs"),
            INSP_COL_REFS,
            ellipsize=True,
            fg_hex=PALETTE_CYAN_HEX,
            min_width=130,
        )

        insp_scrolled = Gtk.ScrolledWindow()
        insp_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        insp_scrolled.add(self.inspector_view)
        self.inspector_box.pack_start(insp_scrolled, True, True, 0)

        # Protect saved visibility from Gtk.Window.show_all() in Tabs.open()
        self.inspector_box.show_all()
        self.inspector_box.set_no_show_all(True)
        self.inspector_box.set_visible(True)

    def _append_inspector_text_column(  # pylint: disable=too-many-arguments
        self,
        title: str,
        text_col: int,
        *,
        bold: bool = False,
        ellipsize: bool = False,
        xalign: float | None = None,
        fg_hex: str | None = None,
        min_width: int = 60,
    ) -> Gtk.TreeViewColumn:
        renderer = Gtk.CellRendererText()
        if bold:
            renderer.set_property("weight", Pango.Weight.BOLD)
        if ellipsize:
            renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        if xalign is not None:
            renderer.set_property("xalign", xalign)
        if fg_hex is not None:
            renderer.set_property("foreground", fg_hex)
        col = Gtk.TreeViewColumn(title, renderer)
        col.add_attribute(renderer, "text", text_col)
        col.set_resizable(True)
        col.set_min_width(min_width)
        self.inspector_view.append_column(col)
        return col

    def _inspector_color_data_func(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        tree_iter: Gtk.TreeIter,
        _data: object,
    ) -> None:
        has_color = bool(model[tree_iter][INSP_COL_HAS_COLOR])
        cell.set_visible(has_color)
        if isinstance(cell, ColorSwatchCellRenderer):
            cell.has_color = has_color
            cell.rgb = (
                float(model[tree_iter][INSP_COL_R]),
                float(model[tree_iter][INSP_COL_G]),
                float(model[tree_iter][INSP_COL_B]),
            )
            cell.has_palette_ref = bool(model[tree_iter][INSP_COL_HAS_COLOR_REF])
            cell.is_manual = False

    def get_position(self) -> int:
        """Get vertical position of the inspector Paned separator."""
        return self.paned.get_position()

    def set_position(self, position: int) -> None:
        """Set vertical position of the inspector Paned separator."""
        self.paned.set_position(int(position))

    def is_inspector_visible(self) -> bool:
        """Return whether the bottom palette inspector panel is visible."""
        return self.inspector_box.get_visible()

    def set_inspector_visible(self, visible: bool) -> None:
        """Show or hide the bottom palette inspector panel."""
        is_vis = bool(visible)
        if self.inspector_toggle.get_active() != is_vis:
            self.inspector_toggle.set_active(is_vis)
        self.inspector_box.set_visible(is_vis)

    def _on_toggle_inspector(self, button: Gtk.ToggleButton) -> None:
        self.inspector_box.set_visible(button.get_active())

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
                self._selected_numbers[cat] = (
                    tile.number if isinstance(tile, PaletteTileWidget) else None
                )
                self._last_selected_index[cat] = selected[0].get_index()
            else:
                self._selected_numbers[cat] = None
                self._last_selected_index[cat] = None
        self._update_details_and_sensitivity()

    def _on_child_activated(
        self, _flowbox: Gtk.FlowBox, child: Gtk.FlowBoxChild
    ) -> None:
        tile = child.get_child()
        if isinstance(tile, PaletteTileWidget):
            self.recall_palette(tile.category, tile.number)

    def update_palette_tile(self, palette: Palette) -> bool:
        """Update an existing PaletteTileWidget in place without rebuilding FlowBox."""
        fb = self.flowboxes.get(palette.category)
        if fb is None:
            return False
        for child in fb.get_children():
            fb_child = typing.cast(Gtk.FlowBoxChild, child)
            tile = fb_child.get_child()
            if isinstance(tile, PaletteTileWidget) and float(tile.number) == float(
                palette.number
            ):
                tile.update_from_palette(palette)
                if palette.category == self.current_category:
                    self._update_details_and_sensitivity()
                elif (
                    self.current_category is PaletteCategory.PRESET
                    and palette.category is not PaletteCategory.PRESET
                ):
                    self.refresh_inspector()
                return True
        return False

    def refresh_category(self, category: PaletteCategory) -> None:
        """Refresh a single category FlowBox, updating tiles in place when unchanged."""
        self.lightshow = self.app.core.lightshow
        cat = category
        prefix, title, accent = _SPEC_BY_CATEGORY[cat]
        fb = self.flowboxes[cat]
        items = self.lightshow.palettes.list_by_category(cat)
        self.stack.child_set_property(
            self.scrolled_windows[cat],
            "title",
            f"{title} ({len(items)})",
        )

        existing_tiles: list[PaletteTileWidget] = []
        for child in fb.get_children():
            tile = typing.cast(Gtk.FlowBoxChild, child).get_child()
            if isinstance(tile, PaletteTileWidget):
                existing_tiles.append(tile)

        existing_nums = [float(t.number) for t in existing_tiles]
        target_nums = [float(p.number) for p in items]

        if (
            len(existing_tiles) == len(fb.get_children())
            and existing_nums == target_nums
        ):
            for tile, pal in zip(existing_tiles, items, strict=True):
                tile.update_from_palette(pal)
        else:
            self._updating_selection = True
            try:
                for child in list(fb.get_children()):
                    fb.remove(child)
                    child.destroy()

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
                    self._last_selected_index[cat] = restored_child.get_index()
                else:
                    self._selected_numbers[cat] = None
                    self._last_selected_index[cat] = None
            finally:
                self._updating_selection = False

        if cat == self.current_category:
            self._update_details_and_sensitivity()
        elif (
            self.current_category is PaletteCategory.PRESET
            and cat is not PaletteCategory.PRESET
        ):
            self.refresh_inspector()

    def refresh(self) -> None:
        """Refresh all category FlowBoxes from LightShow.palettes."""
        for cat, *_rest in CATEGORY_SPECS:
            self.refresh_category(cat)
        self._update_details_and_sensitivity()

    def refresh_inspector(self) -> None:
        """Populate the bottom Inspector tree view for the currently selected tile."""
        self.inspector_store.clear()
        pal = self.get_selected_palette()
        if pal is None:
            escaped = GLib.markup_escape_text(_("Inspector"))
            hint = GLib.markup_escape_text(
                _("Select a tile to inspect stored channels and values")
            )
            self.inspector_title_label.set_markup(f"<b>{escaped}</b> \u2014 {hint}")
            self._update_inspector_buttons()
            return

        prefix, _title, _accent = _SPEC_BY_CATEGORY[pal.category]
        num_str = format_palette_number(pal.number)
        title_str = f"{prefix} {num_str}" + (f" \u2014 {pal.text}" if pal.text else "")
        all_chs = sorted(set(pal.channels) | set(pal.device_values))
        escaped_title = GLib.markup_escape_text(title_str)
        self.inspector_title_label.set_markup(
            f"<b>{escaped_title}</b>  ({len(all_chs)} ch)"
        )

        percent_mode = (
            bool(self.app.settings.get_boolean("percent"))
            if self.app.settings is not None
            else True
        )
        patch = getattr(self.lightshow, "patch", None)
        devices = getattr(patch, "devices", {}) if patch is not None else {}

        for ch in all_chs:
            dev = devices.get(ch)
            fixture_txt = str(dev.label or dev.fixture_name) if dev is not None else ""
            dev_vals = pal.device_values.get(ch, {})
            if ch in pal.channels:
                int_txt = _format_stored_intensity(
                    pal.channels[ch], percent_mode=percent_mode
                )
            elif isinstance(dev_vals, typing.Mapping) and "intensity" in dev_vals:
                raw_int = dev_vals["intensity"]
                int_txt = (
                    _format_stored_intensity(float(raw_int), percent_mode=percent_mode)
                    if isinstance(raw_int, (int, float))
                    else ""
                )
            else:
                int_txt = ""

            rgb = (
                extract_device_values_rgb(dev_vals)
                if isinstance(dev_vals, typing.Mapping)
                else None
            )
            has_color = rgb is not None
            r, g, b = rgb if rgb is not None else (1.0, 1.0, 1.0)
            refs_map = pal.palette_refs.get(ch, {})
            has_color_ref = any(k in refs_map for k in _COLOR_REF_KEYS)
            params_txt = (
                _format_channel_params(dev_vals)
                if isinstance(dev_vals, typing.Mapping)
                else ""
            )
            refs_txt = _format_channel_refs(self.lightshow, refs_map)

            self.inspector_store.append(
                [
                    int(ch),
                    fixture_txt,
                    int_txt,
                    has_color,
                    float(r),
                    float(g),
                    float(b),
                    has_color_ref,
                    params_txt,
                    refs_txt,
                ]
            )

        self._update_inspector_buttons()

    def _update_inspector_buttons(self) -> None:
        pal = self.get_selected_palette()
        has_rows = bool(self.get_selected_inspector_channels())
        self.btn_inspector_select_ch.set_sensitive(pal is not None and has_rows)
        self.btn_inspector_remove_ch.set_sensitive(pal is not None and has_rows)

    def get_selected_inspector_channels(self) -> list[int]:
        """Return ordered channel IDs currently highlighted in the Inspector."""
        model, paths = self.inspector_selection.get_selected_rows()
        if not paths:
            return []
        channels: list[int] = []
        for path in paths:
            tree_iter = model.get_iter(path)
            channels.append(int(model[tree_iter][INSP_COL_CH]))
        return channels

    def _on_inspector_row_activated(
        self,
        _treeview: Gtk.TreeView,
        path: Gtk.TreePath,
        _column: Gtk.TreeViewColumn,
    ) -> None:
        tree_iter = self.inspector_store.get_iter(path)
        ch = int(self.inspector_store[tree_iter][INSP_COL_CH])
        self.select_channels_in_live([ch])

    def select_channels_in_live(self, channels: list[int]) -> list[int]:
        """Select *channels* in LiveView via ActionRegistry."""
        ordered = list(dict.fromkeys(int(ch) for ch in channels))
        last_sel = ordered[-1] if ordered else None
        self.app.core.action_registry.execute(
            "channel.select_channels",
            channels=ordered,
            last_selected=last_sel,
        )
        return ordered

    def select_selected_channels_in_live(self) -> list[int]:
        """Select all channels stored in the selected palette/preset in Live."""
        pal = self.get_selected_palette()
        if pal is None:
            return []
        channels = sorted(set(pal.channels) | set(pal.device_values))
        return self.select_channels_in_live(channels)

    def select_inspector_channels_in_live(self) -> list[int]:
        """Select highlighted Inspector channels in Live."""
        channels = self.get_selected_inspector_channels()
        if not channels:
            return []
        return self.select_channels_in_live(channels)

    def remove_inspector_channels(self) -> bool:
        """Remove highlighted Inspector channel(s) from the active palette/preset."""
        pal = self.get_selected_palette()
        to_remove = set(self.get_selected_inspector_channels())
        if pal is None or not to_remove:
            return False

        channels_data = {
            int(ch): float(lvl)
            for ch, lvl in pal.channels.items()
            if int(ch) not in to_remove
        }
        device_values = {
            int(ch): copy.deepcopy(vals)
            for ch, vals in pal.device_values.items()
            if int(ch) not in to_remove
        }
        palette_refs = {
            int(ch): copy.deepcopy(refs)
            for ch, refs in pal.palette_refs.items()
            if int(ch) not in to_remove
        }
        self.app.core.action_registry.execute(
            "palette.record",
            pal.category,
            pal.number,
            label=pal.text,
            channels_data=channels_data,
            device_values=device_values,
            palette_refs=palette_refs,
        )
        updated = self.lightshow.palettes.get(pal.category, pal.number)
        if updated is not None:
            self.update_palette_tile(updated)
        else:
            self.refresh_category(pal.category)
        return True

    def _update_details_and_sensitivity(self) -> None:
        pal = self.get_selected_palette()
        has_sel = pal is not None
        has_channels = bool(pal is not None and (pal.channels or pal.device_values))
        self.btn_recall.set_sensitive(has_sel)
        self.btn_select_live.set_sensitive(has_channels)
        self.btn_update.set_sensitive(has_sel)
        self.btn_rename.set_sensitive(has_sel)
        self.btn_delete.set_sensitive(has_sel)
        self.btn_record.set_sensitive(True)

        if pal is None:
            items = self.lightshow.palettes.list_by_category(self.current_category)
            if items:
                self.details_label.set_text(
                    _("Select a tile (double-click or Direct Select to apply)")
                )
            else:
                self.details_label.set_text(
                    _(
                        "No entries in this category. Click Record or run "
                        "RECORD <CATEGORY> PALETTE <n>."
                    )
                )
            self.details_label.set_tooltip_text(None)
            self.refresh_inspector()
            return

        prefix, _title, _accent = _SPEC_BY_CATEGORY[pal.category]
        num_str = format_palette_number(pal.number)
        title_part = f"{prefix} {num_str}" + (f" \u2014 {pal.text}" if pal.text else "")
        all_chs = sorted(set(pal.channels) | set(pal.device_values))
        attrs = sorted(
            {
                str(k)
                for dv in pal.device_values.values()
                if isinstance(dv, dict)
                for k in dv
            }
        )
        parts = [title_part, f"{len(all_chs)} ch"]
        if all_chs:
            parts.append("Ch: " + format_channel_summary(all_chs, max_tokens=6))
        if attrs:
            parts.append("params: " + ", ".join(attrs))
        if pal.palette_refs:
            ref_count = sum(len(refs) for refs in pal.palette_refs.values())
            parts.append(f"{ref_count} palette ref(s)")
        self.details_label.set_text("  |  ".join(parts))

        tooltip_lines = [title_part]
        if all_chs:
            tooltip_lines.append("Channels: " + ", ".join(str(ch) for ch in all_chs))
        if attrs:
            tooltip_lines.append("Params: " + ", ".join(attrs))
        self.details_label.set_tooltip_text("\n".join(tooltip_lines))
        self.refresh_inspector()

    def recall_palette(self, category: PaletteCategory, number: float) -> list[int]:
        """Apply *category* / *number* via Core ActionRegistry."""
        raw_affected = self.app.core.action_registry.execute(
            "palette.apply", category, number
        )
        affected: list[int] = (
            [int(ch) for ch in raw_affected]
            if isinstance(raw_affected, (list, tuple))
            else []
        )
        if (
            not affected
            and (pal := self.lightshow.palettes.get(category, number)) is not None
        ):
            prefix, _title, _accent = _SPEC_BY_CATEGORY[pal.category]
            num_str = format_palette_number(pal.number)
            badge = f"{prefix} {num_str}"
            stored = sorted(set(pal.channels) | set(pal.device_values))
            if not stored:
                self.details_label.set_text(
                    _("{badge} has no stored channels to recall").format(badge=badge)
                )
            else:
                summary = format_channel_summary(stored, max_tokens=6)
                self.details_label.set_text(
                    _(
                        "{badge}: Live selection does not match stored channels "
                        "({channels})"
                    ).format(badge=badge, channels=summary)
                )
        return affected

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
        self.refresh_category(cat)
        return target_num

    def update_selected(self) -> None:
        """Update selected palette/preset with current live stage values."""
        if (pal := self.get_selected_palette()) is None:
            return
        self._selected_numbers[pal.category] = float(pal.number)
        self.app.core.action_registry.execute(
            "palette.update", pal.category, pal.number
        )
        updated = self.lightshow.palettes.get(pal.category, pal.number)
        if updated is not None and self.update_palette_tile(updated):
            return
        self.refresh_category(pal.category)

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
        self.refresh_category(cat)

    def _get_selected_index(self) -> int | None:
        cat = self.current_category
        idx = self._last_selected_index.get(cat)
        if idx is not None:
            return idx
        selected = self.flowbox.get_selected_children()
        if selected:
            resolved = selected[0].get_index()
            self._last_selected_index[cat] = resolved
            return resolved
        return None

    def _select_flowbox_child(self, fb_child: Gtk.FlowBoxChild) -> None:
        """Select *fb_child* smoothly via arrow navigation without Direct Select."""
        cat = self.current_category
        tile = fb_child.get_child()
        self._selected_numbers[cat] = (
            tile.number if isinstance(tile, PaletteTileWidget) else None
        )
        self._last_selected_index[cat] = fb_child.get_index()
        self._updating_selection = True
        try:
            self.flowbox.select_child(fb_child)
        finally:
            self._updating_selection = False
        self._update_details_and_sensitivity()

    def _keypress_q(self) -> None:
        """Previous Palette/Preset tile."""
        self._keypress_left()

    def _keypress_w(self) -> None:
        """Next Palette/Preset tile."""
        self._keypress_right()

    def _keypress_right(self) -> None:
        """Select next tile in current category."""
        idx = self._get_selected_index()
        if idx is None:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        elif child := self.flowbox.get_child_at_index(idx + 1):
            self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))

    def _keypress_left(self) -> None:
        """Select previous tile in current category."""
        idx = self._get_selected_index()
        if idx is None:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        elif idx > 0:
            if child := self.flowbox.get_child_at_index(idx - 1):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))

    def _keypress_down(self) -> None:
        """Select tile on next row in current category."""
        idx = self._get_selected_index()
        if idx is None:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        else:
            child = self.flowbox.get_child_at_index(idx)
            if child is not None:
                allocation = child.get_allocation()
                if next_child := self.flowbox.get_child_at_pos(
                    allocation.x, allocation.y + allocation.height + 4
                ):
                    self._select_flowbox_child(
                        typing.cast(Gtk.FlowBoxChild, next_child)
                    )

    def _keypress_up(self) -> None:
        """Select tile on previous row in current category."""
        idx = self._get_selected_index()
        if idx is None:
            if child := self.flowbox.get_child_at_index(0):
                self._select_flowbox_child(typing.cast(Gtk.FlowBoxChild, child))
        else:
            child = self.flowbox.get_child_at_index(idx)
            if child is not None:
                allocation = child.get_allocation()
                y_pos = int(allocation.y - allocation.height / 2)
                if y_pos >= 0 and (
                    prev_child := self.flowbox.get_child_at_pos(allocation.x, y_pos)
                ):
                    self._select_flowbox_child(
                        typing.cast(Gtk.FlowBoxChild, prev_child)
                    )

    def _keypress_delete(self) -> None:
        self.delete_selected()

    def _keypress_f2(self) -> None:
        self.rename_selected()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close the Palettes tab."""
        if self.tabs:
            self.tabs.close("palettes")

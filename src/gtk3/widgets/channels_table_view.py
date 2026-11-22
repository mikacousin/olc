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
"""Hybrid Fixture Sheet / Table view widget for ChannelsView."""

from __future__ import annotations

import typing
from typing import Any, Iterable

import cairo
from gi.repository import Gdk, Gtk, Pango

from olc.core.channel_snapshot import (
    AttributeFamilySnapshot,
    ChannelDisplaySnapshot,
    format_family_readout,
    format_parameter_readout,
)
from olc.core.selection import (
    SelectActiveAction,
    SelectAddAction,
    SelectNoneAction,
    SelectRemoveAction,
    SelectThruAction,
)
from olc.core.tracking import TrackingDisplayState, get_tracking_color

if typing.TYPE_CHECKING:
    from olc.gtk3.widgets.channels_view import ChannelsView

# Model column indices in Gtk.ListStore
COL_CHANNEL = 0
COL_FIXTURE = 1
COL_INTENSITY = 2
COL_INTENSITY_FG = 3
COL_COLOR_TEXT = 4
COL_COLOR_FG = 5
COL_HAS_COLOR = 6
COL_SWATCH_R = 7
COL_SWATCH_G = 8
COL_SWATCH_B = 9
COL_COLOR_HAS_REF = 10
COL_COLOR_IS_MANUAL = 11
COL_FOCUS_TEXT = 12
COL_FOCUS_FG = 13
COL_BEAM_TEXT = 14
COL_BEAM_FG = 15
COL_ADDRESS = 16
COL_CH_FG = 17

_ALL_COL_INDICES: list[int] = list(range(18))

PALETTE_CYAN_HEX = "#59EBFA"
EFFECT_MAGENTA_HEX = "#D959F2"
MANUAL_CORAL_HEX = "#F25959"
PARK_AMBER_HEX = "#FFB200"
MIB_AMBER_HEX = "#FFA626"
PATCHED_CH_HEX = "#E69933"
INDEP_CH_HEX = "#8080CC"
UNPATCHED_CH_HEX = "#808080"
DEFAULT_TEXT_HEX = "#CFD6DC"
MUTED_TEXT_HEX = "#8E969B"

FAMILY_PARAM_ORDER: dict[str, tuple[str, ...]] = {
    "focus": ("pan", "tilt"),
    "color": (
        "red",
        "green",
        "blue",
        "white",
        "amber",
        "lime",
        "cyan",
        "indigo",
        "magenta",
        "yellow",
        "cct",
        "color_wheel",
    ),
    "beam": ("zoom", "focus", "iris", "strobe", "gobo", "frost", "prism"),
}

PARAM_TITLES: dict[str, str] = {
    "pan": "Pan",
    "tilt": "Tilt",
    "red": "Red",
    "green": "Green",
    "blue": "Blue",
    "white": "White",
    "amber": "Amber",
    "lime": "Lime",
    "cyan": "Cyan",
    "indigo": "Indigo",
    "magenta": "Magenta",
    "yellow": "Yellow",
    "cct": "CCT",
    "color_wheel": "C.Wheel",
    "zoom": "Zoom",
    "focus": "Focus",
    "iris": "Iris",
    "strobe": "Shutter",
    "gobo": "Gobo",
    "frost": "Frost",
    "prism": "Prism",
}

_EXPAND_FAMILY_ALIASES: dict[str, str] = {
    "f": "focus",
    "focus": "focus",
    "pos": "focus",
    "position": "focus",
    "c": "color",
    "color": "color",
    "colour": "color",
    "b": "beam",
    "beam": "beam",
}


def normalize_expand_family(family: str) -> str:
    """Normalize family specifier to one of ``'focus'``, ``'color'``, ``'beam'``."""
    return _EXPAND_FAMILY_ALIASES.get(
        str(family).strip().lower(), str(family).strip().lower()
    )


def _rgb_dict_to_hex(col: dict[str, float]) -> str:
    r = round(max(0.0, min(1.0, float(col.get("red", 0.85)))) * 255)
    g = round(max(0.0, min(1.0, float(col.get("green", 0.85)))) * 255)
    b = round(max(0.0, min(1.0, float(col.get("blue", 0.85)))) * 255)
    return f"#{r:02X}{g:02X}{b:02X}"


def _family_cell_fg_hex(
    family_snap: AttributeFamilySnapshot,
    readout: str,
    *,
    is_mib_channel: bool = False,
    param_key: str | None = None,
) -> str:
    """Resolve foreground hex color for a family summary or sub-parameter cell."""
    mode_low = str(readout).strip().lower()
    if (
        param_key is None
        and family_snap.effect_ref is not None
        and mode_low in ("auto", "label", "ref")
    ):
        return EFFECT_MAGENTA_HEX
    has_ref = (
        param_key in family_snap.parameter_refs
        if param_key is not None
        else family_snap.palette_ref is not None
    )
    if has_ref and mode_low in ("auto", "label", "ref"):
        return PALETTE_CYAN_HEX
    if family_snap.is_manual:
        return MANUAL_CORAL_HEX
    if is_mib_channel or family_snap.tracking_state == TrackingDisplayState.MIB:
        return MIB_AMBER_HEX
    if family_snap.tracking_state != TrackingDisplayState.INACTIVE:
        return _rgb_dict_to_hex(get_tracking_color(family_snap.tracking_state))
    return DEFAULT_TEXT_HEX


def _get_snapshot_family(
    snap: ChannelDisplaySnapshot, family: str
) -> AttributeFamilySnapshot:
    if family == "focus":
        return snap.focus
    if family == "color":
        return snap.color
    return snap.beam


class ColorSwatchCellRenderer(Gtk.CellRenderer):
    """Custom Cairo cell renderer drawing a live color preview swatch."""

    has_color: bool
    rgb: tuple[float, float, float]
    has_palette_ref: bool
    is_manual: bool

    def __init__(self) -> None:
        super().__init__()
        self.has_color = False
        self.rgb = (1.0, 1.0, 1.0)
        self.has_palette_ref = False
        self.is_manual = False

    def do_get_size(
        self,
        _widget: Gtk.Widget,
        _cell_area: Gdk.Rectangle | None = None,
    ) -> tuple[int, int, int, int]:
        """Return fixed cell size reservation for the color swatch."""
        return (0, 0, 24, 18)

    def do_render(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        cr: cairo.Context,
        _widget: Gtk.Widget,
        _background_area: Gdk.Rectangle,
        cell_area: Gdk.Rectangle,
        _flags: Any,  # noqa: ANN401
    ) -> None:
        """Draw the real-time color swatch with cyan/coral border hints."""
        if not self.has_color:
            return
        w = 18.0
        h = 12.0
        x = float(cell_area.x) + 2.0
        y = float(cell_area.y) + max(0.0, (float(cell_area.height) - h) / 2.0)

        cr.rectangle(x, y, w, h)
        cr.set_source_rgb(
            max(0.0, min(1.0, float(self.rgb[0]))),
            max(0.0, min(1.0, float(self.rgb[1]))),
            max(0.0, min(1.0, float(self.rgb[2]))),
        )
        cr.fill_preserve()

        if self.has_palette_ref:
            cr.set_source_rgb(0.20, 0.88, 0.96)
            cr.set_line_width(1.5)
        elif self.is_manual:
            cr.set_source_rgb(0.95, 0.35, 0.35)
            cr.set_line_width(1.2)
        else:
            cr.set_source_rgb(0.55, 0.55, 0.55)
            cr.set_line_width(1.0)
        cr.stroke()

        if self.has_palette_ref:
            cr.rectangle(x, y, 3.0, h)
            cr.set_source_rgb(0.20, 0.88, 0.96)
            cr.fill()


# pylint: disable=too-many-instance-attributes
class ChannelsTableView(Gtk.ScrolledWindow):
    """Fixture-sheet style table view with expandable F/C/B columns."""

    channels_view: ChannelsView
    store: Gtk.ListStore
    treeview: Gtk.TreeView
    selection: Gtk.TreeSelection
    swatch_renderer: ColorSwatchCellRenderer
    expanded_families: dict[str, bool]

    def __init__(self, channels_view: ChannelsView) -> None:
        super().__init__()
        self.channels_view = channels_view
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.expanded_families = {"focus": False, "color": False, "beam": False}
        self._dynamic_columns: dict[str, list[Gtk.TreeViewColumn]] = {
            "focus": [],
            "color": [],
            "beam": [],
        }
        self._dynamic_param_keys: dict[str, tuple[str, ...]] = {
            "focus": (),
            "color": (),
            "beam": (),
        }
        self._channel_iters: dict[int, Gtk.TreeIter] = {}
        self._visible_channels: list[int] = []
        self._row_snapshots: dict[int, ChannelDisplaySnapshot] = {}
        self._updating_selection = False
        self._batch_percent_mode: bool | None = None
        self._batch_indep_channels: set[int] | None = None

        self.store = Gtk.ListStore(
            int,  # COL_CHANNEL
            str,  # COL_FIXTURE
            str,  # COL_INTENSITY
            str,  # COL_INTENSITY_FG
            str,  # COL_COLOR_TEXT
            str,  # COL_COLOR_FG
            bool,  # COL_HAS_COLOR
            float,  # COL_SWATCH_R
            float,  # COL_SWATCH_G
            float,  # COL_SWATCH_B
            bool,  # COL_COLOR_HAS_REF
            bool,  # COL_COLOR_IS_MANUAL
            str,  # COL_FOCUS_TEXT
            str,  # COL_FOCUS_FG
            str,  # COL_BEAM_TEXT
            str,  # COL_BEAM_FG
            str,  # COL_ADDRESS
            str,  # COL_CH_FG
        )

        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.set_headers_visible(True)
        self.treeview.set_enable_search(False)
        self.treeview.set_grid_lines(Gtk.TreeViewGridLines.HORIZONTAL)

        self.selection = self.treeview.get_selection()
        self.selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.selection.connect("changed", self._on_selection_changed)
        self.treeview.connect("button-press-event", self._on_button_press)

        self._build_base_columns()
        self.add(self.treeview)

        self.channels_view.register_dirty_flush_listener(self.on_dirty_flushed)
        self.connect("destroy", self._on_destroy)

    def _on_destroy(self, *_args: object) -> None:
        self.channels_view.unregister_dirty_flush_listener(self.on_dirty_flushed)

    @staticmethod
    def _make_text_column(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        title: str,
        text_col: int,
        *,
        fg_col: int | None = None,
        fg_hex: str | None = None,
        ellipsize: bool = False,
        xalign: float | None = None,
        bold: bool = False,
        min_width: int = 72,
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
        if fg_col is not None:
            col.add_attribute(renderer, "foreground", fg_col)
        col.set_resizable(True)
        col.set_min_width(min_width)
        return col

    def _is_membership_view(self) -> bool:
        return bool(getattr(self.channels_view, "is_membership_view", False))

    def _build_base_columns(self) -> None:
        is_membership = self._is_membership_view()
        # 1. Ch
        self.treeview.append_column(
            self._make_text_column(
                "Ch", COL_CHANNEL, fg_col=COL_CH_FG, bold=True, min_width=44
            )
        )

        # 2. Fixture / Label
        self._col_fixture = self._make_text_column(
            "Fixture / Label", COL_FIXTURE, ellipsize=True, min_width=130
        )
        self._col_fixture.set_visible(
            bool(getattr(self.channels_view, "show_labels", True))
        )
        self.treeview.append_column(self._col_fixture)

        # 3. Order (Groups) or Int
        self.treeview.append_column(
            self._make_text_column(
                "Order" if is_membership else "Int",
                COL_INTENSITY,
                fg_col=COL_INTENSITY_FG,
                bold=True,
                xalign=1.0,
                min_width=54,
            )
        )

        # 4. Color (live swatch + text)
        self._col_color = Gtk.TreeViewColumn("Color")
        self._col_color.set_resizable(True)
        self._col_color.set_min_width(110)
        self.swatch_renderer = ColorSwatchCellRenderer()
        self._col_color.pack_start(self.swatch_renderer, False)
        self._col_color.set_cell_data_func(
            typing.cast(Gtk.CellRendererPixbuf, self.swatch_renderer),
            self._color_swatch_data_func,
            None,
        )
        r_col = Gtk.CellRendererText()
        r_col.set_property("ellipsize", Pango.EllipsizeMode.END)
        self._col_color.pack_start(r_col, True)
        self._col_color.add_attribute(r_col, "text", COL_COLOR_TEXT)
        self._col_color.add_attribute(r_col, "foreground", COL_COLOR_FG)
        self._col_color.set_visible(not is_membership)
        self.treeview.append_column(self._col_color)

        # 5. Focus
        self._col_focus = self._make_text_column(
            "Focus", COL_FOCUS_TEXT, fg_col=COL_FOCUS_FG, ellipsize=True, min_width=95
        )
        self._col_focus.set_visible(not is_membership)
        self.treeview.append_column(self._col_focus)

        # 6. Beam
        self._col_beam = self._make_text_column(
            "Beam", COL_BEAM_TEXT, fg_col=COL_BEAM_FG, ellipsize=True, min_width=95
        )
        self._col_beam.set_visible(not is_membership)
        self.treeview.append_column(self._col_beam)

        # 7. Address
        self._col_address = self._make_text_column(
            "Address", COL_ADDRESS, fg_hex=MUTED_TEXT_HEX, min_width=72
        )
        self.treeview.append_column(self._col_address)

    def _color_swatch_data_func(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        tree_iter: Gtk.TreeIter,
        _data: object,
    ) -> None:
        has_color = bool(model[tree_iter][COL_HAS_COLOR])
        cell.set_visible(has_color)
        if isinstance(cell, ColorSwatchCellRenderer):
            cell.has_color = has_color
            cell.rgb = (
                float(model[tree_iter][COL_SWATCH_R]),
                float(model[tree_iter][COL_SWATCH_G]),
                float(model[tree_iter][COL_SWATCH_B]),
            )
            cell.has_palette_ref = bool(model[tree_iter][COL_COLOR_HAS_REF])
            cell.is_manual = bool(model[tree_iter][COL_COLOR_IS_MANUAL])

    def _param_cell_data_func(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        tree_iter: Gtk.TreeIter,
        data: tuple[str, str],
    ) -> None:
        family, param_key = data
        ch = int(model[tree_iter][COL_CHANNEL])
        text, fg_hex = self.get_param_cell_data(ch, family, param_key)
        cell.set_property("text", text)
        cell.set_property("foreground", fg_hex)

    def get_param_cell_data(
        self, channel: int, family: str, param_key: str
    ) -> tuple[str, str]:
        """Return ``(formatted_text, foreground_hex)`` for a dynamic parameter cell."""
        snap = self._row_snapshots.get(channel)
        if snap is None:
            snap = self.channels_view.get_channel_snapshot(channel)
            if snap is not None:
                self._row_snapshots[channel] = snap
        if snap is None:
            return "", DEFAULT_TEXT_HEX
        fam_snap = _get_snapshot_family(snap, family)
        if not fam_snap.available or param_key not in fam_snap.parameters:
            return "", DEFAULT_TEXT_HEX
        text = format_parameter_readout(
            fam_snap, param_key, self.channels_view.readout_mode
        )
        fg_hex = _family_cell_fg_hex(
            fam_snap,
            self.channels_view.readout_mode,
            is_mib_channel=snap.is_mib,
            param_key=param_key,
        )
        return text, fg_hex

    def get_column_titles(self) -> list[str]:
        """Return ordered visible column titles."""
        return [
            col.get_title() or ""
            for col in self.treeview.get_columns()
            if col.get_visible()
        ]

    def set_show_labels(self, show: bool) -> None:
        """Show or hide the Fixture / Label column."""
        self._col_fixture.set_visible(bool(show))

    def set_family_expanded(self, family: str, expanded: bool) -> None:
        """Expand or collapse dynamic sub-columns for *family*."""
        norm = normalize_expand_family(family)
        if norm not in self.expanded_families:
            return
        self.expanded_families[norm] = bool(expanded)
        self.refresh_dynamic_columns()

    def discover_family_parameters(self, family: str) -> tuple[str, ...]:
        """Discover union of active parameter keys for *family* in canonical order."""
        norm = normalize_expand_family(family)
        seen: set[str] = set()
        for ch in self._visible_channels:
            snap = self._row_snapshots.get(ch)
            if snap is None:
                snap = self.channels_view.get_channel_snapshot(ch)
                if snap is not None:
                    self._row_snapshots[ch] = snap
            if snap is None:
                continue
            fam_snap = _get_snapshot_family(snap, norm)
            if not fam_snap.available:
                continue
            keys = set(fam_snap.parameters.keys())
            if norm == "color" and "color" in keys and len(keys) > 1:
                keys.discard("color")
            seen.update(keys)

        ordered: list[str] = []
        for candidate in FAMILY_PARAM_ORDER.get(norm, ()):
            if candidate in seen:
                ordered.append(candidate)
                seen.discard(candidate)
        for extra in sorted(seen):
            ordered.append(extra)
        return tuple(ordered)

    def _anchor_column_for_family(self, family: str) -> Gtk.TreeViewColumn:
        if family == "color":
            return self._col_color
        if family == "focus":
            return self._col_focus
        return self._col_beam

    def refresh_dynamic_columns(self) -> None:
        """Synchronize expanded F/C/B TreeViewColumns with current visible channels."""
        if self._is_membership_view():
            return
        for family in ("color", "focus", "beam"):
            desired = (
                self.discover_family_parameters(family)
                if self.expanded_families.get(family, False)
                else ()
            )
            if desired == self._dynamic_param_keys[family]:
                continue
            for old_col in self._dynamic_columns[family]:
                self.treeview.remove_column(old_col)
            self._dynamic_columns[family].clear()

            if desired:
                cols = self.treeview.get_columns()
                anchor = self._anchor_column_for_family(family)
                try:
                    base_idx = cols.index(anchor)
                except ValueError:
                    base_idx = len(cols) - 1
                for offset, p_key in enumerate(desired):
                    title = PARAM_TITLES.get(p_key, p_key.replace("_", " ").title())
                    renderer = Gtk.CellRendererText()
                    col = Gtk.TreeViewColumn(title, renderer)
                    col.set_resizable(True)
                    col.set_min_width(58)
                    col.set_cell_data_func(
                        renderer, self._param_cell_data_func, (family, p_key)
                    )
                    self.treeview.insert_column(col, base_idx + 1 + offset)
                    self._dynamic_columns[family].append(col)

            self._dynamic_param_keys[family] = desired

    def on_dirty_flushed(self, dirty_channels: set[int] | None) -> None:
        """Handle ~30 fps coalesced dirty flush from parent ChannelsView."""
        if self.channels_view.display_format != "Table":
            return
        self.update_dirty_channels(dirty_channels)

    def _populate_batch_caches(self) -> None:
        settings = self.channels_view.settings
        self._batch_percent_mode = (
            bool(settings.get_boolean("percent")) if settings else True
        )
        lightshow = self.channels_view.lightshow
        self._batch_indep_channels = (
            set(lightshow.independents.get_channels())
            if lightshow is not None
            else set()
        )

    def _clear_batch_caches(self) -> None:
        self._batch_percent_mode = None
        self._batch_indep_channels = None

    def update_dirty_channels(self, dirty_channels: Iterable[int] | None) -> int:
        """Update only dirty rows in the ListStore cleanly in one set() per row."""
        if not self._channel_iters:
            return 0
        if dirty_channels is None:
            targets = [ch for ch in self._visible_channels if ch in self._channel_iters]
        else:
            targets = [
                int(ch) for ch in dirty_channels if int(ch) in self._channel_iters
            ]

        updated = 0
        self._populate_batch_caches()
        try:
            for ch in targets:
                tree_iter = self._channel_iters.get(ch)
                if tree_iter is None:
                    continue
                row = self._build_row_tuple(ch)
                self.store.set(tree_iter, _ALL_COL_INDICES, list(row))
                updated += 1
        finally:
            self._clear_batch_caches()
        return updated

    def rebuild_rows(self, *, force: bool = False) -> None:
        """Populate or refresh ListStore rows matching visible filtered channels."""
        visible = self.channels_view.get_visible_channels()
        if (
            not force
            and visible == self._visible_channels
            and len(self._channel_iters) == len(visible)
        ):
            self.update_dirty_channels(None)
            self.refresh_dynamic_columns()
            self.sync_selection(self.channels_view.get_selected_channels())
            return

        detach_model = len(visible) > 32
        self._updating_selection = True
        self._populate_batch_caches()
        if detach_model:
            self.treeview.set_model(None)
        try:
            self.store.clear()
            self._channel_iters.clear()
            self._row_snapshots.clear()
            self._visible_channels = list(visible)
            for ch in visible:
                row = self._build_row_tuple(ch)
                tree_iter = self.store.append(list(row))
                self._channel_iters[ch] = tree_iter
        finally:
            if detach_model:
                self.treeview.set_model(self.store)
            self._clear_batch_caches()
            self._updating_selection = False

        self.refresh_dynamic_columns()
        self.sync_selection(self.channels_view.get_selected_channels())

    def _channel_number_hex(
        self, channel: int, snap: ChannelDisplaySnapshot | None
    ) -> str:
        lightshow = self.channels_view.lightshow
        if lightshow is not None:
            indep_channels = (
                self._batch_indep_channels
                if self._batch_indep_channels is not None
                else lightshow.independents.get_channels()
            )
            if channel in indep_channels:
                return INDEP_CH_HEX
            if not lightshow.patch.is_patched(channel):
                return UNPATCHED_CH_HEX
            return PATCHED_CH_HEX
        if snap is not None and not snap.is_patched:
            return UNPATCHED_CH_HEX
        return PATCHED_CH_HEX

    def _format_intensity_cell(
        self, channel: int, snap: ChannelDisplaySnapshot | None
    ) -> tuple[str, str]:
        if self._batch_percent_mode is not None:
            percent_mode = self._batch_percent_mode
        else:
            settings = self.channels_view.settings
            percent_mode = bool(settings.get_boolean("percent")) if settings else True
        readout_low = self.channels_view.readout_mode.strip().lower()

        if snap is not None:
            if snap.is_parked:
                fg_hex = PARK_AMBER_HEX
            elif snap.intensity_color:
                fg_hex = _rgb_dict_to_hex(snap.intensity_color)
            else:
                fg_hex = DEFAULT_TEXT_HEX

            if (
                snap.intensity_ref is not None or snap.intensity_effect_ref is not None
            ) and readout_low in (
                "auto",
                "label",
                "ref",
            ):
                parts: list[str] = []
                if snap.intensity_ref is not None:
                    parts.append(
                        snap.intensity_ref.label or snap.intensity_ref.short_ref
                        if readout_low in ("auto", "label")
                        else snap.intensity_ref.short_ref
                    )
                if snap.intensity_effect_ref is not None:
                    parts.append(
                        snap.intensity_effect_ref.label
                        if (readout_low == "label" and snap.intensity_effect_ref.label)
                        else snap.intensity_effect_ref.short_ref
                    )
                return (
                    " + ".join(parts),
                    EFFECT_MAGENTA_HEX
                    if snap.intensity_effect_ref is not None
                    else PALETTE_CYAN_HEX,
                )

            if (
                snap.intensity <= 0.0
                and snap.intensity_state == TrackingDisplayState.INACTIVE
                and not snap.is_parked
            ):
                return "", fg_hex

            if readout_low == "percent":
                val_txt = f"{round(snap.intensity * 100.0)}%"
            elif readout_low == "dmx":
                val_txt = str(round(snap.intensity * 255.0))
            elif percent_mode:
                val_txt = (
                    "F"
                    if snap.intensity >= 1.0
                    else f"{round(snap.intensity * 100.0)}%"
                )
            else:
                val_txt = str(round(snap.intensity * 255.0))

            if snap.is_mib and snap.intensity <= 0.0:
                return "0 (MIB)", MIB_AMBER_HEX
            return val_txt, fg_hex

        # Fallback for Group / Independent / ChannelTime views without snapshots
        widget = self.channels_view.get_channel_widget(channel)
        if self._is_membership_view():
            order = widget.membership_order if widget is not None else None
            if order is not None:
                return f"#{order}", PALETTE_CYAN_HEX
            return "", DEFAULT_TEXT_HEX
        raw_lvl = float(widget.level) if widget is not None else 0.0
        fg_hex = (
            _rgb_dict_to_hex(widget.color_level)
            if widget is not None
            else DEFAULT_TEXT_HEX
        )
        if raw_lvl <= 0.0:
            return "", fg_hex
        norm = min(1.0, raw_lvl / 255.0) if raw_lvl > 1.0 else raw_lvl
        if readout_low == "dmx" or not percent_mode:
            return str(round(norm * 255.0)), fg_hex
        return ("F" if norm >= 1.0 else f"{round(norm * 100.0)}%"), fg_hex

    def _build_row_tuple(self, channel: int) -> tuple[Any, ...]:
        snap = self.channels_view.get_channel_snapshot(channel)
        if snap is not None:
            self._row_snapshots[channel] = snap
        else:
            self._row_snapshots.pop(channel, None)

        ch_fg = self._channel_number_hex(channel, snap)
        int_txt, int_fg = self._format_intensity_cell(channel, snap)
        readout = self.channels_view.readout_mode

        if snap is not None:
            fixture_txt = snap.device_label or snap.fixture_name
            has_color = bool(snap.has_color and snap.preview_rgb is not None)
            rgb = snap.preview_rgb if snap.preview_rgb is not None else (1.0, 1.0, 1.0)
            col_txt = format_family_readout(snap.color, readout)
            col_fg = _family_cell_fg_hex(
                snap.color, readout, is_mib_channel=snap.is_mib
            )
            col_has_ref = snap.color.palette_ref is not None
            col_is_manual = snap.color.is_manual
            foc_txt = format_family_readout(snap.focus, readout)
            foc_fg = _family_cell_fg_hex(
                snap.focus, readout, is_mib_channel=snap.is_mib
            )
            beam_txt = format_family_readout(snap.beam, readout)
            beam_fg = _family_cell_fg_hex(
                snap.beam, readout, is_mib_channel=snap.is_mib
            )
            addr_txt = snap.address_str
        else:
            lightshow = self.channels_view.lightshow
            dev = (
                lightshow.patch.devices.get(channel) if lightshow is not None else None
            )
            fixture_txt = str(dev.label or dev.fixture_name) if dev is not None else ""
            if self._is_membership_view():
                has_color = False
                rgb = (1.0, 1.0, 1.0)
            else:
                preview = dev.get_preview_rgb() if dev is not None else None
                has_color = preview is not None
                rgb = preview if preview is not None else (1.0, 1.0, 1.0)
            col_txt = ""
            col_fg = DEFAULT_TEXT_HEX
            col_has_ref = False
            col_is_manual = False
            foc_txt = ""
            foc_fg = DEFAULT_TEXT_HEX
            beam_txt = ""
            beam_fg = DEFAULT_TEXT_HEX
            addr_txt = (
                f"{dev.universe_display_str}/{dev.address_range_str}"
                if dev is not None and dev.channels
                else ""
            )

        return (
            int(channel),
            fixture_txt,
            int_txt,
            int_fg,
            col_txt,
            col_fg,
            has_color,
            float(rgb[0]),
            float(rgb[1]),
            float(rgb[2]),
            col_has_ref,
            col_is_manual,
            foc_txt,
            foc_fg,
            beam_txt,
            beam_fg,
            addr_txt,
            ch_fg,
        )

    def sync_selection(self, selected_channels: list[int]) -> None:
        """Synchronize logical selected channels into TreeSelection without feedback."""
        self._updating_selection = True
        try:
            self.selection.unselect_all()
            for ch in selected_channels:
                tree_iter = self._channel_iters.get(int(ch))
                if tree_iter is not None:
                    self.selection.select_iter(tree_iter)
        finally:
            self._updating_selection = False

    def scroll_to_channel(self, channel: int) -> None:
        """Scroll Table view to reveal *channel* when visible."""
        tree_iter = self._channel_iters.get(int(channel))
        if tree_iter is None:
            return
        path = self.store.get_path(tree_iter)
        if path is not None:
            self.treeview.scroll_to_cell(path, None, False, 0.0, 0.0)

    def _on_button_press(self, treeview: Gtk.TreeView, event: Gdk.EventButton) -> bool:
        """Route Table clicks through SelectionManager for Undo & Inspector sync."""
        if event.button != Gdk.BUTTON_PRIMARY:
            return False
        hit = treeview.get_path_at_pos(int(event.x), int(event.y))
        if hit is None or hit[0] is None:
            return False
        path = hit[0]
        tree_iter = self.store.get_iter(path)
        ch = int(self.store[tree_iter][COL_CHANNEL])

        accel_mask = Gtk.accelerator_get_default_mod_mask()
        mods = event.state & accel_mask
        mgr = self.channels_view.selection_manager
        if mods & Gdk.ModifierType.SHIFT_MASK:
            mgr.execute_action(SelectThruAction, ch)
        elif mods & Gdk.ModifierType.CONTROL_MASK:
            if ch in mgr.selected_channels:
                mgr.execute_action(SelectRemoveAction, ch)
            else:
                mgr.execute_action(SelectAddAction, ch)
        else:
            mgr.execute_action(SelectActiveAction, ch)
        return True

    def _on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        """Propagate keyboard / programmatic TreeSelection changes back to core."""
        if self._updating_selection or self.channels_view.updating_selection:
            return
        model, paths = selection.get_selected_rows()
        selected_channels: list[int] = []
        for path in paths:
            tree_iter = model.get_iter(path)
            selected_channels.append(int(model[tree_iter][COL_CHANNEL]))

        mgr = self.channels_view.selection_manager
        if selected_channels == list(mgr.selected_channels):
            return

        self._updating_selection = True
        try:
            if not selected_channels:
                mgr.execute_action(SelectNoneAction)
            elif len(selected_channels) == 1:
                mgr.execute_action(SelectActiveAction, selected_channels[0])
            else:
                mgr.selected_channels = list(selected_channels)
                mgr.last_selected_channel = selected_channels[-1]
                mgr.notify_changed()
        finally:
            self._updating_selection = False

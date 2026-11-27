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
"""GTK3 Effects management tab with layer editor and Cairo 1D/2D visualizer."""

from __future__ import annotations

import copy
import math
import time
import typing
from gettext import gettext as _
from typing import Any

import cairo
import numpy as np
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from olc.actions.effect import format_effect_number
from olc.core.effects_engine import compute_channel_phase_offsets, evaluate_waveform
from olc.define import is_non_nul_float
from olc.gtk3.widgets.common import (
    create_pango_layout_for_widget,
    create_system_font_description,
    rounded_rectangle,
    rounded_rectangle_fill,
)
from olc.show.effect import (
    BUILTIN_EFFECT_TEMPLATES,
    DistributeDirection,
    EffectDefinition,
    EffectEnvelopeMode,
    EffectLayer,
    EffectMode,
    WaveformType,
)

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.show.lightshow import LightShow

EFFECT_PARAMETERS: tuple[str, ...] = (
    "intensity",
    "pan",
    "tilt",
    "color",
    "zoom",
    "focus",
    "iris",
    "strobe",
    "cct",
)

WAVEFORM_NAMES: tuple[str, ...] = tuple(w.value for w in WaveformType)
MODE_NAMES: tuple[str, ...] = tuple(m.value for m in EffectMode)
DIRECTION_NAMES: tuple[str, ...] = tuple(d.value for d in DistributeDirection)
ENVELOPE_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (EffectEnvelopeMode.IMMEDIATE.value, "Immediate"),
    (EffectEnvelopeMode.FADE_BY_SIZE.value, "Fade Size"),
    (EffectEnvelopeMode.FADE_BY_RATE.value, "Fade Rate"),
    (EffectEnvelopeMode.FADE_BY_SIZE_AND_RATE.value, "Size & Rate"),
)

_LAYER_COLORS: tuple[tuple[float, float, float], ...] = (
    (0.85, 0.35, 0.95),  # Magenta
    (0.25, 0.85, 0.95),  # Cyan
    (0.95, 0.72, 0.20),  # Amber
    (0.35, 0.92, 0.55),  # Mint
)


def _format_palette_ref_str(ref: tuple[str, float] | None) -> str:
    if ref is None:
        return ""
    cat = str(ref[0]).strip().lower()
    prefix_map = {
        "intensity": "IP",
        "focus": "FP",
        "position": "FP",
        "color": "CP",
        "beam": "BP",
        "preset": "PR",
    }
    prefix = prefix_map.get(cat, cat.upper()[:2])
    num = float(ref[1])
    num_s = str(int(num)) if num.is_integer() else f"{num:g}"
    return f"{prefix} {num_s}"


def _parse_user_palette_ref(
    text: str, default_category: str = "color"
) -> tuple[str, float] | None:
    raw = text.strip()
    if not raw:
        return None
    parts = raw.upper().replace(":", " ").split()
    prefix_to_cat = {
        "IP": "intensity",
        "INTENSITY": "intensity",
        "FP": "focus",
        "FOCUS": "focus",
        "POSITION": "focus",
        "CP": "color",
        "COLOR": "color",
        "COLOUR": "color",
        "BP": "beam",
        "BEAM": "beam",
        "PR": "preset",
        "PRESET": "preset",
        "P": "preset",
    }
    if len(parts) == 1:
        try:
            return (default_category, float(parts[0]))
        except ValueError:
            return None
    cat = prefix_to_cat.get(parts[0], default_category)
    try:
        return (cat, float(parts[1]))
    except ValueError:
        return None


def _default_palette_category_for_param(param: str) -> str:
    p = str(param).strip().lower()
    if p == "intensity":
        return "intensity"
    if p in ("pan", "tilt"):
        return "focus"
    if p in ("color", "cct"):
        return "color"
    return "beam"


class EffectPreviewArea(Gtk.DrawingArea):
    """Real-time Cairo 1D Waveform & 2D Pan/Tilt XY Path visualizer."""

    __gtype_name__ = "EffectPreviewArea"

    def __init__(self, tab: EffectsTab) -> None:
        super().__init__()
        self.tab = tab
        self.preview_mode: str = "auto"  # "auto", "1d", or "2d"
        self._anim_phase: float = 0.0
        self._last_time: float = time.monotonic()
        self.set_size_request(160, 175)
        self.set_hexpand(True)
        self.set_vexpand(True)

    def effective_mode(self, eff: EffectDefinition | None) -> str:
        """Determine whether to render '2d' XY path or '1d' waveform."""
        if self.preview_mode in ("1d", "2d"):
            return self.preview_mode
        if eff is not None:
            params = {layer.parameter for layer in eff.layers}
            if "pan" in params and "tilt" in params:
                return "2d"
        return "1d"

    def step_animation(self, now: float | None = None) -> None:
        """Advance internal animation clock and request redraw."""
        t_now = time.monotonic() if now is None else float(now)
        dt = max(0.0, min(0.25, t_now - self._last_time))
        self._last_time = t_now
        eff = self.tab.get_selected_effect()
        if eff is not None:
            period = max(0.1, float(eff.cycle_time))
            self._anim_phase = (self._anim_phase + dt / period) % 1.0
        self.queue_draw()

    def _get_preview_channels(self) -> list[int]:
        sel = list(getattr(self.tab.app.core, "selected_channels", []))
        if sel:
            return sel[:16]
        eff = self.tab.get_selected_effect()
        if eff is not None:
            for inst in self.tab.app.core.effects_engine.get_active_instances():
                if inst.effect_number == eff.number and inst.channels:
                    return list(inst.channels[:16])
        return list(range(1, 9))

    def _eval_curve_for_layer(
        self, layer: EffectLayer
    ) -> typing.Callable[[np.ndarray], float | np.ndarray] | None:
        if layer.curve_id is None:
            return None
        curve = self.tab.lightshow.curves.get_curve(layer.curve_id)
        if curve is None:
            return None
        curve_ref = curve
        return lambda p: np.array(
            [
                curve_ref.get_level(int(round(float(x) * 255.0))) / 255.0
                for x in np.asarray(p, dtype=np.float64)
            ],
            dtype=np.float64,
        )

    def do_draw(self, cr: cairo.Context) -> bool:
        """Render 1D waveform or 2D XY Pan/Tilt trajectory in Cairo."""
        alloc = self.get_allocation()
        w = float(max(200, alloc.width))
        h = float(max(180, alloc.height))

        # Background card
        cr.set_source_rgb(0.13, 0.14, 0.16)
        rounded_rectangle_fill(cr, (0.0, w, 0.0, h), 8.0)
        cr.set_source_rgb(0.28, 0.30, 0.34)
        cr.set_line_width(1.0)
        rounded_rectangle(cr, (0.5, w - 0.5, 0.5, h - 0.5), 8.0)

        eff = self.tab.get_selected_effect()
        if eff is None or not eff.layers:
            self._draw_centered_message(cr, w, h, _("No Effect Selected"))
            return False

        mode = self.effective_mode(eff)
        if mode == "2d":
            self._draw_2d_xy(cr, w, h, eff)
        else:
            self._draw_1d_wave(cr, w, h, eff)
        return False

    def _draw_centered_message(
        self, cr: cairo.Context, w: float, h: float, text: str
    ) -> None:
        cr.set_source_rgb(0.55, 0.58, 0.62)
        layout = create_pango_layout_for_widget(cr, text)
        desc = create_system_font_description()
        desc.set_size(10 * Pango.SCALE)
        layout.set_font_description(desc)
        _ink, logical = layout.get_pixel_extents()
        cr.move_to((w - logical.width) * 0.5, (h - logical.height) * 0.5)
        PangoCairo.show_layout(cr, layout)

    def _draw_1d_wave(  # pylint: disable=too-many-locals
        self, cr: cairo.Context, w: float, h: float, eff: EffectDefinition
    ) -> None:
        pad_l, pad_r, pad_t, pad_b = 34.0, 14.0, 26.0, 24.0
        plot_w = max(40.0, w - pad_l - pad_r)
        plot_h = max(40.0, h - pad_t - pad_b)
        mid_y = pad_t + plot_h * 0.5

        # Grid & axes
        cr.set_source_rgba(0.32, 0.35, 0.39, 0.6)
        cr.set_line_width(1.0)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            gx = pad_l + plot_w * frac
            cr.move_to(gx, pad_t)
            cr.line_to(gx, pad_t + plot_h)
        for fy in (0.0, 0.5, 1.0):
            gy = pad_t + plot_h * fy
            cr.move_to(pad_l, gy)
            cr.line_to(pad_l + plot_w, gy)
        cr.stroke()

        # Axis labels
        self._draw_small_text(cr, 4.0, pad_t - 5.0, "+1")
        self._draw_small_text(cr, 8.0, mid_y - 6.0, "0")
        self._draw_small_text(cr, 4.0, pad_t + plot_h - 8.0, "-1")
        self._draw_small_text(cr, pad_l, pad_t + plot_h + 4.0, "0°")
        self._draw_small_text(
            cr, pad_l + plot_w * 0.5 - 10.0, pad_t + plot_h + 4.0, "180°"
        )
        self._draw_small_text(cr, pad_l + plot_w - 22.0, pad_t + plot_h + 4.0, "360°")

        n_samples = 120
        phis = np.linspace(0.0, 1.0, n_samples, endpoint=False)
        cyc_idx = np.zeros(n_samples, dtype=np.int64)
        channels = self._get_preview_channels()
        thetas = compute_channel_phase_offsets(
            channels,
            groups=eff.groups,
            blocks=eff.blocks,
            wings=eff.wings,
            direction=eff.direction,
            phase_start_deg=eff.phase_start_deg,
            phase_end_deg=eff.phase_end_deg,
            effect_seed=int(eff.number * 10),
        )

        for l_idx, layer in enumerate(eff.layers):
            col = _LAYER_COLORS[l_idx % len(_LAYER_COLORS)]
            cr.set_source_rgb(*col)
            cr.set_line_width(2.0)

            layer_phi = np.mod(
                phis * layer.freq_mult + layer.phase_offset_deg / 360.0, 1.0
            )
            wave = evaluate_waveform(
                layer.waveform,
                layer_phi,
                mode=layer.mode,
                duty_cycle=layer.duty_cycle,
                softness=layer.softness,
                cycle_index=cyc_idx,
                channels=[1] * n_samples,
                curve_evaluator=self._eval_curve_for_layer(layer),
            )
            if layer.mode == EffectMode.ABSOLUTE:
                y_norm = 2.0 * wave - 1.0
            else:
                y_norm = np.clip(wave, -1.0, 1.0)

            for i in range(n_samples):
                px = pad_l + (i / float(n_samples - 1)) * plot_w
                py = mid_y - float(y_norm[i]) * (plot_h * 0.45)
                if i == 0:
                    cr.move_to(px, py)
                else:
                    cr.line_to(px, py)
            cr.stroke()

            # Animated channel markers along the first layer
            if l_idx == 0 and len(thetas) > 0:
                ch_phi = np.mod(
                    (self._anim_phase - thetas) * layer.freq_mult
                    + layer.phase_offset_deg / 360.0,
                    1.0,
                )
                ch_wave = evaluate_waveform(
                    layer.waveform,
                    ch_phi,
                    mode=layer.mode,
                    duty_cycle=layer.duty_cycle,
                    softness=layer.softness,
                    cycle_index=np.zeros(len(thetas), dtype=np.int64),
                    channels=channels,
                    curve_evaluator=self._eval_curve_for_layer(layer),
                )
                ch_y = (
                    2.0 * ch_wave - 1.0
                    if layer.mode == EffectMode.ABSOLUTE
                    else np.clip(ch_wave, -1.0, 1.0)
                )
                for idx_c in range(len(thetas)):
                    mx = pad_l + float(ch_phi[idx_c]) * plot_w
                    my = mid_y - float(ch_y[idx_c]) * (plot_h * 0.45)
                    cr.new_sub_path()
                    cr.arc(mx, my, 4.0, 0.0, 2.0 * math.pi)
                    cr.set_source_rgb(1.0, 1.0, 1.0)
                    cr.fill_preserve()
                    cr.set_source_rgb(*col)
                    cr.set_line_width(1.5)
                    cr.stroke()

        self._draw_small_text(
            cr,
            pad_l,
            6.0,
            f"1D Wave — {len(channels)} ch "
            f"(G:{eff.groups} B:{eff.blocks} W:{eff.wings})",
        )

    def _draw_2d_xy(  # pylint: disable=too-many-locals
        self, cr: cairo.Context, w: float, h: float, eff: EffectDefinition
    ) -> None:
        pad = 24.0
        avail = max(60.0, min(w - 2 * pad, h - 2 * pad - 12.0))
        cx = w * 0.5
        cy = (h + 12.0) * 0.5
        radius = avail * 0.44

        # Crosshair & reference circle
        cr.set_source_rgba(0.32, 0.35, 0.39, 0.6)
        cr.set_line_width(1.0)
        cr.move_to(cx - radius, cy)
        cr.line_to(cx + radius, cy)
        cr.move_to(cx, cy - radius)
        cr.line_to(cx, cy + radius)
        cr.stroke()

        cr.new_sub_path()
        cr.arc(cx, cy, radius, 0.0, 2.0 * math.pi)
        cr.stroke()

        pan_layer = next(
            (ly for ly in eff.layers if ly.parameter == "pan"), eff.layers[0]
        )
        tilt_layer = next(
            (ly for ly in eff.layers if ly.parameter == "tilt"), eff.layers[-1]
        )

        n_samples = 160
        phis = np.linspace(0.0, 1.0, n_samples, endpoint=True)
        cyc = np.zeros(n_samples, dtype=np.int64)
        p_phi = np.mod(
            phis * pan_layer.freq_mult + pan_layer.phase_offset_deg / 360.0, 1.0
        )
        t_phi = np.mod(
            phis * tilt_layer.freq_mult + tilt_layer.phase_offset_deg / 360.0, 1.0
        )
        u_raw = evaluate_waveform(
            pan_layer.waveform,
            p_phi,
            mode=EffectMode.RELATIVE,
            duty_cycle=pan_layer.duty_cycle,
            softness=pan_layer.softness,
            cycle_index=cyc,
            channels=[1] * n_samples,
            curve_evaluator=self._eval_curve_for_layer(pan_layer),
        )
        v_raw = evaluate_waveform(
            tilt_layer.waveform,
            t_phi,
            mode=EffectMode.RELATIVE,
            duty_cycle=tilt_layer.duty_cycle,
            softness=tilt_layer.softness,
            cycle_index=cyc,
            channels=[1] * n_samples,
            curve_evaluator=self._eval_curve_for_layer(tilt_layer),
        )

        max_sz = max(1.0, float(pan_layer.size), float(tilt_layer.size))
        u = u_raw * (float(pan_layer.size) / max_sz)
        v = v_raw * (float(tilt_layer.size) / max_sz)

        axis_rad = math.radians(float(eff.axis_deg))
        cos_a, sin_a = math.cos(axis_rad), math.sin(axis_rad)
        rx = u * cos_a - v * sin_a
        ry = u * sin_a + v * cos_a

        cr.set_source_rgb(0.85, 0.35, 0.95)
        cr.set_line_width(2.0)
        for i in range(n_samples):
            px = cx + float(rx[i]) * radius
            py = cy - float(ry[i]) * radius
            if i == 0:
                cr.move_to(px, py)
            else:
                cr.line_to(px, py)
        cr.stroke()

        # Animated fixture markers along the 2D trajectory
        channels = self._get_preview_channels()
        thetas = compute_channel_phase_offsets(
            channels,
            groups=eff.groups,
            blocks=eff.blocks,
            wings=eff.wings,
            direction=eff.direction,
            phase_start_deg=eff.phase_start_deg,
            phase_end_deg=eff.phase_end_deg,
            effect_seed=int(eff.number * 10),
        )
        if len(thetas) > 0:
            cp_phi = np.mod(
                (self._anim_phase - thetas) * pan_layer.freq_mult
                + pan_layer.phase_offset_deg / 360.0,
                1.0,
            )
            ct_phi = np.mod(
                (self._anim_phase - thetas) * tilt_layer.freq_mult
                + tilt_layer.phase_offset_deg / 360.0,
                1.0,
            )
            cu = evaluate_waveform(
                pan_layer.waveform,
                cp_phi,
                mode=EffectMode.RELATIVE,
                duty_cycle=pan_layer.duty_cycle,
                softness=pan_layer.softness,
                cycle_index=np.zeros(len(thetas), dtype=np.int64),
                channels=channels,
                curve_evaluator=self._eval_curve_for_layer(pan_layer),
            ) * (float(pan_layer.size) / max_sz)
            cv = evaluate_waveform(
                tilt_layer.waveform,
                ct_phi,
                mode=EffectMode.RELATIVE,
                duty_cycle=tilt_layer.duty_cycle,
                softness=tilt_layer.softness,
                cycle_index=np.zeros(len(thetas), dtype=np.int64),
                channels=channels,
                curve_evaluator=self._eval_curve_for_layer(tilt_layer),
            ) * (float(tilt_layer.size) / max_sz)

            crx = cu * cos_a - cv * sin_a
            cry = cu * sin_a + cv * cos_a
            for idx_c in range(len(thetas)):
                mx = cx + float(crx[idx_c]) * radius
                my = cy - float(cry[idx_c]) * radius
                cr.new_sub_path()
                cr.arc(mx, my, 4.5, 0.0, 2.0 * math.pi)
                cr.set_source_rgb(0.25, 0.90, 0.98)
                cr.fill_preserve()
                cr.set_source_rgb(1.0, 1.0, 1.0)
                cr.set_line_width(1.2)
                cr.stroke()

        self._draw_small_text(
            cr,
            10.0,
            6.0,
            f"2D Pan/Tilt XY — Axis {eff.axis_deg:.0f}° ({len(channels)} ch)",
        )

    @staticmethod
    def _draw_small_text(cr: cairo.Context, x: float, y: float, text: str) -> None:
        cr.set_source_rgb(0.65, 0.68, 0.72)
        layout = create_pango_layout_for_widget(cr, text)
        desc = create_system_font_description()
        desc.set_size(8 * Pango.SCALE)
        layout.set_font_description(desc)
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class EffectsTab(Gtk.Box):
    """GTK3 Effects pool, multi-layer parametric editor, and 1D/2D visualizer."""

    app: Application
    lightshow: LightShow
    tabs: Tabs | None

    def __init__(self, app: Application) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.app = app
        self.lightshow = app.core.lightshow
        self.tabs = app.tabs
        self.selected_number: float | None = None
        self._updating_ui = False
        self._anim_timer_id: int | None = None

        self.set_border_width(4)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_position(195)

        # 1. Left Pane: Compact Effect Pool & Template selector
        left_box = self._build_left_pool_panel()
        self.paned.pack1(left_box, resize=False, shrink=False)

        # 2. Right Pane: Properties + Visualizer (top) and Layers Table (bottom)
        right_box = self._build_center_editor_panel()
        self.paned.pack2(right_box, resize=True, shrink=False)

        self.pack_start(self.paned, True, True, 0)

        self.refresh()
        self._start_preview_timer()
        self.connect("destroy", self._on_destroy)
        self.show_all()

    def _start_preview_timer(self) -> None:
        if self._anim_timer_id is None:
            self._anim_timer_id = GLib.timeout_add(40, self._on_anim_tick)

    def _on_anim_tick(self) -> bool:
        if not self.get_mapped():
            return True
        self.preview_area.step_animation()
        return True

    def _on_destroy(self, *_args: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Stop animation timer on tab closure."""
        if self._anim_timer_id is not None:
            GLib.source_remove(self._anim_timer_id)
            self._anim_timer_id = None

    # --- UI Construction ---

    def _build_left_pool_panel(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_size_request(185, -1)
        box.set_margin_end(4)

        # Top row: + New / Delete
        top_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_new = Gtk.Button(label=_("+ New"))
        self.btn_new.connect("clicked", lambda *_: self.create_effect())
        top_btns.pack_start(self.btn_new, True, True, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.connect("clicked", lambda *_: self.delete_selected_effect())
        top_btns.pack_start(self.btn_delete, False, False, 0)
        box.pack_start(top_btns, False, False, 0)

        # Template creation row
        tpl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.template_combo = Gtk.ComboBoxText()
        for spec in BUILTIN_EFFECT_TEMPLATES.values():
            self.template_combo.append(spec.template_id, spec.default_label)
        self.template_combo.set_active(0)
        tpl_row.pack_start(self.template_combo, True, True, 0)

        self.btn_new_template = Gtk.Button(label=_("+ Tpl"))
        self.btn_new_template.set_tooltip_text(
            _("Create effect from selected template")
        )
        self.btn_new_template.connect(
            "clicked", lambda *_: self.create_effect_from_selected_template()
        )
        tpl_row.pack_start(self.btn_new_template, False, False, 0)
        box.pack_start(tpl_row, False, False, 0)

        # Effect pool TreeView (Num | Label | Cycle / BPM | Layers | Running)
        self.pool_store = Gtk.ListStore(float, str, str, str, int, str)
        self.pool_tree = Gtk.TreeView(model=self.pool_store)
        self.pool_tree.set_headers_visible(True)
        self.pool_tree.connect("row-activated", self._on_pool_row_activated)

        for idx, (title, min_w) in enumerate(
            (("#", 32), (_("Label"), 76), (_("Rate"), 50), (_("Run"), 34)), start=1
        ):
            col_idx = idx if idx < 4 else 5
            r = Gtk.CellRendererText()
            if idx == 1:
                r.set_property("weight", Pango.Weight.BOLD)
            elif idx == 2:
                r.set_property("ellipsize", Pango.EllipsizeMode.END)
            col = Gtk.TreeViewColumn(title, r)
            col.add_attribute(r, "text", col_idx)
            col.set_min_width(min_w)
            col.set_resizable(True)
            if idx == 2:
                col.set_expand(True)
            self.pool_tree.append_column(col)

        sel = self.pool_tree.get_selection()
        sel.set_mode(Gtk.SelectionMode.SINGLE)
        sel.connect("changed", self._on_pool_selection_changed)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.pool_tree)
        box.pack_start(scrolled, True, True, 0)

        # Apply / Stop buttons
        act_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_apply = Gtk.Button(label=_("Apply"))
        self.btn_apply.set_tooltip_text(_("Apply effect to selected channels"))
        self.btn_apply.connect("clicked", lambda *_: self.apply_selected_effect())
        act_btns.pack_start(self.btn_apply, True, True, 0)

        self.btn_stop = Gtk.Button(label=_("Stop"))
        self.btn_stop.set_tooltip_text(_("Stop selected effect"))
        self.btn_stop.connect("clicked", lambda *_: self.stop_selected_effect())
        act_btns.pack_start(self.btn_stop, False, False, 0)

        self.btn_stop_all = Gtk.Button(label=_("All Off"))
        self.btn_stop_all.set_tooltip_text(_("Stop all running effects"))
        self.btn_stop_all.connect("clicked", lambda *_: self.stop_all_effects())
        act_btns.pack_start(self.btn_stop_all, False, False, 0)
        box.pack_start(act_btns, False, False, 0)

        return box

    def _build_center_editor_panel(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(4)

        # Top split: Compact Global Properties (left) + Real-time Visualizer (right)
        top_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Compact 4-column properties grid
        grid = Gtk.Grid()
        grid.set_column_spacing(6)
        grid.set_row_spacing(4)

        # Row 0: Label
        grid.attach(Gtk.Label(label=_("Label:"), halign=Gtk.Align.END), 0, 0, 1, 1)
        self.label_entry = Gtk.Entry()
        self.label_entry.set_width_chars(12)
        self.label_entry.set_hexpand(True)
        self.label_entry.connect("activate", self._on_label_entry_changed)
        self.label_entry.connect("focus-out-event", self._on_label_focus_out)
        grid.attach(self.label_entry, 1, 0, 2, 1)

        self.btn_tap_tempo = Gtk.Button(label=_("Tap Tempo"))
        self.btn_tap_tempo.connect("clicked", lambda *_: self.tap_tempo())
        grid.attach(self.btn_tap_tempo, 3, 0, 1, 1)

        # Row 1: Cycle (s) & BPM
        grid.attach(Gtk.Label(label=_("Cycle (s):"), halign=Gtk.Align.END), 0, 1, 1, 1)
        self.cycle_spin = Gtk.SpinButton.new_with_range(0.05, 120.0, 0.1)
        self.cycle_spin.set_digits(2)
        self.cycle_spin.set_width_chars(5)
        self.cycle_spin.connect("value-changed", self._on_cycle_changed)
        grid.attach(self.cycle_spin, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("BPM:"), halign=Gtk.Align.END), 2, 1, 1, 1)
        self.bpm_spin = Gtk.SpinButton.new_with_range(1.0, 600.0, 1.0)
        self.bpm_spin.set_digits(1)
        self.bpm_spin.set_width_chars(5)
        self.bpm_spin.connect("value-changed", self._on_bpm_changed)
        grid.attach(self.bpm_spin, 3, 1, 1, 1)

        # Row 2: Direction & Groups
        grid.attach(Gtk.Label(label=_("Dir:"), halign=Gtk.Align.END), 0, 2, 1, 1)
        self.direction_combo = Gtk.ComboBoxText()
        for d_name in DIRECTION_NAMES:
            self.direction_combo.append(d_name, d_name.capitalize())
        self.direction_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.direction_combo, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Groups:"), halign=Gtk.Align.END), 2, 2, 1, 1)
        self.groups_spin = Gtk.SpinButton.new_with_range(0, 512, 1)
        self.groups_spin.set_width_chars(4)
        self.groups_spin.set_tooltip_text(
            _("0 = Full Spread, 1 = Unison, k = Grouping")
        )
        self.groups_spin.connect("value-changed", self._on_global_prop_changed)
        grid.attach(self.groups_spin, 3, 2, 1, 1)

        # Row 3: Blocks & Wings
        grid.attach(Gtk.Label(label=_("Blocks:"), halign=Gtk.Align.END), 0, 3, 1, 1)
        self.blocks_spin = Gtk.SpinButton.new_with_range(1, 128, 1)
        self.blocks_spin.set_width_chars(4)
        self.blocks_spin.connect("value-changed", self._on_global_prop_changed)
        grid.attach(self.blocks_spin, 1, 3, 1, 1)

        grid.attach(Gtk.Label(label=_("Wings:"), halign=Gtk.Align.END), 2, 3, 1, 1)
        self.wings_spin = Gtk.SpinButton.new_with_range(1, 32, 1)
        self.wings_spin.set_width_chars(4)
        self.wings_spin.connect("value-changed", self._on_global_prop_changed)
        grid.attach(self.wings_spin, 3, 3, 1, 1)

        # Row 4: Axis (°), Phase Start / End
        grid.attach(Gtk.Label(label=_("Axis°:"), halign=Gtk.Align.END), 0, 4, 1, 1)
        self.axis_spin = Gtk.SpinButton.new_with_range(-180.0, 180.0, 5.0)
        self.axis_spin.set_digits(0)
        self.axis_spin.set_width_chars(4)
        self.axis_spin.connect("value-changed", self._on_global_prop_changed)
        grid.attach(self.axis_spin, 1, 4, 1, 1)

        grid.attach(Gtk.Label(label=_("Spread°:"), halign=Gtk.Align.END), 2, 4, 1, 1)
        spread_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.phase_start_spin = Gtk.SpinButton.new_with_range(0.0, 720.0, 15.0)
        self.phase_start_spin.set_digits(0)
        self.phase_start_spin.set_width_chars(3)
        self.phase_start_spin.set_tooltip_text(_("Phase Start (°)"))
        self.phase_start_spin.connect("value-changed", self._on_global_prop_changed)
        spread_box.pack_start(self.phase_start_spin, False, False, 0)

        self.phase_end_spin = Gtk.SpinButton.new_with_range(0.0, 720.0, 15.0)
        self.phase_end_spin.set_digits(0)
        self.phase_end_spin.set_width_chars(4)
        self.phase_end_spin.set_tooltip_text(_("Phase End (°)"))
        self.phase_end_spin.connect("value-changed", self._on_global_prop_changed)
        spread_box.pack_start(self.phase_end_spin, False, False, 0)
        grid.attach(spread_box, 3, 4, 1, 1)

        # Row 5: Speed Bus & Multiplier
        grid.attach(Gtk.Label(label=_("Speed Bus:"), halign=Gtk.Align.END), 0, 5, 1, 1)
        self.speed_master_combo = Gtk.ComboBoxText()
        self.speed_master_combo.append("none", _("None"))
        for idx in range(1, 9):
            self.speed_master_combo.append(str(idx), f"Speed {idx}")
        self.speed_master_combo.set_active_id("none")
        self.speed_master_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.speed_master_combo, 1, 5, 1, 1)

        grid.attach(Gtk.Label(label=_("Mult:"), halign=Gtk.Align.END), 2, 5, 1, 1)
        self.speed_mult_combo = Gtk.ComboBoxText()
        for mult_str in ("0.25", "0.5", "1.0", "2.0", "4.0"):
            self.speed_mult_combo.append(mult_str, f"×{mult_str}")
        self.speed_mult_combo.set_active_id("1.0")
        self.speed_mult_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.speed_mult_combo, 3, 5, 1, 1)

        # Row 6: Rate Bus & Size Bus
        grid.attach(Gtk.Label(label=_("Rate Bus:"), halign=Gtk.Align.END), 0, 6, 1, 1)
        self.rate_master_combo = Gtk.ComboBoxText()
        self.rate_master_combo.append("none", _("None"))
        for idx in range(1, 5):
            self.rate_master_combo.append(str(idx), f"Rate {idx}")
        self.rate_master_combo.set_active_id("none")
        self.rate_master_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.rate_master_combo, 1, 6, 1, 1)

        grid.attach(Gtk.Label(label=_("Size Bus:"), halign=Gtk.Align.END), 2, 6, 1, 1)
        self.size_master_combo = Gtk.ComboBoxText()
        self.size_master_combo.append("none", _("None"))
        for idx in range(1, 5):
            self.size_master_combo.append(str(idx), f"Size {idx}")
        self.size_master_combo.set_active_id("none")
        self.size_master_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.size_master_combo, 3, 6, 1, 1)

        # Row 7: Entry & Exit Modes
        grid.attach(Gtk.Label(label=_("Entry:"), halign=Gtk.Align.END), 0, 7, 1, 1)
        self.entry_mode_combo = Gtk.ComboBoxText()
        for mode_id, mode_label in ENVELOPE_MODE_LABELS:
            self.entry_mode_combo.append(mode_id, _(mode_label))
        self.entry_mode_combo.set_active_id(EffectEnvelopeMode.FADE_BY_SIZE.value)
        self.entry_mode_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.entry_mode_combo, 1, 7, 1, 1)

        grid.attach(Gtk.Label(label=_("Exit:"), halign=Gtk.Align.END), 2, 7, 1, 1)
        self.exit_mode_combo = Gtk.ComboBoxText()
        for mode_id, mode_label in ENVELOPE_MODE_LABELS:
            self.exit_mode_combo.append(mode_id, _(mode_label))
        self.exit_mode_combo.set_active_id(EffectEnvelopeMode.FADE_BY_SIZE.value)
        self.exit_mode_combo.connect("changed", self._on_global_prop_changed)
        grid.attach(self.exit_mode_combo, 3, 7, 1, 1)

        # Row 8: Global Trail (%)
        grid.attach(Gtk.Label(label=_("Trail (%):"), halign=Gtk.Align.END), 0, 8, 1, 1)
        self.trail_spin = Gtk.SpinButton.new_with_range(1.0, 100.0, 5.0)
        self.trail_spin.set_digits(0)
        self.trail_spin.set_width_chars(4)
        self.trail_spin.set_tooltip_text(
            _(
                "Syncs Duty% across all layers "
                "(use the Duty% column for per-layer control)"
            )
        )
        self.trail_spin.connect("value-changed", self._on_trail_changed)
        grid.attach(self.trail_spin, 1, 8, 1, 1)

        top_hbox.pack_start(grid, False, False, 0)

        # Visualizer alongside properties
        preview_box = self._build_right_preview_panel()
        top_hbox.pack_start(preview_box, True, True, 0)

        box.pack_start(top_hbox, False, False, 0)

        # Layers toolbar
        layer_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_layers = Gtk.Label(label=_("Effect Layers"))
        lbl_layers.set_halign(Gtk.Align.START)
        layer_bar.pack_start(lbl_layers, True, True, 0)

        self.btn_add_layer = Gtk.Button(label=_("+ Add Layer"))
        self.btn_add_layer.connect("clicked", lambda *_: self.add_layer())
        layer_bar.pack_start(self.btn_add_layer, False, False, 0)

        self.btn_remove_layer = Gtk.Button(label=_("- Remove Layer"))
        self.btn_remove_layer.connect(
            "clicked", lambda *_: self.remove_selected_layer()
        )
        layer_bar.pack_start(self.btn_remove_layer, False, False, 0)
        box.pack_start(layer_bar, False, False, 0)

        # Layers TreeView (fills bottom width)
        self.layer_store = Gtk.ListStore(
            int, str, str, str, float, float, float, float, float, str, str, int
        )
        self.layer_tree = Gtk.TreeView(model=self.layer_store)
        self.layer_tree.set_headers_visible(True)
        self._build_layer_columns()

        layer_scroll = Gtk.ScrolledWindow()
        layer_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        layer_scroll.add(self.layer_tree)
        box.pack_start(layer_scroll, True, True, 0)

        return box

    def _build_layer_columns(self) -> None:
        # 1. Parameter combo column
        param_model = Gtk.ListStore(str)
        for p in EFFECT_PARAMETERS:
            param_model.append([p])
        r_param = Gtk.CellRendererCombo()
        r_param.set_property("editable", True)
        r_param.set_property("model", param_model)
        r_param.set_property("text-column", 0)
        r_param.set_property("has-entry", False)
        r_param.connect("edited", self._on_layer_combo_edited, "parameter")
        col_p = Gtk.TreeViewColumn(_("Param"), r_param)
        col_p.add_attribute(r_param, "text", 1)
        col_p.set_min_width(58)
        col_p.set_resizable(True)
        self.layer_tree.append_column(col_p)

        # 2. Mode combo column
        mode_model = Gtk.ListStore(str)
        for m in MODE_NAMES:
            mode_model.append([m])
        r_mode = Gtk.CellRendererCombo()
        r_mode.set_property("editable", True)
        r_mode.set_property("model", mode_model)
        r_mode.set_property("text-column", 0)
        r_mode.set_property("has-entry", False)
        r_mode.connect("edited", self._on_layer_combo_edited, "mode")
        col_m = Gtk.TreeViewColumn(_("Mode"), r_mode)
        col_m.add_attribute(r_mode, "text", 2)
        col_m.set_min_width(56)
        col_m.set_resizable(True)
        self.layer_tree.append_column(col_m)

        # 3. Waveform combo column
        wave_model = Gtk.ListStore(str)
        for w in WAVEFORM_NAMES:
            wave_model.append([w])
        r_wave = Gtk.CellRendererCombo()
        r_wave.set_property("editable", True)
        r_wave.set_property("model", wave_model)
        r_wave.set_property("text-column", 0)
        r_wave.set_property("has-entry", False)
        r_wave.connect("edited", self._on_layer_combo_edited, "waveform")
        col_w = Gtk.TreeViewColumn(_("Wave"), r_wave)
        col_w.add_attribute(r_wave, "text", 3)
        col_w.set_min_width(60)
        col_w.set_resizable(True)
        self.layer_tree.append_column(col_w)

        # 4. Numeric columns: Size, Phase (°), Freq x, Duty %, Soft %
        num_specs = (
            (_("Size"), 4, "size", "{:.1f}"),
            (_("Ph°"), 5, "phase_offset_deg", "{:.0f}"),
            (_("Freq"), 6, "freq_mult", "{:.2f}"),
            (_("Duty%"), 7, "duty_cycle", "{:.0f}"),
            (_("Soft%"), 8, "softness", "{:.0f}"),
        )
        for title, col_idx, field_name, fmt in num_specs:
            r_num = Gtk.CellRendererText()
            r_num.set_property("editable", True)
            r_num.connect("edited", self._on_layer_number_edited, field_name)
            col = Gtk.TreeViewColumn(title, r_num)
            col.set_min_width(42)
            col.set_resizable(True)
            col.set_cell_data_func(
                r_num,
                self._format_float_cell,
                (col_idx, fmt),
            )
            self.layer_tree.append_column(col)

        # 5. Low Palette / High Palette text columns
        for title, col_idx, field_name in (
            (_("Low"), 9, "low_palette"),
            (_("High"), 10, "high_palette"),
        ):
            r_pal = Gtk.CellRendererText()
            r_pal.set_property("editable", True)
            r_pal.connect("edited", self._on_layer_palette_edited, field_name)
            col = Gtk.TreeViewColumn(title, r_pal)
            col.add_attribute(r_pal, "text", col_idx)
            col.set_min_width(48)
            col.set_resizable(True)
            self.layer_tree.append_column(col)

    @staticmethod
    def _format_float_cell(
        _col: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        tree_iter: Gtk.TreeIter,
        data: tuple[int, str],
    ) -> None:
        col_idx, fmt = data
        val = float(model[tree_iter][col_idx])
        cell.set_property("text", fmt.format(val))

    def _build_right_preview_panel(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_size_request(160, 185)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl = Gtk.Label(label=_("Visualizer:"))
        top.pack_start(lbl, False, False, 0)

        self.preview_mode_combo = Gtk.ComboBoxText()
        self.preview_mode_combo.append("auto", _("Auto (1D / 2D)"))
        self.preview_mode_combo.append("1d", _("1D Waveform"))
        self.preview_mode_combo.append("2d", _("2D Pan/Tilt XY"))
        self.preview_mode_combo.set_active_id("auto")
        self.preview_mode_combo.connect("changed", self._on_preview_mode_changed)
        top.pack_start(self.preview_mode_combo, True, True, 0)
        box.pack_start(top, False, False, 0)

        self.preview_area = EffectPreviewArea(self)
        box.pack_start(self.preview_area, True, True, 0)
        return box

    # --- State & Actions ---

    def get_selected_effect(self) -> EffectDefinition | None:
        """Return currently selected EffectDefinition or None."""
        if self.selected_number is None:
            return None
        return self.lightshow.effects.get(self.selected_number)

    def select_effect(self, number: float | None) -> None:
        """Select effect *number* in the pool TreeView."""
        self.selected_number = round(float(number), 3) if number is not None else None
        self._sync_pool_selection()
        self._populate_editor_from_selected()

    def refresh(self) -> None:
        """Rebuild Effect pool list and refresh editor widgets."""
        self.lightshow = self.app.core.lightshow
        self._updating_ui = True
        try:
            self.pool_store.clear()
            active_nums = {
                inst.effect_number
                for inst in self.app.core.effects_engine.get_active_instances()
                if not inst.remove_on_fade_end
            }
            all_effects = self.lightshow.effects.all()
            if self.selected_number is None and all_effects:
                self.selected_number = all_effects[0].number
            elif (
                self.selected_number is not None
                and self.lightshow.effects.get(self.selected_number) is None
            ):
                self.selected_number = all_effects[0].number if all_effects else None

            for eff in all_effects:
                num_str = format_effect_number(eff.number)
                rate_str = (
                    f"{eff.bpm:.0f} BPM"
                    if eff.bpm is not None
                    else f"{eff.cycle_time:.1f}s"
                )
                status_str = "RUN" if eff.number in active_nums else ""
                self.pool_store.append(
                    [
                        float(eff.number),
                        num_str,
                        eff.label,
                        rate_str,
                        len(eff.layers),
                        status_str,
                    ]
                )
        finally:
            self._updating_ui = False

        self._sync_pool_selection()
        self._populate_editor_from_selected()

    def _sync_pool_selection(self) -> None:
        self._updating_ui = True
        try:
            sel = self.pool_tree.get_selection()
            sel.unselect_all()
            if self.selected_number is None:
                return
            tree_iter = self.pool_store.get_iter_first()
            while tree_iter is not None:
                if float(self.pool_store[tree_iter][0]) == float(self.selected_number):
                    sel.select_iter(tree_iter)
                    break
                tree_iter = self.pool_store.iter_next(tree_iter)
        finally:
            self._updating_ui = False

    def _populate_editor_from_selected(self) -> None:
        eff = self.get_selected_effect()
        has_eff = eff is not None
        for widget in (
            self.btn_delete,
            self.btn_apply,
            self.btn_stop,
            self.label_entry,
            self.cycle_spin,
            self.bpm_spin,
            self.btn_tap_tempo,
            self.direction_combo,
            self.groups_spin,
            self.blocks_spin,
            self.wings_spin,
            self.axis_spin,
            self.phase_start_spin,
            self.phase_end_spin,
            self.speed_master_combo,
            self.speed_mult_combo,
            self.rate_master_combo,
            self.size_master_combo,
            self.entry_mode_combo,
            self.exit_mode_combo,
            self.btn_add_layer,
            self.btn_remove_layer,
            self.layer_tree,
        ):
            widget.set_sensitive(has_eff)
        self.trail_spin.set_sensitive(has_eff and eff is not None and bool(eff.layers))

        self._updating_ui = True
        try:
            self.layer_store.clear()
            if eff is None:
                self.label_entry.set_text("")
                self.preview_area.queue_draw()
                return

            self.label_entry.set_text(eff.label)
            self.cycle_spin.set_value(float(eff.cycle_time))
            bpm_val = (
                float(eff.bpm)
                if eff.bpm is not None
                else 60.0 / max(0.05, float(eff.cycle_time))
            )
            self.bpm_spin.set_value(bpm_val)
            self.direction_combo.set_active_id(eff.direction.value)
            self.groups_spin.set_value(float(eff.groups))
            self.blocks_spin.set_value(float(eff.blocks))
            self.wings_spin.set_value(float(eff.wings))
            self.axis_spin.set_value(float(eff.axis_deg))
            self.phase_start_spin.set_value(float(eff.phase_start_deg))
            self.phase_end_spin.set_value(float(eff.phase_end_deg))
            self.speed_master_combo.set_active_id(
                str(eff.speed_master) if eff.speed_master is not None else "none"
            )
            mult_key = f"{float(eff.speed_multiplier):g}"
            if mult_key == "1":
                mult_key = "1.0"
            elif mult_key == "2":
                mult_key = "2.0"
            elif mult_key == "4":
                mult_key = "4.0"
            self.speed_mult_combo.set_active_id(mult_key)
            if self.speed_mult_combo.get_active_id() is None:
                self.speed_mult_combo.set_active_id("1.0")
            self.rate_master_combo.set_active_id(
                str(eff.rate_master) if eff.rate_master is not None else "none"
            )
            self.size_master_combo.set_active_id(
                str(eff.size_master) if eff.size_master is not None else "none"
            )
            self.entry_mode_combo.set_active_id(eff.entry_mode.value)
            self.exit_mode_combo.set_active_id(eff.exit_mode.value)
            if eff.layers:
                self.trail_spin.set_value(
                    round(float(eff.layers[0].duty_cycle) * 100.0)
                )

            for idx, layer in enumerate(eff.layers):
                self.layer_store.append(
                    [
                        idx,
                        layer.parameter,
                        layer.mode.value,
                        layer.waveform.value,
                        float(layer.size),
                        float(layer.phase_offset_deg),
                        float(layer.freq_mult),
                        float(layer.duty_cycle * 100.0),
                        float(layer.softness * 100.0),
                        _format_palette_ref_str(layer.low_palette),
                        _format_palette_ref_str(layer.high_palette),
                        int(layer.curve_id or 0),
                    ]
                )
        finally:
            self._updating_ui = False
        self.preview_area.queue_draw()

    # --- User Actions ---

    def _resolve_requested_effect_number(self, number: float | None = None) -> float:
        if number is not None:
            return round(float(number), 3)
        raw = self.app.core.commandline.get_string().strip()
        if raw and is_non_nul_float(raw):
            self.app.core.action_registry.execute("commandline.clear")
            return round(float(raw), 3)
        return self.lightshow.effects.next_available_number()

    def create_effect(
        self,
        number: float | None = None,
        *,
        template_id: str | None = None,
        label: str = "",
    ) -> EffectDefinition:
        """Create a new effect (blank or from template) via ActionRegistry."""
        target_num = self._resolve_requested_effect_number(number)
        kwargs: dict[str, Any] = {}
        if template_id is None:
            kwargs["layers"] = [EffectLayer(parameter="intensity", size=50.0)]
        eff = self.app.core.action_registry.execute(
            "effect.create",
            target_num,
            label=label,
            template_id=template_id,
            **kwargs,
        )
        self.selected_number = target_num
        self.refresh()
        return typing.cast(EffectDefinition, eff)

    def create_effect_from_selected_template(
        self, number: float | None = None
    ) -> EffectDefinition:
        """Instantiate the template selected in template_combo."""
        tpl_id = self.template_combo.get_active_id() or "sine_dimmer"
        return self.create_effect(number, template_id=tpl_id)

    def delete_selected_effect(self) -> None:
        """Delete the currently selected effect."""
        eff = self.get_selected_effect()
        if eff is None:
            return
        num = eff.number
        self.app.core.action_registry.execute("effect.delete", num)
        self.refresh()

    def apply_selected_effect(self, channels: list[int] | None = None) -> None:
        """Apply the currently selected effect to active channel selection."""
        eff = self.get_selected_effect()
        if eff is None:
            return
        self.app.core.action_registry.execute(
            "effect.apply", eff.number, channels=channels
        )
        self.refresh()

    def stop_selected_effect(self) -> None:
        """Stop the currently selected effect."""
        eff = self.get_selected_effect()
        if eff is None:
            return
        self.app.core.action_registry.execute("effect.stop", number=eff.number)
        self.refresh()

    def stop_all_effects(self) -> None:
        """Stop all running effects."""
        self.app.core.action_registry.execute("effect.stop")
        self.refresh()

    def tap_tempo(self, now: float | None = None) -> float | None:
        """Trigger tap tempo on the selected effect."""
        eff = self.get_selected_effect()
        num = eff.number if eff is not None else None
        res = self.app.core.action_registry.execute("effect.tap_tempo", num, now=now)
        self._populate_editor_from_selected()
        return typing.cast("float | None", res)

    def add_layer(self, parameter: str = "intensity") -> None:
        """Append a new EffectLayer to the selected EffectDefinition."""
        eff = self.get_selected_effect()
        if eff is None:
            return
        layers_copy = [copy.deepcopy(ly) for ly in eff.layers]
        layers_copy.append(EffectLayer(parameter=parameter, size=25.0))
        self.app.core.action_registry.execute(
            "effect.update", eff.number, layers=layers_copy
        )
        self._populate_editor_from_selected()

    def remove_selected_layer(self) -> None:
        """Remove the selected EffectLayer (or last layer if none selected)."""
        eff = self.get_selected_effect()
        if eff is None or not eff.layers:
            return
        model, tree_iter = self.layer_tree.get_selection().get_selected()
        if tree_iter is not None:
            idx = int(model[tree_iter][0])
        else:
            idx = len(eff.layers) - 1
        if 0 <= idx < len(eff.layers):
            layers_copy = [
                copy.deepcopy(ly) for i, ly in enumerate(eff.layers) if i != idx
            ]
            self.app.core.action_registry.execute(
                "effect.update", eff.number, layers=layers_copy
            )
            self._populate_editor_from_selected()

    # --- Signal Callbacks ---

    def _on_pool_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        if self._updating_ui:
            return
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            self.selected_number = float(model[tree_iter][0])
        else:
            self.selected_number = None
        self._populate_editor_from_selected()

    def _on_pool_row_activated(
        self,
        _tree: Gtk.TreeView,
        _path: Gtk.TreePath,
        _col: Gtk.TreeViewColumn,
    ) -> None:
        self.apply_selected_effect()

    def _on_label_entry_changed(self, entry: Gtk.Entry) -> None:
        if self._updating_ui:
            return
        eff = self.get_selected_effect()
        if eff is None:
            return
        new_lbl = entry.get_text().strip()
        if new_lbl != eff.label:
            self.app.core.action_registry.execute("effect.rename", eff.number, new_lbl)
            self.refresh()

    def _on_label_focus_out(self, entry: Gtk.Entry, _event: Gdk.Event) -> bool:
        self._on_label_entry_changed(entry)
        return False

    def _on_cycle_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating_ui:
            return
        eff = self.get_selected_effect()
        if eff is None:
            return
        val = float(spin.get_value())
        if abs(val - eff.cycle_time) > 1e-4:
            self.app.core.action_registry.execute(
                "effect.update", eff.number, cycle_time=val, bpm=None
            )
            self.refresh()

    def _on_bpm_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating_ui:
            return
        eff = self.get_selected_effect()
        if eff is None:
            return
        val = float(spin.get_value())
        if eff.bpm is None or abs(val - eff.bpm) > 1e-3:
            self.app.core.action_registry.execute("effect.update", eff.number, bpm=val)
            self.refresh()

    def _on_global_prop_changed(self, *_args: object) -> None:
        if self._updating_ui:
            return
        eff = self.get_selected_effect()
        if eff is None:
            return
        dir_id = (
            self.direction_combo.get_active_id() or DistributeDirection.FORWARD.value
        )
        sm_id = self.speed_master_combo.get_active_id() or "none"
        rm_id = self.rate_master_combo.get_active_id() or "none"
        sz_id = self.size_master_combo.get_active_id() or "none"
        mult_str = self.speed_mult_combo.get_active_id() or "1.0"
        entry_id = (
            self.entry_mode_combo.get_active_id()
            or EffectEnvelopeMode.FADE_BY_SIZE.value
        )
        exit_id = (
            self.exit_mode_combo.get_active_id()
            or EffectEnvelopeMode.FADE_BY_SIZE.value
        )
        self.app.core.action_registry.execute(
            "effect.update",
            eff.number,
            direction=DistributeDirection(dir_id),
            entry_mode=EffectEnvelopeMode(entry_id),
            exit_mode=EffectEnvelopeMode(exit_id),
            groups=int(self.groups_spin.get_value_as_int()),
            blocks=int(self.blocks_spin.get_value_as_int()),
            wings=int(self.wings_spin.get_value_as_int()),
            axis_deg=float(self.axis_spin.get_value()),
            phase_start_deg=float(self.phase_start_spin.get_value()),
            phase_end_deg=float(self.phase_end_spin.get_value()),
            speed_master=int(sm_id) if sm_id != "none" else None,
            speed_multiplier=float(mult_str),
            rate_master=int(rm_id) if rm_id != "none" else None,
            size_master=int(sz_id) if sz_id != "none" else None,
        )
        self.preview_area.queue_draw()

    def _on_trail_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating_ui:
            return
        eff = self.get_selected_effect()
        if eff is None or not eff.layers:
            return
        self.app.core.action_registry.execute(
            "effect.update", eff.number, trail=float(spin.get_value())
        )
        self.refresh()

    def _on_layer_combo_edited(
        self,
        _renderer: Gtk.CellRendererCombo,
        path_str: str,
        new_text: str,
        field_name: str,
    ) -> None:
        eff = self.get_selected_effect()
        if eff is None or not new_text:
            return
        idx = int(self.layer_store[path_str][0])
        if not 0 <= idx < len(eff.layers):
            return
        layers_copy = [copy.deepcopy(ly) for ly in eff.layers]
        target = layers_copy[idx]
        if field_name == "parameter":
            target.parameter = new_text.strip().lower()
        elif field_name == "mode":
            target.mode = EffectMode(new_text.strip().lower())
        elif field_name == "waveform":
            target.waveform = WaveformType(new_text.strip().lower())
        target.__post_init__()
        self.app.core.action_registry.execute(
            "effect.update", eff.number, layers=layers_copy
        )
        self._populate_editor_from_selected()

    def _on_layer_number_edited(
        self,
        _renderer: Gtk.CellRendererText,
        path_str: str,
        new_text: str,
        field_name: str,
    ) -> None:
        eff = self.get_selected_effect()
        if eff is None:
            return
        try:
            val = float(new_text.strip())
        except ValueError:
            return
        idx = int(self.layer_store[path_str][0])
        if not 0 <= idx < len(eff.layers):
            return
        layers_copy = [copy.deepcopy(ly) for ly in eff.layers]
        target = layers_copy[idx]
        if field_name in ("duty_cycle", "softness"):
            setattr(target, field_name, max(0.0, min(100.0, val)) / 100.0)
        else:
            setattr(target, field_name, val)
        target.__post_init__()
        self.app.core.action_registry.execute(
            "effect.update", eff.number, layers=layers_copy
        )
        self._populate_editor_from_selected()

    def _on_layer_palette_edited(
        self,
        _renderer: Gtk.CellRendererText,
        path_str: str,
        new_text: str,
        field_name: str,
    ) -> None:
        eff = self.get_selected_effect()
        if eff is None:
            return
        idx = int(self.layer_store[path_str][0])
        if not 0 <= idx < len(eff.layers):
            return
        layers_copy = [copy.deepcopy(ly) for ly in eff.layers]
        target = layers_copy[idx]
        def_cat = _default_palette_category_for_param(target.parameter)
        setattr(target, field_name, _parse_user_palette_ref(new_text, def_cat))
        target.__post_init__()
        self.app.core.action_registry.execute(
            "effect.update", eff.number, layers=layers_copy
        )
        self._populate_editor_from_selected()

    def _on_preview_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        self.preview_area.preview_mode = combo.get_active_id() or "auto"
        self.preview_area.queue_draw()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close the Effects tab."""
        if self.tabs:
            self.tabs.close("effects")

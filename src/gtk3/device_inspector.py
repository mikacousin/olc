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
"""Multi-device inspector with IFCB union, 2D Pad, and scientific ColorMatcher."""

# pylint: disable=too-many-lines

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Optional

import cairo
from gi.repository import Gdk, Gtk

from olc.devices.color import sRGB
from olc.devices.color_pick import (
    ColorApplyResult,
    ColorSolver,
    GelSwatch,
    apply_color_to_devices,
    fan_colors_to_devices,
    find_gel,
    hs_to_rgb,
    rgb_to_hs,
    shift_color_hs,
)
from olc.devices.device import COLOR_CHANNEL_TYPES, ChannelType, LightingDevice
from olc.gtk3.widgets.color_picker import ConsoleColorPicker

if TYPE_CHECKING:
    from olc.gtk3.application import Application

BEAM_CHANNEL_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.ZOOM,
        ChannelType.FOCUS,
        ChannelType.IRIS,
        ChannelType.STROBE,
    }
)

GOBO_CHANNEL_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.GOBO_WHEEL,
        ChannelType.PRISM,
        ChannelType.MACRO,
        ChannelType.COLOR_WHEEL,
    }
)


# pylint: disable=too-many-instance-attributes
class PanTiltPadWidget(Gtk.DrawingArea):
    """Interactive 2D Cairo pad for multi-target Pan/Tilt positioning."""

    def __init__(
        self,
        inspector: DeviceInspectorWidget,
        pan_range: tuple[float, float] = (-270.0, 270.0),
        tilt_range: tuple[float, float] = (-135.0, 135.0),
    ) -> None:
        super().__init__()
        self.inspector = inspector
        self.pan_min, self.pan_max = pan_range
        self.tilt_min, self.tilt_max = tilt_range
        self.set_size_request(200, 160)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_hexpand(False)
        self.set_vexpand(False)

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_MOTION_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
        )
        self.connect("button-press-event", self._on_pointer_event)
        self.connect("motion-notify-event", self._on_pointer_event)

    def _coords_to_angles(self, x: float, y: float) -> tuple[float, float]:
        alloc = self.get_allocation()
        w = max(1.0, float(alloc.width))
        h = max(1.0, float(alloc.height))
        norm_x = max(0.0, min(1.0, x / w))
        norm_y = max(0.0, min(1.0, 1.0 - (y / h)))
        pan = self.pan_min + norm_x * (self.pan_max - self.pan_min)
        tilt = self.tilt_min + norm_y * (self.tilt_max - self.tilt_min)
        return round(pan, 2), round(tilt, 2)

    def _angles_to_coords(
        self, pan: float, tilt: float, width: float, height: float
    ) -> tuple[float, float]:
        pan_span = (self.pan_max - self.pan_min) or 540.0
        tilt_span = (self.tilt_max - self.tilt_min) or 270.0
        norm_x = max(0.0, min(1.0, (pan - self.pan_min) / pan_span))
        norm_y = max(0.0, min(1.0, (tilt - self.tilt_min) / tilt_span))
        return norm_x * width, (1.0 - norm_y) * height

    def _on_pointer_event(
        self,
        _widget: Gtk.Widget,
        event: Any,  # noqa: ANN401
    ) -> bool:
        pan, tilt = self._coords_to_angles(event.x, event.y)
        self.inspector.set_pad_position(pan, tilt)
        self.queue_draw()
        return True

    def do_draw(self, cr: cairo.Context) -> bool:  # pylint: disable=too-many-locals
        """Render the 2D coordinate grid, satellite ghost points, and Lead reticle."""
        alloc = self.get_allocation()
        w = float(alloc.width)
        h = float(alloc.height)

        # Background
        cr.set_source_rgb(0.14, 0.16, 0.18)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Center crosshair axes
        cr.set_source_rgba(0.4, 0.45, 0.5, 0.6)
        cr.set_line_width(1.0)
        cr.move_to(w / 2.0, 0)
        cr.line_to(w / 2.0, h)
        cr.move_to(0, h / 2.0)
        cr.line_to(w, h / 2.0)
        cr.stroke()

        targets = self.inspector.get_target_points()
        # Draw satellite points first
        for pt in targets:
            if pt["is_lead"]:
                continue
            px, py = self._angles_to_coords(pt["pan"], pt["tilt"], w, h)
            cr.new_sub_path()
            cr.arc(px, py, 5.0, 0, 2 * math.pi)
            cr.set_source_rgba(0.35, 0.75, 0.95, 0.65)
            cr.fill_preserve()
            cr.set_source_rgba(0.8, 0.9, 1.0, 0.85)
            cr.stroke()

            cr.select_font_face(
                "Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL
            )
            cr.set_font_size(9.0)
            cr.move_to(px + 6.0, py - 4.0)
            cr.show_text(f"#{pt['device_id']}")

        # Draw Lead Fixture reticle on top
        for pt in targets:
            if not pt["is_lead"]:
                continue
            px, py = self._angles_to_coords(pt["pan"], pt["tilt"], w, h)
            cr.new_sub_path()
            cr.arc(px, py, 6.5, 0, 2 * math.pi)
            cr.set_source_rgb(0.2, 0.95, 0.4)
            cr.set_line_width(2.0)
            cr.stroke()

            cr.move_to(px - 10.0, py)
            cr.line_to(px + 10.0, py)
            cr.move_to(px, py - 10.0)
            cr.line_to(px, py + 10.0)
            cr.stroke()

            cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(10.0)
            cr.move_to(px + 8.0, py + 4.0)
            cr.show_text(f"#{pt['device_id']}")

        return False


# pylint: disable=too-many-instance-attributes, too-many-public-methods
class DeviceInspectorWidget(Gtk.Box):
    """Multi-device parameter inspector with IFCB union and NNLS ColorMatcher."""

    def __init__(self, app: Optional[Application] = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        self.selected_devices: list[LightingDevice] = []
        self.lead_index: int = 0
        self.edit_mode: str = "relative"  # "relative" or "absolute"
        self.last_delta_e: float = 0.0
        self.last_worst_delta_e: float = 0.0
        self.last_color_warning: str = ""
        self._color_solver = ColorSolver()
        self._updating_ui: bool = False

        self._build_header()
        self._build_ifcb_sections()

        if self.app is not None and hasattr(self.app, "core"):
            self.app.core.subscribe(
                "channels.selected_changed", self._on_core_selection_changed
            )
            self.app.core.subscribe(
                "channel.level_changed", self._on_core_channel_level_changed
            )
            self.set_selected_channels(self.app.core.selected_channels)
        else:
            self.refresh_ui()

        self.show_all()

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Build context banner, Lead Fixture selector, and permanent Intensity bar."""
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header_box.set_margin_start(6)
        header_box.set_margin_end(6)
        header_box.set_margin_top(4)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.selection_summary_label = Gtk.Label(label="No device selected", xalign=0)
        top_row.pack_start(self.selection_summary_label, True, True, 0)

        self.mode_toggle_btn = Gtk.ToggleButton(label="Mode: Relative (Delta)")
        self.mode_toggle_btn.set_active(False)
        self.mode_toggle_btn.connect("toggled", self._on_mode_btn_toggled)
        top_row.pack_end(self.mode_toggle_btn, False, False, 0)
        header_box.pack_start(top_row, False, False, 0)

        lead_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lead_row.pack_start(Gtk.Label(label="Lead Fixture:", xalign=0), False, False, 0)

        self.prev_lead_btn = Gtk.Button(label="<")
        self.prev_lead_btn.connect("clicked", lambda _b: self.prev_lead())
        lead_row.pack_start(self.prev_lead_btn, False, False, 0)

        self.lead_label = Gtk.Label(label="None", xalign=0)
        lead_row.pack_start(self.lead_label, True, True, 0)

        self.next_lead_btn = Gtk.Button(label=">")
        self.next_lead_btn.connect("clicked", lambda _b: self.next_lead())
        lead_row.pack_start(self.next_lead_btn, False, False, 0)

        self.align_btn = Gtk.Button(label="Align to Lead")
        self.align_btn.connect("clicked", lambda _b: self.align_to_lead())
        lead_row.pack_end(self.align_btn, False, False, 0)
        header_box.pack_start(lead_row, False, False, 0)

        # Permanent Intensity Bar (always visible regardless of active IFCB page)
        int_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.intensity_header_label = Gtk.Label(label="INTENSITY [0/0]", xalign=0)
        self.intensity_value_label = Gtk.Label(label="Dimmer: --", xalign=0)
        self.intensity_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 1.0
        )
        self.intensity_scale.set_digits(1)
        self.intensity_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.intensity_scale.connect("value-changed", self._on_intensity_scale_changed)

        btn_zero = Gtk.Button(label="0%")
        btn_zero.connect(
            "clicked", lambda _b: self.apply_intensity_percent(0.0, force_absolute=True)
        )
        btn_half = Gtk.Button(label="50%")
        btn_half.connect(
            "clicked",
            lambda _b: self.apply_intensity_percent(50.0, force_absolute=True),
        )
        btn_full = Gtk.Button(label="Full")
        btn_full.connect(
            "clicked",
            lambda _b: self.apply_intensity_percent(100.0, force_absolute=True),
        )

        int_row.pack_start(self.intensity_header_label, False, False, 0)
        int_row.pack_start(self.intensity_value_label, False, False, 0)
        int_row.pack_start(self.intensity_scale, True, True, 0)
        int_row.pack_start(btn_zero, False, False, 0)
        int_row.pack_start(btn_half, False, False, 0)
        int_row.pack_start(btn_full, False, False, 0)
        header_box.pack_start(int_row, False, False, 0)

        header_box.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 2
        )
        self.pack_start(header_box, False, False, 0)

    def _build_ifcb_sections(self) -> None:  # pylint: disable=too-many-statements,too-many-locals
        """Build paginated IFCB (Position, Color, Beam & Gobos) stack pages."""
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.stack_switcher = Gtk.StackSwitcher()
        self.stack_switcher.set_stack(self.stack)
        self.stack_switcher.set_halign(Gtk.Align.CENTER)
        self.pack_start(self.stack_switcher, False, False, 2)

        # Page 1: POSITION (PAN / TILT)
        self.position_page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.position_page.set_valign(Gtk.Align.START)
        self.position_page.set_margin_start(6)
        self.position_page.set_margin_end(6)
        self.position_page.set_margin_top(4)

        self.pan_tilt_pad = PanTiltPadWidget(self)
        self.position_page.pack_start(self.pan_tilt_pad, False, False, 0)

        pos_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pos_right.set_valign(Gtk.Align.START)
        self.position_value_label = Gtk.Label(label="Pan: 0.0° | Tilt: 0.0°", xalign=0)
        pos_right.pack_start(self.position_value_label, False, False, 0)

        pos_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        center_btn = Gtk.Button(label="Center (0°, 0°)")
        center_btn.connect("clicked", lambda _b: self.center_position())
        inv_pan_btn = Gtk.Button(label="Invert Pan")
        inv_pan_btn.connect("clicked", lambda _b: self.invert_pan())
        inv_tilt_btn = Gtk.Button(label="Invert Tilt")
        inv_tilt_btn.connect("clicked", lambda _b: self.invert_tilt())
        pos_btn_row.pack_start(center_btn, False, False, 0)
        pos_btn_row.pack_start(inv_pan_btn, False, False, 0)
        pos_btn_row.pack_start(inv_tilt_btn, False, False, 0)
        pos_right.pack_start(pos_btn_row, False, False, 0)

        pos_fan_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        fan_pan_45_btn = Gtk.Button(label="Fan Pan ±45°")
        fan_pan_45_btn.connect("clicked", lambda _b: self.fan_pan(-45.0, 45.0))
        fan_pan_90_btn = Gtk.Button(label="Fan Pan ±90°")
        fan_pan_90_btn.connect("clicked", lambda _b: self.fan_pan(-90.0, 90.0))
        pos_fan_row.pack_start(fan_pan_45_btn, False, False, 0)
        pos_fan_row.pack_start(fan_pan_90_btn, False, False, 0)
        pos_right.pack_start(pos_fan_row, False, False, 0)

        self.position_page.pack_start(pos_right, True, True, 0)
        self.stack.add_titled(self.position_page, "position", "POSITION [0/0]")

        # Page 2: COLOR
        self.color_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.color_page.set_margin_start(6)
        self.color_page.set_margin_end(6)
        self.color_page.set_margin_top(4)

        col_top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.color_value_label = Gtk.Label(label="#FFFFFF | dE: 0.00", xalign=0)
        fan_short_btn = Gtk.Button(label="Fan Hue Short")
        fan_short_btn.connect("clicked", lambda _b: self.fan_color(mode="hs_short"))
        fan_rainbow_btn = Gtk.Button(label="Fan Rainbow")
        fan_rainbow_btn.connect("clicked", lambda _b: self.fan_color(mode="hs_long"))
        col_top_row.pack_start(self.color_value_label, True, True, 0)
        col_top_row.pack_end(fan_rainbow_btn, False, False, 0)
        col_top_row.pack_end(fan_short_btn, False, False, 0)
        self.color_page.pack_start(col_top_row, False, False, 0)

        self.color_picker = ConsoleColorPicker(
            self._on_wheel_color_picked,
            on_emitter_changed=self._on_emitter_fader_changed,
            on_strategy_changed=self.set_color_solver_strategy,
            on_wheel_slot_clicked=self._on_wheel_slot_clicked,
        )
        self.color_page.pack_start(self.color_picker, True, True, 0)
        self.stack.add_titled(self.color_page, "color", "COLOR [0/0]")

        # Page 3: BEAM & GOBOS
        self.beam_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.beam_page.set_margin_start(6)
        self.beam_page.set_margin_end(6)
        self.beam_page.set_margin_top(4)

        beam_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.beam_header_label = Gtk.Label(label="BEAM & OPTICS [0/0]", xalign=0)
        self.zoom_value_label = Gtk.Label(label="Zoom: --", xalign=0)
        self.zoom_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 5.0, 60.0, 0.5
        )
        self.zoom_scale.connect("value-changed", self._on_zoom_scale_changed)
        beam_box.pack_start(self.beam_header_label, False, False, 0)
        beam_box.pack_start(self.zoom_value_label, False, False, 0)
        beam_box.pack_start(self.zoom_scale, False, False, 0)
        self.beam_page.pack_start(beam_box, False, False, 0)

        self.beam_page.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 2
        )

        gobo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.gobos_header_label = Gtk.Label(label="GOBOS & EFFECTS [0/0]", xalign=0)
        self.gobo_combo = Gtk.ComboBoxText()
        self.gobo_combo.connect("changed", self._on_gobo_combo_changed)
        gobo_box.pack_start(self.gobos_header_label, False, False, 0)
        gobo_box.pack_start(self.gobo_combo, False, False, 0)
        self.beam_page.pack_start(gobo_box, False, False, 0)

        self.stack.add_titled(self.beam_page, "beam", "BEAM & GOBOS [0/0]")

        self.pack_start(self.stack, True, True, 0)

    # -------------------------------------------------------------------------
    # Selection & Lead Fixture Management
    # -------------------------------------------------------------------------

    def _on_core_selection_changed(self, channel_ids: list[int]) -> None:
        self.set_selected_channels(channel_ids)

    def _on_core_channel_level_changed(self, channel_id: int, _level: int) -> None:
        if self._updating_ui:
            return
        if any(dev.device_id == channel_id for dev in self.selected_devices):
            self.refresh_ui()

    def _sync_devices_to_live_and_dmx(
        self, devices: list[LightingDevice], sync_intensity: bool = False
    ) -> None:
        """Synchronize modified device parameters to Core DMX engine and LiveView."""
        if self.app is None or not hasattr(self.app, "core"):
            return
        core = self.app.core
        if sync_intensity:
            channels_dict = {
                dev.device_id: round(dev.intensity * 255)
                for dev in devices
                if self._has_intensity(dev) and dev.device_id >= 1
            }
            if channels_dict and getattr(core, "action_registry", None) is not None:
                core.action_registry.execute("channel.set_multi_levels", channels_dict)
        else:
            backend = getattr(core, "backend", None)
            dmx = getattr(backend, "dmx", None) if backend is not None else None
            if dmx is not None:
                dmx.set_levels()

        window = getattr(self.app, "window", None)
        live_view = getattr(window, "live_view", None) if window is not None else None
        if live_view is not None:
            for dev in devices:
                live_view.update_channel_widget(
                    dev.device_id, round(dev.intensity * 255)
                )
            if sync_intensity:
                live_view.channels_view.flowbox.invalidate_filter()

    def set_selected_channels(self, channel_ids: list[int]) -> None:
        """Resolve channel IDs through PatchManager.devices and update inspector."""
        if self.app is None:
            return
        patch = self.app.core.lightshow.patch
        backend = getattr(self.app.core, "backend", None)
        dmx = getattr(backend, "dmx", None) if backend is not None else None
        devices = []
        for ch_id in channel_ids:
            if ch_id in patch.devices:
                dev = patch.devices[ch_id]
                if dmx is not None and 1 <= ch_id <= len(dmx.levels["user"]):
                    lvl, _ = dmx.get_composite_level(ch_id - 1)
                    dev.set_intensity(lvl / 255.0)
                devices.append(dev)
        self.set_selected_devices(devices)

    def set_selected_devices(self, devices: list[LightingDevice]) -> None:
        """Set active list of selected LightingDevice instances."""
        self.selected_devices = list(devices)
        if self.lead_index >= len(self.selected_devices):
            self.lead_index = 0
        self.refresh_ui()

    @property
    def lead_device(self) -> Optional[LightingDevice]:
        """Return currently active Lead Fixture, or None if selection is empty."""
        if not self.selected_devices:
            return None
        idx = max(0, min(self.lead_index, len(self.selected_devices) - 1))
        return self.selected_devices[idx]

    def next_lead(self) -> Optional[LightingDevice]:
        """Advance Lead Fixture to the next device in the selection."""
        if self.selected_devices:
            self.lead_index = (self.lead_index + 1) % len(self.selected_devices)
            self.refresh_ui()
        return self.lead_device

    def prev_lead(self) -> Optional[LightingDevice]:
        """Move Lead Fixture to the previous device in the selection."""
        if self.selected_devices:
            self.lead_index = (self.lead_index - 1) % len(self.selected_devices)
            self.refresh_ui()
        return self.lead_device

    def set_lead_device_id(self, device_id: int) -> bool:
        """Select a specific device_id as the Lead Fixture if in selection."""
        for idx, dev in enumerate(self.selected_devices):
            if dev.device_id == device_id:
                self.lead_index = idx
                self.refresh_ui()
                return True
        return False

    # -------------------------------------------------------------------------
    # Edit Mode (Relative vs Absolute)
    # -------------------------------------------------------------------------

    def set_edit_mode(self, mode: str) -> None:
        """Set parameter application mode ('relative' or 'absolute')."""
        if mode not in ("relative", "absolute"):
            raise ValueError(f"Invalid edit mode: {mode}")
        self.edit_mode = mode
        is_abs = mode == "absolute"
        if self.mode_toggle_btn.get_active() != is_abs:
            self.mode_toggle_btn.set_active(is_abs)
        self.mode_toggle_btn.set_label(
            "Mode: Absolute" if is_abs else "Mode: Relative (Delta)"
        )

    def toggle_edit_mode(self) -> str:
        """Toggle between 'relative' and 'absolute' edit modes."""
        new_mode = "absolute" if self.edit_mode == "relative" else "relative"
        self.set_edit_mode(new_mode)
        return new_mode

    def _on_mode_btn_toggled(self, button: Gtk.ToggleButton) -> None:
        target = "absolute" if button.get_active() else "relative"
        if self.edit_mode != target:
            self.set_edit_mode(target)

    # -------------------------------------------------------------------------
    # IFCB Scope Counts & Disparity Detection
    # -------------------------------------------------------------------------

    @staticmethod
    def _has_intensity(dev: LightingDevice) -> bool:
        return dev.has_physical_dimmer or dev.uses_virtual_dimmer

    @staticmethod
    def _has_position(dev: LightingDevice) -> bool:
        return any(
            ch.channel_type in (ChannelType.PAN, ChannelType.TILT)
            for ch in dev.channels
        )

    @staticmethod
    def _has_color(dev: LightingDevice) -> bool:
        return any(
            ch.channel_type in COLOR_CHANNEL_TYPES
            or ch.channel_type in (ChannelType.COLOR_WHEEL, ChannelType.COLOR_TEMP)
            for ch in dev.channels
        )

    @staticmethod
    def _has_beam(dev: LightingDevice) -> bool:
        return any(ch.channel_type in BEAM_CHANNEL_TYPES for ch in dev.channels)

    @staticmethod
    def _has_gobos(dev: LightingDevice) -> bool:
        return any(ch.channel_type in GOBO_CHANNEL_TYPES for ch in dev.channels)

    def get_section_counts(self) -> dict[str, tuple[int, int]]:
        """Return (compatible_count, total_selected) for each IFCB section."""
        total = len(self.selected_devices)
        return {
            "intensity": (
                sum(1 for d in self.selected_devices if self._has_intensity(d)),
                total,
            ),
            "position": (
                sum(1 for d in self.selected_devices if self._has_position(d)),
                total,
            ),
            "color": (
                sum(1 for d in self.selected_devices if self._has_color(d)),
                total,
            ),
            "beam": (
                sum(1 for d in self.selected_devices if self._has_beam(d)),
                total,
            ),
            "gobos": (
                sum(1 for d in self.selected_devices if self._has_gobos(d)),
                total,
            ),
        }

    def _get_device_param_value(  # pylint: disable=too-many-return-statements
        self, dev: LightingDevice, param_name: str
    ) -> float | tuple[int, int, int] | None:
        """Extract current parameter value from a single device if supported."""
        p = param_name.lower()
        if p == "intensity" and self._has_intensity(dev):
            return round(dev.intensity_percent, 1)
        if p == "pan" and dev.get_channel(ChannelType.PAN) is not None:
            return round(dev.pan_degrees, 1)
        if p == "tilt" and dev.get_channel(ChannelType.TILT) is not None:
            return round(dev.tilt_degrees, 1)
        if p == "color" and self._has_color(dev):
            return dev.color_rgb
        if p == "zoom" and dev.get_channel(ChannelType.ZOOM) is not None:
            z = dev.zoom_degrees
            return round(z, 1) if z is not None else None
        if p == "focus" and dev.get_channel(ChannelType.FOCUS) is not None:
            f = dev.focus_meters
            return round(f, 1) if f is not None else None
        if p == "strobe" and dev.get_channel(ChannelType.STROBE) is not None:
            s = dev.strobe_hz
            return round(s, 1) if s is not None else None
        return None

    def is_parameter_disparate(self, param_name: str) -> bool:
        """Return True if compatible devices in selection have different values."""
        values = [
            self._get_device_param_value(d, param_name) for d in self.selected_devices
        ]
        valid = [v for v in values if v is not None]
        if len(valid) <= 1:
            return False
        first = valid[0]
        return any(v != first for v in valid[1:])

    def format_parameter_display(self, param_name: str) -> str:
        """Format parameter value for Lead Fixture with '~ ... [Multi]' on disparity."""
        lead = self.lead_device
        if lead is None:
            return "--"
        val = self._get_device_param_value(lead, param_name)
        if val is None:
            # Find first compatible device if Lead does not have this parameter
            for dev in self.selected_devices:
                val = self._get_device_param_value(dev, param_name)
                if val is not None:
                    break
        if val is None:
            return "N/A"

        p = param_name.lower()
        if p == "intensity":
            base = f"{val}%"
        elif p in ("pan", "tilt", "zoom"):
            base = f"{val}°"
        elif p == "focus":
            base = f"{val} m"
        elif p == "strobe":
            base = f"{val} Hz"
        elif p == "color" and isinstance(val, tuple):
            base = f"#{val[0]:02X}{val[1]:02X}{val[2]:02X}"
        else:
            base = str(val)

        if self.is_parameter_disparate(param_name):
            return f"~ {base} [Multi]"
        return base

    # -------------------------------------------------------------------------
    # Parameter Application (Relative Delta vs Absolute)
    # -------------------------------------------------------------------------

    def apply_intensity_percent(
        self, percent: float, force_absolute: bool = False
    ) -> None:
        """Apply intensity [0.0..100.0] to all intensity-capable selected devices."""
        eligible = [d for d in self.selected_devices if self._has_intensity(d)]
        if not eligible:
            return

        target_pct = max(0.0, min(100.0, float(percent)))
        if self.edit_mode == "relative" and not force_absolute:
            ref_dev = self.lead_device if self.lead_device in eligible else eligible[0]
            assert ref_dev is not None
            delta = target_pct - ref_dev.intensity_percent
            for dev in eligible:
                dev.set_intensity_percent(
                    max(0.0, min(100.0, dev.intensity_percent + delta))
                )
        else:
            for dev in eligible:
                dev.set_intensity_percent(target_pct)

        self._sync_devices_to_live_and_dmx(eligible, sync_intensity=True)
        self.refresh_ui()

    apply_intensity = apply_intensity_percent

    def set_pad_position(self, pan_deg: float, tilt_deg: float) -> None:
        """Apply 2D Pan/Tilt coordinates in physical degrees (Relative or Absolute)."""
        eligible = [d for d in self.selected_devices if self._has_position(d)]
        if not eligible:
            return

        if self.edit_mode == "relative":
            ref_dev = self.lead_device if self.lead_device in eligible else eligible[0]
            assert ref_dev is not None
            d_pan = pan_deg - ref_dev.pan_degrees
            d_tilt = tilt_deg - ref_dev.tilt_degrees
            for dev in eligible:
                if dev.get_channel(ChannelType.PAN) is not None:
                    dev.set_pan_degrees(dev.pan_degrees + d_pan)
                if dev.get_channel(ChannelType.TILT) is not None:
                    dev.set_tilt_degrees(dev.tilt_degrees + d_tilt)
        else:
            for dev in eligible:
                if dev.get_channel(ChannelType.PAN) is not None:
                    dev.set_pan_degrees(pan_deg)
                if dev.get_channel(ChannelType.TILT) is not None:
                    dev.set_tilt_degrees(tilt_deg)

        self._sync_devices_to_live_and_dmx(eligible)
        self.refresh_ui()

    def get_target_points(self) -> list[dict[str, Any]]:
        """Return 2D Pad points for all position-capable devices in selection."""
        lead = self.lead_device
        points: list[dict[str, Any]] = []
        for dev in self.selected_devices:
            if self._has_position(dev):
                points.append(
                    {
                        "device_id": dev.device_id,
                        "pan": dev.pan_degrees,
                        "tilt": dev.tilt_degrees,
                        "is_lead": dev is lead,
                    }
                )
        # If Lead does not have position, mark the first position-capable device as lead
        if points and not any(p["is_lead"] for p in points):
            points[0]["is_lead"] = True
        return points

    def center_position(self) -> None:
        """Center Pan and Tilt to (0.0°, 0.0°) on all position-capable devices."""
        for dev in self.selected_devices:
            if dev.get_channel(ChannelType.PAN) is not None:
                dev.set_pan_degrees(0.0)
            if dev.get_channel(ChannelType.TILT) is not None:
                dev.set_tilt_degrees(0.0)
        self._sync_devices_to_live_and_dmx(self.selected_devices)
        self.refresh_ui()

    def invert_pan(self) -> None:
        """Invert Pan angle sign (-pan) on all position-capable devices."""
        for dev in self.selected_devices:
            if dev.get_channel(ChannelType.PAN) is not None:
                dev.set_pan_degrees(-dev.pan_degrees)
        self._sync_devices_to_live_and_dmx(self.selected_devices)
        self.refresh_ui()

    def invert_tilt(self) -> None:
        """Invert Tilt angle sign (-tilt) on all position-capable devices."""
        for dev in self.selected_devices:
            if dev.get_channel(ChannelType.TILT) is not None:
                dev.set_tilt_degrees(-dev.tilt_degrees)
        self._sync_devices_to_live_and_dmx(self.selected_devices)
        self.refresh_ui()

    def fan_pan(self, min_deg: float, max_deg: float) -> None:
        """Distribute Pan angles evenly from min_deg to max_deg across moving heads."""
        eligible = [
            d
            for d in self.selected_devices
            if d.get_channel(ChannelType.PAN) is not None
        ]
        count = len(eligible)
        if count == 0:
            return
        if count == 1:
            eligible[0].set_pan_degrees((min_deg + max_deg) / 2.0)
        else:
            for idx, dev in enumerate(eligible):
                angle = min_deg + (idx / (count - 1)) * (max_deg - min_deg)
                dev.set_pan_degrees(angle)
        self._sync_devices_to_live_and_dmx(eligible)
        self.refresh_ui()

    def align_to_lead(self) -> None:
        """Align all compatible parameters of selected devices to Lead Fixture."""
        lead = self.lead_device
        if lead is None:
            return
        color_satellites: list[LightingDevice] = []
        for dev in self.selected_devices:
            if dev is lead:
                continue
            if self._has_intensity(lead) and self._has_intensity(dev):
                dev.set_intensity_percent(lead.intensity_percent)
            if (
                lead.get_channel(ChannelType.PAN) is not None
                and dev.get_channel(ChannelType.PAN) is not None
            ):
                dev.set_pan_degrees(lead.pan_degrees)
            if (
                lead.get_channel(ChannelType.TILT) is not None
                and dev.get_channel(ChannelType.TILT) is not None
            ):
                dev.set_tilt_degrees(lead.tilt_degrees)
            if self._has_color(lead) and self._has_color(dev):
                color_satellites.append(dev)
            if (
                lead.zoom_degrees is not None
                and dev.get_channel(ChannelType.ZOOM) is not None
            ):
                dev.set_zoom_degrees(lead.zoom_degrees)
        if color_satellites:
            c = lead.color_srgb
            apply_color_to_devices(color_satellites, c.r, c.g, c.b, self._color_solver)
        self._sync_devices_to_live_and_dmx(self.selected_devices, sync_intensity=True)
        self._sync_devices_to_live_and_dmx(self.selected_devices, sync_intensity=False)
        self.refresh_ui()

    def apply_color_srgb(  # pylint: disable=too-many-locals
        self, r: float, g: float, b: float
    ) -> dict[int, float]:
        """Apply sRGB color via NNLS ColorMatcher (Relative or Absolute).

        Returns:
            Mapping {device_id: delta_e} for each color-matched device.
        """
        color_devs = [d for d in self.selected_devices if self._has_color(d)]
        if not color_devs:
            return {}

        if self.edit_mode == "relative":
            ref_dev = (
                self.lead_device if self.lead_device in color_devs else color_devs[0]
            )
            assert ref_dev is not None
            ref_c = ref_dev.color_srgb
            ref_h, ref_s = rgb_to_hs(ref_c.r, ref_c.g, ref_c.b)
            new_h, new_s = rgb_to_hs(r, g, b, hue_hint=ref_h)
            d_hue = (new_h - ref_h) % 1.0
            if d_hue > 0.5:
                d_hue -= 1.0
            d_sat = new_s - ref_s

            outcome = ColorApplyResult()
            for dev in color_devs:
                if dev is ref_dev:
                    target = (r, g, b)
                else:
                    dc = dev.color_srgb
                    target = shift_color_hs(
                        (dc.r, dc.g, dc.b), d_hue, d_sat, hue_hint=ref_h
                    )
                sub = apply_color_to_devices([dev], *target, self._color_solver)
                outcome.delta_e.update(sub.delta_e)
                outcome.warnings.update(sub.warnings)
        else:
            outcome = apply_color_to_devices(color_devs, r, g, b, self._color_solver)

        self.last_delta_e = outcome.mean_delta_e
        self.last_worst_delta_e = outcome.worst_delta_e
        self.last_color_warning = outcome.warning
        self._sync_devices_to_live_and_dmx(color_devs)
        self.refresh_ui()
        return outcome.delta_e

    def apply_color_hex(self, hex_str: str) -> dict[int, float]:
        """Apply HTML hex color (#RRGGBB) to all color-capable devices."""
        c = sRGB.from_hex(hex_str)
        return self.apply_color_srgb(c.r, c.g, c.b)

    def apply_gel(self, query: str) -> Optional[GelSwatch]:
        """Find a gel by code/number/name (e.g. 'L201', '181', 'Congo') and apply it."""
        gel = find_gel(query)
        if gel is None:
            return None
        self.apply_color_srgb(*gel.rgb)
        return gel

    def set_color_solver_strategy(self, strategy: str) -> None:
        """Set NNLS solver strategy ('spectral', 'punch', 'rgb_only') and re-solve."""
        self._color_solver.strategy = strategy
        color_devs = [d for d in self.selected_devices if self._has_color(d)]
        if not color_devs:
            return
        outcome = ColorApplyResult()
        for dev in color_devs:
            dc = dev.color_srgb
            sub = apply_color_to_devices([dev], dc.r, dc.g, dc.b, self._color_solver)
            outcome.delta_e.update(sub.delta_e)
            outcome.warnings.update(sub.warnings)
        self.last_delta_e = outcome.mean_delta_e
        self.last_worst_delta_e = outcome.worst_delta_e
        self.last_color_warning = outcome.warning
        self._sync_devices_to_live_and_dmx(color_devs)
        self.refresh_ui()

    def apply_emitter_level(self, channel_type: ChannelType, level: float) -> None:
        """Apply normalized [0.0..1.0] emitter level (Relative or Absolute)."""
        eligible = [
            d for d in self.selected_devices if d.get_channel(channel_type) is not None
        ]
        if not eligible:
            return
        target = max(0.0, min(1.0, float(level)))
        if self.edit_mode == "relative":
            ref_dev = self.lead_device if self.lead_device in eligible else eligible[0]
            assert ref_dev is not None
            delta = target - ref_dev.get_emitter_level(channel_type)
            for dev in eligible:
                dev.set_emitter_level(
                    channel_type, dev.get_emitter_level(channel_type) + delta
                )
        else:
            for dev in eligible:
                dev.set_emitter_level(channel_type, target)
        self._sync_devices_to_live_and_dmx(eligible)
        self.refresh_ui()

    def fan_color(
        self,
        start_rgb: Optional[tuple[float, float, float]] = None,
        end_rgb: Optional[tuple[float, float, float]] = None,
        mode: str = "hs_short",
    ) -> dict[int, float]:
        """Distribute a color gradient across color-capable selected devices."""
        color_devs = [d for d in self.selected_devices if self._has_color(d)]
        if not color_devs:
            return {}
        if start_rgb is None:
            sc = color_devs[0].color_srgb
            start_rgb = (sc.r, sc.g, sc.b)
        if end_rgb is None:
            ec = color_devs[-1].color_srgb
            end_rgb = (ec.r, ec.g, ec.b)
            h1, s1 = rgb_to_hs(*start_rgb)
            h2, s2 = rgb_to_hs(*end_rgb, hue_hint=h1)
            if abs(h2 - h1) < 1e-3 and abs(s2 - s1) < 1e-3:
                # Default spread when all fixtures share the same color
                eff_s = max(0.85, s1)
                start_rgb = hs_to_rgb(h1, eff_s)
                span = (
                    (1.0 - 1.0 / max(2, len(color_devs))) if mode == "hs_long" else 0.25
                )
                end_rgb = hs_to_rgb((h1 + span) % 1.0, eff_s)

        outcome = fan_colors_to_devices(
            color_devs, start_rgb, end_rgb, self._color_solver, mode=mode
        )
        self.last_delta_e = outcome.mean_delta_e
        self.last_worst_delta_e = outcome.worst_delta_e
        self.last_color_warning = outcome.warning
        self._sync_devices_to_live_and_dmx(color_devs)
        self.refresh_ui()
        return outcome.delta_e

    def apply_physical_parameter(self, channel_type: ChannelType, value: float) -> None:
        """Apply physical parameter (Zoom, Focus, Strobe, CCT) to eligible devices."""
        eligible = [
            d for d in self.selected_devices if d.get_channel(channel_type) is not None
        ]
        if not eligible:
            return

        param_map = {
            ChannelType.ZOOM: ("zoom_degrees", "set_zoom_degrees"),
            ChannelType.FOCUS: ("focus_meters", "set_focus_meters"),
            ChannelType.STROBE: ("strobe_hz", "set_strobe_hz"),
            ChannelType.COLOR_TEMP: ("color_temp_kelvin", "set_color_temp_kelvin"),
            ChannelType.PAN: ("pan_degrees", "set_pan_degrees"),
            ChannelType.TILT: ("tilt_degrees", "set_tilt_degrees"),
        }
        if channel_type not in param_map:
            return

        getter_name, setter_name = param_map[channel_type]
        if self.edit_mode == "relative":
            ref_dev = self.lead_device if self.lead_device in eligible else eligible[0]
            assert ref_dev is not None
            ref_val = getattr(ref_dev, getter_name) or 0.0
            delta = float(value) - float(ref_val)
            for dev in eligible:
                cur_val = getattr(dev, getter_name) or 0.0
                getattr(dev, setter_name)(float(cur_val) + delta)
        else:
            for dev in eligible:
                getattr(dev, setter_name)(float(value))

        self._sync_devices_to_live_and_dmx(eligible)
        self.refresh_ui()

    def apply_discrete_range(self, channel_type: ChannelType, range_label: str) -> int:
        """Activate a named ChannelRange on all compatible selected devices."""
        activated_count = 0
        for dev in self.selected_devices:
            ch = dev.get_channel(channel_type)
            if ch is None:
                continue
            for r in ch.ranges:
                if r.label.lower() == range_label.lower():
                    ch.set_value(r.activation_value)
                    activated_count += 1
                    break
        self._sync_devices_to_live_and_dmx(self.selected_devices)
        self.refresh_ui()
        return activated_count

    # -------------------------------------------------------------------------
    # UI Signal Handlers & Refresh
    # -------------------------------------------------------------------------

    def _on_intensity_scale_changed(self, scale: Gtk.Scale) -> None:
        if self._updating_ui:
            return
        self.apply_intensity_percent(scale.get_value())

    def _on_zoom_scale_changed(self, scale: Gtk.Scale) -> None:
        if self._updating_ui:
            return
        self.apply_physical_parameter(ChannelType.ZOOM, scale.get_value())

    def _on_wheel_color_picked(self, r: float, g: float, b: float) -> None:
        if self._updating_ui:
            return
        self.apply_color_srgb(r, g, b)

    def _on_emitter_fader_changed(self, etype: str, level: float) -> None:
        if self._updating_ui:
            return
        try:
            ctype = ChannelType(etype)
        except ValueError:
            return
        self.apply_emitter_level(ctype, level)

    def _on_wheel_slot_clicked(self, slot_label: str) -> None:
        if self._updating_ui:
            return
        self.apply_discrete_range(ChannelType.COLOR_WHEEL, slot_label)

    def _on_gobo_combo_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._updating_ui:
            return
        label = combo.get_active_text()
        if label:
            self.apply_discrete_range(ChannelType.GOBO_WHEEL, label)

    def refresh_ui(  # pylint: disable=too-many-locals,too-many-statements
        self,
    ) -> None:
        """Synchronize all IFCB section headers, badges, and widgets with selection."""
        self._updating_ui = True
        try:
            total = len(self.selected_devices)
            if total == 0:
                self.selection_summary_label.set_text("No device selected")
                self.lead_label.set_text("None")
            else:
                ids_str = ", ".join(
                    f"#{d.device_id}" for d in self.selected_devices[:6]
                )
                if total > 6:
                    ids_str += f" (+{total - 6})"
                self.selection_summary_label.set_text(
                    f"{total} device(s) selected: {ids_str}"
                )
                lead = self.lead_device
                if lead is not None:
                    self.lead_label.set_text(
                        f"#{lead.device_id}: {lead.label or lead.fixture_type.value}"
                    )

            counts = self.get_section_counts()
            i_c, i_t = counts["intensity"]
            p_c, p_t = counts["position"]
            c_c, c_t = counts["color"]
            b_c, b_t = counts["beam"]
            g_c, g_t = counts["gobos"]
            bg_c = sum(
                1
                for d in self.selected_devices
                if self._has_beam(d) or self._has_gobos(d)
            )

            self.intensity_header_label.set_text(f"INTENSITY [{i_c}/{i_t}]")
            self.beam_header_label.set_text(f"BEAM & OPTICS [{b_c}/{b_t}]")
            self.gobos_header_label.set_text(f"GOBOS & EFFECTS [{g_c}/{g_t}]")
            self.stack.child_set_property(
                self.position_page, "title", f"POSITION [{p_c}/{p_t}]"
            )
            self.stack.child_set_property(
                self.color_page, "title", f"COLOR [{c_c}/{c_t}]"
            )
            self.stack.child_set_property(
                self.beam_page, "title", f"BEAM & GOBOS [{bg_c}/{b_t}]"
            )

            self.intensity_value_label.set_text(
                f"Dimmer: {self.format_parameter_display('intensity')}"
            )
            self.position_value_label.set_text(
                f"Pan: {self.format_parameter_display('pan')} | "
                f"Tilt: {self.format_parameter_display('tilt')}"
            )
            self.color_value_label.set_text(
                f"Color: {self.format_parameter_display('color')} | "
                f"dE: {self.last_delta_e:.2f}"
            )
            self.zoom_value_label.set_text(
                f"Zoom: {self.format_parameter_display('zoom')}"
            )

            lead = self.lead_device
            if lead is not None and self._has_intensity(lead):
                self.intensity_scale.set_value(lead.intensity_percent)
            if lead is not None and lead.zoom_degrees is not None:
                self.zoom_scale.set_value(lead.zoom_degrees)

            self.pan_tilt_pad.queue_draw()
            color_devs = [d for d in self.selected_devices if self._has_color(d)]
            if color_devs:
                ref = (
                    self.lead_device
                    if self.lead_device in color_devs
                    else color_devs[0]
                )
                assert ref is not None
                lead_color = ref.color_srgb
                self.color_picker.set_color(lead_color.r, lead_color.g, lead_color.b)
                self.color_picker.set_devices_context(ref, color_devs)
                self.color_picker.set_match(
                    self.last_worst_delta_e, self.last_color_warning
                )
            else:
                self.color_picker.set_devices_context(None, [])
                self.color_picker.clear_match()
            if (
                self.app is not None
                and self.app.window is not None
                and self.app.window.live_view is not None
            ):
                self.app.window.live_view.channels_view.flowbox.queue_draw()
        finally:
            self._updating_ui = False

    def refresh(self) -> None:
        """Refresh inspector state from current Core selection."""
        if self.app is not None and hasattr(self.app, "core"):
            self.set_selected_channels(self.app.core.selected_channels)
        else:
            self.refresh_ui()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close the Device Inspector tab."""
        if self.app is not None and self.app.tabs is not None:
            self.app.tabs.close("device_inspector")

    def cleanup(self) -> None:
        """Unsubscribe from Core events when the tab is closed."""
        self.color_picker.cleanup()
        if self.app is not None and hasattr(self.app, "core"):
            self.app.core.unsubscribe(
                "channels.selected_changed", self._on_core_selection_changed
            )

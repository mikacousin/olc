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

from gi.repository import Gtk

from olc.show.fader import (
    FaderEffect,
    FaderMain,
    FaderPreset,
    FaderSequence,
    FaderType,
)
from olc.show.palette import PaletteCategory

if typing.TYPE_CHECKING:
    from gi.repository import Gio

    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.window import Window
    from olc.show.lightshow import LightShow


_EFFECT_MODE_LABELS: dict[str, str] = {
    "size": "Mode: Size",
    "rate": "Mode: Rate",
    "both": "Mode: Size+Rate",
}


# pylint: disable=too-many-instance-attributes
class FaderEdit(Gtk.Box):
    """Fader edition widget"""

    page: int
    index: int
    label: Gtk.Label
    fix_button: Gtk.ToggleButton
    fixed_origin_label: Gtk.Label
    type_button: Gtk.MenuButton
    contents_button: Gtk.MenuButton
    effect_controls_box: Gtk.Box | None
    effect_mode_button: Gtk.MenuButton | None
    effect_channels_button: Gtk.MenuButton | None

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        page: int,
        index: int,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.get_style_context().add_class("olc-fader-box")
        self.page = page
        self.index = index
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings
        self.effect_controls_box = None
        self.effect_mode_button = None
        self.effect_channels_button = None
        self._updating_fix = False

        fader = self.lightshow.fader_bank.faders[page][index]

        self.label = Gtk.Label()
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header_box.pack_start(self.label, True, True, 0)
        self.fix_button = Gtk.ToggleButton(label=_("Fix"))
        self.fix_button.set_tooltip_text(_("Fix this fader across all pages"))
        self.fix_button.connect("toggled", self._on_fix_toggled)
        header_box.pack_start(self.fix_button, False, False, 0)

        self.fixed_origin_label = Gtk.Label()
        self.fixed_origin_label.set_no_show_all(True)

        fader_type: list[tuple[FaderType, str]] = [
            (FaderType.NONE, ""),
            (FaderType.PRESET, "Preset"),
            (FaderType.SEQUENCE, "Sequence"),
            (FaderType.EFFECT, "Effect"),
            (FaderType.MAIN, "Main Fader"),
        ]
        self.type_button = Gtk.MenuButton()
        popover = Gtk.Popover()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        for ftype, ftext in fader_type:
            button = Gtk.ModelButton()
            button.set_label(ftext)
            button.connect("clicked", self._on_type_changed, ftype)
            vbox.add(button)
        vbox.show_all()
        popover.add(vbox)
        popover.set_position(Gtk.PositionType.BOTTOM)
        self.type_button.set_popover(popover)

        if isinstance(fader, FaderPreset):
            self._fader_preset()
        elif isinstance(fader, FaderSequence):
            self._fader_sequence()
        elif isinstance(fader, FaderEffect):
            self._fader_effect()
        elif isinstance(fader, FaderMain):
            self._fader_main()
        else:
            self._fader_none()

        self.add(header_box)
        self.add(self.fixed_origin_label)
        self.add(self.type_button)
        self.add(self.contents_button)
        if self.effect_controls_box is not None:
            self.add(self.effect_controls_box)
        self._update_fix_ui()

    def _update_fix_ui(self) -> None:
        """Synchronize Fix toggle button and cross-page fixed indicator."""
        fader_bank = self.lightshow.fader_bank
        fader_type = fader_bank.get_fader_type(self.page, self.index)
        is_fixed_here = fader_bank.is_fader_fixed(self.page, self.index)
        src_page = fader_bank.get_fixed_source_page(self.index)

        self._updating_fix = True
        try:
            self.fix_button.set_active(is_fixed_here)
            self.fix_button.set_sensitive(fader_type != FaderType.NONE or is_fixed_here)
        finally:
            self._updating_fix = False

        if src_page is not None and src_page != self.page:
            msg = _("Fixed on Page {page}").format(page=src_page)
            self.fixed_origin_label.set_markup(
                f"<span foreground='#e59933' size='small'>{msg}</span>"
            )
            self.fixed_origin_label.set_visible(True)
        else:
            self.fixed_origin_label.set_visible(False)

    def _on_fix_toggled(self, widget: Gtk.ToggleButton) -> None:
        if self._updating_fix:
            return
        app = self.lightshow.app
        if app is not None:
            app.action_registry.execute(
                "fader.set_fixed", self.page, self.index, widget.get_active()
            )

    def _fader_none(self) -> None:
        """Create edition of not defined fader"""
        self.label.set_markup(f"<span foreground='#666666'>Fader {self.index}</span>")
        self.get_style_context().add_class("empty")
        self.type_button.set_label("")
        self.contents_button = Gtk.MenuButton()
        self.contents_button.set_label("")

    def _fader_main(self) -> None:
        """Create edition of main fader"""
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.get_style_context().remove_class("empty")
        self.type_button.set_label("Main Fader")
        self.contents_button = Gtk.MenuButton()
        self.contents_button.set_label("")

    def _fader_sequence(self) -> None:
        """Create edition of sequence fader"""
        fader = self.lightshow.fader_bank.faders[self.page][self.index]
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.get_style_context().remove_class("empty")
        self.type_button.set_label("Sequence")
        self.contents_button = Gtk.MenuButton()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        for seq in self.lightshow.sequences:
            button = Gtk.ModelButton()
            button.set_label(f"{seq.index:g} : {seq.text}")
            button.connect(
                "clicked", self._on_contents_changed, FaderType.SEQUENCE, seq.index
            )
            vbox.add(button)
            if seq is fader.contents:
                self.contents_button.set_label(f"{seq.index:g} : {seq.text}")
        self._contents_popup(vbox)

    def _fader_effect(self) -> None:
        """Create edition of procedural Effect fader."""
        fader = self.lightshow.fader_bank.faders[self.page][self.index]
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.get_style_context().remove_class("empty")
        self.type_button.set_label("Effect")
        self.contents_button = Gtk.MenuButton()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        effects = (
            self.lightshow.effects.all() if hasattr(self.lightshow, "effects") else []
        )
        for eff in effects:
            button = Gtk.ModelButton()
            lbl = f"{eff.number:g} : {eff.label or f'Effect {eff.number:g}'}"
            button.set_label(lbl)
            button.connect(
                "clicked", self._on_contents_changed, FaderType.EFFECT, eff.number
            )
            vbox.add(button)
            if eff is fader.contents:
                self.contents_button.set_label(lbl)
        self._contents_popup(vbox)

        # Control mode selector (Size / Rate / Size+Rate) & Target channels binding
        self.effect_controls_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4
        )

        current_mode = getattr(fader, "control_mode", "size")
        self.effect_mode_button = Gtk.MenuButton()
        self.effect_mode_button.set_label(
            _EFFECT_MODE_LABELS.get(current_mode, "Mode: Size")
        )
        mode_popover = Gtk.Popover()
        mode_vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        mode_vbox.set_border_width(5)
        for mode_key, mode_text in (
            ("size", "Size"),
            ("rate", "Rate"),
            ("both", "Size + Rate"),
        ):
            m_btn = Gtk.ModelButton()
            m_btn.set_label(mode_text)
            m_btn.connect("clicked", self._on_effect_mode_changed, mode_key)
            mode_vbox.add(m_btn)
        mode_vbox.show_all()
        mode_popover.add(mode_vbox)
        mode_popover.set_position(Gtk.PositionType.BOTTOM)
        self.effect_mode_button.set_popover(mode_popover)

        ch_label = (
            fader.format_target_channels()
            if isinstance(fader, FaderEffect)
            else "Auto (Sel)"
        )
        self.effect_channels_button = Gtk.MenuButton()
        self.effect_channels_button.set_label(ch_label)
        ch_popover = Gtk.Popover()
        ch_vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        ch_vbox.set_border_width(5)

        btn_sel = Gtk.ModelButton()
        btn_sel.set_label("Set from Selection")
        btn_sel.connect("clicked", self._on_effect_channels_from_selection)
        ch_vbox.add(btn_sel)

        btn_clear = Gtk.ModelButton()
        btn_clear.set_label("Clear (Auto / Selection)")
        btn_clear.connect("clicked", self._on_effect_channels_clear)
        ch_vbox.add(btn_clear)

        ch_vbox.show_all()
        ch_popover.add(ch_vbox)
        ch_popover.set_position(Gtk.PositionType.BOTTOM)
        self.effect_channels_button.set_popover(ch_popover)

        self.effect_controls_box.add(self.effect_mode_button)
        self.effect_controls_box.add(self.effect_channels_button)

    def _fader_preset(self) -> None:
        """Create edition of preset fader."""
        fader = self.lightshow.fader_bank.faders[self.page][self.index]
        self.label.set_markup(f"<span foreground='#e59933'>Fader {self.index}</span>")
        self.get_style_context().remove_class("empty")
        self.type_button.set_label("Preset")
        self.contents_button = Gtk.MenuButton()
        vbox = Gtk.Box(spacing=1, orientation=Gtk.Orientation.VERTICAL)
        vbox.set_border_width(5)
        presets = self.lightshow.palettes.list_by_category(PaletteCategory.PRESET)
        for preset in presets:
            button = Gtk.ModelButton()
            lbl = f"{preset.number:g} : {preset.text}"
            button.set_label(lbl)
            button.connect(
                "clicked",
                self._on_contents_changed,
                FaderType.PRESET,
                preset.number,
            )
            vbox.add(button)
            if preset is fader.contents:
                self.contents_button.set_label(lbl)
        self._contents_popup(vbox)

    def _on_type_changed(self, _widget: Gtk.ModelButton, fader_type: FaderType) -> None:
        app = self.lightshow.app
        if app is not None:
            app.action_registry.execute(
                "fader.assign", self.page, self.index, fader_type
            )

    def _on_contents_changed(
        self,
        widget: Gtk.ModelButton,
        fader_type: FaderType,
        contents: dict[int, int] | int | float | None,
    ) -> None:
        """Fader contents has been changed

        Args:
            widget: Button clicked
            fader_type: Fader Type
            contents: New contents
        """
        if self.contents_button:
            # Max label size: 30 characters
            self.contents_button.set_label(f"{widget.get_label():<.30}")
        app = self.lightshow.app
        if app is not None:
            app.action_registry.execute(
                "fader.assign", self.page, self.index, fader_type, contents
            )

    def _on_effect_mode_changed(self, _widget: Gtk.ModelButton, mode: str) -> None:
        app = self.lightshow.app
        if app is not None:
            app.action_registry.execute(
                "fader.configure_effect", self.page, self.index, control_mode=mode
            )

    def _on_effect_channels_from_selection(self, _widget: Gtk.ModelButton) -> None:
        app = self.lightshow.app
        if app is not None:
            selected = list(getattr(app, "selected_channels", []))
            if selected:
                app.action_registry.execute(
                    "fader.configure_effect",
                    self.page,
                    self.index,
                    effect_channels=selected,
                )

    def _on_effect_channels_clear(self, _widget: Gtk.ModelButton) -> None:
        app = self.lightshow.app
        if app is not None:
            app.action_registry.execute(
                "fader.configure_effect", self.page, self.index, effect_channels=[]
            )

    def refresh(self) -> None:
        """Refresh this fader widget representation in place."""
        fader_type = self.lightshow.fader_bank.get_fader_type(self.page, self.index)

        self.remove(self.contents_button)
        if self.effect_controls_box is not None:
            self.remove(self.effect_controls_box)
            self.effect_controls_box = None
            self.effect_mode_button = None
            self.effect_channels_button = None

        if fader_type == FaderType.NONE:
            self._fader_none()
        elif fader_type == FaderType.MAIN:
            self._fader_main()
        elif fader_type == FaderType.PRESET:
            self._fader_preset()
        elif fader_type == FaderType.SEQUENCE:
            self._fader_sequence()
        elif fader_type == FaderType.EFFECT:
            self._fader_effect()
        self.add(self.contents_button)
        if self.effect_controls_box is not None:
            self.add(self.effect_controls_box)
        self._update_fix_ui()
        self.show_all()

    def _contents_popup(self, vbox: Gtk.Box) -> None:
        """Create contents popover

        Args:
            vbox: Popover box
        """
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(vbox)
        scrollable.show_all()
        popover = Gtk.Popover()
        popover.add(scrollable)
        popover.set_position(Gtk.PositionType.BOTTOM)
        height, _ = vbox.get_preferred_height()
        height = min(height, 600)
        scrollable.set_min_content_height(height)
        if self.contents_button:
            self.contents_button.set_popover(popover)


class FaderTab(Gtk.Box):
    """Fader edition"""

    def __init__(
        self,
        lightshow: LightShow,
        tabs: Tabs,
        window: Window,
        settings: Gio.Settings,
    ) -> None:
        super().__init__()
        self.lightshow = lightshow
        self.tabs = tabs
        self.window = window
        self.settings = settings
        self.fader_bank = self.lightshow.fader_bank
        self.fader_widgets: dict[tuple[int, int], FaderEdit] = {}
        max_pages = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        self.current_page: int = 1
        self._updating_page_selector = False

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nav_box.set_halign(Gtk.Align.CENTER)
        nav_box.set_margin_top(6)
        nav_box.set_margin_bottom(6)

        self.btn_page_prev = Gtk.Button(label=_("Page -"))
        self.btn_page_prev.connect("clicked", self._on_page_prev_clicked)
        nav_box.pack_start(self.btn_page_prev, False, False, 0)

        lbl_page = Gtk.Label(label=_("Page"))
        nav_box.pack_start(lbl_page, False, False, 0)

        self.page_adjustment = Gtk.Adjustment(
            value=float(self.current_page),
            lower=1.0,
            upper=float(max_pages),
            step_increment=1.0,
            page_increment=5.0,
            page_size=0.0,
        )
        self.spin_page = Gtk.SpinButton(
            adjustment=self.page_adjustment, climb_rate=1.0, digits=0
        )
        self.spin_page.set_numeric(True)
        self.spin_page.connect("value-changed", self._on_spin_page_changed)
        nav_box.pack_start(self.spin_page, False, False, 0)

        self.label_total_pages = Gtk.Label(label=f"/ {max_pages}")
        nav_box.pack_start(self.label_total_pages, False, False, 0)

        self.btn_page_next = Gtk.Button(label=_("Page +"))
        self.btn_page_next.connect("clicked", self._on_page_next_clicked)
        nav_box.pack_start(self.btn_page_next, False, False, 0)

        self.page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._populate_active_page()

        vbox.pack_start(nav_box, False, False, 0)
        vbox.pack_start(self.page_box, True, True, 0)

        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.set_hexpand(True)
        scrollable.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrollable.add(vbox)
        self.add(scrollable)

    def _on_page_prev_clicked(self, _btn: Gtk.Button) -> None:
        max_p = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        target = self.current_page - 1 if self.current_page > 1 else max_p
        self.set_page(target)

    def _on_page_next_clicked(self, _btn: Gtk.Button) -> None:
        max_p = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        target = self.current_page + 1 if self.current_page < max_p else 1
        self.set_page(target)

    def _on_spin_page_changed(self, widget: Gtk.SpinButton) -> None:
        if self._updating_page_selector:
            return
        max_p = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        target = max(1, min(max_p, widget.get_value_as_int()))
        if target != self.current_page:
            self.set_page(target)

    def set_page(self, page: int) -> None:
        """Select a fader page and instantiate its widgets on demand."""
        max_p = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        target = max(1, min(max_p, int(page)))
        self.current_page = target
        self._sync_page_selector_ui()
        self._populate_active_page()

    def _sync_page_selector_ui(self) -> None:
        max_p = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        self._updating_page_selector = True
        try:
            self.page_adjustment.set_upper(float(max_p))
            if self.spin_page.get_value_as_int() != self.current_page:
                self.spin_page.set_value(float(self.current_page))
            self.label_total_pages.set_text(f"/ {max_p}")
        finally:
            self._updating_page_selector = False

    def refresh(self) -> None:
        """Refresh active page display or rebuild on page clamp/resize."""
        max_p = max(1, int(getattr(self.fader_bank, "max_fader_page", 10)))
        page_clamped = False
        if self.current_page > max_p:
            self.current_page = max_p
            page_clamped = True

        self._sync_page_selector_ui()
        expected_keys = {
            (self.current_page, index)
            for index in self.fader_bank.faders.get(self.current_page, {}).keys()
        }

        if page_clamped or set(self.fader_widgets.keys()) != expected_keys:
            self._populate_active_page()
        else:
            for widget in self.fader_widgets.values():
                widget.refresh()

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        self.tabs.close("faders")

    def _populate_active_page(self) -> None:
        """Instantiate FaderEdit widgets for the currently selected page only."""
        for child in list(self.page_box.get_children()):
            self.page_box.remove(child)
        self.fader_widgets.clear()

        faders = self.fader_bank.faders.get(self.current_page, {})
        hbox1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox1.set_homogeneous(True)
        hbox2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox2.set_homogeneous(True)
        for index in faders.keys():
            fader_edit = FaderEdit(
                self.current_page,
                index,
                lightshow=self.lightshow,
                tabs=self.tabs,
                window=self.window,
                settings=self.settings,
            )
            self.fader_widgets[(self.current_page, index)] = fader_edit
            # Display faders on 2 lines
            if index <= self.fader_bank.max_fader_per_page / 2:
                hbox1.add(fader_edit)
            else:
                hbox2.add(fader_edit)
        self.page_box.add(hbox1)
        self.page_box.add(hbox2)
        self.page_box.show_all()

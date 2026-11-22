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

import ipaddress
import socket
import time
import typing
from gettext import gettext as _

from gi.repository import Gdk, GLib, Gtk

from olc.gtk3.settings_universes import UniversesSettingsMixin

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


# pylint: disable=too-many-instance-attributes
class SettingsTab(Gtk.Box, UniversesSettingsMixin):
    """Settings"""

    def __init__(
        self,
        app: Application,
    ) -> None:
        self.app = app
        self.settings = app.settings
        self.tabs = app.tabs
        self.midi = app.core.midi

        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._last_artnet_state: list[list[str]] | None = None
        self.universe_widgets: dict[int, dict[str, typing.Any]] = {}
        self.universe_frames: dict[int, Gtk.Frame] = {}
        self.delete_universe_buttons: dict[int, Gtk.Button] = {}
        self.universes_box: Gtk.Box | None = None
        self._updating_settings = False

        builder = Gtk.Builder()
        builder.add_from_resource("/com/github/mikacousin/olc/settings.ui")
        settings_dialog = typing.cast(Gtk.Notebook, builder.get_object("settings"))

        self._setup_appearance(builder)
        self._setup_osc(builder)

        # MIDI
        self._midi(builder)

        # Art-Net Discovery Page
        self._artnet(builder)

        # Universes Tab
        universes_tab = self._create_universes_tab()
        settings_dialog.append_page(universes_tab, Gtk.Label(label=_("Universes")))

        builder.connect_signals(self)
        self.pack_start(settings_dialog, True, True, 0)

    def _setup_appearance(self, builder: Gtk.Builder) -> None:
        self.switch_percent = typing.cast(
            Gtk.Switch, builder.get_object("switch_percent")
        )
        self.switch_percent.set_state(self.settings.get_boolean("percent"))
        adjustment = Gtk.Adjustment(
            value=0,
            lower=1,
            upper=100,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        widget2 = typing.cast(Gtk.SpinButton, builder.get_object("spin_percent_level"))
        widget2.set_adjustment(adjustment)
        widget2.set_value(self.settings.get_int("percent-level"))
        adjustment = Gtk.Adjustment(
            value=0,
            lower=1,
            upper=100,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        self.spin_default_time = typing.cast(
            Gtk.SpinButton, builder.get_object("spin_default_time")
        )
        self.spin_default_time.set_adjustment(adjustment)
        self.spin_default_time.set_value(self.settings.get_double("default-time"))
        adjustment = Gtk.Adjustment(
            value=0,
            lower=1,
            upper=100,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        widget4 = typing.cast(Gtk.SpinButton, builder.get_object("spin_go_back_time"))
        widget4.set_adjustment(adjustment)
        widget4.set_value(self.settings.get_double("go-back-time"))
        adjustment_sneak = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=100,
            step_increment=0.5,
            page_increment=5,
            page_size=0,
        )
        widget5 = typing.cast(Gtk.SpinButton, builder.get_object("spin_sneak_time"))
        widget5.set_adjustment(adjustment_sneak)
        widget5.set_value(self.settings.get_double("sneak-time"))

        adjustment_check = Gtk.Adjustment(
            value=80.0,
            lower=0.0,
            upper=100.0,
            step_increment=5.0,
            page_increment=10.0,
            page_size=0,
        )
        widget6 = typing.cast(
            Gtk.SpinButton, builder.get_object("spin_channel_check_level")
        )
        widget6.set_adjustment(adjustment_check)
        schema = getattr(self.settings.props, "settings_schema", None)
        if schema is None or schema.has_key("channel-check-level"):
            widget6.set_value(self.settings.get_double("channel-check-level"))
        else:
            widget6.set_value(80.0)

        adjustment_home = Gtk.Adjustment(
            value=0.0,
            lower=0.0,
            upper=9999.0,
            step_increment=1.0,
            page_increment=10.0,
            page_size=0,
        )
        self.spin_home_preset = typing.cast(
            Gtk.SpinButton | None, builder.get_object("spin_home_preset")
        )
        if self.spin_home_preset is not None:
            self.spin_home_preset.set_adjustment(adjustment_home)
            core = getattr(self.app, "core", None)
            lightshow = getattr(core, "lightshow", None) if core is not None else None
            hp = getattr(lightshow, "home_preset", None)
            self.spin_home_preset.set_value(
                float(hp) if hp is not None and hp > 0.0 else 0.0
            )

        adjustment_pages = Gtk.Adjustment(
            value=10.0,
            lower=1.0,
            upper=100.0,
            step_increment=1.0,
            page_increment=10.0,
            page_size=0.0,
        )
        self.spin_fader_pages = typing.cast(
            Gtk.SpinButton | None, builder.get_object("spin_fader_pages")
        )
        if self.spin_fader_pages is not None:
            self.spin_fader_pages.set_adjustment(adjustment_pages)
            core = getattr(self.app, "core", None)
            lightshow = getattr(core, "lightshow", None) if core is not None else None
            fader_bank = (
                getattr(lightshow, "fader_bank", None)
                if lightshow is not None
                else None
            )
            max_pages = getattr(fader_bank, "max_fader_page", 10)
            self.spin_fader_pages.set_value(float(max_pages))

        self.switch_skip_empty_fader_pages = typing.cast(
            Gtk.Switch | None,
            builder.get_object("switch_skip_empty_fader_pages"),
        )
        if self.switch_skip_empty_fader_pages is not None:
            core = getattr(self.app, "core", None)
            lightshow = getattr(core, "lightshow", None) if core is not None else None
            fader_bank = (
                getattr(lightshow, "fader_bank", None)
                if lightshow is not None
                else None
            )
            skip_empty = bool(getattr(fader_bank, "skip_empty_pages", False))
            self.switch_skip_empty_fader_pages.set_state(skip_empty)
            self.switch_skip_empty_fader_pages.set_active(skip_empty)

    def _setup_osc(self, builder: Gtk.Builder) -> None:
        self.switch_osc = typing.cast(Gtk.Switch, builder.get_object("switch_osc"))
        self.switch_osc.set_state(self.settings.get_boolean("osc"))

        self.entry_client_ip = typing.cast(
            Gtk.Entry, builder.get_object("entry_client_ip")
        )
        self.entry_client_ip.set_text(self.settings.get_string("osc-host"))
        self.entry_client_ip.connect("focus-out-event", self._on_client_ip_focus_out)

        self.spin_client_port = typing.cast(
            Gtk.SpinButton, builder.get_object("spin_client_port")
        )
        adjustment = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=65535,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        self.spin_client_port.set_adjustment(adjustment)
        self.spin_client_port.set_value(self.settings.get_int("osc-client-port"))

        self.spin_server_port = typing.cast(
            Gtk.SpinButton, builder.get_object("spin_server_port")
        )
        adjustment = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=65535,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        self.spin_server_port.set_adjustment(adjustment)
        self.spin_server_port.set_value(self.settings.get_int("osc-server-port"))

        local_ip = typing.cast(Gtk.Label, builder.get_object("local_ip"))
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        local_ip.set_label(ip_addr)

        self.switch_static_client = typing.cast(
            Gtk.Switch, builder.get_object("switch_static_client")
        )
        is_static_enabled = False
        if hasattr(self.settings, "get_boolean"):
            try:
                is_static_enabled = self.settings.get_boolean("osc-static-client")
            except Exception:  # pylint: disable=broad-exception-caught
                is_static_enabled = False
        if self.switch_static_client is not None:
            self.switch_static_client.set_state(is_static_enabled)
            self.switch_static_client.set_active(is_static_enabled)

        self.entry_client_ip.set_sensitive(is_static_enabled)
        self.spin_client_port.set_sensitive(is_static_enabled)

        osc_grid = typing.cast(Gtk.Grid, builder.get_object("osc_grid"))
        if osc_grid is not None:
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.set_margin_top(6)
            separator.set_margin_bottom(6)
            osc_grid.attach(separator, 0, 6, 2, 1)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            info_box.set_margin_start(10)
            info_box.set_margin_end(10)
            info_box.set_margin_top(4)
            info_box.set_margin_bottom(6)

            self.label_osc_mdns = Gtk.Label()
            self.label_osc_mdns.set_halign(Gtk.Align.START)
            self.label_osc_mdns.set_use_markup(True)
            self.label_osc_mdns.set_markup(
                f"<span foreground='#888888'>○</span> <b>{_('mDNS Discovery:')}</b> "
                f"<i>{_('Inactive')}</i>"
            )
            info_box.pack_start(self.label_osc_mdns, False, False, 0)

            label_norm_info = Gtk.Label(
                label=_(
                    "All fader and channel levels are exchanged on a "
                    "normalized 0.0 - 1.0 scale."
                )
            )
            label_norm_info.set_halign(Gtk.Align.START)
            label_norm_info.set_line_wrap(True)
            label_norm_info.set_max_width_chars(70)
            label_norm_info.get_style_context().add_class("dim-label")
            info_box.pack_start(label_norm_info, False, False, 0)

            osc_grid.attach(info_box, 0, 7, 2, 1)

            frame = Gtk.Frame(label=_("Active Dynamic Subscribers (Pub/Sub)"))
            frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            frame_box.set_margin_start(6)
            frame_box.set_margin_end(6)
            frame_box.set_margin_top(6)
            frame_box.set_margin_bottom(6)
            frame.add(frame_box)

            self.liststore_osc_subscribers = Gtk.ListStore(str, str, str, str, int)
            self.treeview_osc_subscribers = Gtk.TreeView(
                model=self.liststore_osc_subscribers
            )
            self.treeview_osc_subscribers.set_headers_visible(True)

            renderer_client = Gtk.CellRendererText()
            col_client = Gtk.TreeViewColumn(
                title=_("Client (IP:Port)"), cell_renderer=renderer_client
            )
            col_client.add_attribute(renderer_client, "text", 0)
            col_client.set_min_width(160)
            col_client.set_resizable(True)
            self.treeview_osc_subscribers.append_column(col_client)

            renderer_topics = Gtk.CellRendererText()
            col_topics = Gtk.TreeViewColumn(
                title=_("Topics"), cell_renderer=renderer_topics
            )
            col_topics.add_attribute(renderer_topics, "text", 1)
            col_topics.set_min_width(140)
            col_topics.set_resizable(True)
            self.treeview_osc_subscribers.append_column(col_topics)

            renderer_last = Gtk.CellRendererText()
            col_last = Gtk.TreeViewColumn(
                title=_("Last Contact"), cell_renderer=renderer_last
            )
            col_last.add_attribute(renderer_last, "text", 2)
            col_last.set_min_width(120)
            col_last.set_resizable(True)
            self.treeview_osc_subscribers.append_column(col_last)

            scrolled = Gtk.ScrolledWindow()
            scrolled.set_hexpand(True)
            scrolled.set_vexpand(True)
            scrolled.set_min_content_height(140)
            scrolled.add(self.treeview_osc_subscribers)
            frame_box.pack_start(scrolled, True, True, 0)

            action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            self.label_osc_subscribers_count = Gtk.Label(
                label=_("Total: 0 active client(s)")
            )
            self.label_osc_subscribers_count.set_halign(Gtk.Align.START)
            action_box.pack_start(self.label_osc_subscribers_count, True, True, 0)

            btn_disconnect = Gtk.Button(label=_("Disconnect Selection"))
            btn_disconnect.connect("clicked", self._on_disconnect_subscriber_clicked)
            action_box.pack_end(btn_disconnect, False, False, 0)

            btn_refresh = Gtk.Button(label=_("Refresh"))
            btn_refresh.connect("clicked", lambda _b: self._refresh_osc_subscribers())
            action_box.pack_end(btn_refresh, False, False, 0)

            frame_box.pack_start(action_box, False, False, 0)
            osc_grid.attach(frame, 0, 8, 2, 1)
            frame.show_all()

            GLib.timeout_add_seconds(2, self._refresh_osc_subscribers)

    def _midi(self, builder: Gtk.Builder) -> None:
        # List of MIDI Controllers
        liststore_modes = Gtk.ListStore(str)
        for item in ["Absolute", "Relative1", "Relative2", "Relative3 (Makie)"]:
            liststore_modes.append([item])
        midi_grid = typing.cast(Gtk.Grid, builder.get_object("midi_io_grid"))
        midi_grid.set_orientation(Gtk.Orientation.VERTICAL)
        self.liststore_midi = Gtk.ListStore(str, bool, str, str)
        treeview = Gtk.TreeView(model=self.liststore_midi)
        self._populate_midi_ports()
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn(
            title=_("MIDI Port"), cell_renderer=renderer_text
        )
        column_text.add_attribute(renderer_text, "text", 0)
        treeview.append_column(column_text)
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_midi_toggle)
        column_toggle = Gtk.TreeViewColumn(
            title=_("Active"), cell_renderer=renderer_toggle
        )
        column_toggle.add_attribute(renderer_toggle, "active", 1)
        treeview.append_column(column_toggle)
        renderer_combo = Gtk.CellRendererCombo()
        renderer_combo.set_property("editable", True)
        renderer_combo.set_property("model", liststore_modes)
        renderer_combo.set_property("text-column", 0)
        renderer_combo.set_property("has-entry", False)
        renderer_combo.connect("edited", self.on_combo_change)
        column_combo = Gtk.TreeViewColumn(
            title=_("Rotary encoder Mode"), cell_renderer=renderer_combo
        )
        column_combo.add_attribute(renderer_combo, "text", 2)
        treeview.append_column(column_combo)
        midi_grid.add(treeview)

    def _get_midi_port_mode(self, port_name: str) -> str:
        """Get the display mode name for a MIDI port from settings."""
        if port_name in self.settings.get_strv("relative1"):
            return "Relative1"
        if port_name in self.settings.get_strv("relative2"):
            return "Relative2"
        if port_name in self.settings.get_strv("makie"):
            return "Relative3 (Makie)"
        if port_name in self.settings.get_strv("absolute"):
            return "Absolute"
        return "Relative3 (Makie)"

    def _populate_midi_ports(self) -> None:
        default = self.settings.get_strv("midi-ports")
        ports_list = []
        if self.midi is not None and self.midi.ports is not None:
            ports_list = self.midi.ports.mido_ports or []
        for midi_port in sorted(list(set(ports_list))):
            if midi_port in default:
                mode = self._get_midi_port_mode(midi_port)
                self.liststore_midi.append(
                    [midi_port.split(":")[0], True, mode, midi_port]
                )
            else:
                self.liststore_midi.append(
                    [midi_port.split(":")[0], False, "", midi_port]
                )

    def refresh(self) -> None:
        """Refresh MIDI ports and show-scoped settings"""
        if hasattr(self, "liststore_midi"):
            self.liststore_midi.clear()
            self._populate_midi_ports()
        core = getattr(self.app, "core", None)
        lightshow = getattr(core, "lightshow", None) if core is not None else None
        hp = getattr(lightshow, "home_preset", None)
        self.update_home_preset_ui(hp)
        fader_bank = (
            getattr(lightshow, "fader_bank", None) if lightshow is not None else None
        )
        max_pages = getattr(fader_bank, "max_fader_page", 10)
        self.update_fader_pages_ui(max_pages)
        skip_empty = bool(getattr(fader_bank, "skip_empty_pages", False))
        self.update_skip_empty_fader_pages_ui(skip_empty)

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Tab on close clicked"""
        if self.tabs is not None:
            self.tabs.close("settings")

    def on_combo_change(self, _widget: Gtk.Widget, path: str, text: str) -> None:
        """Change rotatives mode

        Args:
            _widget: Widget clicked
            path: Path to combo
            text: New combo's text
        """
        self.liststore_midi[path][2] = text
        port_name = self.liststore_midi[path][3]
        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("midi.set_port_mode", port_name, text)

    def on_midi_toggle(self, _widget: Gtk.Widget, path: str) -> None:
        """Active / Inactive MIDI controllers

        Args:
            _widget: Widget clicked
            path: button number
        """
        port_name = self.liststore_midi[path][3]
        new_state = not self.liststore_midi[path][1]
        self.liststore_midi[path][1] = new_state
        if new_state:
            mode = self._get_midi_port_mode(port_name)
            self.liststore_midi.set_value(self.liststore_midi.get_iter(path), 2, mode)
            has_mode = any(
                port_name in self.settings.get_strv(m)
                for m in ("relative1", "relative2", "makie", "absolute")
            )
            if (
                not has_mode
                and self.app.core is not None
                and hasattr(self.app.core, "action_registry")
            ):
                self.app.core.action_registry.execute(
                    "midi.set_port_mode", port_name, "Relative3 (Makie)"
                )
        else:
            self.liststore_midi.set_value(self.liststore_midi.get_iter(path), 2, "")

        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute(
                "midi.port_toggle", port_name, new_state
            )

    def update_midi_port_toggle(self, port_name: str, enable: bool) -> None:
        """Update MIDI port toggle state from external action or undo/redo."""
        if not hasattr(self, "liststore_midi"):
            return
        for row in self.liststore_midi:
            if row[3] == port_name:
                row[1] = enable
                row[2] = self._get_midi_port_mode(port_name) if enable else ""
                break

    def update_midi_port_mode(self, port_name: str, mode: str) -> None:
        """Update MIDI port encoder mode from external action or undo/redo."""
        if not hasattr(self, "liststore_midi"):
            return
        display_mode = mode
        lower = mode.lower()
        if "makie" in lower or "mackie" in lower or "relative3" in lower:
            display_mode = "Relative3 (Makie)"
        elif "relative1" in lower:
            display_mode = "Relative1"
        elif "relative2" in lower:
            display_mode = "Relative2"
        elif "absolute" in lower:
            display_mode = "Absolute"
        for row in self.liststore_midi:
            if row[3] == port_name:
                row[2] = display_mode
                break

    def _artnet(self, builder: Gtk.Builder) -> None:
        # pylint: disable=too-many-locals
        self.liststore_artnet = Gtk.ListStore(str, str, str, str)
        treeview = Gtk.TreeView(model=self.liststore_artnet)

        renderer_text_name = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn(
            title=_("Name"), cell_renderer=renderer_text_name
        )
        column_name.add_attribute(renderer_text_name, "text", 0)
        treeview.append_column(column_name)

        renderer_text_ip = Gtk.CellRendererText()
        column_ip = Gtk.TreeViewColumn(
            title=_("IP Address"), cell_renderer=renderer_text_ip
        )
        column_ip.add_attribute(renderer_text_ip, "text", 1)
        treeview.append_column(column_ip)

        renderer_text_type = Gtk.CellRendererText()
        column_type = Gtk.TreeViewColumn(
            title=_("Type"), cell_renderer=renderer_text_type
        )
        column_type.add_attribute(renderer_text_type, "text", 2)
        treeview.append_column(column_type)

        renderer_text_univ = Gtk.CellRendererText()
        column_univ = Gtk.TreeViewColumn(
            title=_("Universes"), cell_renderer=renderer_text_univ
        )
        column_univ.add_attribute(renderer_text_univ, "text", 3)
        treeview.append_column(column_univ)

        artnet_grid = typing.cast(Gtk.Grid, builder.get_object("artnet_grid"))
        if artnet_grid:
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_hexpand(True)
            scrolled_window.set_vexpand(True)
            scrolled_window.add(treeview)
            artnet_grid.attach(scrolled_window, 0, 1, 1, 1)
            scrolled_window.show_all()

            self.refresh_artnet()

    def refresh_artnet(self) -> None:
        """Refresh the Art-Net discovered devices list from CoreApplication."""
        if self.app is None or self.app.core is None:
            return

        new_state = self.app.core.get_artnet_devices()

        if self._last_artnet_state != new_state:
            self.liststore_artnet.clear()
            for row in new_state:
                self.liststore_artnet.append(row)
            self._last_artnet_state = new_state

    def _on_change_percent(self, widget: Gtk.SpinButton) -> None:
        lvl = widget.get_value_as_int()
        self.settings.set_value("percent-level", GLib.Variant("i", lvl))

    def _on_change_default_time(self, widget: Gtk.SpinButton) -> None:
        if getattr(self, "_updating_settings", False):
            return
        time = widget.get_value()
        if (
            self.app is not None
            and hasattr(self.app, "core")
            and self.app.core is not None
            and hasattr(self.app.core, "action_registry")
        ):
            self.app.core.action_registry.execute(
                "gui.set_default_time", default_time=time
            )
        else:
            self.settings.set_value("default-time", GLib.Variant("d", time))

    def _on_change_go_back_time(self, widget: Gtk.SpinButton) -> None:
        time = widget.get_value()
        self.settings.set_value("go-back-time", GLib.Variant("d", time))

    def _on_change_sneak_time(self, widget: Gtk.SpinButton) -> None:
        time = widget.get_value()
        self.settings.set_value("sneak-time", GLib.Variant("d", time))

    def _on_change_channel_check_level(self, widget: Gtk.SpinButton) -> None:
        level = widget.get_value()
        schema = getattr(self.settings.props, "settings_schema", None)
        if schema is None or schema.has_key("channel-check-level"):
            self.settings.set_value("channel-check-level", GLib.Variant("d", level))

    def _on_change_home_preset(self, widget: Gtk.SpinButton) -> None:
        if getattr(self, "_updating_settings", False):
            return
        val = round(widget.get_value(), 1)
        target: float | None = val if val > 0.0 else None
        core = getattr(self.app, "core", None)
        if core is not None and hasattr(core, "action_registry"):
            lightshow = getattr(core, "lightshow", None)
            current = getattr(lightshow, "home_preset", None)
            if current != target:
                core.action_registry.execute(
                    "show.set_home_preset", preset_number=target
                )

    def _confirm_fader_pages_reduction(
        self,
        new_count: int,
        populated: list[tuple[int, int, typing.Any, str]],
    ) -> bool:
        """Prompt user before reducing pages when populated faders would be lost."""
        pages_str = ", ".join(str(p) for p in sorted({p for p, _, _, _ in populated}))
        dialog = Gtk.MessageDialog(
            transient_for=getattr(self.app, "window", None),
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=_("Reduce Fader Pages?"),
        )
        dialog.format_secondary_text(
            _(
                "{count} configured fader(s) on page(s) {pages} will be lost "
                "if you reduce the number of pages to {target}. "
                "Do you want to continue?"
            ).format(count=len(populated), pages=pages_str, target=new_count)
        )
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def _on_change_fader_pages(self, widget: Gtk.SpinButton) -> None:
        if getattr(self, "_updating_settings", False):
            return
        new_count = widget.get_value_as_int()
        core = getattr(self.app, "core", None)
        lightshow = getattr(core, "lightshow", None) if core is not None else None
        fader_bank = (
            getattr(lightshow, "fader_bank", None) if lightshow is not None else None
        )
        if core is None or fader_bank is None or not hasattr(core, "action_registry"):
            return
        current_count = getattr(fader_bank, "max_fader_page", 10)
        if new_count == current_count:
            return
        if new_count < current_count:
            populated = fader_bank.get_populated_faders_above_page(new_count)
            if populated and not self._confirm_fader_pages_reduction(
                new_count, populated
            ):
                self.update_fader_pages_ui(current_count)
                return
        core.action_registry.execute("fader.set_page_count", page_count=new_count)

    def _on_toggle_skip_empty_fader_pages(
        self, _widget: Gtk.Switch, state: bool
    ) -> bool:
        if getattr(self, "_updating_settings", False):
            return False
        core = getattr(self.app, "core", None)
        lightshow = getattr(core, "lightshow", None) if core is not None else None
        fader_bank = (
            getattr(lightshow, "fader_bank", None) if lightshow is not None else None
        )
        if (
            core is not None
            and fader_bank is not None
            and hasattr(core, "action_registry")
        ):
            if bool(getattr(fader_bank, "skip_empty_pages", False)) != bool(state):
                core.action_registry.execute(
                    "fader.set_skip_empty_pages", skip_empty=bool(state)
                )
        return False

    def _update_ui_percent(self, _widget: Gtk.Switch, state: bool) -> bool:
        """Change levels view (0-100) or (0-255)

        Args:
            _widget: Gtk.Switch widget
            state: State of the toggle

        Returns:
            Always False for event handler.
        """
        if getattr(self, "_updating_settings", False):
            return False
        if (
            self.app is not None
            and hasattr(self.app, "core")
            and self.app.core is not None
            and hasattr(self.app.core, "action_registry")
        ):
            self.app.core.action_registry.execute(
                "gui.set_percent_display", percent=state
            )
        else:
            self.settings.set_value("percent", GLib.Variant("b", state))
            if self.app is not None and self.app.window is not None:
                self.app.window.live_view.channels_view.update()
        return False

    def _switch_osc(self, _widget: Gtk.Switch, state: bool) -> None:
        if getattr(self, "_updating_settings", False):
            return
        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("osc.toggle", state)

    def _switch_static_client(self, _widget: Gtk.Switch, state: bool) -> None:
        if getattr(self, "_updating_settings", False):
            return
        if hasattr(self, "entry_client_ip") and self.entry_client_ip is not None:
            self.entry_client_ip.set_sensitive(state)
        if hasattr(self, "spin_client_port") and self.spin_client_port is not None:
            self.spin_client_port.set_sensitive(state)

        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("osc.toggle_static_client", state)

    def _client_port_changed(self, widget: Gtk.SpinButton) -> None:
        if getattr(self, "_updating_settings", False):
            return
        port = widget.get_value_as_int()
        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("osc.set_config", client_port=port)

    def _server_port_changed(self, widget: Gtk.SpinButton) -> None:
        if getattr(self, "_updating_settings", False):
            return
        port = widget.get_value_as_int()
        if self.app.core is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute("osc.set_config", server_port=port)

    def _on_client_ip_focus_out(
        self, widget: Gtk.Entry, _event: Gdk.EventFocus
    ) -> bool:
        self._client_ip_changed(widget)
        return False

    def _client_ip_changed(self, widget: Gtk.Entry) -> None:
        if getattr(self, "_updating_settings", False):
            return
        ip_addr = widget.get_text()
        if self._is_ip(ip_addr):
            if ip_addr != self.settings.get_string("osc-host"):
                if self.app.core is not None and hasattr(
                    self.app.core, "action_registry"
                ):
                    self.app.core.action_registry.execute(
                        "osc.set_config", host=ip_addr
                    )
            parent = self.get_parent()
            if parent:
                parent.grab_focus()
        else:
            widget.set_text(self.settings.get_string("osc-host"))

    def update_osc_config(self, host: str, client_port: int, server_port: int) -> None:
        """Update OSC widgets from external config change or undo/redo."""
        self._updating_settings = True
        try:
            if (
                host
                and hasattr(self, "entry_client_ip")
                and self.entry_client_ip.get_text() != host
            ):
                self.entry_client_ip.set_text(host)
            if client_port > 0 and hasattr(self, "spin_client_port"):
                if (
                    self.spin_client_port.get_value_as_int() != client_port
                    or self.spin_client_port.get_text() != str(client_port)
                ):
                    self.spin_client_port.set_value(client_port)
            if server_port > 0 and hasattr(self, "spin_server_port"):
                if (
                    self.spin_server_port.get_value_as_int() != server_port
                    or self.spin_server_port.get_text() != str(server_port)
                ):
                    self.spin_server_port.set_value(server_port)
        finally:
            self._updating_settings = False

    def update_osc_toggle(self, state: bool) -> None:
        """Update OSC switch state from external toggle change or undo/redo."""
        self._updating_settings = True
        try:
            if hasattr(self, "switch_osc") and self.switch_osc.get_state() != state:
                self.switch_osc.set_state(state)
                self.switch_osc.set_active(state)
        finally:
            self._updating_settings = False

    def update_osc_static_client_toggle(self, state: bool) -> None:
        """Update static client switch and input sensitivity from undo/redo."""
        self._updating_settings = True
        try:
            if (
                hasattr(self, "switch_static_client")
                and self.switch_static_client is not None
            ):
                if self.switch_static_client.get_state() != state:
                    self.switch_static_client.set_state(state)
                    self.switch_static_client.set_active(state)
            if hasattr(self, "entry_client_ip") and self.entry_client_ip is not None:
                self.entry_client_ip.set_sensitive(state)
            if hasattr(self, "spin_client_port") and self.spin_client_port is not None:
                self.spin_client_port.set_sensitive(state)
        finally:
            self._updating_settings = False

    def update_osc_subscribers(self, subscribers: list[dict[str, typing.Any]]) -> None:
        """Update subscribers TreeView with current active subscribers."""
        if not hasattr(self, "liststore_osc_subscribers"):
            return

        self.liststore_osc_subscribers.clear()
        now = time.time()
        active_count = 0

        for sub in subscribers:
            host = sub.get("host", "")
            port = sub.get("port", 0)
            topics = sub.get("topics", [])
            last_seen = sub.get("last_seen", now)
            is_static = sub.get("is_static", False)

            if is_static:
                topics_str = ", ".join(topics) + " [Static]"
                elapsed_str = _("Persistent")
            else:
                topics_str = ", ".join(topics)
                elapsed = max(0, int(now - last_seen))
                elapsed_str = (
                    _("just now") if elapsed == 0 else _("about %ds ago") % elapsed
                )

            endpoint_str = f"{host}:{port}"
            self.liststore_osc_subscribers.append(
                [endpoint_str, topics_str, elapsed_str, host, port]
            )
            active_count += 1

        if hasattr(self, "label_osc_subscribers_count"):
            self.label_osc_subscribers_count.set_text(
                _("Total: %d active client(s)") % active_count
            )

    def _refresh_osc_subscribers(self) -> bool:
        """Periodic refresh of active OSC subscribers and mDNS status."""
        if not self.tabs or not self.tabs.tabs.get("settings"):
            return False

        core_app = getattr(self.app, "core", None)
        osc = getattr(core_app, "osc", None) if core_app is not None else None
        if hasattr(self, "label_osc_mdns") and self.label_osc_mdns is not None:
            if (
                osc is not None
                and getattr(osc, "mdns", None) is not None
                and osc.mdns.is_active
            ):
                port = getattr(osc.mdns, "port", 9000)
                http_port = getattr(osc.mdns, "http_port", None)
                name = getattr(osc.mdns, "service_name", "Open Lighting Console")
                title = _("mDNS Discovery:")
                oscq_suffix = f" • OSCQuery :{http_port}" if http_port else ""
                self.label_osc_mdns.set_markup(
                    f"<span foreground='#2ec27e'>●</span> <b>{title}</b> "
                    f"{name}._osc._udp.local (Port {port}){oscq_suffix}"
                )
            else:
                title = _("mDNS Discovery:")
                inactive_msg = _("Inactive (OSC server stopped)")
                self.label_osc_mdns.set_markup(
                    f"<span foreground='#888888'>○</span> <b>{title}</b> "
                    f"<i>{inactive_msg}</i>"
                )

        if osc is None:
            return True

        osc.subscriptions.cleanup_expired(60.0)
        snapshots = osc.subscriptions.get_subscribers_snapshot()
        self.update_osc_subscribers(snapshots)
        return True

    def _on_disconnect_subscriber_clicked(self, _widget: Gtk.Button) -> None:
        """Evict selected OSC subscriber."""
        if not hasattr(self, "treeview_osc_subscribers"):
            return
        selection = self.treeview_osc_subscribers.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            host = model.get_value(tree_iter, 3)
            port = model.get_value(tree_iter, 4)
            if self.app.core is not None and hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute(
                    "osc.remove_subscriber", host, port
                )

    def update_percent_ui(self, percent: bool) -> None:
        """Update percent display switch from external event or undo/redo."""
        self._updating_settings = True
        try:
            if hasattr(self, "switch_percent") and self.switch_percent is not None:
                if self.switch_percent.get_state() != percent:
                    self.switch_percent.set_state(percent)
                    self.switch_percent.set_active(percent)
        finally:
            self._updating_settings = False

    def update_default_time_ui(self, default_time: float) -> None:
        """Update default time spin button from external event or undo/redo."""
        self._updating_settings = True
        try:
            if (
                hasattr(self, "spin_default_time")
                and self.spin_default_time is not None
            ):
                if self.spin_default_time.get_value() != default_time:
                    self.spin_default_time.set_value(default_time)
        finally:
            self._updating_settings = False

    def update_home_preset_ui(self, preset_number: float | None) -> None:
        """Update Home Preset spin button from external event or undo/redo."""
        self._updating_settings = True
        try:
            if hasattr(self, "spin_home_preset") and self.spin_home_preset is not None:
                target_val = (
                    float(preset_number)
                    if preset_number is not None and preset_number > 0.0
                    else 0.0
                )
                if abs(self.spin_home_preset.get_value() - target_val) > 1e-6:
                    self.spin_home_preset.set_value(target_val)
        finally:
            self._updating_settings = False

    def update_fader_pages_ui(self, page_count: int) -> None:
        """Update Fader Pages spin button from external event or undo/redo."""
        self._updating_settings = True
        try:
            if hasattr(self, "spin_fader_pages") and self.spin_fader_pages is not None:
                if self.spin_fader_pages.get_value_as_int() != int(page_count):
                    self.spin_fader_pages.set_value(float(page_count))
        finally:
            self._updating_settings = False

    def update_skip_empty_fader_pages_ui(self, skip_empty: bool) -> None:
        """Update Skip Empty Fader Pages switch from external event or undo/redo."""
        self._updating_settings = True
        try:
            sw = getattr(self, "switch_skip_empty_fader_pages", None)
            if sw is not None and sw.get_state() != bool(skip_empty):
                sw.set_state(bool(skip_empty))
                sw.set_active(bool(skip_empty))
        finally:
            self._updating_settings = False

    def _is_ip(self, string: str) -> bool:
        try:
            ipaddress.ip_address(string)
            return True
        except ValueError:
            return False


__all__ = ["SettingsTab"]

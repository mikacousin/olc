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

import contextlib
import typing
from typing import Callable

from gi.repository import Gdk, Gio, GLib, Gtk

from olc.define import MAX_CHANNELS, string_to_time, time_to_string
from olc.gtk3.widgets.commandline import CommandLineWidget
from olc.gtk3.widgets.main_fader import MainFaderWidget
from olc.gtk3.window_channels import LiveView
from olc.gtk3.window_playback import MainPlaybackView

if typing.TYPE_CHECKING:
    import olc.gtk3.window
    from olc.gtk3.application import Application
    from olc.gtk3.tabs_manager import Tabs
    from olc.gtk3.widgets.channels_view import ChannelsView


# pylint: disable=too-many-instance-attributes
class Window(Gtk.ApplicationWindow):
    """Main Window"""

    @property
    def app(self) -> Application:
        """Get parent application instance safely."""
        app = self.get_application()
        return typing.cast("Application", app)

    def __init__(self, app: Gtk.Application, tabs: Tabs) -> None:
        # Full screen
        self.full = False
        self.tabs_manager = tabs
        self.block_switch_page = 0

        super().__init__(title="Open Lighting Console", application=app)
        self.set_default_size(1400, 1080)
        self.set_name("olc")
        self.connect("delete-event", self.app.exit)
        self.key_controller = Gtk.EventControllerKey.new(self)
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect("key-pressed", self._on_key_controller_pressed)

        # Header Bar
        self.header = Gtk.HeaderBar(title="Open Lighting Console")
        self.header.set_subtitle("")
        self.header.props.show_close_button = True
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Main Fader viewer
        self.main_fader = MainFaderWidget(self.app.core.backend)
        box.add(self.main_fader)
        # Menu button
        button = Gtk.MenuButton()
        icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.add(image)
        box.add(button)
        popover = Gtk.Popover.new_from_model(button, self.app.setup_app_menu())
        button.set_popover(popover)
        self.header.pack_end(box)
        self.set_titlebar(self.header)

        # Paned
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(800)

        # Channels
        self.live_view = LiveView(
            typing.cast("olc.gtk3.window.Window", self), self.tabs_manager
        )
        paned_chan = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned_chan.set_position(1100)
        paned_chan.pack1(self.live_view, resize=True, shrink=False)
        # Gtk.Statusbar to display keyboard's keys
        self.commandline_widget = CommandLineWidget(self.app)
        paned_chan.pack2(self.commandline_widget.widget, resize=True, shrink=False)
        paned.pack1(paned_chan, resize=True, shrink=False)

        # Main Playback
        self.playback = MainPlaybackView(self.app)
        paned.pack2(self.playback, resize=True, shrink=False)

        self.add(paned)

        self.live_view.connect("page-reordered", self._on_page_reordered, "live")
        self.playback.connect("page-reordered", self._on_page_reordered, "playback")

        self.live_view.connect("page-added", self._on_page_added, "live")
        self.playback.connect("page-added", self._on_page_added, "playback")

        self.live_view.connect("switch-page", self._on_switch_page, "live")
        self.playback.connect("switch-page", self._on_switch_page, "playback")

        self.set_icon_name("olc")

    def get_active_tab(self) -> Gtk.Paned | None:
        """Get active tab

        Returns:
            Active tab
        """
        widget = self.get_focus()
        while widget:
            if widget in (self.live_view, self.playback):
                break
            widget = widget.get_parent()
        if not widget:
            return None
        notebook_id = "live" if widget is self.live_view else "playback"
        if self.app.core.tabs:
            self.app.core.tabs.active_notebook = notebook_id
        any_widget = typing.cast(typing.Any, widget)
        return any_widget.get_nth_page(any_widget.get_current_page())

    def toggle_focus(self) -> None:
        """Toggle focus Left/Right"""
        focus = self.get_focus()
        if focus is self.live_view:
            self.playback.grab_focus()
        else:
            self.live_view.grab_focus()

    def fullscreen_toggle(
        self,
        _action: Gio.SimpleAction | None = None,
        _param: GLib.Variant | None = None,
    ) -> None:
        """Toggle full screen"""
        if self.full:
            self.unfullscreen()
            self.full = False
        else:
            self.fullscreen()
            self.full = True

    def move_tab(self) -> None:
        """Move focused tab on next notebook"""
        focus = typing.cast(typing.Any, self.get_focus())
        if focus not in (self.live_view, self.playback):
            return
        page = focus.get_current_page()
        if page < 0:
            return
        child = focus.get_nth_page(page)
        tab_name = None
        if child is self.playback.grid:
            tab_name = "playback"
        elif child is self.live_view.channels_view:
            tab_name = "channels"
        else:
            if self.app.tabs:
                for name, widget in self.app.tabs.tabs.items():
                    if widget is child:
                        tab_name = name
                        break
        if tab_name is None:
            return

        from_nb = "live" if focus is self.live_view else "playback"
        to_nb = "playback" if focus is self.live_view else "live"
        new_index = len(self.app.core.tabs.notebooks[to_nb])

        self.app.core.action_registry.execute(
            "gui.tab_move", tab_name, from_nb, to_nb, new_index
        )

    def _on_page_reordered(
        self,
        _notebook: Gtk.Notebook,
        child: Gtk.Widget,
        page_num: int,
        notebook_id: str,
    ) -> None:
        """Handle manual tab drag and drop reordering by executing Core Action."""
        tab_name = None
        if child is self.playback.grid:
            tab_name = "playback"
        elif child is self.live_view.channels_view:
            tab_name = "channels"
        else:
            if self.app.tabs:
                for name, widget in self.app.tabs.tabs.items():
                    if widget is child:
                        tab_name = name
                        break
        if tab_name is None:
            return

        logical_index = page_num

        if tab_name in self.app.core.tabs.notebooks[notebook_id]:
            current_index = self.app.core.tabs.notebooks[notebook_id].index(tab_name)
            if current_index != logical_index:
                self.app.core.action_registry.execute(
                    "gui.tab_move", tab_name, notebook_id, notebook_id, logical_index
                )

    def _on_page_added(
        self,
        _notebook: Gtk.Notebook,
        child: Gtk.Widget,
        page_num: int,
        notebook_id: str,
    ) -> None:
        """Handle manual tab drag and drop between notebooks."""
        if self.block_switch_page > 0:
            return

        tab_name = None
        if child is self.playback.grid:
            tab_name = "playback"
        elif child is self.live_view.channels_view:
            tab_name = "channels"
        else:
            if self.app.tabs:
                for name, widget in self.app.tabs.tabs.items():
                    if widget is child:
                        tab_name = name
                        break

        if tab_name is None:
            return

        if self.app.core.tabs:
            from_nb = self.app.core.tabs.get_notebook_of_tab(tab_name)
            if from_nb is not None and from_nb != notebook_id:
                self.app.core.action_registry.execute(
                    "gui.tab_move", tab_name, from_nb, notebook_id, page_num
                )

    @contextlib.contextmanager
    def blocking_switch_page(self) -> typing.Generator[None]:
        """Context manager to block switch-page signals."""
        self.block_switch_page += 1
        try:
            yield
        finally:
            self.block_switch_page -= 1

    def _on_switch_page(
        self,
        _notebook: Gtk.Notebook,
        page: Gtk.Widget,
        page_num: int,
        notebook_id: str,
    ) -> None:
        """Handle manual tab switch by the user."""
        if self.block_switch_page > 0 or page_num < 0:
            return

        if self.app.core.tabs:
            self.app.core.tabs.active_notebook = notebook_id

        tab_name = None
        if page is self.playback.grid:
            tab_name = "playback"
        elif page is self.live_view.channels_view:
            tab_name = "channels"
        else:
            if self.app.tabs:
                for name, widget in self.app.tabs.tabs.items():
                    if widget is page:
                        tab_name = name
                        break

        if tab_name is None:
            return

        if self.app.core.tabs.active_tabs.get(notebook_id) != tab_name:
            self.app.core.action_registry.execute("gui.tab_open", tab_name, notebook_id)

    def update_channels_display(self, step: int) -> None:
        """Update Channels levels display

        Args:
            step: Step
        """
        from olc.core.tracking import (  # pylint: disable=import-outside-toplevel
            classify_channel_tracking_state,
            get_tracking_color,
        )

        main_pb = self.app.core.lightshow.main_playback
        dmx = self.app.core.backend.dmx if self.app.core.backend is not None else None

        for channel in range(1, MAX_CHANNELS + 1):
            state, level = classify_channel_tracking_state(main_pb, step, channel)
            color_level = get_tracking_color(state)
            if dmx is not None and step == main_pb.position:
                comp_level, comp_color = dmx.get_composite_level(channel - 1)
                if comp_level > 0 or dmx.levels["user"][channel - 1] != -1:
                    level = comp_level
                    color_level = comp_color
            next_level = main_pb.get_next_channel_level(channel, level)
            widget = self.live_view.channels_view.get_channel_widget(channel)
            if widget is not None:
                widget.color_level = color_level
                widget.level = level
                widget.next_level = next_level
                widget.queue_draw()

    def _get_active_page(self) -> Gtk.Widget | None:
        """Return the currently active notebook page widget."""
        page = self.get_active_tab()
        if page is not None:
            return page
        active_nb = "live"
        if hasattr(self.app, "core") and self.app.core.tabs:
            active_nb = getattr(self.app.core.tabs, "active_notebook", "live") or "live"
        notebook = self.playback if active_nb == "playback" else self.live_view
        idx = notebook.get_current_page()
        if idx >= 0:
            return notebook.get_nth_page(idx)
        return None

    def _get_active_channels_view(self) -> ChannelsView:
        """Return the ChannelsView of the focused notebook page, or live_view's."""
        page = self._get_active_page()
        if page is not None:
            cv = getattr(page, "channels_view", None)
            if cv is not None:
                return typing.cast("ChannelsView", cv)
            if hasattr(page, "toggle_view_mode") and hasattr(page, "select_all"):
                return typing.cast("ChannelsView", page)
        return self.live_view.channels_view

    def _is_editing_tab_focused(self) -> bool:
        """Return True if the active page is an editing tab."""
        page = self._get_active_page()
        return page is not None and page not in (
            self.live_view.channels_view,
            self.playback.grid,
        )

    def _handle_modifier_shortcuts(  # pylint: disable=too-many-return-statements
        self, keyval: int, modifiers: int
    ) -> bool:
        """Handle Ctrl / Alt keyboard shortcuts before GTK accelerators."""
        if modifiers == int(Gdk.ModifierType.CONTROL_MASK):
            if keyval in (Gdk.KEY_f, Gdk.KEY_F):
                cv = self._get_active_channels_view()
                cv.toggle_view_mode()
                cv.grab_focus()
                return True
            if keyval in (Gdk.KEY_a, Gdk.KEY_A):
                cv = self._get_active_channels_view()
                cv.select_all()
                cv.grab_focus()
                return True
            if keyval == Gdk.KEY_Up:
                cv = self._get_active_channels_view()
                cv.level_plus()
                cv.update()
                return True
            if keyval == Gdk.KEY_Down:
                cv = self._get_active_channels_view()
                cv.level_minus()
                cv.update()
                return True
        elif modifiers == int(Gdk.ModifierType.MOD1_MASK):
            if keyval == Gdk.KEY_Up:
                if self._is_editing_tab_focused():
                    page = self._get_active_page()
                    if page is not None and (
                        func := getattr(page, "_keypress_q", None)
                    ):
                        func()
                        return True
                self.app.core.action_registry.execute("playback.sequence_minus")
                self.app.core.action_registry.execute("commandline.clear")
                return True
            if keyval == Gdk.KEY_Down:
                if self._is_editing_tab_focused():
                    page = self._get_active_page()
                    if page is not None and (
                        func := getattr(page, "_keypress_w", None)
                    ):
                        func()
                        return True
                self.app.core.action_registry.execute("playback.sequence_plus")
                self.app.core.action_registry.execute("commandline.clear")
                return True
        return False

    def _handle_navigation_keys(  # pylint: disable=too-many-return-statements,too-many-branches
        self, keyval: int, modifiers: int
    ) -> bool | None:
        """Handle navigation and function keys (arrows, PageUp/Down, F2, Delete)."""
        if modifiers == int(Gdk.ModifierType.SHIFT_MASK):
            if keyval == Gdk.KEY_Up:
                self.app.core.action_registry.execute("commandline.history_prev")
                return True
            if keyval == Gdk.KEY_Down:
                self.app.core.action_registry.execute("commandline.history_next")
                return True

        if keyval == Gdk.KEY_F2 and modifiers == 0:
            page = self._get_active_page()
            if page is not None and hasattr(page, "rename_selected"):
                typing.cast(typing.Any, page).rename_selected()
                return True
            return False

        if keyval not in (
            Gdk.KEY_Up,
            Gdk.KEY_Down,
            Gdk.KEY_Left,
            Gdk.KEY_Right,
            Gdk.KEY_Page_Up,
            Gdk.KEY_Page_Down,
            Gdk.KEY_Delete,
            Gdk.KEY_Insert,
        ):
            return None

        if self._is_editing_tab_focused():
            page = self._get_active_page()
            if page is None:
                return False
            stack = getattr(page, "stack", None)
            if (
                stack is not None
                and hasattr(stack, "get_visible_child_name")
                and stack.get_visible_child_name() == "devices"
            ):
                return False
            keyname = Gdk.keyval_name(keyval)
            if keyname:
                if func := getattr(page, f"_keypress_{keyname.lower()}", None):
                    func()
                    return True
                cv = getattr(page, "channels_view", None)
                if cv is not None and keyval in (Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
                    if cv_func := getattr(cv, f"_keypress_{keyname.lower()}", None):
                        cv_func()
                        return True
            return False

        if keyval == Gdk.KEY_Up:
            self.app.core.action_registry.execute("commandline.history_prev")
            return True
        if keyval == Gdk.KEY_Down:
            self.app.core.action_registry.execute("commandline.history_next")
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Down):
            self.live_view.channels_view.select_previous()
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Up):
            self.live_view.channels_view.select_next()
            return True
        return False

    def _clear_on_escape(self) -> None:
        """Clear command line and unselect channels on Escape."""
        self.app.core.action_registry.execute("commandline.clear")
        self.live_view.channels_view.flowbox.unselect_all()
        self.live_view.channels_view.last_selected_channel = ""
        active_cv = self._get_active_channels_view()
        if active_cv is not self.live_view.channels_view:
            active_cv.flowbox.unselect_all()
            active_cv.last_selected_channel = ""
        if self.app.tabs and "track_channels" in self.app.tabs.tabs:
            tc = typing.cast(typing.Any, self.app.tabs.tabs["track_channels"])
            if tc:
                tc.update_display()

    def _on_key_controller_pressed(  # pylint: disable=too-many-return-statements,too-many-branches
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        """Handle window-level key press events via modern EventControllerKey.

        Returns True if the event was consumed, False to allow propagation.
        """
        modifiers = int(state) & Gtk.accelerator_get_default_mod_mask()

        # Universal GO shortcut (<Control>g) works everywhere, even in text entries
        if modifiers == int(Gdk.ModifierType.CONTROL_MASK) and keyval in (
            Gdk.KEY_g,
            Gdk.KEY_G,
        ):
            self.app.core.action_registry.execute("playback.go")
            return True

        focused = self.get_focus()
        if focused and isinstance(focused, (Gtk.Entry, Gtk.CellEditable)):
            return False

        if bool(
            modifiers & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)
        ):
            return self._handle_modifier_shortcuts(keyval, modifiers)

        # Spacebar triggers GO when the command line is empty, or appends a space
        if keyval == Gdk.KEY_space:
            if not self.app.core.commandline.get_string().strip():
                self.app.core.action_registry.execute("playback.go")
            else:
                self.app.core.action_registry.execute("commandline.append_char", " ")
            return True

        # Command line validation / execution (ENTER)
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.app.core.action_registry.execute("commandline.execute")
            return True

        if keyval == Gdk.KEY_BackSpace:
            self.app.core.action_registry.execute("commandline.backspace")
            return True

        if keyval == Gdk.KEY_Escape:
            self._clear_on_escape()
            return True

        if keyval == Gdk.KEY_Tab:
            if self.app.core.commandline.get_string().strip():
                self.app.core.action_registry.execute("commandline.autocomplete")
                return True
            self.toggle_focus()
            return True

        if keyval == Gdk.KEY_ISO_Left_Tab:
            self.move_tab()
            return True

        nav_handled = self._handle_navigation_keys(keyval, modifiers)
        if nav_handled is not None:
            return nav_handled

        # Keypad digits (KP_0 .. KP_9)
        if Gdk.KEY_KP_0 <= keyval <= Gdk.KEY_KP_9:
            char = str(keyval - Gdk.KEY_KP_0)
            self.app.core.action_registry.execute("commandline.append_char", char)
            return True

        # Keypad operators
        if keyval == Gdk.KEY_KP_Decimal:
            self.app.core.action_registry.execute("commandline.append_char", ".")
            return True

        if keyval == Gdk.KEY_KP_Add:
            self.app.core.action_registry.execute("commandline.append_char", " + ")
            return True

        if keyval == Gdk.KEY_KP_Subtract:
            self.app.core.action_registry.execute("commandline.append_char", " - ")
            return True

        if keyval == Gdk.KEY_KP_Divide:
            self.app.core.action_registry.execute("commandline.append_char", " / ")
            return True

        # Printable Unicode characters (letters, numbers, symbols)
        unichar = Gdk.keyval_to_unicode(keyval)
        if unichar > 0:
            char = chr(unichar)
            if char.isprintable():
                self.app.core.action_registry.execute("commandline.append_char", char)
                return True

        return False

    def on_window_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        """Compatibility wrapper for legacy key-press event delegation."""
        focused = self.get_focus()
        if focused and isinstance(focused, (Gtk.Entry, Gtk.CellEditable)):
            return bool(focused.event(event))
        return False

    def on_key_press_event(
        self, _widget: Gtk.Widget | None, event: Gdk.EventKey
    ) -> Callable | bool:
        """Executed on key press event

        Args:
            event: Gdk.EventKey

        Returns:
            function() or False
        """
        state = getattr(event, "state", 0) or 0
        modifiers = int(state) & Gtk.accelerator_get_default_mod_mask()
        if bool(
            modifiers & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)
        ):
            return False

        keyname = Gdk.keyval_name(event.keyval)

        if keyname is None:
            return False

        if keyname in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            self.app.core.action_registry.execute("commandline.append_char", keyname)

        if keyname in (
            "KP_1",
            "KP_2",
            "KP_3",
            "KP_4",
            "KP_5",
            "KP_6",
            "KP_7",
            "KP_8",
            "KP_9",
            "KP_0",
        ):
            self.app.core.action_registry.execute(
                "commandline.append_char", keyname[3:]
            )

        if keyname == "period":
            self.app.core.action_registry.execute("commandline.append_char", ".")

        # Channels View
        self.live_view.channels_view.on_key_press(keyname)

        if func := getattr(self, f"_keypress_{keyname.lower()}", None):
            return func()
        return False

    def _keypress_exclam(self) -> None:
        """Level + (% level) of selected channels"""
        self.live_view.channels_view.level_plus()

    def _keypress_colon(self) -> None:
        """Level - (% level) of selected channels"""
        self.live_view.channels_view.level_minus()

    def _keypress_kp_enter(self) -> None:
        """@ Level"""
        self._keypress_equal()

    def _keypress_equal(self) -> None:
        """@ Level"""
        self.live_view.channels_view.at_level()
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_backspace(self) -> None:
        """Empty keys buffer"""
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_escape(self) -> None:
        """Deselect all channels"""
        self.live_view.channels_view.flowbox.unselect_all()
        self.live_view.channels_view.last_selected_channel = ""
        if self.app.tabs is not None:
            track_channels = typing.cast(
                typing.Any, self.app.tabs.tabs["track_channels"]
            )
            if track_channels:
                track_channels.update_display()

    def _keypress_q(self) -> None:
        """Seq -"""
        self.app.core.action_registry.execute("playback.sequence_minus")
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_w(self) -> None:
        """Seq +"""
        self.app.core.action_registry.execute("playback.sequence_plus")
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_g(self) -> None:
        """Goto"""
        self.app.core.action_registry.execute(
            "playback.goto", self.app.core.commandline.get_string()
        )
        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_r(self) -> None:
        """Record new Step and new Preset"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            self.app.core.action_registry.execute("playback.record_cue")
        else:
            mem = float(keystring)
            found, step = self.app.core.lightshow.main_playback.get_step(cue=mem)
            if not found:
                self.app.core.action_registry.execute(
                    "playback.record_cue", number=mem, step=step
                )
            else:
                self.app.core.action_registry.execute(
                    "playback.update_active_step", number=mem
                )

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_u(self) -> None:
        """Update Cue"""
        position = self.app.core.lightshow.main_playback.position
        step_obj = self.app.core.lightshow.main_playback.steps[position]
        cue = step_obj.cue
        if cue is None:
            return

        number = cue.number

        # Confirmation Dialog
        dialog = Dialog(self, number)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            self.app.core.action_registry.execute(
                "playback.update_active_step", number=number
            )

        dialog.destroy()

    def _keypress_t(self) -> None:
        """Change Time In and Time Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_time(time)
        self.playback.cues_liststore1[position + 3][5] = string
        self.playback.cues_liststore1[position + 3][7] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_in
        self.playback.sequential.time_out = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_out
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_i(self) -> None:
        """Change Time In of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_time_in(time)
        self.playback.cues_liststore1[position + 3][7] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_in
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_o(self) -> None:
        """Change Time Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_time_out(time)
        self.playback.cues_liststore1[position + 3][5] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.time_out = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].time_out
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_x(self) -> None:
        """Change Wait Time of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_wait(time)
        self.playback.cues_liststore1[position + 3][3] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.wait = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].wait
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_d(self) -> None:
        """Change Delay In and Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_delay(time)
        self.playback.cues_liststore1[position + 3][4] = string
        self.playback.cues_liststore1[position + 3][6] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].delay_in
        self.playback.sequential.delay_out = (
            self.app.core.lightshow.main_playback.steps[position + 1].delay_out
        )
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_k(self) -> None:
        """Change Delay In of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_delay_in(time)
        self.playback.cues_liststore1[position + 3][6] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_in = self.app.core.lightshow.main_playback.steps[
            position + 1
        ].delay_in
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")

    def _keypress_l(self) -> None:
        """Change Delay Out of next step"""
        keystring = self.app.core.commandline.get_string()
        if keystring == "":
            return

        position = self.app.core.lightshow.main_playback.position

        time = string_to_time(keystring)
        string = time_to_string(time)
        self.app.core.lightshow.main_playback.steps[position + 1].set_delay_out(time)
        self.playback.cues_liststore1[position + 3][4] = string
        self.playback.step_filter1.refilter()
        self.playback.sequential.delay_out = (
            self.app.core.lightshow.main_playback.steps[position + 1].delay_out
        )
        self.playback.sequential.total_time = (
            self.app.core.lightshow.main_playback.steps[position + 1].total_time
        )
        self.playback.grid.queue_draw()

        # Tag filename as modified
        self.app.core.lightshow.set_modified()

        self.app.core.action_registry.execute("commandline.clear")


class Dialog(Gtk.Dialog):
    """Confirmation dialog when updating a Cue."""

    def __init__(self, parent: Gtk.Window, number: float) -> None:
        super().__init__(title="", transient_for=parent)
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )

        self.set_default_size(150, 100)

        label = Gtk.Label(label=f"Update cue {number} ?")

        box = self.get_content_area()
        box.add(label)
        self.show_all()

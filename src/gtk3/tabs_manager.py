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

import copy
import typing

from gi.repository import Gtk

from olc.gtk3.widgets.channels_view import ChannelsView

if typing.TYPE_CHECKING:
    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.gtk3.channel_time import ChanneltimeTab
    from olc.gtk3.cue import CuesEditionTab
    from olc.gtk3.curve import CurvesTab
    from olc.gtk3.device_inspector import DeviceInspectorWidget
    from olc.gtk3.dmx_outputs import DMXOutputsTab
    from olc.gtk3.fader import FaderTab
    from olc.gtk3.fixture_library import FixtureLibraryTab
    from olc.gtk3.group import GroupTab
    from olc.gtk3.history import HistoryTab
    from olc.gtk3.independent import IndependentsTab
    from olc.gtk3.patch_channels import PatchChannelsTab
    from olc.gtk3.sequence import SequenceTab
    from olc.gtk3.track_channels import TrackChannelsTab
    from olc.gtk3.window import Window
    from olc.settings import SettingsTab

    TabWidget = (
        ChanneltimeTab
        | CuesEditionTab
        | CurvesTab
        | DeviceInspectorWidget
        | DMXOutputsTab
        | FaderTab
        | FixtureLibraryTab
        | GroupTab
        | HistoryTab
        | IndependentsTab
        | PatchChannelsTab
        | SequenceTab
        | SettingsTab
        | TrackChannelsTab
    )


class Tabs:
    """Tabs manager

    Attributes:
        tabs: Tabs defined by a unique name and widgets
    """

    tabs: dict[str, TabWidget | None]
    app: Application
    window: Window | None
    commandline: CoreCommandLine

    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = None
        self.commandline = app.core.commandline
        self.default_notebook_id = "playback"

        self.tabs = {
            "channel_time": None,
            "curves": None,
            "device_inspector": None,
            "faders": None,
            "fixtures": None,
            "groups": None,
            "history": None,
            "indes": None,
            "memories": None,
            "dmx_outputs": None,
            "patch_channels": None,
            "sequences": None,
            "settings": None,
            "track_channels": None,
        }

    def open(
        self,
        tab_name: str,
        widget: typing.Any,  # noqa: ANN401
        label: str,
        *args: object,
        notebook_id: str = "playback",
    ) -> None:
        """Open tab

        Args:
            tab_name: Tab name found in self.tabs
            widget: Widget to open
            label: Tab label
            *args: additional parameters
            notebook_id: Notebook container ID
        """
        if self.window is None:
            return
        if tab_name in ("playback", "channels"):
            tab = (
                self.window.playback.grid
                if tab_name == "playback"
                else self.window.live_view.channels_view
            )
            parent = tab.get_parent()
            if isinstance(parent, Gtk.Notebook):
                page = parent.page_num(tab)
                parent.set_current_page(page)
                parent.grab_focus()
            return

        if tab_name not in self.tabs:
            return
        nb_id = self.default_notebook_id if notebook_id == "playback" else notebook_id
        notebook = self.window.live_view if nb_id == "live" else self.window.playback
        if self.tabs[tab_name] is None:
            self.tabs[tab_name] = widget(*args)
            tab_any = typing.cast(typing.Any, self.tabs[tab_name])
            self._apply_tab_settings(tab_name, tab_any)
            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect(
                "clicked",
                tab_any.on_close_icon,
            )
            newlabel = Gtk.Box()
            newlabel.pack_start(Gtk.Label(label=label), False, False, 0)
            newlabel.pack_start(button, False, False, 0)
            newlabel.show_all()
            notebook.append_page(tab_any, newlabel)
            notebook.set_tab_reorderable(tab_any, True)
            notebook.set_tab_detachable(tab_any, True)
            self.window.show_all()
            notebook.set_current_page(-1)
        else:
            tab = self.tabs[tab_name]
            assert tab is not None
            parent = tab.get_parent()
            if isinstance(parent, Gtk.Notebook):
                notebook = parent
            page = notebook.page_num(tab)
            notebook.set_current_page(page)
        active_tab = self.tabs[tab_name]
        if active_tab is not None and hasattr(active_tab, "grab_focus"):
            active_tab.grab_focus()
        else:
            notebook.grab_focus()

    def close(self, tab_name: str) -> None:
        """Close tab by executing Core Action.

        Args:
            tab_name : Tab name found in self.tabs
        """
        if tab_name not in self.tabs:
            return
        if self.tabs[tab_name]:
            self.app.core.action_registry.execute("gui.tab_close", tab_name)

    def close_physically(self, tab_name: str) -> None:
        """Physically close and remove the tab widget.

        Args:
            tab_name: Tab name to remove.
        """
        if tab_name not in self.tabs:
            return
        if self.tabs[tab_name]:
            self.app.core.action_registry.execute("commandline.clear")
            tab = self.tabs[tab_name]
            assert tab is not None
            self._capture_tab_settings(tab_name, tab)
            cleanup_func = getattr(tab, "cleanup", None)
            if callable(cleanup_func):
                typing.cast(typing.Callable[[], None], cleanup_func)()
            notebook = tab.get_parent()
            if notebook is not None:
                notebook_nb = typing.cast(Gtk.Notebook, notebook)
                page = notebook_nb.page_num(tab)
                if self.window is not None:
                    with self.window.blocking_switch_page():
                        notebook_nb.remove_page(page)
                else:
                    notebook_nb.remove_page(page)
            self.tabs[tab_name] = None

    def move(self, tab_name: str, _from_nb: str, to_nb: str, new_index: int) -> None:
        """Physically move the tab widget between or within notebooks.

        Args:
            tab_name: Tab name.
            _from_nb: Source notebook ID.
            to_nb: Target notebook ID.
            new_index: Target index in notebooks list.
        """
        if self.window is None:
            return

        if tab_name == "playback":
            tab = self.window.playback.grid
        elif tab_name == "channels":
            tab = self.window.live_view.channels_view
        else:
            tab = self.tabs.get(tab_name)

        if not tab:
            return

        to_notebook = self.window.live_view if to_nb == "live" else self.window.playback

        target_physical_index = new_index

        parent = tab.get_parent()
        if parent is not to_notebook:
            parent_nb = (
                typing.cast(Gtk.Notebook, parent) if parent is not None else None
            )
            label = (
                parent_nb.get_tab_label(tab)
                if parent_nb is not None
                else Gtk.Label(label=tab_name)
            )
            if parent is not None:
                typing.cast(Gtk.Notebook, parent).detach_tab(tab)
            to_notebook.append_page(tab, label)
            to_notebook.set_tab_reorderable(tab, True)
            to_notebook.set_tab_detachable(tab, True)

        to_notebook.reorder_child(tab, target_physical_index)
        to_notebook.set_current_page(target_physical_index)
        to_notebook.grab_focus()

    def refresh_all(self) -> None:
        """Refresh all open tabs"""
        for tab in self.tabs.values():
            if tab:
                tab.refresh()

    def _get_tab_widget(self, tab_name: str) -> Gtk.Widget | None:
        """Get the GTK widget for a given tab name."""
        if not self.window:
            return None
        if tab_name == "channels":
            return getattr(self.window.live_view, "channels_view", None)
        if tab_name == "playback":
            return getattr(self.window.playback, "grid", None)
        return self.tabs.get(tab_name)

    def _capture_tab_settings(self, tab_name: str, widget: Gtk.Widget | None) -> None:
        """Capture settings for a tab widget into lightshow.workspace."""
        if not widget or not getattr(self.app, "core", None):
            return
        lightshow = self.app.core.lightshow
        if not hasattr(lightshow, "workspace"):
            return
        tab_settings = lightshow.workspace.setdefault("tab_settings", {})
        current = tab_settings.setdefault(tab_name, {})

        # ChannelsView / view_mode
        channels_view = getattr(widget, "channels_view", widget)
        if isinstance(channels_view, ChannelsView):
            current["view_mode"] = channels_view.get_view_mode_name()

    def _apply_tab_settings(self, tab_name: str, widget: Gtk.Widget | None) -> None:
        """Apply saved settings from lightshow.workspace to a tab widget."""
        if not widget or not getattr(self.app, "core", None):
            return
        lightshow = self.app.core.lightshow
        if not hasattr(lightshow, "workspace"):
            return
        tab_settings = lightshow.workspace.get("tab_settings", {})
        settings = tab_settings.get(tab_name)
        if not settings or not isinstance(settings, dict):
            return

        # ChannelsView / view_mode
        view_mode_name = settings.get("view_mode")
        if view_mode_name and isinstance(view_mode_name, str):
            channels_view = getattr(widget, "channels_view", widget)
            if isinstance(channels_view, ChannelsView):
                channels_view.set_view_mode_by_name(view_mode_name)

    def get_workspace_state(self) -> dict[str, typing.Any]:
        """Capture the full GUI workspace state."""
        if not self.window:
            return {}

        window = self.window

        def _name_of_child(child: Gtk.Widget | None) -> str | None:
            if not child:
                return None
            if child is getattr(window.live_view, "channels_view", None):
                return "channels"
            if child is getattr(window.playback, "grid", None):
                return "playback"
            for t_name, w in self.tabs.items():
                if w is child:
                    return t_name
            return None

        # Capture settings of live channels view
        if hasattr(window, "live_view") and hasattr(window.live_view, "channels_view"):
            self._capture_tab_settings("channels", window.live_view.channels_view)

        # Capture settings of all currently open tabs
        for t_name, w in self.tabs.items():
            if w is not None:
                self._capture_tab_settings(t_name, w)

        live_tabs: list[str] = []
        for i in range(window.live_view.get_n_pages()):
            ch = window.live_view.get_nth_page(i)
            name = _name_of_child(ch)
            if name:
                live_tabs.append(name)

        playback_tabs: list[str] = []
        for i in range(window.playback.get_n_pages()):
            ch = window.playback.get_nth_page(i)
            name = _name_of_child(ch)
            if name:
                playback_tabs.append(name)

        live_curr = window.live_view.get_current_page()
        live_active = (
            _name_of_child(window.live_view.get_nth_page(live_curr))
            if live_curr >= 0
            else "channels"
        )

        pb_curr = window.playback.get_current_page()
        pb_active = (
            _name_of_child(window.playback.get_nth_page(pb_curr))
            if pb_curr >= 0
            else "playback"
        )

        # Virtual console state
        vc = getattr(self.app, "virtual_console", None)
        vc_open = bool(vc is not None and getattr(vc.props, "visible", False))

        active_pane = getattr(self.app.core.tabs, "active_notebook", "playback")

        # Tab settings from lightshow.workspace
        tab_settings: dict[str, typing.Any] = {}
        if getattr(self.app, "core", None) and hasattr(
            self.app.core.lightshow, "workspace"
        ):
            ws = self.app.core.lightshow.workspace
            tab_settings = copy.deepcopy(ws.get("tab_settings", {}))

        return {
            "version": 1,
            "active_pane": active_pane,
            "panes": {
                "live": {"tabs": live_tabs, "active_tab": live_active},
                "playback": {"tabs": playback_tabs, "active_tab": pb_active},
            },
            "tab_settings": tab_settings,
            "virtual_console": {"open": vc_open},
        }

    def apply_workspace_state(self, state: dict[str, typing.Any]) -> None:
        """Apply a workspace layout and settings state to the GUI."""
        if not self.window or not state:
            return

        with self.window.blocking_switch_page():
            self._do_apply_workspace_state(state)

    def _do_apply_workspace_state(self, state: dict[str, typing.Any]) -> None:
        """Internal helper to apply workspace layout without event triggers."""
        assert self.window is not None
        panes = state.get("panes", {})
        live_info = panes.get("live", {})
        playback_info = panes.get("playback", {})
        target_live_tabs = live_info.get("tabs", ["channels"])
        target_playback_tabs = playback_info.get("tabs", ["playback"])
        all_targets = set(target_live_tabs + target_playback_tabs)

        # 1. Update tab_settings in lightshow.workspace
        if getattr(self.app, "core", None) and hasattr(
            self.app.core.lightshow, "workspace"
        ):
            ws = self.app.core.lightshow.workspace
            if "tab_settings" in state:
                ws.setdefault("tab_settings", {}).update(
                    copy.deepcopy(state["tab_settings"])
                )

        # 2. Close open tabs not present in target
        for tab_name, widget in list(self.tabs.items()):
            if widget is not None and tab_name not in all_targets:
                self.close_physically(tab_name)

        # 3. Open tabs in target notebook if closed
        app_any = typing.cast(typing.Any, self.app)
        mapping = {
            "dmx_outputs": app_any.open_dmx_outputs,
            "patch_channels": app_any.open_patch_channels,
            "track_channels": app_any.open_track_channels,
            "memories": app_any.open_memories,
            "sequences": app_any.open_sequences,
            "groups": app_any.open_groups,
            "indes": app_any.open_independents,
            "device_inspector": app_any.open_device_inspector,
            "fixtures": getattr(app_any, "open_fixtures", lambda: None),
            "curves": app_any.open_curves,
            "faders": app_any.open_faders,
            "settings": app_any.open_settings,
            "history": app_any.open_history,
        }

        for nb_id, tabs_list in [
            ("live", target_live_tabs),
            ("playback", target_playback_tabs),
        ]:
            target_nb = (
                self.window.live_view if nb_id == "live" else self.window.playback
            )
            for t_name in tabs_list:
                if t_name in ("channels", "playback"):
                    tab_w = self._get_tab_widget(t_name)
                    if tab_w and tab_w.get_parent() is not target_nb:
                        src_nb = "playback" if nb_id == "live" else "live"
                        self.move(t_name, src_nb, nb_id, -1)
                elif t_name in self.tabs:
                    if self.tabs[t_name] is not None:
                        tab_w = self.tabs[t_name]
                        if tab_w and tab_w.get_parent() is not target_nb:
                            src_nb = "playback" if nb_id == "live" else "live"
                            self.move(t_name, src_nb, nb_id, -1)
                    else:
                        if t_name in mapping:
                            orig_nb = self.default_notebook_id
                            self.default_notebook_id = nb_id
                            try:
                                mapping[t_name]()
                            finally:
                                self.default_notebook_id = orig_nb

        # 4. Reorder tabs and set active page
        for nb_id, nb_dict in panes.items():
            notebook = (
                self.window.live_view if nb_id == "live" else self.window.playback
            )
            order = nb_dict.get("tabs", [])
            for idx, t_name in enumerate(order):
                tab_w = self._get_tab_widget(t_name)
                if tab_w and tab_w.get_parent() is notebook:
                    notebook.reorder_child(tab_w, idx)
            active_name = nb_dict.get("active_tab")
            if active_name:
                active_w = self._get_tab_widget(active_name)
                if active_w and active_w.get_parent() is notebook:
                    pg = notebook.page_num(active_w)
                    if pg >= 0:
                        notebook.set_current_page(pg)

        # 5. Apply tab settings to all open tabs
        if hasattr(self.window, "live_view") and hasattr(
            self.window.live_view, "channels_view"
        ):
            self._apply_tab_settings("channels", self.window.live_view.channels_view)
        for t_name, w in self.tabs.items():
            if w is not None:
                self._apply_tab_settings(t_name, w)

        # 6. Restore Virtual Console if requested
        vc_state = state.get("virtual_console", {})
        if vc_state.get("open") is True:
            if hasattr(self.app, "open_virtual_console"):
                self.app.open_virtual_console()
        elif vc_state.get("open") is False:
            vc = getattr(self.app, "virtual_console", None)
            if vc is not None:
                vc.destroy()
                self.app.virtual_console = None

        # 7. Focus active pane
        active_pane = state.get("active_pane", "playback")
        target_nb = (
            self.window.live_view if active_pane == "live" else self.window.playback
        )
        target_nb.grab_focus()

        # 8. Sync CoreTabs model
        if getattr(self.app, "core", None) and hasattr(self.app.core, "tabs"):
            self.app.core.tabs.notebooks = {
                "live": list(target_live_tabs),
                "playback": list(target_playback_tabs),
            }
            self.app.core.tabs.active_tabs = {
                "live": live_info.get("active_tab", "channels"),
                "playback": playback_info.get("active_tab", "playback"),
            }
            self.app.core.tabs.active_notebook = active_pane

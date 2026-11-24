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
"""Real-time overview tab for all concurrent sequence playbacks."""

from __future__ import annotations

import typing
from gettext import gettext as _

from gi.repository import GLib, Gtk

from olc.core.playback_engine import PlaybackRunnerSnapshot, RunnerState

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


_STATE_COLORS: dict[RunnerState, str] = {
    RunnerState.FADING: "#4caf50",
    RunnerState.ACTIVE: "#42a5f5",
    RunnerState.PAUSED: "#ffa726",
    RunnerState.RELEASING: "#ef5350",
    RunnerState.IDLE: "#78909c",
}


class PlaybacksTab(Gtk.Box):
    """Real-time multi-sequence playback monitor and control tab."""

    def __init__(self, app: Application) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        self.set_border_width(8)
        self._timer_id: int | None = None
        self._subscriptions: list[tuple[str, typing.Callable[..., typing.Any]]] = []

        self._build_toolbar()
        self._build_treeview()
        self._build_transport_bar()

        for evt in (
            "playback.runner_changed",
            "playback.main_sequence_changed",
            "playback.sequence_released",
            "playback.sequence_asserted",
            "sequence.created",
            "sequence.deleted",
            "sequence.options_changed",
        ):
            cb = self._make_refresh_callback()
            self.app.core.subscribe(evt, cb)
            self._subscriptions.append((evt, cb))

        self.connect("destroy", self._on_destroy)
        self.refresh()

    def _make_refresh_callback(self) -> typing.Callable[..., None]:
        def _cb(*_args: object) -> None:
            GLib.idle_add(self._idle_refresh)

        return _cb

    def _idle_refresh(self) -> bool:
        if self.get_parent() is not None:
            self.refresh()
        return False

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._stop_timer()
        for evt, cb in self._subscriptions:
            if hasattr(self.app.core, "unsubscribe"):
                self.app.core.unsubscribe(evt, cb)
        self._subscriptions.clear()

    def _create_new_sequence(self) -> None:
        """Create a new secondary sequence using the next available index."""
        next_idx = (
            max((int(s.index) for s in self.app.core.lightshow.sequences), default=1)
            + 1
        )
        self.app.core.action_registry.execute("sequence.new", float(next_idx))

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close Playbacks tab when its close icon is clicked."""
        if self.app.tabs is not None:
            self.app.tabs.close("playbacks")

    def _build_toolbar(self) -> None:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.active_only_toggle = Gtk.ToggleButton(label=_("Active Only"))
        self.active_only_toggle.set_tooltip_text(
            _("Show only running, fading, or paused sequences")
        )
        self.active_only_toggle.connect("toggled", lambda *_: self.refresh())
        toolbar.pack_start(self.active_only_toggle, False, False, 0)

        self.status_label = Gtk.Label(label="")
        toolbar.pack_start(self.status_label, False, False, 8)

        spacer = Gtk.Box()
        toolbar.pack_start(spacer, True, True, 0)

        self.btn_new_sequence = Gtk.Button(label=_("+ New Sequence"))
        self.btn_new_sequence.set_tooltip_text(_("Create a new secondary sequence"))
        self.btn_new_sequence.connect("clicked", lambda *_: self._create_new_sequence())
        toolbar.pack_start(self.btn_new_sequence, False, False, 0)

        self.btn_set_main = Gtk.Button(label=_("Set as Main"))
        self.btn_set_main.set_tooltip_text(
            _("Bind selected sequence to CrossFade and Main Header")
        )
        self.btn_set_main.connect("clicked", lambda *_: self._set_selected_as_main())
        toolbar.pack_start(self.btn_set_main, False, False, 0)

        self.btn_pause_all = Gtk.Button(label=_("Pause All"))
        self.btn_pause_all.connect("clicked", lambda *_: self._pause_all())
        toolbar.pack_start(self.btn_pause_all, False, False, 0)

        self.btn_release_all = Gtk.Button(label=_("Release All"))
        self.btn_release_all.connect(
            "clicked",
            lambda *_: self.app.core.action_registry.execute("sequence.release_all"),
        )
        toolbar.pack_start(self.btn_release_all, False, False, 0)

        self.pack_start(toolbar, False, False, 0)

    def _build_treeview(self) -> None:
        # Columns:
        # 0: seq_index (float), 1: seq_str, 2: role, 3: name, 4: state,
        # 5: state_color, 6: cue_next, 7: progress_pct (int),
        # 8: progress_text, 9: fader_str, 10: priority, 11: channels_str
        self.liststore = Gtk.ListStore(
            float, str, str, str, str, str, str, int, str, str, str, str
        )
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.get_selection().connect(
            "changed", lambda *_: self._update_action_sensitivity()
        )

        text_cols = (
            (_("Seq"), 1),
            (_("Role"), 2),
            (_("Name"), 3),
            (_("Cue → Next"), 6),
        )
        for title, col_idx in text_cols:
            rend = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, rend)
            col.add_attribute(rend, "text", col_idx)
            col.set_resizable(True)
            self.treeview.append_column(col)

        state_rend = Gtk.CellRendererText()
        state_col = Gtk.TreeViewColumn(_("State"), state_rend)
        state_col.add_attribute(state_rend, "text", 4)
        state_col.add_attribute(state_rend, "foreground", 5)
        state_col.set_resizable(True)
        self.treeview.append_column(state_col)

        prog_rend = Gtk.CellRendererProgress()
        prog_col = Gtk.TreeViewColumn(_("Progress"), prog_rend)
        prog_col.add_attribute(prog_rend, "value", 7)
        prog_col.add_attribute(prog_rend, "text", 8)
        prog_col.set_min_width(110)
        prog_col.set_resizable(True)
        self.treeview.append_column(prog_col)

        for title, col_idx in (
            (_("Fader"), 9),
            (_("Priority"), 10),
            (_("Channels"), 11),
        ):
            rend = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, rend)
            col.add_attribute(rend, "text", col_idx)
            col.set_resizable(True)
            self.treeview.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.treeview)
        self.pack_start(scrolled, True, True, 0)

    def _build_transport_bar(self) -> None:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.btn_go = Gtk.Button(label=_("Go"))
        self.btn_go.connect("clicked", lambda *_: self._exec_selected("sequence.go"))
        bar.pack_start(self.btn_go, False, False, 0)

        self.btn_go_back = Gtk.Button(label=_("Go Back"))
        self.btn_go_back.connect(
            "clicked", lambda *_: self._exec_selected("sequence.go_back")
        )
        bar.pack_start(self.btn_go_back, False, False, 0)

        self.btn_pause = Gtk.Button(label=_("Pause"))
        self.btn_pause.connect(
            "clicked", lambda *_: self._exec_selected("sequence.pause")
        )
        bar.pack_start(self.btn_pause, False, False, 0)

        self.btn_assert = Gtk.Button(label=_("Assert"))
        self.btn_assert.connect(
            "clicked", lambda *_: self._exec_selected("sequence.assert")
        )
        bar.pack_start(self.btn_assert, False, False, 0)

        self.btn_release = Gtk.Button(label=_("Release"))
        self.btn_release.connect(
            "clicked", lambda *_: self._exec_selected("sequence.release")
        )
        bar.pack_start(self.btn_release, False, False, 0)

        self.pack_start(bar, False, False, 0)

    def get_selected_sequence_index(self) -> float | None:
        """Return currently selected sequence index in the overview table."""
        model, tree_iter = self.treeview.get_selection().get_selected()
        if tree_iter is None:
            return None
        return float(model.get_value(tree_iter, 0))

    def _exec_selected(self, action_name: str) -> None:
        seq_idx = self.get_selected_sequence_index()
        if seq_idx is not None:
            self.app.core.action_registry.execute(action_name, seq_idx)

    def _set_selected_as_main(self) -> None:
        seq_idx = self.get_selected_sequence_index()
        if seq_idx is not None:
            self.app.core.action_registry.execute("playback.set_main_sequence", seq_idx)

    def _pause_all(self) -> None:
        engine = getattr(self.app.core, "playback_engine", None)
        if engine is not None:
            engine.pause_all()
            self.refresh()

    def _update_action_sensitivity(self) -> None:
        has_sel = self.get_selected_sequence_index() is not None
        for btn in (
            self.btn_go,
            self.btn_go_back,
            self.btn_pause,
            self.btn_assert,
            self.btn_release,
            self.btn_set_main,
        ):
            btn.set_sensitive(has_sel)

    @staticmethod
    def _format_cue_pair(snap: PlaybackRunnerSnapshot) -> str:
        curr = f"Q{snap.active_cue:g}" if snap.active_cue is not None else "—"
        if snap.active_cue_text:
            curr = f"{curr} {snap.active_cue_text}"
        nxt = f"Q{snap.next_cue:g}" if snap.next_cue is not None else "—"
        if snap.next_cue_text:
            nxt = f"{nxt} {snap.next_cue_text}"
        return f"{curr}  →  {nxt}"

    def _start_timer_if_needed(self, has_fading: bool) -> None:
        if has_fading and self._timer_id is None:
            self._timer_id = GLib.timeout_add(66, self._on_tick)
        elif not has_fading:
            self._stop_timer()

    def _stop_timer(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _on_tick(self) -> bool:
        if self.get_parent() is None or not self.get_visible():
            self._timer_id = None
            return False
        self.refresh()
        return self._timer_id is not None

    def refresh(self) -> None:
        """Reload all sequence runner snapshots into the ListStore."""
        engine = getattr(self.app.core, "playback_engine", None)
        if engine is None:
            return
        selected_idx = self.get_selected_sequence_index()
        active_only = self.active_only_toggle.get_active()
        all_snaps = engine.get_all_runner_snapshots(active_only=False)
        active_count = sum(1 for s in all_snaps if s.state is not RunnerState.IDLE)
        snaps = (
            [s for s in all_snaps if s.state is not RunnerState.IDLE]
            if active_only
            else all_snaps
        )

        self.status_label.set_text(
            _("{count} active playback(s)").format(count=active_count)
        )

        self.liststore.clear()
        has_fading = False
        reselect_path: Gtk.TreePath | None = None
        for row_idx, snap in enumerate(snaps):
            if snap.state in (RunnerState.FADING, RunnerState.RELEASING):
                has_fading = True
            seq_str = (
                str(int(snap.seq_index))
                if snap.seq_index.is_integer()
                else f"{snap.seq_index:g}"
            )
            role_parts: list[str] = []
            if snap.is_main:
                role_parts.append("MAIN")
            if snap.assigned_fader:
                role_parts.append(snap.assigned_fader)
            role_str = " · ".join(role_parts) if role_parts else "—"
            pct = (
                round(snap.fade_progress * 100)
                if snap.state in (RunnerState.FADING, RunnerState.RELEASING)
                else (100 if snap.state is RunnerState.ACTIVE else 0)
            )
            prog_txt = (
                f"{pct}% ({snap.fade_remaining:.1f}s)"
                if snap.fade_remaining > 0.0
                else f"{pct}%"
            )
            self.liststore.append(
                [
                    snap.seq_index,
                    seq_str,
                    role_str,
                    snap.name,
                    snap.state.value.upper(),
                    _STATE_COLORS.get(snap.state, "#78909c"),
                    self._format_cue_pair(snap),
                    pct,
                    prog_txt,
                    f"{round(snap.fader_level * 100)}%",
                    snap.priority.name.title(),
                    f"{snap.owned_channels_count} ch",
                ]
            )
            if selected_idx is not None and snap.seq_index == selected_idx:
                reselect_path = Gtk.TreePath.new_from_indices([row_idx])

        if reselect_path is not None:
            self.treeview.get_selection().select_path(reselect_path)
        self._update_action_sensitivity()
        self._start_timer_if_needed(has_fading)

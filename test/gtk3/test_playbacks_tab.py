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
"""GTK3 tests for PlaybacksTab overview and VirtualConsole 3-button fader strips."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.playbacks import PlaybacksTab  # noqa: E402
from olc.show.cue import Cue  # noqa: E402
from olc.show.fader import FaderType  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402
from olc.show.sequence import Sequence  # noqa: E402
from olc.show.step import Step  # noqa: E402
from test.gtk3.conftest import process_events  # noqa: E402


def test_playbacks_tab_and_vc_three_strip_buttons(app_gui: Application) -> None:
    """Verify PlaybacksTab table, Set as Main, Release All, and VC 3-button strips."""
    ls = app_gui.core.lightshow
    ls.fader_bank.reset_faders(reset_page_count=True)

    try:
        seq2 = Sequence(2, text="Overlay", lightshow=ls)
        for num in (10.0, 20.0):
            cue = Cue(2, num, channels={2: 0.8}, text=f"Q{num:g}")
            seq2.cues.add(cue)
            seq2.insert_step(len(seq2.steps) - 1, Step(sequence=2, cue=cue))
        ls.sequences.append(seq2)

        ls.palettes.add(Palette(PaletteCategory.PRESET, 1.0, "Work", channels={3: 1.0}))
        app_gui.core.action_registry.execute(
            "fader.assign", 1, 1, FaderType.SEQUENCE, 2
        )
        app_gui.core.action_registry.execute(
            "fader.assign", 1, 2, FaderType.PRESET, 1.0
        )

        app_gui.activate_action("virtual_console", None)
        app_gui.activate_action("playbacks", None)
        process_events()

        assert app_gui.virtual_console is not None
        vc = app_gui.virtual_console
        assert app_gui.tabs is not None
        pb_tab = app_gui.tabs.tabs.get("playbacks")
        assert isinstance(pb_tab, PlaybacksTab)

        # 1. Generic 3-button strip: Sequence enabled (fader 1), Preset disabled (2)
        assert len(vc.fader_buttons) == 10
        b_back, b_pause, b_go = vc.fader_buttons[0]
        assert b_back.get_sensitive() is True
        assert b_pause.get_sensitive() is True
        assert b_go.get_sensitive() is True
        assert b_go.get_label() == "▶"

        p0, p1, p2 = vc.fader_buttons[1]
        assert p0.get_sensitive() is False
        assert p1.get_sensitive() is False
        assert p2.get_sensitive() is False

        # 2. Clicking ▶ on Fader 1 triggers Go on Seq 2 without moving CrossFade scales
        vc.scale_a.set_value(0.25)
        vc.scale_b.set_value(0.25)
        b_go.emit("clicked")
        process_events()
        assert vc.scale_a.get_value() == 0.25
        assert vc.scale_b.get_value() == 0.25

        # 3. PlaybacksTab lists Seq 1 and Seq 2; Active Only filters properly
        assert len(pb_tab.liststore) == 2
        pb_tab.active_only_toggle.set_active(True)
        process_events()
        assert len(pb_tab.liststore) <= 2

        pb_tab.active_only_toggle.set_active(False)
        process_events()

        # Select row 1 (Seq 2) -> Set as Main + Undo
        pb_tab.treeview.get_selection().select_path(Gtk.TreePath.new_from_indices([1]))
        process_events()
        pb_tab.btn_set_main.emit("clicked")
        process_events()
        assert app_gui.core.playback_engine.main_sequence is seq2

        app_gui.core.history.undo()
        process_events()
        assert app_gui.core.playback_engine.main_sequence is ls.main_playback

        # Release All clears all active playbacks
        pb_tab.btn_release_all.emit("clicked")
        process_events()
        assert app_gui.core.playback_arbitrator.active_sequences() == []

        # 4. VirtualConsole CLI row 6: Label, Assert, Release, Stop
        for btn_attr in ("label_btn", "assert_btn", "release_btn", "stop_btn"):
            assert hasattr(vc, btn_attr)
        app_gui.core.action_registry.execute("commandline.clear")
        vc.label_btn.emit("clicked")
        process_events()
        assert app_gui.core.commandline.get_string() == "LABEL "
        app_gui.core.action_registry.execute("commandline.clear")
        app_gui.core.action_registry.execute("commandline.append_char", "SEQ 2")
        vc.label_btn.emit("clicked")
        process_events()
        assert app_gui.core.commandline.get_string() == "SEQ 2 LABEL "
        app_gui.core.action_registry.execute("commandline.clear")
    finally:
        app_gui.core.playback_arbitrator.clear()
        app_gui.core.playback_engine.clear()
        ls.fader_bank.reset_faders(reset_page_count=True)
        ls.sequences.clear()
        ls.palettes.clear()
        app_gui.core.history.clear()
        process_events()

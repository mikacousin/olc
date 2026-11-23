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
"""GUI behavior tests for MainPlaybackView."""

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.sequence import format_step_tooltip  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_main_playback_enriched_columns_and_live_updates(app_gui: Application) -> None:
    """Verify IFCB timings, FX, Flags, Total, Link, Notes and EventBridge updates."""
    assert app_gui.window is not None
    playback = app_gui.window.playback
    expected_titles = [
        "Step",
        "Cue",
        "Text",
        "Wait",
        "Delay Out",
        "Out",
        "Delay In",
        "In",
        "Channel Time",
        "Pos",
        "Color",
        "Beam",
        "FX",
        "Flags",
        "Total",
        "Link",
        "Notes",
    ]
    assert [c.get_title() for c in playback.treeview1.get_columns()] == expected_titles
    assert [c.get_title() for c in playback.treeview2.get_columns()] == expected_titles

    scroll1 = playback.treeview1.get_parent()
    scroll2 = playback.treeview2.get_parent()
    assert isinstance(scroll1, Gtk.ScrolledWindow)
    assert isinstance(scroll2, Gtk.ScrolledWindow)
    assert scroll1.get_policy()[0] == Gtk.PolicyType.AUTOMATIC
    assert scroll2.get_policy()[0] == Gtk.PolicyType.AUTOMATIC
    assert scroll1.get_hadjustment() is scroll2.get_hadjustment()

    app_gui.core.action_registry.execute("sequence.insert_step", 1.0, 1, 1.0, {1: 255})
    step = app_gui.core.lightshow.main_playback.steps[1]
    assert step.cue is not None
    step.cue.execute_preset = 7.0
    step.cue.effect_refs = {1: {"effect": 3.0}}

    app_gui.core.action_registry.execute(
        "step.update_times",
        1.0,
        1,
        delay_position=2.0,
        time_position=4.0,
        time_color=1.5,
    )
    app_gui.core.action_registry.execute("cue.set_block", 1.0, True, 1)
    app_gui.core.action_registry.execute("cue.set_int_block", 1.0, True, 1)
    app_gui.core.action_registry.execute("cue.set_assert", 1.0, True, 1)
    app_gui.core.action_registry.execute("cue.set_notes", 1.0, "Blackout on beat", 1)
    process_events()

    # Rows 0 and 1 are sentinels, row 2 is step 0, row 3 is step 1
    row = playback.cues_liststore1[3]
    assert row[1] == "1.0"
    assert row[12] == "2/4"
    assert row[13] == "1.5"
    assert row[14] == ""
    assert row[15] == "FX 3"
    assert row[16] == "B IB A"
    assert row[17] == "6"
    assert row[18] == "P7"
    assert row[19] == "Blackout on beat"
    assert row[21] is True

    # Tooltips helper covers Pos, Flags, and Notes
    assert format_step_tooltip(step, "Pos") == "Pos — Delay: 2  Time: 4"
    assert (
        format_step_tooltip(step, "Flags")
        == "Block (B), Intensity Block (IB), Assert (A)"
    )
    assert format_step_tooltip(step, "Notes") == "Blackout on beat"

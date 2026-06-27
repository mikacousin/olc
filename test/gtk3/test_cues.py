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
"""GUI behavior tests for the Cues edition tab."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402
from olc.cue import Cue  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.cue import CuesEditionTab  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_cues_edition_tab_behavior(app_gui: Application) -> None:
    """Test CuesEditionTab insertion, rename, delete, and undo/redo."""
    # 1. Clear cues and add one
    app_gui.core.lightshow.cues.clear()
    app_gui.core.lightshow.cues.append(Cue(0, 1.0, {}, "Cue 1"))

    # 2. Open memories/cues tab
    app_gui.activate_action("memories", None)
    process_events()

    assert app_gui.tabs is not None
    cues_tab = app_gui.tabs.tabs.get("memories")
    assert isinstance(cues_tab, CuesEditionTab)
    assert cues_tab.treeview is not None

    # Verify initial treeview row
    model = cues_tab.treeview.get_model()
    assert model is not None
    assert len(model) == 1, "TreeView should have 1 row initially."

    # 3. Insert a new cue (cue 2.0)
    cues_tab._insert_cue_on_next_free_number()
    process_events()
    assert len(app_gui.core.lightshow.cues) == 2, "There should be 2 cues now."
    assert len(model) == 2, "TreeView should render 2 rows."

    # 4. Rename the first cue
    cues_tab._text_edited(Gtk.CellRendererText(), "0", "Cue 1 Renamed")
    process_events()
    assert app_gui.core.lightshow.cues[0].text == "Cue 1 Renamed"

    # Undo rename
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.cues[0].text == "Cue 1"

    # 5. Delete selected cue (cue 2.0)
    # Execute delete action directly (to avoid GUI confirmation dialog popup blocker)
    # Note: We do not set the treeview cursor here to avoid queuing asynchronous
    # cursor-changed events that inject cue.select into the undo history.
    cue_to_del = app_gui.core.lightshow.cues[1]
    app_gui.core.action_registry.execute(
        "cue.delete", cue_to_del.number, cue_to_del.sequence
    )
    process_events()

    assert len(app_gui.core.lightshow.cues) == 1, "Cue should be deleted."
    assert len(model) == 1, "TreeView should render 1 row."

    # 6. Undo delete
    app_gui.activate_action("undo", None)
    process_events()
    assert len(app_gui.core.lightshow.cues) == 2, "Undo should restore the deleted cue."
    assert len(model) == 2, "TreeView should render 2 rows."

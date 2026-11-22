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
"""Pytest conftest configuration for GTK3 GUI behavior tests."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import os
import typing
from collections.abc import Generator

import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk  # noqa: E402

from olc.gtk3.application import Application  # noqa: E402


# Helper to process the GTK event loop and flush idle callbacks
def process_events() -> None:
    """Process GTK events to flush the main loop."""
    for _ in range(15):
        while Gtk.events_pending():
            Gtk.main_iteration()


@pytest.fixture(scope="session")
def app_gui_instance() -> Generator[Application, None, None]:
    """Fixture to launch the complete GTK Application instance once for the module."""
    # Register resources
    gresource_path = None
    candidates = [
        os.path.join(
            os.path.dirname(__file__), "..", "..", "builddir", "data", "olc.gresource"
        ),
        "/usr/local/share/olc/olc.gresource",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            gresource_path = candidate
            break

    if gresource_path is not None:
        resource = Gio.resource_load(gresource_path)
        Gio.Resource._register(resource)  # type: ignore

    # Disable DBus unique registration
    original_init = Gtk.Application.__init__

    def patched_init(
        self: Gtk.Application,
        *args: typing.Any,  # noqa: ANN401
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> None:
        kwargs["application_id"] = None
        kwargs["flags"] = Gio.ApplicationFlags.NON_UNIQUE
        original_init(self, *args, **kwargs)

    Gtk.Application.__init__ = patched_init

    app = Application("test-version")
    app.register(None)

    # Initialize Engine and Backend (normally done in do_command_line)
    app.core.init_engine(monitor_port=5555, no_listen=True)

    app.core.start()

    # Activate
    app.activate()
    process_events()

    yield app

    # Cleanup application window and stop engines
    app.core.stop()
    if app.window:
        app.window.destroy()
    app.quit()
    process_events()


@pytest.fixture(scope="function")
def app_gui(app_gui_instance: Application) -> Generator[Application, None, None]:
    """Fixture to reset state and open/close tabs for each test function."""
    app = app_gui_instance

    # 1. Clear any logical data and stop background playback transitions
    from olc.show.cue import Cue  # noqa: E402
    from olc.show.step import Step  # noqa: E402

    main_pb = app.core.lightshow.main_playback
    main_pb.stop()
    main_pb.steps.clear()
    cue0 = Cue(0, 0.0)
    main_pb.cues = {cue0}
    step0 = Step(sequence=main_pb.index, cue=cue0)
    main_pb.add_step(step0)
    main_pb.add_step(step0)
    main_pb.position = 0
    main_pb._on_go = False
    main_pb.tracking_mode = False
    main_pb.mib_enabled = True
    main_pb.channels.clear()
    app.core.effects_engine.stop_all()
    app.core.lightshow.effects.clear()
    app.core.lightshow.sequences.clear()
    app.core.lightshow.groups.clear()
    app.core.lightshow.cues.clear()
    app.core.lightshow.palettes.clear()
    app.core.lightshow.park.clear()
    app.core.lightshow.patch.patch_empty()
    app.core.lightshow.curves.reset()
    app.core.live_state.clear_all()
    app.core.commandline.set_string("")
    app.core.selected_channels = []
    if app.core.midi is not None:
        app.core.midi.learning = ""
    if app.virtual_console is not None:
        app.virtual_console.close()
    if app.core.backend and getattr(app.core.backend, "dmx", None):
        dmx = app.core.backend.dmx
        dmx.levels["user"].fill(-1)
        dmx.levels["sequence"].fill(0.0)
        dmx.levels["faders"].fill(0.0)

    # 2. Close any open tabs
    if app.tabs:
        for tab_name in list(app.tabs.tabs.keys()):
            app.tabs.close(tab_name)
    process_events()

    # 3. Reset lightshow workspace
    from olc.show.lightshow import default_workspace  # noqa: E402

    app.core.lightshow.workspace = default_workspace()

    if app.window:
        if not app.window.get_visible():
            app.window.show_all()
        live_cv = app.window.live_view.channels_view
        live_cv.set_display_format("Compact")
        live_cv.sync_selection_to_gui([])
        live_cv.combo.set_active(0)
        live_cv.set_readout_mode("Auto")
        live_cv.set_show_labels(True)
        live_cv.set_family_expanded("focus", False)
        live_cv.set_family_expanded("color", False)
        live_cv.set_family_expanded("beam", False)
        live_cv.flush_dirty_channels()
        live_cv.invalidate_all_snapshots()

    process_events()

    yield app

    process_events()

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

    Gtk.Application.__init__ = patched_init  # type: ignore

    app = Application("test-version")
    app.register(None)

    # Initialize Engine and Backend (normally done in do_command_line)
    from olc.backends import DMXBackend
    from olc.core.engine import CoreEngine
    from olc.core.universe_config import Protocol, UniverseMap
    from olc.define import UNIVERSES

    universe_map = UniverseMap(max(UNIVERSES) + 1)
    for u in range(1, 5):
        universe_map.enable_protocol(u, Protocol.ARTNET)
        universe_map.enable_protocol(u, Protocol.SACN)

    app.engine = CoreEngine(universe_map, monitor_port=5555, no_listen=True)
    app.core.engine = app.engine

    app.backend = DMXBackend(app.core.lightshow)
    app.core.backend = app.backend

    app.engine.start()

    def on_patch_empty_cb() -> None:
        if app.backend:
            app.backend.dmx.all_outputs_at_zero()

    def on_unpatch_cb(index: int, output: int) -> None:
        if app.backend:
            app.backend.dmx.frame[index][output] = 0

    app.core.lightshow.patch.on_patch_empty_cb = on_patch_empty_cb
    app.core.lightshow.patch.on_unpatch_cb = on_unpatch_cb
    app.backend.dmx.add_notification_callback(app.on_backend_notification)

    # Activate
    app.activate()
    process_events()

    yield app

    # Cleanup application window and stop engines
    if app.engine:
        app.engine.stop()
    if app.backend:
        app.backend.stop()
    if app.window:
        app.window.destroy()
    app.quit()
    process_events()


@pytest.fixture(scope="function")
def app_gui(app_gui_instance: Application) -> Generator[Application, None, None]:
    """Fixture to reset state and open/close tabs for each test function."""
    app = app_gui_instance

    # 1. Clear any logical data
    app.core.lightshow.groups.clear()
    app.core.lightshow.cues.clear()
    app.core.lightshow.patch.patch_empty()

    # 2. Close any open tabs
    if app.tabs:
        for tab_name in list(app.tabs.tabs.keys()):
            app.tabs.close(tab_name)

    if app.window:
        app.window.show_all()

    process_events()

    yield app

    if app.window:
        app.window.hide()

    process_events()

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
from typing import Any

from gi.repository import GLib
from olc.backends.artnet_backend import ArtnetBackend

ARTNET = True

try:
    import sacn  # noqa: F401, pylint: disable=W0611
except ImportError:
    SACN = False
else:
    SACN = True
    from olc.backends.sacn import Sacn
try:
    import ola  # noqa: F401, pylint: disable=W0611
except ImportError:
    OLA = False
else:
    OLA = True
    from olc.backends.ola import Ola

if typing.TYPE_CHECKING:
    from gi.repository import Gtk
    from olc.patch import DMXPatch


def select_backend(
    options: GLib.VariantDict, settings: Gtk.Settings, patch: DMXPatch
) -> None | Ola | ArtnetBackend | Sacn:
    """Select and create DMX backend

    Args:
        options: command line options
        settings: GSettings
        patch: DMX patch

    Returns:
        Backend or None
    """
    backend = options.get("backend", settings.get_string("backend"))
    backend_instance: Any = None

    if "ola" in backend and OLA:
        olad_port = options.get("http-port", 9090)
        backend_instance = Ola(patch, olad_port=olad_port)
    elif "artnet" in backend and ARTNET:
        backend_instance = ArtnetBackend(patch)
    elif "sacn" in backend and SACN:
        backend_instance = Sacn(patch)
    elif backend:
        print(f"{backend} is not supported. Fallback to sACN")
        backend = "sacn"
        if SACN:
            backend_instance = Sacn(patch)

    # Handle case where a backend module is missing
    if not backend_instance:
        missing_module = None
        if "ola" in backend and not OLA:
            missing_module = "ola"

        elif "sacn" in backend and not SACN:
            missing_module = "sACN"
        if missing_module:
            print(f"Can't find {missing_module} python module.")

    settings.set_value("backend", GLib.Variant("s", backend))
    return backend_instance

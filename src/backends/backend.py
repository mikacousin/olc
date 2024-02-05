# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Any

from gi.repository import GLib

try:
    import sacn  # noqa: F401, pylint: disable=W0611
except ImportError:
    SACN = False
else:
    SACN = True
    from .sacn import Sacn
try:
    import ola  # noqa: F401, pylint: disable=W0611
except ImportError:
    OLA = False
else:
    OLA = True
    from .ola import Ola


def select_backend(options, settings, patch) -> Any:
    """Select and create DMX backend

    Args:
        options: command line options
        settings: GSettings
        patch: DMX patch

    Returns:
        Backend or None
    """
    backend = settings.get_string("backend")
    if "backend" in options:
        backend = options["backend"]
    if "ola" in backend:
        if OLA:
            olad_port = 9090
            if "http-port" in options:
                olad_port = options["http-port"]
            settings.set_value("backend", GLib.Variant("s", backend))
            return Ola(patch, olad_port=olad_port)
        print("Can't find ola python module")
        return None
    if "sacn" in backend:
        if SACN:
            settings.set_value("backend", GLib.Variant("s", backend))
            return Sacn(patch)
        print("Can't find sACN python module")
        return None
    if backend:
        print(f"{backend} is not supported. Fallback to sACN")
        if SACN:
            settings.set_value("backend", GLib.Variant("s", backend))
            return Sacn(patch)
    print("Can't find sACN python module")
    return None

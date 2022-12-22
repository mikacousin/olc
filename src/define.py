# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
"""Some defines for olc project."""
from typing import Any
from gi.repository import Gio

UNIVERSES = [1, 2, 3, 4]
NB_UNIVERSES = len(UNIVERSES)

MAX_CHANNELS = 1024

MAX_FADER_PAGE = 10

App = Gio.Application.get_default


def is_float(element: Any) -> bool:
    """Test if argument is a float

    Args:
        element: argument to test

    Returns:
        True or False
    """
    try:
        float(element)
        return True
    except ValueError:
        return False


def is_non_nul_float(element: Any) -> bool:
    """Test if argument is a float and non nul

    Args:
        element: argument to test

    Returns:
        True or False
    """
    return bool(float(element)) if is_float(element) else False


def is_int(element: Any) -> bool:
    """Test if argument is an integer

    Args:
        element: argument to test

    Returns:
        True or False
    """
    try:
        int(element)
        return True
    except ValueError:
        return False


def is_non_nul_int(element: Any) -> bool:
    """Test if argument is an integer and non nul

    Args:
        element: argument to test

    Returns:
        True or False
    """
    return bool(int(element)) if is_int(element) else False


def time_to_string(time: float) -> str:
    """A number of seconds to human readable text

    Args:
        time: seconds

    Returns:
        Human readable time ([[hours:]minutes:]seconds[.tenths])
    """
    minutes, seconds = divmod(time, 60)
    hours, minutes = divmod(minutes, 60)
    string = ""
    if hours:
        string += str(int(hours)) + ":"
    if minutes:
        string += str(int(minutes)) + ":"
    if seconds.is_integer():
        string += str(int(seconds))
    else:
        string += str(seconds)
    if string == "0":
        string = ""
    return string


def string_to_time(string: str) -> float:
    """Convert a string time to float

    Args:
        string: format = [[hours:]minutes:]seconds[.tenths]

    Returns:
        time in seconds
    """
    if string == "":
        string = "0"
    if ":" in string:
        tsplit = string.split(":")
        if len(tsplit) == 2:
            time = int(tsplit[0]) * 60 + float(tsplit[1])
        elif len(tsplit) == 3:
            time = int(tsplit[0]) * 3600 + int(tsplit[1]) * 60 + float(tsplit[2])
        else:
            time = 0
    else:
        time = float(string)
    return time

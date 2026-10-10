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
"""Pango markup syntax highlighter for lighting console command lines."""

from __future__ import annotations

import html

from olc.core.parser.executor import COLOR_PRESETS
from olc.core.parser.lexer import CommandLexer

# Color Palette for Pango Markup
COLOR_SELECTION = "#FFB74D"  # Amber (+, -, /, THRU, GROUP, ALL, ODD, EVEN)
COLOR_COMMAND = "#F06292"  # Magenta bold (AT, FULL, OUT, RECORD, CUE, GOTO...)
COLOR_ATTRIBUTE = "#69F0AE"  # Mint Green for ML (PAN, TILT, COLOR, ZOOM...)
COLOR_NUMBER = "#4FC3F7"  # Soft Cyan for numbers, channels, cue IDs, levels
COLOR_STRING = "#E0E0E0"  # Light grey for strings
COLOR_IDENT = "#B0BEC5"  # Blue-grey for default identifiers
COLOR_ERROR = "#FF5252"  # Red underline for unrecognized characters

SELECTION_KEYWORDS = frozenset(
    {
        "THRU",
        "GROUP",
        "ALL",
        "ODD",
        "EVEN",
    }
)

COMMAND_KEYWORDS = frozenset(
    {
        "AT",
        "FULL",
        "OUT",
        "RECORD",
        "REC",
        "UPDATE",
        "CUE",
        "SEQUENCE",
        "SEQ",
        "GOTO",
        "BLOCK",
        "UNBLOCK",
        "DELETE",
    }
)

ATTRIBUTE_KEYWORDS = frozenset(
    {
        "PAN",
        "TILT",
        "COLOR",
        "COLOUR",
        "ZOOM",
        "FOCUS",
        "IRIS",
        "STROBE",
        "CCT",
        "GOBO",
        "PRISM",
        "COLOR_WHEEL",
        "COLORWHEEL",
        "GOBO_WHEEL",
        "GOBOWHEEL",
        "TIME",
        "DELAY",
    }
)


def highlight_commandline_markup(  # pylint: disable=too-many-branches
    text: str,
) -> str:
    """Transform raw command line text into rich Pango markup for GTK3 rendering.

    Args:
        text: Raw command string (can be partial or in-progress).

    Returns:
        Pango markup formatted string.
    """
    if not text:
        return ""

    parts: list[str] = []

    for match in CommandLexer._TOKEN_RE.finditer(text):  # pylint: disable=protected-access
        kind = match.lastgroup
        val = match.group()
        escaped = html.escape(val, quote=True)

        if kind == "WHITESPACE":
            parts.append(escaped)

        elif kind == "NUMBER":
            parts.append(f'<span foreground="{COLOR_NUMBER}">{escaped}</span>')

        elif kind == "HEX_COLOR":
            parts.append(f'<span foreground="{val}" weight="bold">{escaped}</span>')

        elif kind == "STRING":
            parts.append(f'<span foreground="{COLOR_STRING}">{escaped}</span>')

        elif kind == "AT":
            parts.append(
                f'<span foreground="{COLOR_COMMAND}" weight="bold">{escaped}</span>'
            )

        elif kind in ("PLUS", "MINUS", "SLASH"):
            parts.append(f'<span foreground="{COLOR_SELECTION}">{escaped}</span>')

        elif kind == "IDENT":
            upper = val.upper()
            if upper in SELECTION_KEYWORDS:
                parts.append(f'<span foreground="{COLOR_SELECTION}">{escaped}</span>')
            elif upper in COMMAND_KEYWORDS:
                parts.append(
                    f'<span foreground="{COLOR_COMMAND}" weight="bold">{escaped}</span>'
                )
            elif upper in ATTRIBUTE_KEYWORDS:
                parts.append(
                    f'<span foreground="{COLOR_ATTRIBUTE}" '
                    f'weight="bold">{escaped}</span>'
                )
            elif upper in COLOR_PRESETS:
                hex_color = COLOR_PRESETS[upper]
                parts.append(
                    f'<span foreground="{hex_color}" weight="bold">{escaped}</span>'
                )
            else:
                parts.append(f'<span foreground="{COLOR_IDENT}">{escaped}</span>')

        elif kind == "MISMATCH":
            parts.append(
                f'<span foreground="{COLOR_ERROR}" underline="error">{escaped}</span>'
            )

    return "".join(parts)

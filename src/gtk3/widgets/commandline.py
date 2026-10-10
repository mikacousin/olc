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
"""Interactive command line prompt widget with real-time syntax highlighting."""

from __future__ import annotations

import html
import typing

from gi.repository import GLib, Gtk

from olc.core.parser.highlighter import highlight_commandline_markup

if typing.TYPE_CHECKING:
    from olc.gtk3.application import Application


class CommandLineWidget:
    """Rich interactive command line prompt widget with real-time syntax highlighting.

    Displays an industry-standard console prompt (e.g. 'Live > ') with token-colored
    text, monospace typography, cursor indicator, and execution/error feedback.
    """

    def __init__(self, app: Application) -> None:
        """Initialize the CommandLine widget.

        Args:
            app: The main application instance.
        """
        self.app = app

        # Root horizontal container
        self.widget = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.widget.set_margin_start(8)
        self.widget.set_margin_end(8)
        self.widget.set_margin_top(4)
        self.widget.set_margin_bottom(4)

        # Context prompt badge (Live > )
        self.prompt_label = Gtk.Label()
        self.prompt_label.set_markup(
            '<span foreground="#FFD54F" weight="bold">Live &gt; </span>'
        )
        self.widget.pack_start(self.prompt_label, False, False, 0)

        # Main command text label with markup and left alignment
        self.command_label = Gtk.Label()
        self.command_label.set_xalign(0.0)
        self.command_label.set_use_markup(True)
        self.widget.pack_start(self.command_label, True, True, 0)

        # Status / Feedback label on the right
        self.feedback_label = Gtk.Label()
        self.feedback_label.set_xalign(1.0)
        self.feedback_label.set_use_markup(True)
        self.widget.pack_end(self.feedback_label, False, False, 0)

        # Render initial empty state
        self._render_text("")

        # Subscribe to Core events
        self.app.core.subscribe("commandline.changed", self.on_changed)
        self.app.core.subscribe("commandline.error", self.on_error)
        self.app.core.subscribe("commandline.executed", self.on_executed)

    def on_changed(self, keystring: str) -> None:
        """Callback triggered when the logical command line changes.

        Args:
            keystring: The new command line string.
        """
        GLib.idle_add(self._on_changed_ui, keystring)

    def _on_changed_ui(self, keystring: str) -> bool:
        self._render_text(keystring)
        self.feedback_label.set_text("")
        return False

    def on_error(self, message: str) -> None:
        """Callback triggered on command syntax or execution error.

        Args:
            message: Error description.
        """
        GLib.idle_add(self._on_error_ui, message)

    def _on_error_ui(self, message: str) -> bool:
        escaped = html.escape(message, quote=True)
        self.feedback_label.set_markup(
            f'<span foreground="#FF5252" weight="bold">⚠ {escaped}</span>'
        )
        return False

    def on_executed(self, message: str) -> None:
        """Callback triggered on successful command execution.

        Args:
            message: Execution success message or details.
        """
        GLib.idle_add(self._on_executed_ui, message)

    def _on_executed_ui(self, message: str) -> bool:
        if message and message != "Empty command line":
            escaped = html.escape(message, quote=True)
            self.feedback_label.set_markup(
                f'<span foreground="#81C784">{escaped}</span>'
            )
        else:
            self.feedback_label.set_text("")
        return False

    def _render_text(self, text: str) -> None:
        """Render command line text with syntax highlighting and trailing cursor."""
        cursor = '<span foreground="#888888">_</span>'
        if not text:
            self.command_label.set_markup(
                f'<span font_family="Monaco, monospace">{cursor}</span>'
            )
            return

        markup = highlight_commandline_markup(text)
        self.command_label.set_markup(
            f'<span font_family="Monaco, monospace">{markup}{cursor}</span>'
        )

    def destroy(self) -> None:
        """Unsubscribe from application events."""
        self.app.core.unsubscribe("commandline.changed", self.on_changed)
        self.app.core.unsubscribe("commandline.error", self.on_error)
        self.app.core.unsubscribe("commandline.executed", self.on_executed)

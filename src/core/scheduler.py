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
"""UI-agnostic periodic timer scheduler for core subsystems."""

from __future__ import annotations

import threading
import typing


class TimerScheduler(typing.Protocol):
    """Protocol for scheduling and cancelling periodic callbacks."""

    def timeout_add(
        self, interval_ms: int, callback: typing.Callable[[], bool]
    ) -> typing.Any:  # noqa: ANN401
        """Schedule *callback* every *interval_ms* until it returns False."""

    def source_remove(self, handle: typing.Any) -> None:  # noqa: ANN401
        """Cancel a previously scheduled timer handle."""


class ThreadingScheduler:
    """Default pure-Python periodic scheduler using daemon threads."""

    def timeout_add(
        self, interval_ms: int, callback: typing.Callable[[], bool]
    ) -> threading.Event:
        """Schedule *callback* repeatedly every *interval_ms*."""
        stop_event = threading.Event()
        interval_sec = max(0.001, interval_ms / 1000.0)

        def _loop() -> None:
            while not stop_event.wait(interval_sec):
                if not callback():
                    break

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return stop_event

    def source_remove(self, handle: typing.Any) -> None:  # noqa: ANN401
        """Stop the periodic timer associated with *handle*."""
        if isinstance(handle, threading.Event):
            handle.set()

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
"""Unit tests for RepeatedTimer single-thread execution and lifecycle."""

from __future__ import annotations

import threading
import time

from olc.timer import RepeatedTimer


def test_repeated_timer_single_thread_and_stop() -> None:
    """Verify RepeatedTimer reuses one thread and stops cleanly."""
    thread_ids: set[int] = set()
    hits = 0
    done = threading.Event()

    def on_tick() -> None:
        nonlocal hits
        thread_ids.add(threading.get_ident())
        hits += 1
        if hits >= 3:
            done.set()

    timer = RepeatedTimer(0.01, on_tick)
    try:
        assert done.wait(timeout=1.0)
        assert hits >= 3
        assert len(thread_ids) == 1
    finally:
        timer.stop()

    assert timer.is_running is False
    count_after_stop = hits
    time.sleep(0.05)
    assert hits == count_after_stop

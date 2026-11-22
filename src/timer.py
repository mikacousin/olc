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
import threading
import time
from typing import Callable


class RepeatedTimer:
    """Call a function every 'interval' seconds using one persistent thread."""

    def __init__(
        self, interval: float, function: Callable, *args: object, **kwargs: object
    ) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.next_call = time.monotonic()
        self.start()

    def _loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.next_call += self.interval
            wait_time = self.next_call - time.monotonic()
            if wait_time > 0.0 and stop_event.wait(wait_time):
                break
            if stop_event.is_set():
                break
            self.function(*self.args, **self.kwargs)
            # Prevent catch-up storms if execution stalls temporarily
            now = time.monotonic()
            if self.next_call < now - self.interval:
                self.next_call = now

    def start(self) -> None:
        """Start periodic execution."""
        with self._lock:
            if not self.is_running:
                stop_event = threading.Event()
                self._stop_event = stop_event
                self.is_running = True
                self.next_call = time.monotonic()
                thread = threading.Thread(
                    target=self._loop,
                    args=(stop_event,),
                    name="RepeatedTimer",
                    daemon=True,
                )
                self._thread = thread
                thread.start()

    def stop(self) -> None:
        """Stop periodic execution cleanly."""
        with self._lock:
            self.is_running = False
            self._stop_event.set()
            self._thread = None

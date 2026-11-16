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
import sys
import threading
import time
from collections import deque
from typing import Callable


class DMXLoop:  # pylint: disable=too-many-instance-attributes
    """
    Manages a thread dedicated to sending DMX at a fixed frequency.

    Usage:
        loop = DMXLoop(send_fn=my_send, hz=40)
        loop.start()
        ...
        loop.stop()

    Or via context manager:
        with DMXLoop(send_fn=my_send, hz=40):
            time.sleep(10)
    """

    def __init__(
        self,
        send_fn: Callable[[], None],
        hz: float = 40.0,
        busywait_threshold: float = 0.002 if sys.platform == "win32" else 0.0,
        window_seconds: float = 30.0,
    ) -> None:
        self.send_fn = send_fn
        self.hz = hz
        self.period = 1.0 / hz
        self.busywait_threshold = busywait_threshold
        self.window_seconds = window_seconds

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._lock = threading.Lock()
        self._frame_count: int = 0
        self._late_count: int = 0
        self._last_jitter: float = 0.0
        self._start_time: float | None = None

        # Sliding window: timestamps of recent frames
        self._frame_timestamps: deque[float] = deque(
            maxlen=int(window_seconds * hz * 2)
        )

    def start(self) -> None:
        """Starts the DMX thread. Raises RuntimeError if already active."""
        if self.is_running:
            raise RuntimeError("DMXLoop is already running.")

        self._stop_event.clear()
        self._frame_count = 0
        self._late_count = 0
        self._frame_timestamps.clear()

        self._thread = threading.Thread(target=self._loop, name="DMXLoop", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stops the thread cleanly and waits for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    @property
    def is_running(self) -> bool:
        """Returns True if the loop thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def __enter__(self) -> "DMXLoop":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    @property
    def frame_count(self) -> int:
        """Total number of frames sent."""
        with self._lock:
            return self._frame_count

    @property
    def late_count(self) -> int:
        """Number of frames sent late (jitter > 10% of the period)."""
        with self._lock:
            return self._late_count

    @property
    def last_jitter(self) -> float:
        """Difference in seconds between the expected tick and the actual send."""
        with self._lock:
            return self._last_jitter

    @property
    def effective_hz(self) -> float:
        """Average real frequency since startup."""
        elapsed = self._elapsed
        if elapsed is None or elapsed == 0:
            return 0.0
        return self.frame_count / elapsed

    @property
    def windowed_hz(self) -> float | None:
        """
        Real frequency over the last `window_seconds` seconds.
        Returns None if the window is not yet full.
        """
        now = time.perf_counter()
        cutoff = now - self.window_seconds

        with self._lock:
            # Purge timestamps outside the window
            while self._frame_timestamps and self._frame_timestamps[0] < cutoff:
                self._frame_timestamps.popleft()

            count = len(self._frame_timestamps)

            if count < 2:
                return None

            # Window not yet full
            if self._elapsed is not None and self._elapsed < self.window_seconds:
                return None

            span = self._frame_timestamps[-1] - self._frame_timestamps[0]

        if span == 0:
            return None

        return (count - 1) / span

    def _loop(self) -> None:
        next_tick = time.perf_counter()
        self._start_time = next_tick

        while not self._stop_event.is_set():
            now = time.perf_counter()
            jitter = now - next_tick
            self.send_fn()

            with self._lock:
                self._frame_count += 1
                self._last_jitter = jitter
                if jitter > self.period * 0.1:
                    self._late_count += 1
                self._frame_timestamps.append(now)

            next_tick += self.period
            sleep_for = next_tick - time.perf_counter() - self.busywait_threshold

            if sleep_for > 0:
                time.sleep(sleep_for)

            # Busy-wait for the last microseconds
            # Active only if busywait_threshold > 0 (Windows)
            while time.perf_counter() < next_tick:
                if self._stop_event.is_set():
                    return

    @property
    def _elapsed(self) -> float | None:
        if self._start_time is None:
            return None
        return time.perf_counter() - self._start_time

    def __repr__(self) -> str:
        state = "running" if self.is_running else "stopped"
        windowed = self.windowed_hz
        windowed_str = (
            f"{windowed:.1f}Hz"
            if windowed is not None
            else f"<{self.window_seconds:.0f}s"
        )

        return (
            f"<DMXLoop {state} | "
            f"target {self.hz}Hz | "
            f"{windowed_str} ({self.window_seconds:.0f}s) / "
            f"{self.effective_hz:.1f}Hz total | "
            f"frames={self.frame_count} late={self.late_count} | "
            f"jitter={self.last_jitter * 1000:.2f}ms>"
        )

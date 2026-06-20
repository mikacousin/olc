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
import time
from dataclasses import dataclass, field

import numpy as np
from olc.core.universe_data import DMXUniverse


@dataclass
class Fade:
    """Represents a single in-progress fade between two DMX frames."""

    start: np.ndarray
    target: np.ndarray
    duration: float
    t0: float = field(default_factory=time.monotonic)
    done: bool = False

    def compute(self, now: float) -> np.ndarray:
        """Compute the interpolated frame at the given timestamp."""
        if self.duration <= 0:
            self.done = True
            return self.target

        t = min((now - self.t0) / self.duration, 1.0)
        if t >= 1.0:
            self.done = True
            return self.target

        # Linear interpolation over 512 channels — no per-channel loop, zero allocation
        return (self.start + t * (self.target.astype(np.float32) - self.start)).astype(
            np.uint8
        )


class FadeEngine:
    """
    Manages the active fade on a DMX universe.
    Call tick() on every DMX frame to update the universe values.
    """

    def __init__(self, universe: DMXUniverse) -> None:
        self._universe = universe
        self._fade: Fade | None = None

    def go(self, target: np.ndarray, duration: float) -> None:
        """Starts a fade toward `target` over `duration` seconds."""
        self._fade = Fade(
            start=self._universe.snapshot(),
            target=target.astype(np.uint8),
            duration=max(duration, 0.0),
        )

    def snap(self, target: np.ndarray) -> None:
        """Applies the target immediately without a fade."""
        self._universe.apply_array(target)
        self._fade = None

    def tick(self) -> bool:
        """
        Updates the universe if a fade is active.
        Returns True while a fade is still running.
        """
        if self._fade is None or self._fade.done:
            return False
        frame = self._fade.compute(time.monotonic())
        self._universe.apply_array(frame)
        return not self._fade.done

    @property
    def is_fading(self) -> bool:
        """Returns True if a fade is currently active."""
        return self._fade is not None and not self._fade.done

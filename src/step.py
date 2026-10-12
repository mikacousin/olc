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
from typing import Optional

if typing.TYPE_CHECKING:
    from olc.cue import Cue

POSITION_PARAMETERS: frozenset[str] = frozenset({"pan", "tilt"})
COLOR_PARAMETERS: frozenset[str] = frozenset(
    {"color", "colour", "cct", "color_temp", "colortemp"}
)


def get_parameter_family(param_name: str) -> str:
    """Return the IFCB attribute family ('intensity', 'position', 'color', 'beam')."""
    p_lower = param_name.lower()
    if p_lower == "intensity":
        return "intensity"
    if p_lower in POSITION_PARAMETERS:
        return "position"
    if p_lower in COLOR_PARAMETERS:
        return "color"
    return "beam"


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class Step:
    """Step
    A Step is used to store times and a Cue in a Sequence
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    def __init__(
        self,
        sequence: float = 0.0,
        cue: Optional[Cue] = None,
        time_in: float = 5.0,
        time_out: float = 5.0,
        delay_in: float = 0.0,
        delay_out: float = 0.0,
        wait: float = 0.0,
        channel_time: Optional[dict] = None,
        text: str = "",
        time_position: Optional[float] = None,
        delay_position: Optional[float] = None,
        time_color: Optional[float] = None,
        delay_color: Optional[float] = None,
        time_beam: Optional[float] = None,
        delay_beam: Optional[float] = None,
    ) -> None:
        self.sequence = sequence
        self.cue = cue
        self.time_in = time_in
        self.time_out = time_out
        self.delay_in = delay_in
        self.delay_out = delay_out
        self.wait = wait
        if channel_time is None:
            channel_time = {}
        self.channel_time = channel_time
        self.text = text
        self.time_position = time_position
        self.delay_position = delay_position
        self.time_color = time_color
        self.delay_color = delay_color
        self.time_beam = time_beam
        self.delay_beam = delay_beam

        self.update_total_time()

    @property
    def effective_time_position(self) -> float:
        """Return Position fade time (inherits time_in when None)."""
        return self.time_in if self.time_position is None else self.time_position

    @property
    def effective_delay_position(self) -> float:
        """Return Position delay time (inherits delay_in when None)."""
        return self.delay_in if self.delay_position is None else self.delay_position

    @property
    def effective_time_color(self) -> float:
        """Return Color fade time (inherits time_in when None)."""
        return self.time_in if self.time_color is None else self.time_color

    @property
    def effective_delay_color(self) -> float:
        """Return Color delay time (inherits delay_in when None)."""
        return self.delay_in if self.delay_color is None else self.delay_color

    @property
    def effective_time_beam(self) -> float:
        """Return Beam/Optics fade time (inherits time_in when None)."""
        return self.time_in if self.time_beam is None else self.time_beam

    @property
    def effective_delay_beam(self) -> float:
        """Return Beam/Optics delay time (inherits delay_in when None)."""
        return self.delay_in if self.delay_beam is None else self.delay_beam

    def has_explicit_family_timing(self, family: str) -> bool:
        """Return True if the given IFCB family has an explicit time or delay set."""
        fam = family.lower()
        if fam == "position":
            return self.time_position is not None or self.delay_position is not None
        if fam == "color":
            return self.time_color is not None or self.delay_color is not None
        if fam == "beam":
            return self.time_beam is not None or self.delay_beam is not None
        return False

    def get_attribute_timing(self, param_name: str) -> tuple[float, float]:
        """Return (effective_delay, effective_time) for a parameter's IFCB family."""
        family = get_parameter_family(param_name)
        if family == "position":
            return self.effective_delay_position, self.effective_time_position
        if family == "color":
            return self.effective_delay_color, self.effective_time_color
        if family == "beam":
            return self.effective_delay_beam, self.effective_time_beam
        return self.delay_in, self.time_in

    def update_total_time(self) -> None:
        """Calculate Total Time across Intensity, IFCB families, and ChannelTime."""
        max_end = max(
            self.time_in + self.delay_in,
            self.time_out + self.delay_out,
            self.effective_time_position + self.effective_delay_position,
            self.effective_time_color + self.effective_delay_color,
            self.effective_time_beam + self.effective_delay_beam,
        )
        self.total_time = max_end + self.wait

        for channel in self.channel_time.keys():
            self.total_time = max(
                self.total_time,
                self.channel_time[channel].delay
                + self.channel_time[channel].time
                + self.wait,
            )

    def set_time_in(self, time_in: float) -> None:
        """Set Time In

        Args:
            time_in: Time In
        """
        self.time_in = time_in
        self.update_total_time()

    def set_time_out(self, time_out: float) -> None:
        """Set Time Out

        Args:
            time_out: Time Out
        """
        self.time_out = time_out
        self.update_total_time()

    def set_delay_in(self, delay_in: float) -> None:
        """Set Delay In

        Args:
            delay_in: Delay In
        """
        self.delay_in = delay_in
        self.update_total_time()

    def set_delay_out(self, delay_out: float) -> None:
        """Set Delay Out

        Args:
            delay_out: Delay Out
        """
        self.delay_out = delay_out
        self.update_total_time()

    def set_wait(self, wait: float) -> None:
        """Set Wait

        Args:
            wait: Wait
        """
        self.wait = wait
        self.update_total_time()

    def set_time(self, time: float) -> None:
        """Set Time In and Time Out

        Args:
            time: Time
        """
        self.time_in = time
        self.time_out = time
        self.update_total_time()

    def set_delay(self, delay: float) -> None:
        """Set Delay In and Out

        Args:
            delay: Delay
        """
        self.delay_in = delay
        self.delay_out = delay
        self.update_total_time()

    def set_time_position(self, time_position: Optional[float]) -> None:
        """Set Position family fade time (None to inherit time_in)."""
        self.time_position = time_position
        self.update_total_time()

    def set_delay_position(self, delay_position: Optional[float]) -> None:
        """Set Position family delay time (None to inherit delay_in)."""
        self.delay_position = delay_position
        self.update_total_time()

    def set_time_color(self, time_color: Optional[float]) -> None:
        """Set Color family fade time (None to inherit time_in)."""
        self.time_color = time_color
        self.update_total_time()

    def set_delay_color(self, delay_color: Optional[float]) -> None:
        """Set Color family delay time (None to inherit delay_in)."""
        self.delay_color = delay_color
        self.update_total_time()

    def set_time_beam(self, time_beam: Optional[float]) -> None:
        """Set Beam/Optics family fade time (None to inherit time_in)."""
        self.time_beam = time_beam
        self.update_total_time()

    def set_delay_beam(self, delay_beam: Optional[float]) -> None:
        """Set Beam/Optics family delay time (None to inherit delay_in)."""
        self.delay_beam = delay_beam
        self.update_total_time()

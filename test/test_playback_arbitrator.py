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
"""Unit tests for PlaybackArbitrator and Sequence playback options."""

from __future__ import annotations

import pytest

from olc.core.playback_arbitrator import (
    PlaybackArbitrator,
    PlaybackPriority,
    parse_playback_priority,
)
from olc.show.sequence import Sequence


def test_arbitrator_htp_intensity_and_fader_scaling() -> None:
    """Verify HTP intensity merging and fader scaling across concurrent sequences."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(1, {1: 0.6, 2: 0.4}, cue_number=1.0, fader_level=1.0)
    out = arb.set_sequence_output(2, {1: 0.9, 2: 0.8}, cue_number=10.0, fader_level=0.5)

    # Ch 1: max(0.6, 0.9 * 0.5 = 0.45) = 0.6 -> owned by Seq 1
    assert out.intensities[0] == pytest.approx(0.6)
    assert out.owners[1] == (1.0, 1.0)
    # Ch 2: max(0.4, 0.8 * 0.5 = 0.4) -> Seq 2 at full fader wins
    out2 = arb.set_fader_level(2, 1.0)
    assert out2.intensities[0] == pytest.approx(0.9)
    assert out2.intensities[1] == pytest.approx(0.8)
    assert out2.owners[1] == (2.0, 10.0)


def test_arbitrator_ltp_intensity_mode() -> None:
    """Verify htp_intensity=False allows lower latest level to override HTP."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(1, {1: 0.9}, cue_number=1.0, htp_intensity=True)
    out = arb.set_sequence_output(2, {1: 0.25}, cue_number=2.0, htp_intensity=False)

    assert out.intensities[0] == pytest.approx(0.25)
    assert out.owners[1] == (2.0, 2.0)


def test_arbitrator_priority_stack() -> None:
    """Verify SUPER > HIGH > NORMAL > LOW priority tiers for intensity and ML attrs."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(
        1,
        {1: 0.8},
        {1: {"color": "#ff0000", "pan": 0.2}},
        priority=PlaybackPriority.HIGH,
        cue_number=1.0,
    )
    out = arb.set_sequence_output(
        2,
        {1: 0.3},
        {1: {"color": "#00ff00", "tilt": 0.7}},
        priority=PlaybackPriority.LOW,
        cue_number=5.0,
    )
    # Even though Seq 2 ran later, HIGH priority beats LOW on shared keys
    assert out.intensities[0] == pytest.approx(0.8)
    assert out.device_values[1]["color"] == "#ff0000"
    assert out.device_values[1]["pan"] == 0.2
    assert out.device_values[1]["tilt"] == 0.7

    # SUPER beats HIGH even with lower intensity
    out_sup = arb.set_sequence_output(
        3,
        {1: 0.1},
        {1: {"color": "#ffffff"}},
        priority=PlaybackPriority.SUPER,
        cue_number=99.0,
    )
    assert out_sup.intensities[0] == pytest.approx(0.1)
    assert out_sup.device_values[1]["color"] == "#ffffff"
    assert out_sup.param_owners[(1, "color")] == (3.0, 99.0)


def test_arbitrator_ltp_device_values_and_assert_reclaim() -> None:
    """Verify LTP device parameter arbitration and assert_sequence ownership reclaim."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(
        1,
        None,
        {1: {"color": "#0000ff", "zoom": 0.5}},
        cue_number=1.0,
    )
    out = arb.set_sequence_output(
        2,
        None,
        {1: {"color": "#ff0000"}},
        cue_number=2.0,
    )
    assert out.device_values[1]["color"] == "#ff0000"
    assert out.device_values[1]["zoom"] == 0.5
    assert out.param_owners[(1, "color")] == (2.0, 2.0)

    # Assert Seq 1 reclaims color ownership
    out_assert = arb.assert_sequence(1)
    assert out_assert.device_values[1]["color"] == "#0000ff"
    assert out_assert.param_owners[(1, "color")] == (1.0, 1.0)


def test_arbitrator_release_fallback_and_home_orphans() -> None:
    """Verify release_sequence falls back to lower layer and reports orphan params."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(
        1,
        {1: 0.5},
        {1: {"color": "#0000ff"}},
        cue_number=1.0,
    )
    arb.set_sequence_output(
        2,
        {1: 1.0},
        {1: {"color": "#ff0000", "gobo": 3}},
        cue_number=2.0,
    )

    out, orphans = arb.release_sequence(2)
    assert 2.0 not in arb.active_sequences()
    assert out.intensities[0] == pytest.approx(0.5)
    assert out.device_values[1] == {"color": "#0000ff"}
    assert orphans == {1: {"gobo"}}


def test_arbitrator_off_on_overwritten() -> None:
    """Verify off_on_overwritten auto-releases a completely dominated sequence."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(
        2,
        None,
        {1: {"color": "#00ff00"}},
        off_on_overwritten=True,
        cue_number=1.0,
    )
    assert 2.0 in arb.active_sequences()

    # Seq 1 overwrites the only parameter Seq 2 owned -> Seq 2 auto-releases
    arb.set_sequence_output(1, None, {1: {"color": "#ff00ff"}}, cue_number=1.0)
    assert 2.0 not in arb.active_sequences()


def test_sequence_playback_options_serialization() -> None:
    """Verify Sequence playback options defaults and dict round-trip."""
    seq = Sequence(2, text="FX Seq")
    assert seq.priority is PlaybackPriority.NORMAL
    assert seq.htp_intensity is True
    assert seq.playback_options_to_dict() == {}

    seq.priority = PlaybackPriority.HIGH
    seq.htp_intensity = False
    seq.auto_start = True
    seq.auto_stop = True
    seq.off_on_overwritten = True
    seq.wrap_around = True
    seq.release_on_end = True
    seq.release_time = 1.5

    payload = seq.playback_options_to_dict()
    seq2 = Sequence(2, text="Restored")
    seq2.apply_playback_options(payload)
    assert seq2.priority is PlaybackPriority.HIGH
    assert seq2.htp_intensity is False
    assert seq2.auto_start is True
    assert seq2.auto_stop is True
    assert seq2.off_on_overwritten is True
    assert seq2.wrap_around is True
    assert seq2.release_on_end is True
    assert seq2.release_time == 1.5
    assert parse_playback_priority("super") is PlaybackPriority.SUPER


def test_arbitrator_set_sequence_output_reports_released_to_home() -> None:
    """Verify set_sequence_output reports orphaned params unless owned elsewhere."""
    arb = PlaybackArbitrator()
    arb.set_sequence_output(
        1,
        {1: 1.0, 2: 0.8},
        {1: {"intensity": 1.0, "pan": 45.0}, 2: {"intensity": 0.8, "color": "#ff0000"}},
        cue_number=2.0,
    )
    # Seq 2 also owns color on device 2
    arb.set_sequence_output(
        2,
        {2: 0.5},
        {2: {"color": "#00ff00"}},
        cue_number=1.0,
    )

    # Seq 1 steps back to Cue 0 (empty device_values & 0 intensities)
    out = arb.set_sequence_output(1, {}, {}, cue_number=0.0)
    assert out.released_to_home[1] == {"intensity", "pan"}
    # Device 2 color is still owned by Seq 2, so only intensity is orphaned
    assert out.released_to_home[2] == {"intensity"}
    assert out.device_values[2] == {"color": "#00ff00"}

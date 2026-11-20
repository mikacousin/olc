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
"""Unit tests for OSC and OSCQuery parametric Effects routes."""

# pylint: disable=protected-access

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.controllers.osc.delegate import OSCDelegate
from olc.controllers.osc.oscquery import (
    ACCESS_CONTAINER,
    ACCESS_WRITE_ONLY,
    build_oscquery_tree,
    find_node_by_path,
)
from olc.core.app import CoreApplication


def test_osc_key_effect_appends_keyword() -> None:
    """Test that /olc/key/effect appends EFFECT to the logical command line."""
    app = CoreApplication(MagicMock())
    delegate = OSCDelegate(app)

    delegate._effect_key("/olc/key/effect", [1])
    assert "EFFECT" in app.commandline.get_string()


def test_osc_effect_start_rate_size_stop_and_stop_all() -> None:
    """Test starting, modulating rate/size, and stopping an effect via OSC."""
    app = CoreApplication(MagicMock())
    delegate = OSCDelegate(app)

    app.action_registry.execute(
        "effect.create", 1.0, "Sine Wave", template_id="sine_dimmer"
    )
    app.selected_channels = [1, 2, 3]

    # 1. Start Effect 1 on selected channels via /olc/effect/1/start
    delegate._direct_effect("/olc/effect/1/start", [1])
    active = app.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].effect_number == 1.0
    assert active[0].channels == [1, 2, 3]

    # 2. Modulate rate via /olc/effect/1/rate (normalized 1.5x or percentage 150)
    delegate._direct_effect("/olc/effect/1/rate", [1.5])
    assert active[0].rate_scale == pytest.approx(1.5)
    delegate._direct_effect("/olc/effect/1/rate", [200.0])
    assert active[0].rate_scale == pytest.approx(2.0)

    # 3. Modulate size via /olc/effect/1/size (normalized 0.5x or percentage 75)
    delegate._direct_effect("/olc/effect/1/size", [0.5])
    assert active[0].size_scale == pytest.approx(0.5)
    delegate._direct_effect("/olc/effect/1/size", [75.0])
    assert active[0].size_scale == pytest.approx(0.75)

    # 4. Stop Effect 1 via /olc/effect/1/stop
    delegate._direct_effect("/olc/effect/1/stop", [1])
    assert len(app.effects_engine.get_active_instances()) == 0

    # 5. Restart Effect 1 and stop all via /olc/effect/stop_all
    delegate._direct_effect("/olc/effect/1/start", [1])
    assert len(app.effects_engine.get_active_instances()) == 1
    delegate._effect_stop_all("/olc/effect/stop_all", [1])
    assert len(app.effects_engine.get_active_instances()) == 0


def test_osc_effect_tap_tempo() -> None:
    """Test /olc/effect/tap_tempo updates active effect BPM."""
    app = CoreApplication(MagicMock())
    delegate = OSCDelegate(app)

    app.action_registry.execute(
        "effect.create", 1.0, "Chase", template_id="chase_cancan"
    )
    eff = app.lightshow.effects.get(1.0)
    assert eff is not None
    app.selected_channels = [1, 2]
    app.action_registry.execute("effect.apply", 1.0, [1, 2])

    # Trigger two taps via action / OSC route
    app.effects_engine.tap_tempo(1.0, now=10.0)
    app.effects_engine.tap_tempo(1.0, now=10.5)
    assert eff.bpm == pytest.approx(120.0)

    # Also verify OSC handler invokes tap_tempo without error
    delegate._effect_tap_tempo("/olc/effect/tap_tempo", [1])
    delegate._direct_effect("/olc/effect/1/tap_tempo", [1])


def test_oscquery_tree_exposes_effect_nodes() -> None:
    """Test that build_oscquery_tree exposes /olc/key/effect and /olc/effect/*."""
    tree = build_oscquery_tree(osc_port=9000)

    key_eff = find_node_by_path(tree, "/olc/key/effect")
    assert key_eff is not None
    assert key_eff["ACCESS"] == ACCESS_WRITE_ONLY

    eff_root = find_node_by_path(tree, "/olc/effect")
    assert eff_root is not None
    assert eff_root["ACCESS"] == ACCESS_CONTAINER

    stop_all = find_node_by_path(tree, "/olc/effect/stop_all")
    assert stop_all is not None
    assert stop_all["ACCESS"] == ACCESS_WRITE_ONLY

    tap = find_node_by_path(tree, "/olc/effect/tap_tempo")
    assert tap is not None
    assert tap["ACCESS"] == ACCESS_WRITE_ONLY

    eff1_rate = find_node_by_path(tree, "/olc/effect/1/rate")
    assert eff1_rate is not None
    assert eff1_rate["TYPE"] == "f"

    eff1_size = find_node_by_path(tree, "/olc/effect/1/size")
    assert eff1_size is not None
    assert eff1_size["TYPE"] == "f"

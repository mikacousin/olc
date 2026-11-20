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
"""Unit tests for Effect actions (create, delete, rename, update, apply, stop, tap)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.core.dmx_backend import DMXBackend
from olc.core.effects_engine import EffectsEngine
from olc.show.effect import DistributeDirection, EffectDefinition, WaveformType


class _ManualScheduler:
    """Deterministic no-thread timer scheduler for unit testing."""

    def __init__(self) -> None:
        self.active_handles: list[int] = []
        self._next_id = 1

    def timeout_add(
        self,
        interval_ms: int,
        callback: Any,  # noqa: ANN401
    ) -> int:
        _ = (interval_ms, callback)
        handle = self._next_id
        self._next_id += 1
        self.active_handles.append(handle)
        return handle

    def source_remove(self, handle: Any) -> None:  # noqa: ANN401
        if handle in self.active_handles:
            self.active_handles.remove(handle)


def _make_app() -> CoreApplication:
    settings = MagicMock()
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    app.backend = DMXBackend(app.lightshow)
    app.effects_engine = EffectsEngine(
        app=app, lightshow=app.lightshow, scheduler=_ManualScheduler()
    )
    return app


def test_effect_create_and_delete_undo_redo() -> None:
    """Test effect.create and effect.delete with full Undo/Redo support."""
    app = _make_app()
    created: list[float] = []
    deleted: list[float] = []
    app.subscribe("effect.created", created.append)
    app.subscribe("effect.deleted", deleted.append)

    # Create Effect 1 from Circle template
    eff = app.action_registry.execute(
        "effect.create", 1.0, template_id="circle", label="Main Circle"
    )
    assert isinstance(eff, EffectDefinition)
    assert eff.number == pytest.approx(1.0)
    assert eff.label == "Main Circle"
    assert len(eff.layers) == 2
    assert created == [1.0]

    # Undo creation
    app.history.undo()
    assert app.lightshow.effects.get(1.0) is None
    assert deleted == [1.0]

    # Redo creation
    app.history.redo()
    eff_redone = app.lightshow.effects.get(1.0)
    assert eff_redone is not None
    assert eff_redone.label == "Main Circle"

    # Start effect and delete it -> should stop running instance too
    app.action_registry.execute("effect.apply", 1.0, channels=[1, 2, 3, 4])
    assert app.effects_engine.has_active_effects

    app.action_registry.execute("effect.delete", 1.0)
    assert app.lightshow.effects.get(1.0) is None
    assert not app.effects_engine.has_active_effects

    # Undo deletion restores effect definition
    app.history.undo()
    eff_restored = app.lightshow.effects.get(1.0)
    assert eff_restored is not None
    assert eff_restored.label == "Main Circle"

    # Redo deletion removes effect again
    app.history.redo()
    assert app.lightshow.effects.get(1.0) is None


def test_effect_rename_and_update_undo_redo() -> None:
    """Test effect.rename and effect.update actions with Undo/Redo."""
    app = _make_app()
    app.action_registry.execute("effect.create", 2.0, template_id="sine_dimmer")

    # Rename
    app.action_registry.execute("effect.rename", 2.0, "Slow Sine")
    eff2 = app.lightshow.effects.get(2.0)
    assert eff2 is not None and eff2.label == "Slow Sine"

    app.history.undo()
    eff2 = app.lightshow.effects.get(2.0)
    assert eff2 is not None and eff2.label == "Sine Dimmer"

    app.history.redo()
    eff2 = app.lightshow.effects.get(2.0)
    assert eff2 is not None and eff2.label == "Slow Sine"

    # Update bpm, size, wings, direction while running
    app.action_registry.execute("effect.apply", 2.0, channels=[1, 2, 3, 4])
    app.action_registry.execute(
        "effect.update",
        2.0,
        bpm=120.0,
        size=75.0,
        groups=2,
        blocks=1,
        wings=2,
        direction=DistributeDirection.BOUNCE,
    )
    eff = app.lightshow.effects.get(2.0)
    assert eff is not None
    assert eff.bpm == pytest.approx(120.0)
    assert eff.cycle_time == pytest.approx(0.5)
    assert eff.layers[0].size == pytest.approx(75.0)
    assert eff.groups == 2
    assert eff.wings == 2
    assert eff.direction == DistributeDirection.BOUNCE

    # Undo update
    app.history.undo()
    eff_undone = app.lightshow.effects.get(2.0)
    assert eff_undone is not None
    assert eff_undone.cycle_time == pytest.approx(3.0)
    assert eff_undone.layers[0].size == pytest.approx(50.0)
    assert eff_undone.wings == 1
    assert eff_undone.direction == DistributeDirection.FORWARD

    # Redo update
    app.history.redo()
    eff_redone = app.lightshow.effects.get(2.0)
    assert eff_redone is not None
    assert eff_redone.bpm == pytest.approx(120.0)
    assert eff_redone.layers[0].size == pytest.approx(75.0)
    assert eff_redone.layers[0].waveform == WaveformType.SINE


def test_effect_apply_and_stop_live_state_undo_redo() -> None:
    """Test effect.apply and effect.stop update live_state and support Undo/Redo."""
    app = _make_app()
    app.action_registry.execute("effect.create", 3.0, template_id="figure_8")

    # Apply to channels [4, 3, 2, 1] with rate/size scales
    affected = app.action_registry.execute(
        "effect.apply",
        3.0,
        channels=[4, 3, 2, 1],
        rate_scale=1.5,
        size_scale=0.5,
        wings=2,
    )
    assert affected == [4, 3, 2, 1]
    assert app.effects_engine.has_active_effects
    ref_4 = app.live_state.get_effect_ref(4)
    ref_1 = app.live_state.get_effect_ref(1)
    assert ref_4 is not None and ref_4["order_index"] == 0
    assert ref_1 is not None and ref_1["order_index"] == 3
    assert ref_4["rate_scale"] == pytest.approx(1.5)
    assert ref_4["size_scale"] == pytest.approx(0.5)
    assert ref_4["wings"] == 2

    # Stop on channels [2, 1] only
    stopped = app.action_registry.execute("effect.stop", channels=[2, 1])
    assert isinstance(stopped, list) and set(stopped) == {1, 2}
    insts = app.effects_engine.get_active_instances()
    assert len(insts) == 1
    assert insts[0].channels == [4, 3]
    assert app.live_state.get_effect_ref(2) == {"stop": True}

    # Undo stop -> channels [4, 3, 2, 1] active again
    app.history.undo()
    insts = app.effects_engine.get_active_instances()
    assert len(insts) == 1
    assert insts[0].channels == [4, 3, 2, 1]
    ref_2 = app.live_state.get_effect_ref(2)
    assert ref_2 is not None and ref_2["effect"] == pytest.approx(3.0)

    # Undo apply -> no active effects and live_state cleared
    app.history.undo()
    assert not app.effects_engine.has_active_effects
    assert app.live_state.get_all_effect_refs() == {}


def test_effect_tap_tempo_action() -> None:
    """Test effect.tap_tempo action calculates BPM from tap intervals."""
    app = _make_app()
    app.action_registry.execute("effect.create", 1.0, template_id="chase_cancan")

    res1 = app.action_registry.execute("effect.tap_tempo", 1.0, now=10.0)
    assert res1 is None
    res2 = app.action_registry.execute("effect.tap_tempo", 1.0, now=10.5)
    assert res2 == pytest.approx(120.0)
    eff1 = app.lightshow.effects.get(1.0)
    assert eff1 is not None and eff1.bpm == pytest.approx(120.0)

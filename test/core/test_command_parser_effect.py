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
"""Unit tests for Effect CLI parser, completer, executor, cue tracking, and .olc I/O."""

from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.core.dmx_backend import DMXBackend
from olc.core.effects_engine import EffectsEngine
from olc.core.parser.ast_nodes import (
    ApplyEffectCommandNode,
    DeleteEffectCommandNode,
    EditEffectCommandNode,
    StopEffectCommandNode,
)
from olc.core.parser.completer import CommandCompleter
from olc.core.parser.executor import CommandExecutor
from olc.core.parser.highlighter import highlight_commandline_markup
from olc.core.parser.parser import CommandParser
from olc.core.sneak import SneakController
from olc.core.tracking import TrackingEngine
from olc.devices.channel import Channel, ChannelType, FixtureType
from olc.devices.device import LightingDevice
from olc.files.file_type import FileType
from olc.files.import_file import ImportFile
from olc.files.olc.writer import OlcWriter
from olc.show.sequence_threads import _sync_resolved_effects


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


def _make_app() -> tuple[CoreApplication, _ManualScheduler]:
    settings = MagicMock()
    settings.get_boolean.return_value = True
    settings.get_double.return_value = 3.0
    app = CoreApplication(settings)
    app.backend = DMXBackend(app.lightshow)
    sched = _ManualScheduler()
    app.effects_engine = EffectsEngine(
        app=app, lightshow=app.lightshow, scheduler=sched
    )
    app.sneak_controller = SneakController(app, scheduler=sched)
    return app, sched


def _patch_moving_head(
    app: CoreApplication, fixture_id: int, address: int
) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.MOVING_HEAD,
        label=f"Spot {fixture_id}",
        manufacturer="OLC",
        model="Spot",
    )
    dev.add_channel(
        Channel(universe=1, address=address, channel_type=ChannelType.INTENSITY)
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 1,
            channel_type=ChannelType.PAN,
            physical_min=-270.0,
            physical_max=270.0,
            default_value=128,
        )
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 2,
            channel_type=ChannelType.TILT,
            physical_min=-135.0,
            physical_max=135.0,
            default_value=128,
        )
    )
    app.lightshow.patch.restore_device(dev)
    app.lightshow.patch.invalidate_cache()
    return dev


def test_parse_effect_commands() -> None:
    """Test parsing of EFFECT, FX, STOP EFFECT, STOMP, and DELETE EFFECT commands."""
    parser = CommandParser()

    node1 = parser.parse("1 THRU 8 EFFECT 1")
    assert isinstance(node1, ApplyEffectCommandNode)
    assert node1.effect_id == pytest.approx(1.0)
    assert node1.selection is not None

    node2 = parser.parse("1 THRU 8 FX 2 RATE 120 SIZE 50 GROUPS 2 BLOCKS 2 WINGS 2")
    assert isinstance(node2, ApplyEffectCommandNode)
    assert node2.effect_id == pytest.approx(2.0)
    assert node2.rate == pytest.approx(120.0)
    assert node2.size == pytest.approx(50.0)
    assert node2.groups == 2
    assert node2.blocks == 2
    assert node2.wings == 2

    node3 = parser.parse("1 THRU 4 STOP EFFECT")
    assert isinstance(node3, StopEffectCommandNode)
    assert node3.selection is not None
    assert node3.effect_id is None

    node4 = parser.parse("1 THRU 4 EFFECT")
    assert isinstance(node4, StopEffectCommandNode)
    assert node4.selection is not None
    assert node4.effect_id is None

    node5 = parser.parse("STOP EFFECT 3")
    assert isinstance(node5, StopEffectCommandNode)
    assert node5.selection is None
    assert node5.effect_id == pytest.approx(3.0)

    node6 = parser.parse('EFFECT 1 LABEL "Ballyhoo Public"')
    assert isinstance(node6, EditEffectCommandNode)
    assert node6.effect_id == pytest.approx(1.0)
    assert node6.label == "Ballyhoo Public"

    node7 = parser.parse("EFFECT 1 RATE 90 SIZE 60")
    assert isinstance(node7, EditEffectCommandNode)
    assert node7.effect_id == pytest.approx(1.0)
    assert node7.rate == pytest.approx(90.0)
    assert node7.size == pytest.approx(60.0)

    node8 = parser.parse("DELETE EFFECT 4")
    assert isinstance(node8, DeleteEffectCommandNode)
    assert node8.effect_id == pytest.approx(4.0)


def test_effect_completer_and_highlighter() -> None:
    """Test Tab completion and Pango syntax highlighting for Effect keywords."""
    app, _ = _make_app()
    app.action_registry.execute("effect.create", 1.0, template_id="circle")
    app.action_registry.execute("effect.create", 5.0, template_id="figure_8")

    parser = CommandParser()
    completer = CommandCompleter(parser, app.lightshow)

    _, _, cands_after_sel = completer.get_candidates("1 THRU 8 ")
    assert "EFFECT" in cands_after_sel
    assert "STOP" in cands_after_sel

    _, _, cands_fx_num = completer.get_candidates("1 THRU 8 EFFECT ")
    assert "1" in cands_fx_num
    assert "5" in cands_fx_num

    _, _, cands_fx_mods = completer.get_candidates("1 THRU 8 EFFECT 1 ")
    for mod in ("RATE", "SIZE", "GROUPS", "BLOCKS", "WINGS"):
        assert mod in cands_fx_mods

    markup = highlight_commandline_markup("1 THRU 8 EFFECT 1 RATE 120 SIZE 50")
    assert "EFFECT" in markup
    assert "RATE" in markup
    assert "SIZE" in markup


def test_executor_preserves_selection_order_and_edits_effects() -> None:
    """Test descending THRU and explicit '+' selection ordering for phase spreading."""
    app, _ = _make_app()
    app.action_registry.execute("effect.create", 1.0, template_id="sine_dimmer")

    parser = CommandParser()
    executor = CommandExecutor(app)

    res = executor.execute(parser.parse("4 THRU 1 EFFECT 1 RATE 150 SIZE 50"))
    assert res.success
    assert res.affected_channels == [4, 3, 2, 1]
    insts = app.effects_engine.get_active_instances()
    assert len(insts) == 1
    assert insts[0].channels == [4, 3, 2, 1]
    assert insts[0].rate_scale == pytest.approx(1.5)
    assert insts[0].size_scale == pytest.approx(0.5)

    # Edit effect label and parameters via CLI
    res_label = executor.execute(parser.parse('EFFECT 1 LABEL "Reverse Wave"'))
    assert res_label.success
    eff1 = app.lightshow.effects.get(1.0)
    assert eff1 is not None and eff1.label == "Reverse Wave"

    res_edit = executor.execute(parser.parse("EFFECT 1 SIZE 40 WINGS 2"))
    assert res_edit.success
    eff1 = app.lightshow.effects.get(1.0)
    assert eff1 is not None
    assert eff1.layers[0].size == pytest.approx(40.0)
    assert eff1.wings == 2

    # Stop effect on channels 1 and 2
    res_stop = executor.execute(parser.parse("1 + 2 STOP EFFECT"))
    assert res_stop.success
    assert app.effects_engine.get_active_instances()[0].channels == [4, 3]

    # Delete effect
    res_del = executor.execute(parser.parse("DELETE EFFECT 1"))
    assert res_del.success
    assert app.lightshow.effects.get(1.0) is None
    assert not app.effects_engine.has_active_effects


def test_record_cue_captures_unmodulated_base_and_tracks_effects() -> None:
    """Test RECORD CUE stores clean base Pan/Tilt + effect_refs, and tracks phase."""
    app, _ = _make_app()
    dev1 = _patch_moving_head(app, 1, 1)
    dev2 = _patch_moving_head(app, 2, 10)
    app.lightshow.main_playback.tracking_mode = True

    app.action_registry.execute("effect.create", 1.0, template_id="circle")
    parser = CommandParser()
    executor = CommandExecutor(app)

    # Position devices at Pan 30, Tilt -15 and apply Effect 1
    executor.execute(parser.parse("1 + 2 AT FULL PAN 30 TILT -15"))
    executor.execute(parser.parse("1 + 2 EFFECT 1"))

    # Advance effect clock so instantaneous Pan/Tilt are modulated away from (30, -15)
    inst0 = app.effects_engine.get_active_instances()[0]
    app.effects_engine.tick(now=inst0.start_timestamp + 1.0)
    assert dev1.pan_degrees != pytest.approx(30.0, abs=1.0)

    # Record Cue 1 -> must capture unmodulated base (30.0, -15.0) + effect_refs!
    res_c1 = executor.execute(parser.parse("RECORD CUE 1 TIME 2"))
    assert res_c1.success
    cue1 = app.lightshow.cues.get(1.0, 1)
    assert cue1 is not None
    assert cue1.device_values[1]["pan"] == pytest.approx(30.0, abs=2.5)
    assert cue1.device_values[1]["tilt"] == pytest.approx(-15.0, abs=2.5)
    assert cue1.effect_refs[1]["effect"] == pytest.approx(1.0)
    assert cue1.effect_refs[2]["effect"] == pytest.approx(1.0)

    # Record Cue 2 without touching effect (tracks from Cue 1)
    res_c2 = executor.execute(parser.parse("RECORD CUE 2 TIME 2"))
    assert res_c2.success

    # Stomp effect on channel 1 and record Cue 3
    executor.execute(parser.parse("1 STOP EFFECT"))
    res_c3 = executor.execute(parser.parse("RECORD CUE 3 TIME 2"))
    assert res_c3.success
    cue3 = app.lightshow.cues.get(3.0, 1)
    assert cue3 is not None
    assert cue3.effect_refs[1] == {"stop": True}

    # Resolve tracked states across steps 1, 2, 3
    r1 = TrackingEngine.resolve_step_state(
        app.lightshow.main_playback,
        1,
        tracking_mode=True,
        patch=app.lightshow.patch,
    )
    r2 = TrackingEngine.resolve_step_state(
        app.lightshow.main_playback,
        2,
        tracking_mode=True,
        patch=app.lightshow.patch,
    )
    r3 = TrackingEngine.resolve_step_state(
        app.lightshow.main_playback,
        3,
        tracking_mode=True,
        patch=app.lightshow.patch,
    )
    assert set(r1.effect_refs.keys()) == {1, 2}
    assert set(r2.effect_refs.keys()) == {1, 2}
    assert set(r3.effect_refs.keys()) == {2}

    # Sync Cue 1 -> Cue 2 transition: start_timestamp must remain continuous
    app.effects_engine.stop_all()
    _sync_resolved_effects(app, r1, fade_time=2.0)
    inst1 = app.effects_engine.get_active_instances()[0]
    start_ts = inst1.start_timestamp
    assert inst1.fade_duration == pytest.approx(2.0)
    app.effects_engine.tick(now=start_ts + 1.0)
    assert inst1.effective_size_scale(start_ts + 1.0) == pytest.approx(0.5)

    # Transition to Cue 2 (tracked): start_timestamp (phase) is preserved!
    _sync_resolved_effects(app, r2, fade_time=2.0)
    inst2 = app.effects_engine.get_active_instances()[0]
    assert inst2.start_timestamp == pytest.approx(start_ts)
    _ = dev2


def test_sneak_fades_out_manual_effect() -> None:
    """Test SNEAK command fades out manual live effects by size."""
    app, _ = _make_app()
    app.action_registry.execute("effect.create", 1.0, template_id="sine_dimmer")

    parser = CommandParser()
    executor = CommandExecutor(app)

    executor.execute(parser.parse("1 THRU 4 EFFECT 1"))
    assert app.effects_engine.has_active_effects

    # Sneak in 2s -> effect enters stopping fade-out over 2s
    res = executor.execute(parser.parse("1 THRU 4 SNEAK 2"))
    assert res.success
    inst = app.effects_engine.get_active_instances()[0]
    assert inst.remove_on_fade_end is True
    assert inst.fade_duration == pytest.approx(2.0)

    # Tick 2.1s -> effect finishes fade-out and is removed
    app.effects_engine.tick(now=inst.fade_start_time + 2.1)
    assert not app.effects_engine.has_active_effects


def test_olc_persistence_roundtrip_effects_and_cue_effect_refs(
    tmp_path: pathlib.Path,
) -> None:
    """Test saving and loading EffectManager and Cue.effect_refs in .olc files."""
    app, _ = _make_app()
    app.action_registry.execute(
        "effect.create", 1.0, template_id="circle", label="Saved Circle"
    )
    app.action_registry.execute(
        "effect.update", 1.0, bpm=95.0, size=25.0, groups=2, wings=2
    )

    parser = CommandParser()
    executor = CommandExecutor(app)
    executor.execute(parser.parse("1 THRU 4 AT 80"))
    executor.execute(parser.parse("1 THRU 4 EFFECT 1 RATE 150"))
    executor.execute(parser.parse("RECORD CUE 1 TIME 3"))

    olc_file = tmp_path / "effects_show.olc"
    writer = OlcWriter(olc_file, app.lightshow)
    writer.write()
    assert olc_file.exists()

    # Load into a fresh application instance
    app2, _ = _make_app()
    importer = ImportFile(app2.lightshow, olc_file, FileType.OLC)
    importer.parse_sync(auto_import=True)

    loaded_fx = app2.lightshow.effects.get(1.0)
    assert loaded_fx is not None
    assert loaded_fx.label == "Saved Circle"
    assert loaded_fx.bpm == pytest.approx(95.0)
    assert loaded_fx.layers[0].size == pytest.approx(25.0)
    assert loaded_fx.groups == 2
    assert loaded_fx.wings == 2
    assert len(loaded_fx.layers) == 2

    loaded_cue = app2.lightshow.cues.get(1.0, 0) or app2.lightshow.cues.get(1.0, 1)
    assert loaded_cue is not None
    assert 1 in loaded_cue.effect_refs
    assert loaded_cue.effect_refs[1]["effect"] == pytest.approx(1.0)
    assert loaded_cue.effect_refs[1]["rate_scale"] == pytest.approx(1.5)

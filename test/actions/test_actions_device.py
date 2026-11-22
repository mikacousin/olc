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
"""Unit tests for device.home and device.locate actions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.actions import register_all_actions
from olc.actions.device import resolve_home_preset_device_values
from olc.core.app import CoreApplication
from olc.devices import create_moving_head_definition
from olc.show.palette import Palette, PaletteCategory


@pytest.fixture
def test_app() -> CoreApplication:
    """Fixture providing an initialized CoreApplication with a moving head fixture."""
    settings = MagicMock()
    app = CoreApplication(settings)
    register_all_actions(app.action_registry)

    mock_backend = MagicMock()
    mock_dmx = MagicMock()
    mock_backend.dmx = mock_dmx
    app.backend = mock_backend

    # Patch moving head spot on channel 1 (universe 1, DMX address 1)
    fix_def = create_moving_head_definition()
    app.lightshow.patch.patch_device(1, fix_def, 1, 1)

    return app


def test_device_home_action(test_app: CoreApplication) -> None:
    """Test device.home resets non-intensity parameters and preserves intensity."""
    dev = test_app.lightshow.patch.devices[1]

    # Alter parameters
    dev.set_intensity(0.75)
    dev.set_position_degrees(45.0, -30.0)
    dev.set_zoom_degrees(35.0)

    assert dev.intensity == 0.75
    assert dev.pan_degrees == pytest.approx(45.0, abs=0.1)

    # Execute Home action
    test_app.action_registry.execute("device.home", channels=[1])

    # Intensity is untouched
    assert dev.intensity == 0.75
    # Pan and Tilt are homed to center (0.0°, 0.0°)
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)
    assert dev.tilt_degrees == pytest.approx(0.0, abs=0.1)
    # Zoom is homed to default (22.5°)
    assert dev.zoom_degrees == pytest.approx(22.5, abs=0.2)

    # Test Undo
    test_app.history.undo()
    assert dev.pan_degrees == pytest.approx(45.0, abs=0.1)
    assert dev.zoom_degrees == pytest.approx(35.0, abs=0.1)

    # Test Redo
    test_app.history.redo()
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)


def test_device_home_category_action(test_app: CoreApplication) -> None:
    """Test device.home with category filtering (e.g. position only)."""
    dev = test_app.lightshow.patch.devices[1]

    dev.set_position_degrees(90.0, 45.0)
    dev.set_zoom_degrees(35.0)

    # Home position only
    test_app.action_registry.execute("device.home", channels=[1], category="position")

    # Pan/tilt homed
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)
    assert dev.tilt_degrees == pytest.approx(0.0, abs=0.1)
    # Zoom remains altered!
    assert dev.zoom_degrees == pytest.approx(35.0, abs=0.1)


def test_device_locate_action(test_app: CoreApplication) -> None:
    """Test device.locate action sets intensity to full and homes parameters."""
    dev = test_app.lightshow.patch.devices[1]

    dev.set_intensity(0.0)
    dev.set_position_degrees(-90.0, 50.0)

    # Execute Locate action
    test_app.action_registry.execute("device.locate", channels=[1])

    # Intensity is 1.0 (100%)
    assert dev.intensity == 1.0
    # Position homed to center
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)
    assert dev.tilt_degrees == pytest.approx(0.0, abs=0.1)

    # Undo
    test_app.history.undo()
    assert dev.intensity == 0.0
    assert dev.pan_degrees == pytest.approx(-90.0, abs=0.1)

    # Redo
    test_app.history.redo()
    assert dev.intensity == 1.0
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)


def test_device_home_resolves_home_preset_palette_refs(
    test_app: CoreApplication,
) -> None:
    """Test device.home resolves Home Preset palette_refs and strips intensity."""
    dev = test_app.lightshow.patch.devices[1]
    test_app.lightshow.palettes.add(
        Palette(
            PaletteCategory.FOCUS,
            1.0,
            device_values={1: {"pan": 30.0, "tilt": -15.0}},
        )
    )
    test_app.lightshow.palettes.add(
        Palette(
            PaletteCategory.BEAM,
            2.0,
            device_values={1: {"zoom": 16.0, "intensity": 0.2}},
        )
    )
    test_app.lightshow.palettes.add(
        Palette(
            PaletteCategory.PRESET,
            999.0,
            device_values={1: {"intensity": 0.9}},
            palette_refs={
                1: {"pan": ("focus", 1.0), "tilt": ("focus", 1.0), "*": ("beam", 2.0)}
            },
        )
    )
    test_app.lightshow.home_preset = 999.0

    resolved = resolve_home_preset_device_values(test_app.lightshow, 1)
    assert "intensity" not in resolved
    assert resolved["pan"] == pytest.approx(30.0)
    assert resolved["tilt"] == pytest.approx(-15.0)
    assert resolved["zoom"] == pytest.approx(16.0)

    dev.set_intensity(0.6)
    dev.set_position_degrees(-80.0, 40.0)
    dev.set_zoom_degrees(40.0)

    test_app.action_registry.execute("device.home", channels=[1])
    assert dev.intensity == 0.6
    assert dev.pan_degrees == pytest.approx(30.0, abs=1.0)
    assert dev.tilt_degrees == pytest.approx(-15.0, abs=1.0)
    assert dev.zoom_degrees == pytest.approx(16.0, abs=0.5)

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
"""Unit tests for GUI preference actions and Undo/Redo."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.gtk3.event_bridge import GuiEventBridge
from olc.gtk3.settings import SettingsTab


def test_set_theme_action_and_undo_redo() -> None:
    """Test gui.set_theme action execution, Undo, and Redo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    events: list[bool] = []

    def on_theme_changed(dark_theme: bool) -> None:
        events.append(dark_theme)

    app.subscribe("gui.theme_changed", on_theme_changed)

    action = app.action_registry.get("gui.set_theme")
    assert action is not None
    assert action.can_undo is True

    # Initial default theme is True (dark)
    assert app.dark_theme is True

    # 1. Switch to light theme (False)
    app.action_registry.execute("gui.set_theme", dark_theme=False)
    assert app.dark_theme is False
    assert events == [False]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores dark theme (True)
    app.history.undo()
    assert app.dark_theme is True
    assert events == [False, True]

    # 3. Redo -> re-applies light theme (False)
    app.history.redo()
    assert app.dark_theme is False
    assert events == [False, True, False]


def test_set_percent_display_action_and_undo_redo() -> None:
    """Test gui.set_percent_display action execution, Undo, and Redo."""
    settings = MagicMock()
    settings.get_boolean.return_value = False

    app = CoreApplication(settings)

    events: list[bool] = []

    def on_percent_changed(percent: bool) -> None:
        events.append(percent)

    app.subscribe("gui.percent_display_changed", on_percent_changed)

    action = app.action_registry.get("gui.set_percent_display")
    assert action is not None
    assert action.can_undo is True

    # 1. Enable percentage display
    app.action_registry.execute("gui.set_percent_display", percent=True)
    settings.set_boolean.assert_called_with("percent", True)
    assert events == [True]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores False
    app.history.undo()
    settings.set_boolean.assert_called_with("percent", False)
    assert events == [True, False]

    # 3. Redo -> re-applies True
    app.history.redo()
    settings.set_boolean.assert_called_with("percent", True)
    assert events == [True, False, True]


def test_set_default_time_action_and_undo_redo() -> None:
    """Test gui.set_default_time action execution, Undo, and Redo."""
    settings = MagicMock()
    settings.get_double.return_value = 0.0

    app = CoreApplication(settings)

    events: list[float] = []

    def on_default_time_changed(time_val: float) -> None:
        events.append(time_val)

    app.subscribe("gui.default_time_changed", on_default_time_changed)

    action = app.action_registry.get("gui.set_default_time")
    assert action is not None
    assert action.can_undo is True

    # 1. Set default transfer time to 4.5 seconds
    app.action_registry.execute("gui.set_default_time", default_time=4.5)
    settings.set_double.assert_called_with("default-time", 4.5)
    assert events == [4.5]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores 0.0
    app.history.undo()
    settings.set_double.assert_called_with("default-time", 0.0)
    assert events == [4.5, 0.0]

    # 3. Redo -> re-applies 4.5
    app.history.redo()
    settings.set_double.assert_called_with("default-time", 4.5)
    assert events == [4.5, 0.0, 4.5]


def test_event_bridge_preferences_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GuiEventBridge routes preference events to UI components."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))

    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core
    mock_app.window = MagicMock()

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {
        "settings": mock_settings_tab,
        "sequences": MagicMock(),
        "groups": MagicMock(),
        "cues": MagicMock(),
    }

    _bridge = GuiEventBridge(mock_app)

    # 1. Percent display event
    core.emit("gui.percent_display_changed", True)
    mock_settings_tab.update_percent_ui.assert_called_once_with(True)
    mock_app.window.live_view.channels_view.update.assert_called_once()
    mock_app.tabs.tabs["sequences"].channels_view.update.assert_called_once()
    mock_app.tabs.tabs["groups"].channels_view.update.assert_called_once()
    mock_app.tabs.tabs["cues"].channels_view.update.assert_called_once()

    # 2. Default time event
    core.emit("gui.default_time_changed", 2.5)
    mock_settings_tab.update_default_time_ui.assert_called_once_with(2.5)

    # 3. Home Preset changed event
    core.emit("show.home_preset_changed", 999.0)
    mock_settings_tab.update_home_preset_ui.assert_called_once_with(999.0)

    # 4. Fader page count changed event
    core.emit("fader.page_count_changed", 15)
    mock_settings_tab.update_fader_pages_ui.assert_called_once_with(15)

    # 5. Skip empty fader pages changed event
    core.emit("fader.skip_empty_pages_changed", True)
    mock_settings_tab.update_skip_empty_fader_pages_ui.assert_called_once_with(True)


def test_settings_tab_update_percent_and_default_time() -> None:
    """Test SettingsTab programmatic updates for percentage switch and default time."""
    # pylint: disable=protected-access
    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    tab.switch_percent = MagicMock()
    tab.switch_percent.get_state.return_value = False
    tab.spin_default_time = MagicMock()
    tab.spin_default_time.get_value.return_value = 0.0
    tab.spin_home_preset = MagicMock()
    tab.spin_home_preset.get_value.return_value = 0.0

    # 1. Update percent switch
    tab.update_percent_ui(True)
    tab.switch_percent.set_state.assert_called_once_with(True)
    tab.switch_percent.set_active.assert_called_once_with(True)
    assert not tab._updating_settings

    # 2. Update default time
    tab.update_default_time_ui(3.0)
    tab.spin_default_time.set_value.assert_called_once_with(3.0)
    assert not tab._updating_settings

    # 3. Update Home Preset UI, _on_change_home_preset, and refresh()
    tab.update_home_preset_ui(999.0)
    tab.spin_home_preset.set_value.assert_called_with(999.0)
    assert not tab._updating_settings

    tab.update_home_preset_ui(None)
    tab.spin_home_preset.get_value.return_value = 999.0
    tab.update_home_preset_ui(None)
    tab.spin_home_preset.set_value.assert_called_with(0.0)

    core = CoreApplication(MagicMock())
    tab.app = MagicMock()
    tab.app.core = core
    mock_spin = MagicMock()
    mock_spin.get_value.return_value = 42.0
    tab._on_change_home_preset(mock_spin)
    assert core.lightshow.home_preset == pytest.approx(42.0)

    core.lightshow.home_preset = 777.0
    tab.spin_home_preset.get_value.return_value = 42.0
    tab.refresh()
    tab.spin_home_preset.set_value.assert_called_with(777.0)


def test_fader_pages_setting_warning_and_undo_redo() -> None:
    """Test hot fader page count setting, reduction warning cancel/ok, and Undo."""
    # pylint: disable=protected-access
    from olc.show.fader import FaderType
    from olc.show.palette import Palette, PaletteCategory

    core = CoreApplication(MagicMock())
    fb = core.lightshow.fader_bank
    assert fb.max_fader_page == 10

    # Configure preset and assign fader on page 8 at level 0.6
    core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 3.0, "Warm", channels={1: 1.0})
    )
    core.action_registry.execute("fader.assign", 8, 2, FaderType.PRESET, 3.0)
    core.action_registry.execute("fader.set_level", 8, 2, 0.6)
    core.action_registry.execute("fader.set_page", 8)
    assert fb.active_page == 8
    core.history.clear()

    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    tab.app = MagicMock()
    tab.app.core = core
    tab.spin_fader_pages = MagicMock()
    tab.spin_fader_pages.get_value_as_int.return_value = 10

    # 1. Cancel warning on reduction (10 -> 5): preserves page count & fader
    tab._confirm_fader_pages_reduction = MagicMock(return_value=False)  # type: ignore[method-assign]
    mock_spin = MagicMock()
    mock_spin.get_value_as_int.return_value = 5
    tab.spin_fader_pages.get_value_as_int.return_value = 5
    tab._on_change_fader_pages(mock_spin)

    assert tab._confirm_fader_pages_reduction.called
    assert fb.max_fader_page == 10
    assert fb.get_fader_type(8, 2) == FaderType.PRESET
    tab.spin_fader_pages.set_value.assert_called_with(10.0)

    # 2. Confirm warning on reduction (10 -> 5): drops pages > 5 & clamps active_page
    tab._confirm_fader_pages_reduction = MagicMock(return_value=True)  # type: ignore[method-assign]
    tab._on_change_fader_pages(mock_spin)

    assert fb.max_fader_page == 5
    assert fb.active_page == 5
    assert 8 not in fb.faders

    # 3. Undo restores page 8, fader (8, 2), level 0.6, and active_page 8
    core.history.undo()
    assert fb.max_fader_page == 10
    assert fb.active_page == 8
    assert fb.get_fader_type(8, 2) == FaderType.PRESET
    assert fb.faders[8][2].level == pytest.approx(0.6)

    # 4. Redo drops back to 5 pages
    core.history.redo()
    assert fb.max_fader_page == 5
    assert 8 not in fb.faders


def test_skip_empty_fader_pages_navigation_action_and_settings() -> None:
    """Test FaderBank.get_next_page skipping, action Undo/Redo, and SettingsTab."""
    # pylint: disable=protected-access
    from olc.show.fader import FaderType

    core = CoreApplication(MagicMock())
    fb = core.lightshow.fader_bank
    assert fb.skip_empty_pages is False

    # 1. With all pages empty, even skip_empty=True falls back to 1..N stepping
    assert fb.get_next_page(1, skip_empty=True) == 2
    assert fb.get_next_page(-1, skip_empty=True) == 10

    # 2. Only page 4 populated -> jumps to 4 and stays on 4
    fb.set_fader(4, 1, FaderType.MAIN)
    fb.active_page = 1
    assert fb.get_next_page(1, skip_empty=True) == 4
    fb.active_page = 4
    assert fb.get_next_page(1, skip_empty=True) == 4
    assert fb.get_next_page(-1, skip_empty=True) == 4

    # 3. Multiple populated pages (1, 3, 8) -> cyclic skipping + empty-page anchor
    fb.set_fader(4, 1, FaderType.NONE)
    fb.set_fader(1, 1, FaderType.MAIN)
    fb.set_fader(3, 1, FaderType.MAIN)
    fb.set_fader(8, 1, FaderType.MAIN)

    fb.active_page = 1
    assert fb.get_next_page(1, skip_empty=True) == 3
    assert fb.get_next_page(-1, skip_empty=True) == 8
    fb.active_page = 3
    assert fb.get_next_page(1, skip_empty=True) == 8
    assert fb.get_next_page(-1, skip_empty=True) == 1
    fb.active_page = 8
    assert fb.get_next_page(1, skip_empty=True) == 1
    assert fb.get_next_page(-1, skip_empty=True) == 3

    # Starting on empty page 2
    fb.active_page = 2
    assert fb.get_next_page(1, skip_empty=True) == 3
    assert fb.get_next_page(-1, skip_empty=True) == 1

    # 4. Action fader.set_skip_empty_pages + Undo/Redo + SettingsTab handler
    core.history.clear()
    core.lightshow.set_not_modified()
    events: list[bool] = []
    core.subscribe("fader.skip_empty_pages_changed", events.append)

    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    tab.app = MagicMock()
    tab.app.core = core
    tab.switch_skip_empty_fader_pages = MagicMock()
    tab.switch_skip_empty_fader_pages.get_state.return_value = False

    tab._on_toggle_skip_empty_fader_pages(tab.switch_skip_empty_fader_pages, True)
    assert fb.skip_empty_pages is True
    assert core.lightshow.modified is True
    assert events == [True]
    assert core.history.undo_stack[-1].get_feedback_state() == {
        "skip_empty_pages": True
    }

    core.history.undo()
    assert fb.skip_empty_pages is False
    assert core.lightshow.modified is False
    assert events == [True, False]

    core.history.redo()
    assert fb.skip_empty_pages is True
    assert core.lightshow.modified is True

    tab.update_skip_empty_fader_pages_ui(True)
    tab.switch_skip_empty_fader_pages.set_state.assert_called_with(True)
    tab.switch_skip_empty_fader_pages.set_active.assert_called_with(True)
    assert not tab._updating_settings


def test_fader_set_fixed_preservation_skip_empty_and_undo_redo() -> None:
    """Test fixing a fader across all pages, masking underlying pages, and Undo/Redo."""
    from olc.show.fader import FaderType
    from olc.show.palette import Palette, PaletteCategory

    core = CoreApplication(MagicMock())
    fb = core.lightshow.fader_bank
    core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 1.0, "Master Sub", channels={1: 1.0})
    )
    core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 2.0, "Page2 Sub", channels={2: 1.0})
    )
    core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 5.0, "Page5 Sub", channels={3: 1.0})
    )

    # Configure faders on (1, 10), (2, 10), and (5, 1)
    core.action_registry.execute("fader.assign", 1, 10, FaderType.PRESET, 1.0)
    core.action_registry.execute("fader.assign", 2, 10, FaderType.PRESET, 2.0)
    core.action_registry.execute("fader.assign", 5, 1, FaderType.PRESET, 5.0)
    core.history.clear()
    core.lightshow.set_not_modified()

    fixed_events: list[tuple[int, int, bool]] = []
    core.subscribe(
        "fader.fixed_changed",
        lambda p, i, f: fixed_events.append((p, i, f)),
    )

    # 1. Fix (1, 10) across all pages
    core.action_registry.execute("fader.set_fixed", 1, 10, True)
    assert fb.is_fader_fixed(1, 10) is True
    assert fixed_events == [(1, 10, True)]
    assert core.lightshow.modified is True

    # Switching to page 3 resolves fader 10 to (1, 10), and set_level / flash target it
    core.action_registry.execute("fader.set_page", 3)
    assert fb.active_page == 3
    assert fb.get_fader(10) is fb.faders[1][10]

    lvl_events: list[tuple[int, float]] = []
    flash_events: list[tuple[int, bool]] = []
    core.subscribe(
        "fader.level_changed", lambda idx, lvl: lvl_events.append((idx, lvl))
    )
    core.subscribe(
        "fader.flash_changed", lambda idx, st: flash_events.append((idx, st))
    )

    core.action_registry.execute("fader.set_level", 3, 10, 0.75)
    assert fb.faders[1][10].level == pytest.approx(0.75)
    assert lvl_events == [(10, 0.75)]

    core.action_registry.execute("fader.flash", 3, 10, True)
    assert fb.faders[1][10].level == pytest.approx(1.0)
    assert flash_events == [(10, True)]
    core.action_registry.execute("fader.flash", 3, 10, False)
    assert fb.faders[1][10].level == pytest.approx(0.75)

    # 2. Non-destructive preservation on page 2
    assert fb.get_fader(10, page=2) is fb.faders[1][10]
    assert fb.faders[2][10].contents is not None
    assert fb.faders[2][10].contents.number == 2.0

    # Undo unfixes (1, 10) and restores underlying page 2 access + unmodified flag
    core.history.undo()
    assert fb.is_fader_fixed(1, 10) is False
    assert core.lightshow.modified is False
    assert fb.get_fader(10, page=2) is fb.faders[2][10]
    core.history.redo()
    assert fb.is_fader_fixed(1, 10) is True

    # 3. skip_empty_pages still skips empty pages 2,3,4,6..10 even with (1, 10) fixed
    fb.set_fader(2, 10, FaderType.NONE)
    fb.active_page = 1
    assert fb.get_next_page(1, skip_empty=True) == 5
    fb.active_page = 5
    assert fb.get_next_page(1, skip_empty=True) == 1

    # 4. fader.clear on fixed (1, 10) unfixes it and Undo restores fixed state
    core.action_registry.execute("fader.clear", 1, 10)
    assert fb.is_fader_fixed(1, 10) is False
    core.history.undo()
    assert fb.is_fader_fixed(1, 10) is True

    # 5. fader.set_page_count dropping fixed fader on page 8 restores it on Undo
    core.action_registry.execute("fader.assign", 8, 4, FaderType.MAIN)
    core.action_registry.execute("fader.set_fixed", 8, 4, True)
    assert fb.is_fader_fixed(8, 4) is True
    core.action_registry.execute("fader.set_page_count", page_count=5)
    assert fb.get_fixed_source_page(4) is None
    core.history.undo()
    assert fb.is_fader_fixed(8, 4) is True


def test_set_notifications_action_and_undo_redo() -> None:
    """Test gui.set_notifications action execution, Undo, and Redo."""
    settings = MagicMock()
    settings.get_boolean.return_value = True

    app = CoreApplication(settings)

    events: list[bool] = []

    def on_notifications_changed(enabled: bool) -> None:
        events.append(enabled)

    app.subscribe("gui.notifications_changed", on_notifications_changed)

    action = app.action_registry.get("gui.set_notifications")
    assert action is not None
    assert action.can_undo is True

    # 1. Disable desktop notifications
    app.action_registry.execute("gui.set_notifications", enabled=False)
    settings.set_boolean.assert_called_with("notifications", False)
    assert events == [False]
    assert len(app.history.undo_stack) == 1

    # 2. Undo -> restores True
    app.history.undo()
    settings.set_boolean.assert_called_with("notifications", True)
    assert events == [False, True]

    # 3. Redo -> re-applies False
    app.history.redo()
    settings.set_boolean.assert_called_with("notifications", False)
    assert events == [False, True, False]


def test_backend_notification_respects_notifications_setting() -> None:
    """Verify Application.on_backend_notification honors the notifications setting."""
    # pylint: disable=import-outside-toplevel
    from olc.gtk3.application import Application

    settings = MagicMock()
    fake_app = MagicMock(spec=Application)
    fake_app.settings = settings

    settings.get_boolean.return_value = False
    Application.on_backend_notification(fake_app, "Alert", "Body")
    fake_app.send_notification.assert_not_called()

    settings.get_boolean.return_value = True
    Application.on_backend_notification(fake_app, "Alert", "Body")
    fake_app.send_notification.assert_called_once()

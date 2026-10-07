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
"""GUI event bridge handler for patch and DMX outputs."""

from __future__ import annotations

import typing

from olc.define import UNIVERSES

from .base import BaseEventBridgeHandler

if typing.TYPE_CHECKING:
    from olc.gtk3.patch_channels import PatchChannelsTab
    from olc.gtk3.patch_outputs import PatchOutputsTab
    from olc.settings import SettingsTab


# pylint: disable=too-few-public-methods
class PatchDmxBridgeHandler(BaseEventBridgeHandler):
    """Handles patch changes, DMX outputs, blackout, and universe events."""

    def register(self) -> None:
        """Subscribe to Core events for patch, DMX outputs, and universes."""
        self.app.core.subscribe(
            "patch.changed", lambda: self._run_idle(self._safe_refresh_patch)
        )
        self.app.core.subscribe(
            "patch.selected_outputs_changed",
            lambda: self._run_idle(self._on_selected_outputs_changed),
        )
        self.app.core.subscribe(
            "dmx.user_output_changed",
            lambda universe, output, level: self._run_idle(
                self._on_user_output_changed, universe, output, level
            ),
        )
        self.app.core.subscribe(
            "dmx.user_outputs_cleared",
            lambda: self._run_idle(self._safe_refresh_patch_outputs),
        )
        self.app.core.subscribe(
            "dmx.user_outputs_changed",
            lambda: self._run_idle(self._safe_refresh_patch_outputs),
        )
        self.app.core.subscribe(
            "dmx.blackout_all_changed",
            lambda state: self._run_idle(self._on_blackout_all_changed, state),
        )
        self.app.core.subscribe(
            "universe.protocol_changed",
            lambda universe, protocol, enabled: self._run_idle(
                self._on_universe_config_updated, universe
            ),
        )
        self.app.core.subscribe(
            "universe.config_changed",
            lambda universe, changed: self._run_idle(
                self._on_universe_config_updated, universe
            ),
        )

    def _safe_refresh_patch(self) -> bool:
        """Refresh patch UI tabs and live channels view safely in the GTK thread.

        Returns:
            Always False.
        """
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.channels_view.update()
        if self.app.tabs:
            if self.app.tabs.tabs.get("patch_outputs") is not None:
                patch_outputs = typing.cast(
                    "PatchOutputsTab", self.app.tabs.tabs["patch_outputs"]
                )
                patch_outputs.refresh()
            if self.app.tabs.tabs.get("patch_channels") is not None:
                patch_channels = typing.cast(
                    "PatchChannelsTab", self.app.tabs.tabs["patch_channels"]
                )
                patch_channels.refresh()
        return False

    def _safe_refresh_patch_outputs(self) -> bool:
        """Refresh the patch outputs tab UI safely in the GTK thread.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("patch_outputs") is not None:
            patch_outputs = typing.cast(
                "PatchOutputsTab", self.app.tabs.tabs["patch_outputs"]
            )
            patch_outputs.refresh()
        return False

    def _on_selected_outputs_changed(self) -> bool:
        """Refresh selected outputs UI and reset command line in the GTK thread.

        Returns:
            Always False.
        """
        if self.app.tabs:
            if self.app.tabs.tabs.get("patch_outputs") is not None:
                patch_outputs = typing.cast(
                    "PatchOutputsTab", self.app.tabs.tabs["patch_outputs"]
                )
                patch_outputs.select_outputs()
        self.app.core.commandline.set_string("")
        return False

    def _on_user_output_changed(self, universe: int, output: int, _level: int) -> bool:
        """Refresh the specific patch output widget safely in the GTK thread.

        Args:
            universe: Universe identifier.
            output: Output number (1-512).
            _level: Output level (0-255).

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("patch_outputs") is not None:
            patch_outputs = typing.cast(
                "PatchOutputsTab", self.app.tabs.tabs["patch_outputs"]
            )
            if universe in UNIVERSES:
                idx = UNIVERSES.index(universe)
                output_idx = output - 1 + (512 * idx)
                if 0 <= output_idx < len(patch_outputs.outputs):
                    patch_outputs.outputs[output_idx].queue_draw()
        return False

    def _on_blackout_all_changed(self, _state: bool) -> bool:
        """Handle blackout all changed event to update live view and patch outputs.

        Args:
            _state: True if blackout active, False otherwise.

        Returns:
            Always False.
        """
        if self.app.window and self.app.window.live_view:
            self.app.window.live_view.channels_view.update()
        self._safe_refresh_patch_outputs()
        return False

    def _on_universe_config_updated(self, universe: int) -> bool:
        """Handle universe config/protocol update to refresh Settings tab if open.

        Args:
            universe: Universe identifier.

        Returns:
            Always False.
        """
        if self.app.tabs and self.app.tabs.tabs.get("settings") is not None:
            settings_tab = typing.cast("SettingsTab", self.app.tabs.tabs["settings"])
            if hasattr(settings_tab, "update_universe_ui"):
                settings_tab.update_universe_ui(universe)
        return False

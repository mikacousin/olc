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

from olc.core.action import Action
from olc.devices.device import FixtureType, LightingDevice
from olc.devices.fixture import FixtureDefinition

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class PatchAddOutputAction(Action):
    """Action to associate a DMX output with a channel."""

    name = "patch.add_output"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channel: int = 1
        self.output: int = 1
        self.univ: int = 0
        self.curve: int = 0

        # State saved for undo
        self.old_channel: typing.Optional[int] = None
        self.old_curve: int = 0

    def configure(self, channel: int, output: int, univ: int, curve: int = 0) -> None:
        """Configure the action with output patching parameters.

        Args:
            channel: The channel to associate with the output.
            output: The DMX output number.
            univ: The DMX universe index.
            curve: The transfer curve index (default 0 = linear).
        """
        self.channel = channel
        self.output = output
        self.univ = univ
        self.curve = curve

    def execute(self) -> None:
        """Execute the action, patching the configured output."""
        patch = self.app.lightshow.patch

        # Save previous state of this output
        info = patch.get_output_info(self.univ, self.output)
        if info is not None:
            self.old_channel, self.old_curve = info
        else:
            self.old_channel = None
            self.old_curve = 0

        # Execute
        if self.old_channel is not None:
            patch.unpatch_address(self.univ, self.output)
        patch.add_output(self.channel, self.output, self.univ, self.curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.unpatch_address(self.univ, self.output)
        if self.old_channel is not None:
            patch.add_output(self.old_channel, self.output, self.univ, self.old_curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        if self.old_channel is not None:
            patch.unpatch_address(self.univ, self.output)
        patch.add_output(self.channel, self.output, self.univ, self.curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchAddOutputsAction(Action):
    """Action to atomically associate multiple DMX outputs with channels."""

    name = "patch.add_outputs"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.assignments: list[tuple[int, int, int, int]] = []
        self._previous_outputs: list[tuple[int, int, int | None, int]] = []
        self._previous_non_dimmers: dict[int, dict[str, typing.Any]] = {}

    def configure(self, assignments: list[tuple[int, int, int, int]]) -> None:
        """Configure with a list of (channel, output, universe, curve) tuples."""
        self.assignments = list(assignments)

    def execute(self) -> None:
        """Execute all output assignments as one atomic undoable step."""
        patch = self.app.lightshow.patch
        self._previous_outputs = []
        self._previous_non_dimmers = {}

        for _ch, output, univ, _curve in self.assignments:
            info = patch.get_output_info(univ, output)
            if info is not None:
                old_ch, old_curve = info
                self._previous_outputs.append((univ, output, old_ch, old_curve))
                old_dev = patch.get_device(old_ch)
                if (
                    old_dev is not None
                    and old_dev.fixture_type != FixtureType.DIMMER
                    and old_ch not in self._previous_non_dimmers
                ):
                    self._previous_non_dimmers[old_ch] = old_dev.to_dict()
            else:
                self._previous_outputs.append((univ, output, None, 0))

        for ch, output, univ, curve in self.assignments:
            if patch.get_address_occupant(univ, output) is not None:
                patch.unpatch_address(univ, output)
            patch.add_output(ch, output, univ, curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        """Restore all affected DMX addresses to their previous state."""
        patch = self.app.lightshow.patch
        for univ, output, old_ch, old_curve in reversed(self._previous_outputs):
            patch.unpatch_address(univ, output)
            if old_ch is not None and old_ch not in self._previous_non_dimmers:
                patch.add_output(old_ch, output, univ, old_curve)

        for dev_id, dev_dict in self._previous_non_dimmers.items():
            patch.unpatch_device(dev_id)
            patch.restore_device(LightingDevice.from_dict(dev_dict))

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        """Re-apply all output assignments."""
        patch = self.app.lightshow.patch
        for ch, output, univ, curve in self.assignments:
            if patch.get_address_occupant(univ, output) is not None:
                patch.unpatch_address(univ, output)
            patch.add_output(ch, output, univ, curve)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchUnpatchOutputAction(Action):
    """Action to unpatch a DMX output."""

    name = "patch.unpatch_output"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.output: int = 1
        self.univ: int = 0
        self.old_channel: typing.Optional[int] = None
        self.old_curve: int = 0

    def configure(self, output: int, univ: int) -> None:
        """Configure the action with the output to unpatch.

        Args:
            output: The DMX output number.
            univ: The DMX universe index.
        """
        self.output = output
        self.univ = univ

    def execute(self) -> None:
        """Execute the action, unpatching the configured output."""
        patch = self.app.lightshow.patch
        info = patch.get_output_info(self.univ, self.output)
        if info is not None:
            self.old_channel, self.old_curve = info
        else:
            self.old_channel = None
            self.old_curve = 0

        if self.old_channel is not None:
            patch.unpatch_address(self.univ, self.output)

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        if self.old_channel is not None:
            patch = self.app.lightshow.patch
            patch.add_output(self.old_channel, self.output, self.univ, self.old_curve)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def redo(self) -> None:
        if self.old_channel is not None:
            patch = self.app.lightshow.patch
            patch.unpatch_address(self.univ, self.output)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")


class PatchClearAction(Action):
    """Action to clear the entire DMX patch."""

    name = "patch.clear"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.saved_devices: list[dict[str, typing.Any]] = []

    def execute(self) -> None:
        patch = self.app.lightshow.patch

        # Save all patched devices
        self.saved_devices = [
            dev.to_dict() for dev in getattr(patch, "devices", {}).values()
        ]

        patch.patch_empty()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_empty()
        for dev_data in self.saved_devices:
            patch.restore_device(LightingDevice.from_dict(dev_data))

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_empty()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchSet1on1Action(Action):
    """Action to set default 1:1 patch."""

    name = "patch.set_1on1"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.saved_devices: list[dict[str, typing.Any]] = []

    def execute(self) -> None:
        patch = self.app.lightshow.patch

        # Save all patched devices
        self.saved_devices = [
            dev.to_dict() for dev in getattr(patch, "devices", {}).values()
        ]

        patch.patch_1on1()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_empty()
        for dev_data in self.saved_devices:
            patch.restore_device(LightingDevice.from_dict(dev_data))

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        patch.patch_1on1()

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchSetOutputCurveAction(Action):
    """Action to set the transfer curve of a patched DMX output."""

    name = "patch.set_output_curve"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.output: int = 1
        self.univ: int = 0
        self.curve: int = 0
        self.old_curve: int = 0

    def configure(self, output: int, univ: int, curve: int) -> None:
        """Configure the action with the output and new curve.

        Args:
            output: The DMX output number.
            univ: The DMX universe index.
            curve: The new transfer curve index.
        """
        self.output = output
        self.univ = univ
        self.curve = curve

    def execute(self) -> None:
        """Execute the action, assigning the configured curve to the output."""
        patch = self.app.lightshow.patch
        info = patch.get_output_info(self.univ, self.output)
        if info is not None:
            self.old_curve = info[1]
            patch.set_output_curve(self.univ, self.output, self.curve)
        else:
            raise ValueError(
                f"Output {self.output} in universe {self.univ} is not patched."
            )

        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        if patch.set_output_curve(self.univ, self.output, self.old_curve):
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        if patch.set_output_curve(self.univ, self.output, self.curve):
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")


class PatchSetDeviceCurveAction(Action):
    """Action to set the transfer curve of a lighting device."""

    name = "patch.set_device_curve"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.device_id: int = 1
        self.curve: int = 0
        self.old_curve: int = 0

    def configure(self, device_id: int, curve: int) -> None:
        """Configure the action with the device ID and new curve.

        Args:
            device_id: The lighting device ID.
            curve: The new transfer curve index.
        """
        self.device_id = device_id
        self.curve = curve

    def _apply_curve(self, curve_id: int) -> None:
        patch = self.app.lightshow.patch
        dev = patch.get_device(self.device_id)
        if dev is None:
            raise ValueError(f"Device {self.device_id} is not patched.")
        dev.set_curve_id(curve_id)
        patch.invalidate_cache()
        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def execute(self) -> None:
        """Execute the action, setting the curve on the device and intensity outputs."""
        patch = self.app.lightshow.patch
        dev = patch.get_device(self.device_id)
        if dev is None:
            raise ValueError(f"Device {self.device_id} is not patched.")
        self.old_curve = dev.curve_id
        self._apply_curve(self.curve)

    def undo(self) -> None:
        """Undo the action, restoring the previous curve."""
        self._apply_curve(self.old_curve)

    def redo(self) -> None:
        """Redo the action, re-applying the configured curve."""
        self._apply_curve(self.curve)


class PatchDeviceAction(Action):
    """Action to patch a lighting device."""

    name = "patch.device"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.device_id: int = 1
        self.fixture_def: typing.Optional[FixtureDefinition] = None
        self.universe: int = 1
        self.address: int = 1
        self.mode_name: typing.Optional[str] = None
        self.label: str = ""
        self.force: bool = False
        self.old_device_dict: typing.Optional[dict[str, typing.Any]] = None

    def configure(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_id: int,
        fixture_def: FixtureDefinition,
        universe: int,
        address: int,
        mode_name: typing.Optional[str] = None,
        label: str = "",
        force: bool = False,
    ) -> None:
        """Configure the action with fixture patching parameters."""
        self.device_id = device_id
        self.fixture_def = fixture_def
        self.universe = universe
        self.address = address
        self.mode_name = mode_name
        self.label = label
        self.force = force

    def execute(self) -> None:
        patch = self.app.lightshow.patch
        old_dev = patch.get_device(self.device_id)
        self.old_device_dict = old_dev.to_dict() if old_dev else None

        if self.fixture_def is not None:
            patch.patch_device(
                device_id=self.device_id,
                fixture_def=self.fixture_def,
                universe=self.universe,
                address=self.address,
                mode_name=self.mode_name,
                label=self.label,
                force=self.force,
            )
        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.unpatch_device(self.device_id)
        if self.old_device_dict is not None:
            restored = LightingDevice.from_dict(self.old_device_dict)
            patch.restore_device(restored)
        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        self.execute()


class PatchUnpatchDeviceAction(Action):
    """Action to unpatch a lighting device."""

    name = "patch.unpatch_device"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.device_id: int = 1
        self.old_device_dict: typing.Optional[dict[str, typing.Any]] = None

    def configure(self, device_id: int) -> None:
        """Configure the action with the device ID to unpatch."""
        self.device_id = device_id

    def execute(self) -> None:
        patch = self.app.lightshow.patch
        old_dev = patch.get_device(self.device_id)
        if old_dev is not None:
            self.old_device_dict = old_dev.to_dict()
            patch.unpatch_device(self.device_id)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def undo(self) -> None:
        if self.old_device_dict is not None:
            patch = self.app.lightshow.patch
            restored = LightingDevice.from_dict(self.old_device_dict)
            patch.restore_device(restored)
            self.app.lightshow.set_modified()
            self.app.emit("patch.changed")

    def redo(self) -> None:
        patch = self.app.lightshow.patch
        patch.unpatch_device(self.device_id)
        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")


class PatchExchangeFixtureAction(Action):
    """Action to exchange the fixture definition of an already patched device."""

    name = "patch.exchange_fixture"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.device_id: int = 1
        self.new_fixture_key: str = ""
        self.new_mode_name: typing.Optional[str] = None
        self.universe: typing.Optional[int] = None
        self.address: typing.Optional[int] = None
        self.force: bool = False
        self.old_device_dict: typing.Optional[dict[str, typing.Any]] = None

    def configure(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device_id: int,
        new_fixture_key: str,
        new_mode_name: typing.Optional[str] = None,
        universe: typing.Optional[int] = None,
        address: typing.Optional[int] = None,
        force: bool = False,
    ) -> None:
        """Configure the fixture exchange action."""
        self.device_id = device_id
        self.new_fixture_key = new_fixture_key
        self.new_mode_name = new_mode_name
        self.universe = universe
        self.address = address
        self.force = force

    def execute(self) -> None:
        lightshow = self.app.lightshow
        patch = lightshow.patch
        fdef = lightshow.fixture_library.get_by_key(self.new_fixture_key)
        if fdef is None:
            raise KeyError(
                f"Fixture profile '{self.new_fixture_key}' not found in library"
            )
        old_dev = patch.get_device(self.device_id)
        self.old_device_dict = old_dev.to_dict() if old_dev is not None else None
        patch.exchange_fixture(
            device_id=self.device_id,
            new_fixture_def=fdef,
            new_mode_name=self.new_mode_name,
            universe=self.universe,
            address=self.address,
            force=self.force,
        )
        lightshow.set_modified()
        self.app.emit("patch.changed")

    def undo(self) -> None:
        patch = self.app.lightshow.patch
        patch.unpatch_device(self.device_id)
        if self.old_device_dict is not None:
            restored = LightingDevice.from_dict(self.old_device_dict)
            patch.restore_device(restored)
        self.app.lightshow.set_modified()
        self.app.emit("patch.changed")

    def redo(self) -> None:
        self.execute()


__all__ = [
    "PatchAddOutputAction",
    "PatchClearAction",
    "PatchDeviceAction",
    "PatchExchangeFixtureAction",
    "PatchSet1on1Action",
    "PatchSetDeviceCurveAction",
    "PatchSetOutputCurveAction",
    "PatchUnpatchDeviceAction",
    "PatchUnpatchOutputAction",
]

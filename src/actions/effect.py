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
"""Core actions for creating, editing, applying, and stopping parametric Effects."""

from __future__ import annotations

import copy
import typing
from typing import Any

from olc.core.action import Action
from olc.show.effect import (
    ActiveEffectInstance,
    DistributeDirection,
    EffectDefinition,
    EffectLayer,
)

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def format_effect_number(number: float) -> str:
    """Format effect number concisely (1.0 -> '1', 1.5 -> '1.5')."""
    num = float(number)
    return str(int(num)) if num.is_integer() else str(num)


class EffectCreateAction(Action):
    """Action to create a new EffectDefinition (blank or from a built-in template)."""

    name = "effect.create"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 1.0
        self.label: str = ""
        self.template_id: str | None = None
        self.extra_kwargs: dict[str, Any] = {}
        self._previous_dict: dict[str, Any] | None = None
        self._created_dict: dict[str, Any] | None = None

    def configure(
        self,
        number: float | None = None,
        label: str = "",
        template_id: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Configure effect creation parameters."""
        mgr = self.app.lightshow.effects
        self.number = (
            mgr.next_available_number() if number is None else round(float(number), 3)
        )
        self.label = str(label)
        self.template_id = (
            str(template_id).strip().lower() if template_id is not None else None
        )
        self.extra_kwargs = dict(kwargs)

    @property
    def description(self) -> str:
        """Human-readable description for undo history."""
        num_s = format_effect_number(self.number)
        if self.template_id:
            return f"Create Effect {num_s} ({self.template_id})"
        return f"Create Effect {num_s}"

    def execute(self) -> EffectDefinition:
        mgr = self.app.lightshow.effects
        existing = mgr.get(self.number)
        self._previous_dict = (
            copy.deepcopy(existing.to_dict()) if existing is not None else None
        )

        if self.template_id is not None:
            eff = mgr.create_from_template(
                self.template_id, number=self.number, label=self.label
            )
        else:
            eff = EffectDefinition(
                number=self.number,
                label=self.label or f"Effect {format_effect_number(self.number)}",
            )
            mgr.add(eff)

        for key, val in self.extra_kwargs.items():
            if key == "layers" and isinstance(val, list):
                eff.layers = [
                    item
                    if isinstance(item, EffectLayer)
                    else EffectLayer.from_dict(item)
                    for item in val
                ]
            elif hasattr(eff, key):
                setattr(eff, key, val)
        eff.__post_init__()

        self._created_dict = copy.deepcopy(eff.to_dict())
        self.app.lightshow.set_modified()
        self.app.emit("effect.created", eff.number)
        self.app.emit("effect.changed", eff.number)
        return eff

    def undo(self) -> None:
        mgr = self.app.lightshow.effects
        if self._previous_dict is not None:
            mgr.add(EffectDefinition.from_dict(self._previous_dict))
        else:
            mgr.delete(self.number)
        self.app.lightshow.set_modified()
        self.app.emit("effect.deleted", self.number)
        self.app.emit("effect.changed", self.number)

    def redo(self) -> None:
        if self._created_dict is not None:
            self.app.lightshow.effects.add(
                EffectDefinition.from_dict(self._created_dict)
            )
            self.app.lightshow.set_modified()
            self.app.emit("effect.created", self.number)
            self.app.emit("effect.changed", self.number)


class EffectDeleteAction(Action):
    """Action to delete an EffectDefinition from the show."""

    name = "effect.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 1.0
        self._deleted_dict: dict[str, Any] | None = None

    def configure(self, number: float) -> None:
        """Configure effect number to delete."""
        self.number = round(float(number), 3)

    @property
    def description(self) -> str:
        """Human-readable description for undo history."""
        return f"Delete Effect {format_effect_number(self.number)}"

    def execute(self) -> None:
        mgr = self.app.lightshow.effects
        eff = mgr.get(self.number)
        if eff is None:
            raise ValueError(
                f"Effect {format_effect_number(self.number)} does not exist"
            )
        self._deleted_dict = copy.deepcopy(eff.to_dict())
        self.app.effects_engine.stop_effect(effect_number=self.number)
        mgr.delete(self.number)
        self.app.lightshow.set_modified()
        self.app.emit("effect.deleted", self.number)
        self.app.emit("effect.changed", self.number)

    def undo(self) -> None:
        if self._deleted_dict is not None:
            self.app.lightshow.effects.add(
                EffectDefinition.from_dict(self._deleted_dict)
            )
            self.app.lightshow.set_modified()
            self.app.emit("effect.created", self.number)
            self.app.emit("effect.changed", self.number)

    def redo(self) -> None:
        self.app.effects_engine.stop_effect(effect_number=self.number)
        self.app.lightshow.effects.delete(self.number)
        self.app.lightshow.set_modified()
        self.app.emit("effect.deleted", self.number)
        self.app.emit("effect.changed", self.number)


class EffectRenameAction(Action):
    """Action to rename an EffectDefinition."""

    name = "effect.rename"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 1.0
        self.new_label: str = ""
        self._old_label: str = ""

    def configure(self, number: float, label: str) -> None:
        """Configure effect number and new label."""
        self.number = round(float(number), 3)
        self.new_label = str(label)

    @property
    def description(self) -> str:
        """Human-readable description for undo history."""
        return f"Rename Effect {format_effect_number(self.number)}"

    def execute(self) -> None:
        eff = self.app.lightshow.effects.get(self.number)
        if eff is None:
            raise ValueError(
                f"Effect {format_effect_number(self.number)} does not exist"
            )
        self._old_label = eff.label
        eff.label = self.new_label
        self.app.lightshow.set_modified()
        self.app.emit("effect.changed", self.number)

    def undo(self) -> None:
        eff = self.app.lightshow.effects.get(self.number)
        if eff is not None:
            eff.label = self._old_label
            self.app.lightshow.set_modified()
            self.app.emit("effect.changed", self.number)

    def redo(self) -> None:
        eff = self.app.lightshow.effects.get(self.number)
        if eff is not None:
            eff.label = self.new_label
            self.app.lightshow.set_modified()
            self.app.emit("effect.changed", self.number)


class EffectUpdateAction(Action):
    """Action to update parameters or layers on an EffectDefinition."""

    name = "effect.update"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 1.0
        self.changes: dict[str, Any] = {}
        self._before_dict: dict[str, Any] | None = None
        self._after_dict: dict[str, Any] | None = None

    def configure(
        self,
        number: float,
        **changes: Any,  # noqa: ANN401
    ) -> None:
        """Configure effect number and field changes."""
        self.number = round(float(number), 3)
        self.changes = dict(changes)

    @property
    def description(self) -> str:
        """Human-readable description for undo history."""
        return f"Update Effect {format_effect_number(self.number)}"

    def execute(self) -> None:
        mgr = self.app.lightshow.effects
        eff = mgr.get(self.number)
        if eff is None:
            raise ValueError(
                f"Effect {format_effect_number(self.number)} does not exist"
            )
        self._before_dict = copy.deepcopy(eff.to_dict())

        if "bpm" in self.changes:
            eff.set_bpm(self.changes["bpm"])
        if "cycle_time" in self.changes:
            eff.set_cycle_time(float(self.changes["cycle_time"]))
        if "rate" in self.changes and self.changes["rate"] is not None:
            rate_pct = max(1.0, float(self.changes["rate"]))
            eff.set_cycle_time(2.0 / (rate_pct / 100.0))
        if "size" in self.changes and self.changes["size"] is not None:
            new_size = float(self.changes["size"])
            for layer in eff.layers:
                layer.size = new_size
        if "trail" in self.changes and self.changes["trail"] is not None:
            new_duty = max(0.01, min(1.0, float(self.changes["trail"]) / 100.0))
            for layer in eff.layers:
                layer.duty_cycle = new_duty
        for key in (
            "label",
            "direction",
            "entry_mode",
            "exit_mode",
            "groups",
            "blocks",
            "wings",
            "axis_deg",
            "phase_start_deg",
            "phase_end_deg",
            "speed_multiplier",
        ):
            if key in self.changes and self.changes[key] is not None:
                setattr(eff, key, self.changes[key])
        for nullable_key in ("speed_master", "rate_master", "size_master"):
            if nullable_key in self.changes:
                setattr(eff, nullable_key, self.changes[nullable_key])
        if "layers" in self.changes and isinstance(self.changes["layers"], list):
            eff.layers = [
                item if isinstance(item, EffectLayer) else EffectLayer.from_dict(item)
                for item in self.changes["layers"]
            ]
        eff.__post_init__()
        self._after_dict = copy.deepcopy(eff.to_dict())
        self.app.lightshow.set_modified()
        self.app.emit("effect.changed", self.number)

    def undo(self) -> None:
        if self._before_dict is not None:
            self.app.lightshow.effects.add(
                EffectDefinition.from_dict(self._before_dict)
            )
            self.app.lightshow.set_modified()
            self.app.emit("effect.changed", self.number)

    def redo(self) -> None:
        if self._after_dict is not None:
            self.app.lightshow.effects.add(EffectDefinition.from_dict(self._after_dict))
            self.app.lightshow.set_modified()
            self.app.emit("effect.changed", self.number)


# pylint: disable=too-many-instance-attributes
class EffectApplyAction(Action):
    """Action to apply/start an Effect on an ordered channel selection."""

    name = "effect.apply"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float = 1.0
        self.channels: list[int] = []
        self.rate_scale: float = 1.0
        self.size_scale: float = 1.0
        self.groups: int | None = None
        self.blocks: int | None = None
        self.wings: int | None = None
        self.direction: DistributeDirection | None = None
        self.fade_in: float = 0.0
        self._prev_instances: list[dict[str, Any]] = []
        self._prev_live_refs: dict[int, dict[str, Any] | None] = {}

    # pylint: disable=too-many-arguments
    def configure(
        self,
        number: float,
        channels: list[int] | None = None,
        *,
        rate_scale: float = 1.0,
        size_scale: float = 1.0,
        groups: int | None = None,
        blocks: int | None = None,
        wings: int | None = None,
        direction: str | DistributeDirection | None = None,
        fade_in: float = 0.0,
    ) -> None:
        """Configure effect application parameters."""
        self.number = round(float(number), 3)
        raw_chs = (
            list(channels) if channels is not None else list(self.app.selected_channels)
        )
        self.channels = list(dict.fromkeys(int(c) for c in raw_chs))
        self.rate_scale = max(0.01, float(rate_scale))
        self.size_scale = max(0.0, float(size_scale))
        self.groups = int(groups) if groups is not None else None
        self.blocks = int(blocks) if blocks is not None else None
        self.wings = int(wings) if wings is not None else None
        if direction is None:
            self.direction = None
        elif isinstance(direction, DistributeDirection):
            self.direction = direction
        else:
            self.direction = DistributeDirection(str(direction).strip().lower())
        self.fade_in = max(0.0, float(fade_in))

    @property
    def description(self) -> str:
        """Human-readable description for undo history."""
        return f"Apply Effect {format_effect_number(self.number)}"

    def execute(self) -> list[int]:
        if not self.channels:
            return []
        eff = self.app.lightshow.effects.get(self.number)
        if eff is None:
            raise ValueError(
                f"Effect {format_effect_number(self.number)} does not exist"
            )

        self._prev_instances = [
            copy.deepcopy(inst.to_dict())
            for inst in self.app.effects_engine.get_active_instances()
        ]
        self._prev_live_refs = self.app.live_state.snapshot_effect_refs(self.channels)

        self.app.live_state.set_effect_ref(
            self.channels,
            self.number,
            rate_scale=self.rate_scale,
            size_scale=self.size_scale,
            groups=self.groups,
            blocks=self.blocks,
            wings=self.wings,
            direction=self.direction.value if self.direction is not None else None,
        )
        self.app.effects_engine.start_effect(
            self.number,
            self.channels,
            rate_scale=self.rate_scale,
            size_scale=self.size_scale,
            groups_override=self.groups,
            blocks_override=self.blocks,
            wings_override=self.wings,
            direction_override=self.direction,
            fade_in=self.fade_in,
        )
        self.app.effects_engine.tick()
        self.app.emit("effect.applied", self.number, list(self.channels))
        self.app.emit("live.state_changed", list(self.channels))
        return list(self.channels)

    def undo(self) -> None:
        self.app.effects_engine.stop_all()
        for inst_dict in self._prev_instances:
            inst = ActiveEffectInstance.from_dict(inst_dict)
            self.app.effects_engine.start_effect(
                inst.effect_number,
                inst.channels,
                rate_scale=inst.rate_scale,
                size_scale=inst.size_scale,
                groups_override=inst.groups_override,
                blocks_override=inst.blocks_override,
                wings_override=inst.wings_override,
                direction_override=inst.direction_override,
            )
        if self._prev_instances:
            self.app.effects_engine.tick()
        self.app.live_state.restore_effect_refs(self._prev_live_refs)
        self.app.emit("effect.stopped", self.number, list(self.channels))
        self.app.emit("live.state_changed", list(self.channels))

    def redo(self) -> None:
        self.execute()


class EffectStopAction(Action):
    """Action to stop/stomp running effect(s) on selected or all channels."""

    name = "effect.stop"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float | None = None
        self.channels: list[int] | None = None
        self.fade_out: float = 0.0
        self.mark_live_stop: bool = True
        self._prev_instances: list[dict[str, Any]] = []
        self._prev_live_refs: dict[int, dict[str, Any] | None] = {}
        self._affected_channels: list[int] = []

    def configure(
        self,
        number: float | None = None,
        channels: list[int] | None = None,
        *,
        fade_out: float = 0.0,
        mark_live_stop: bool = True,
    ) -> None:
        """Configure optional effect number, channel filter, and fade_out time."""
        self.number = round(float(number), 3) if number is not None else None
        self.channels = (
            list(dict.fromkeys(int(c) for c in channels))
            if channels is not None
            else None
        )
        self.fade_out = max(0.0, float(fade_out))
        self.mark_live_stop = bool(mark_live_stop)

    @property
    def description(self) -> str:
        """Human-readable description for undo history."""
        if self.number is not None:
            return f"Stop Effect {format_effect_number(self.number)}"
        return "Stop Effect"

    def execute(self) -> list[int]:
        active = self.app.effects_engine.get_active_instances()
        self._prev_instances = [copy.deepcopy(inst.to_dict()) for inst in active]
        if self.channels is not None:
            target_chs = list(self.channels)
        else:
            target_chs = sorted({ch for inst in active for ch in inst.channels})
        self._affected_channels = target_chs
        self._prev_live_refs = self.app.live_state.snapshot_effect_refs(target_chs)

        if self.mark_live_stop and target_chs:
            self.app.live_state.set_effect_stopped(target_chs, self.number)

        self.app.effects_engine.stop_effect(
            effect_number=self.number,
            channels=self.channels,
            fade_out=self.fade_out,
        )
        self.app.emit("effect.stopped", self.number, list(target_chs))
        self.app.emit("live.state_changed", list(target_chs))
        return list(target_chs)

    def undo(self) -> None:
        self.app.effects_engine.stop_all()
        for inst_dict in self._prev_instances:
            inst = ActiveEffectInstance.from_dict(inst_dict)
            self.app.effects_engine.start_effect(
                inst.effect_number,
                inst.channels,
                rate_scale=inst.rate_scale,
                size_scale=inst.size_scale,
                groups_override=inst.groups_override,
                blocks_override=inst.blocks_override,
                wings_override=inst.wings_override,
                direction_override=inst.direction_override,
            )
        if self._prev_instances:
            self.app.effects_engine.tick()
        self.app.live_state.restore_effect_refs(self._prev_live_refs)
        self.app.emit("effect.applied", self.number, list(self._affected_channels))
        self.app.emit("live.state_changed", list(self._affected_channels))

    def redo(self) -> None:
        self.execute()


class EffectTapTempoAction(Action):
    """Action to tap musical tempo for a specific effect or all active effects."""

    name = "effect.tap_tempo"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.number: float | None = None
        self.now: float | None = None

    def configure(
        self, number: float | None = None, *, now: float | None = None
    ) -> None:
        """Configure optional effect number and timestamp."""
        self.number = round(float(number), 3) if number is not None else None
        self.now = float(now) if now is not None else None

    def execute(self) -> float | None:
        bpm = self.app.effects_engine.tap_tempo(self.number, now=self.now)
        if bpm is not None:
            self.app.lightshow.set_modified()
            self.app.emit("effect.changed", self.number)
        return bpm

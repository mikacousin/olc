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
"""Actions for fader operations (assign, clear, set_level, set_page, flash)."""

from __future__ import annotations

import typing
from gettext import gettext as _

from olc.core.action import Action
from olc.define import MAX_ALLOWED_FADER_PAGES, MAX_FADER_PAGE
from olc.show.fader import (
    FADER_OPTION_FLAGS,
    FaderEffect,
    FaderEffectMaster,
    FaderType,
)

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _get_fader_contents_number(
    app: CoreApplication, page: int, index: int
) -> float | tuple[str, int] | None:
    """Return the identifier of the current fader contents, or None.

    Args:
        app: Core application instance.
        page: Fader page number.
        index: Fader index within the page.

    Returns:
        Float identifier, ``(master_kind, master_id)`` tuple, or None.
    """
    fader = app.lightshow.fader_bank.faders[page][index]
    if isinstance(fader, FaderEffectMaster):
        return (fader.master_kind, fader.master_id)
    contents = getattr(fader, "contents", None)
    if contents is None:
        return None
    # Sequence has .index and .steps
    if hasattr(contents, "index") and hasattr(contents, "steps"):
        return float(contents.index)
    # Preset Palette or Cue has .number
    if hasattr(contents, "number"):
        return float(contents.number)
    if hasattr(contents, "index"):
        return float(contents.index)
    return None


class FaderAssignAction(Action):
    """Action to assign a type and optional contents to a fader.

    Supports full undo/redo: the previous type and contents are saved and
    restored on undo.
    """

    name = "fader.assign"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.new_type: FaderType = FaderType.NONE
        self.new_contents: float | tuple[str, int] | None = None
        self.old_type: FaderType = FaderType.NONE
        self.old_contents: float | tuple[str, int] | None = None
        self.old_control_mode: str = "size"
        self.old_effect_channels: list[int] = []
        self.old_fixed_source: int | None = None
        self._blocked: bool = False

    def configure(
        self,
        page: int,
        index: int,
        fader_type: FaderType,
        contents: float | tuple[str, int] | None = None,
    ) -> None:
        """Configure the fader assignment.

        Args:
            page: Fader page number.
            index: Fader index within the page.
            fader_type: Target FaderType to assign.
            contents: Optional numeric identifier for the fader contents
                (preset/cue number or sequence index).
        """
        self.page = page
        self.index = index
        self.new_type = fader_type
        self.new_contents = contents

    def execute(self) -> None:
        """Snapshot the current state, then apply the new assignment."""
        old_fader = self.app.lightshow.fader_bank.faders[self.page][self.index]
        if getattr(old_fader, "locked", False):
            self._blocked = True
            self.can_undo = False
            return
        self._blocked = False
        self.old_type = self.app.lightshow.fader_bank.get_fader_type(
            self.page, self.index
        )
        self.old_contents = _get_fader_contents_number(self.app, self.page, self.index)
        self.old_fixed_source = self.app.lightshow.fader_bank.get_fixed_source_page(
            self.index
        )
        if isinstance(old_fader, FaderEffect):
            self.old_control_mode = old_fader.control_mode
            self.old_effect_channels = list(old_fader.effect_channels)
        else:
            self.old_control_mode = "size"
            self.old_effect_channels = []

        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.new_type, self.new_contents
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def undo(self) -> None:
        """Restore the previous fader assignment."""
        if self._blocked:
            return
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.old_type, self.old_contents
        )
        restored = self.app.lightshow.fader_bank.faders[self.page][self.index]
        if isinstance(restored, FaderEffect):
            restored.set_control_mode(self.old_control_mode)
            restored.set_effect_channels(self.old_effect_channels)
        if self.old_fixed_source is not None:
            self.app.lightshow.fader_bank.set_fader_fixed(
                self.old_fixed_source, self.index, True
            )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def redo(self) -> None:
        """Re-apply the fader assignment."""
        if self._blocked:
            return
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.new_type, self.new_contents
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)


class FaderClearAction(Action):
    """Action to clear (reset to NONE) a fader assignment.

    A dedicated action rather than a simple alias of fader.assign so that it
    appears explicitly in OSC/MIDI bindings and the action registry.
    """

    name = "fader.clear"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.old_type: FaderType = FaderType.NONE
        self.old_contents: float | tuple[str, int] | None = None
        self.old_control_mode: str = "size"
        self.old_effect_channels: list[int] = []
        self.old_fixed_source: int | None = None
        self._blocked: bool = False

    def configure(self, page: int, index: int) -> None:
        """Configure the fader to clear.

        Args:
            page: Fader page number.
            index: Fader index within the page.
        """
        self.page = page
        self.index = index

    def execute(self) -> None:
        """Snapshot the current assignment, then clear the fader."""
        old_fader = self.app.lightshow.fader_bank.faders[self.page][self.index]
        if getattr(old_fader, "locked", False):
            self._blocked = True
            self.can_undo = False
            return
        self._blocked = False
        self.old_type = self.app.lightshow.fader_bank.get_fader_type(
            self.page, self.index
        )
        self.old_contents = _get_fader_contents_number(self.app, self.page, self.index)
        self.old_fixed_source = self.app.lightshow.fader_bank.get_fixed_source_page(
            self.index
        )
        if isinstance(old_fader, FaderEffect):
            self.old_control_mode = old_fader.control_mode
            self.old_effect_channels = list(old_fader.effect_channels)
        else:
            self.old_control_mode = "size"
            self.old_effect_channels = []

        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, FaderType.NONE, None
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def undo(self) -> None:
        """Restore the previous fader assignment."""
        if self._blocked:
            return
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, self.old_type, self.old_contents
        )
        restored = self.app.lightshow.fader_bank.faders[self.page][self.index]
        if isinstance(restored, FaderEffect):
            restored.set_control_mode(self.old_control_mode)
            restored.set_effect_channels(self.old_effect_channels)
        if self.old_fixed_source is not None:
            self.app.lightshow.fader_bank.set_fader_fixed(
                self.old_fixed_source, self.index, True
            )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def redo(self) -> None:
        """Re-clear the fader."""
        if self._blocked:
            return
        self.app.lightshow.fader_bank.set_fader(
            self.page, self.index, FaderType.NONE, None
        )
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)


# pylint: disable=too-many-instance-attributes
class FaderConfigureEffectAction(Action):
    """Action to configure control mode and target channels of a FaderEffect."""

    name = "fader.configure_effect"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.new_mode: str | None = None
        self.new_channels: list[int] | None = None
        self._old_mode: str = "size"
        self._old_channels: list[int] = []

    def configure(
        self,
        page: int,
        index: int,
        *,
        control_mode: str | None = None,
        effect_channels: list[int] | None = None,
    ) -> None:
        """Configure control_mode and/or effect_channels on a FaderEffect."""
        self.page = int(page)
        self.index = int(index)
        self.new_mode = str(control_mode) if control_mode is not None else None
        self.new_channels = (
            list(dict.fromkeys(int(c) for c in effect_channels))
            if effect_channels is not None
            else None
        )

    def _apply(self, mode: str | None, channels: list[int] | None) -> None:
        fader = self.app.lightshow.fader_bank.faders[self.page][self.index]
        if not isinstance(fader, FaderEffect):
            return
        if mode is not None:
            fader.set_control_mode(mode)
        if channels is not None:
            fader.set_effect_channels(channels)
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def execute(self) -> None:
        """Snapshot current effect fader settings and apply new ones."""
        fader = self.app.lightshow.fader_bank.faders[self.page][self.index]
        if not isinstance(fader, FaderEffect):
            return
        self._old_mode = fader.control_mode
        self._old_channels = list(fader.effect_channels)
        self._apply(self.new_mode, self.new_channels)

    def undo(self) -> None:
        """Restore previous control mode and target channels."""
        self._apply(
            self._old_mode if self.new_mode is not None else None,
            self._old_channels if self.new_channels is not None else None,
        )

    def redo(self) -> None:
        """Re-apply new control mode and target channels."""
        self._apply(self.new_mode, self.new_channels)


class FaderSetLevelAction(Action):
    """Action to set fader level in real time."""

    name = "fader.set_level"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.level: float = 0.0

    def configure(self, page: int, index: int, level: float) -> None:
        """Configure the action parameters.

        Args:
            page: Fader page number.
            index: Fader index within the page.
            level: The target intensity level (0.0 to 1.0).
        """
        self.page = page
        self.index = index
        self.level = level

    def execute(self) -> None:
        """Apply the level to the fader and emit event for remote synchronization."""
        fader_bank = self.app.lightshow.fader_bank
        effective_page = fader_bank.resolve_page(self.page, self.index)
        fader_bank.faders[effective_page][self.index].set_level(self.level)
        if effective_page == fader_bank.resolve_page(
            fader_bank.active_page, self.index
        ):
            self.app.emit("fader.level_changed", self.index, self.level)


class FaderSetPageAction(Action):
    """Action to set the active fader page in real time."""

    name = "fader.set_page"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1

    def configure(self, page: int) -> None:
        """Configure the action parameters.

        Args:
            page: Fader page number.
        """
        self.page = page

    def execute(self) -> None:
        """Apply the active page to the fader bank and emit event."""
        fader_bank = self.app.lightshow.fader_bank
        max_page = getattr(fader_bank, "max_fader_page", MAX_FADER_PAGE)

        target_page = self.page
        if target_page < 1:
            target_page = max_page
        elif target_page > max_page:
            target_page = 1

        if fader_bank.active_page != target_page:
            fader_bank.active_page = target_page
            self.app.emit("fader.page_changed", target_page)


class FaderFlashAction(Action):
    """Action to toggle a fader flash (press or release)."""

    name = "fader.flash"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.pressed: bool = False

    def configure(self, page: int, index: int, pressed: bool) -> None:
        """Configure the flash action.

        Args:
            page: Fader page number.
            index: Fader index within the page.
            pressed: True if flash button is pressed, False if released.
        """
        self.page = page
        self.index = index
        self.pressed = pressed

    def execute(self) -> None:
        """Execute the flash action."""
        fader_bank = self.app.lightshow.fader_bank
        effective_page = fader_bank.resolve_page(self.page, self.index)
        fader = fader_bank.faders[effective_page][self.index]
        if self.pressed:
            fader.flash_on()
        else:
            fader.flash_off()

        if effective_page == fader_bank.resolve_page(
            fader_bank.active_page, self.index
        ):
            self.app.emit("fader.flash_changed", self.index, self.pressed)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state for this action."""
        return {"active": self.pressed, "index": self.index}


def _snapshot_fader(
    app: CoreApplication, page: int, index: int
) -> dict[str, typing.Any]:
    """Capture complete configuration and level of fader at *(page, index)*."""
    fader_bank = app.lightshow.fader_bank
    fader_type = fader_bank.get_fader_type(page, index)
    fader = fader_bank.faders[page][index]
    if fader_type == FaderType.CHANNELS:
        raw_ch = getattr(fader, "channels_dict", None) or getattr(
            fader, "contents", None
        )
        contents: typing.Any = dict(raw_ch) if isinstance(raw_ch, dict) else {}
    else:
        contents = _get_fader_contents_number(app, page, index)
    return {
        "fader_type": fader_type,
        "contents": contents,
        "level": float(getattr(fader, "level", 0.0)),
        "text": str(getattr(fader, "text", "")),
        "exempt_grand_master": bool(getattr(fader, "exempt_grand_master", False)),
        "intensity_master": bool(getattr(fader, "intensity_master", False)),
        "control_mode": str(getattr(fader, "control_mode", "size")),
        "effect_channels": list(getattr(fader, "effect_channels", [])),
        "base_channels": dict(getattr(fader, "base_channels", {})),
        "fixed": fader_bank.is_fader_fixed(page, index),
    }


def _restore_fader(
    app: CoreApplication,
    page: int,
    index: int,
    snap: dict[str, typing.Any],
) -> None:
    """Restore a fader at *(page, index)* from *snap*."""
    fader_bank = app.lightshow.fader_bank
    fader_bank.set_fader(page, index, snap["fader_type"], snap["contents"])
    restored = fader_bank.faders[page][index]
    if snap["exempt_grand_master"]:
        restored.exempt_grand_master = True
    if snap["intensity_master"] and hasattr(restored, "intensity_master"):
        restored.intensity_master = True
    if isinstance(restored, FaderEffect):
        restored.set_control_mode(snap["control_mode"])
        restored.set_effect_channels(snap["effect_channels"])
        if snap["base_channels"]:
            restored.set_base_channels(snap["base_channels"])
    if snap["text"] and not restored.text:
        restored.text = snap["text"]
    if snap["level"] > 0.0 and not snap["fader_type"] == FaderType.MAIN:
        restored.set_level(float(snap["level"]))
    if snap.get("fixed"):
        fader_bank.set_fader_fixed(page, index, True)


class FaderSetPageCountAction(Action):
    """Action to resize total available fader pages at runtime with Undo/Redo."""

    name = "fader.set_page_count"
    history_label = _("Set fader pages")
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.page_count: int = MAX_FADER_PAGE
        self.old_page_count: int = MAX_FADER_PAGE
        self.old_active_page: int = 1
        self.old_modified: bool = False
        self._removed_faders: dict[tuple[int, int], dict[str, typing.Any]] = {}

    def configure(self, page_count: int) -> None:
        """Configure target total number of fader pages (1..100)."""
        self.page_count = max(1, min(MAX_ALLOWED_FADER_PAGES, int(page_count)))

    def get_history_details(self) -> str:
        """Return target page count string for history panel."""
        return str(self.page_count)

    def execute(self) -> None:
        """Resize fader bank pages and snapshot removed non-empty faders."""
        fader_bank = self.app.lightshow.fader_bank
        self.old_page_count = fader_bank.max_fader_page
        self.old_active_page = fader_bank.active_page
        self.old_modified = bool(self.app.lightshow.modified)
        if self.page_count == self.old_page_count:
            self.can_undo = False
            return

        self._removed_faders = {}
        if self.page_count < self.old_page_count:
            for p in range(self.page_count + 1, self.old_page_count + 1):
                for idx in range(1, fader_bank.max_fader_per_page + 1):
                    if fader_bank.get_fader_type(p, idx) != FaderType.NONE:
                        self._removed_faders[(p, idx)] = _snapshot_fader(
                            self.app, p, idx
                        )

        page_clamped = fader_bank.set_max_pages(self.page_count)
        self.app.lightshow.set_modified()
        if page_clamped:
            self.app.emit("fader.page_changed", fader_bank.active_page)
        self.app.emit("fader.page_count_changed", self.page_count)

    def undo(self) -> None:
        """Restore previous fader page count and any removed faders."""
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.set_max_pages(self.old_page_count)
        for (p, idx), snap in self._removed_faders.items():
            _restore_fader(self.app, p, idx, snap)

        page_changed = fader_bank.active_page != self.old_active_page
        fader_bank.active_page = self.old_active_page
        if self.old_modified:
            self.app.lightshow.set_modified()
        else:
            self.app.lightshow.set_not_modified()

        if page_changed:
            self.app.emit("fader.page_changed", fader_bank.active_page)
        self.app.emit("fader.page_count_changed", self.old_page_count)

    def redo(self) -> None:
        """Re-apply target fader page count."""
        fader_bank = self.app.lightshow.fader_bank
        page_clamped = fader_bank.set_max_pages(self.page_count)
        self.app.lightshow.set_modified()
        if page_clamped:
            self.app.emit("fader.page_changed", fader_bank.active_page)
        self.app.emit("fader.page_count_changed", self.page_count)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return page count feedback state metadata."""
        return {"page_count": self.page_count}


class FaderSetSkipEmptyPagesAction(Action):
    """Action to toggle skipping empty fader pages during playback navigation."""

    name = "fader.set_skip_empty_pages"
    history_label = _("Toggle skip empty fader pages")
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.skip_empty: bool = False
        self.old_skip_empty: bool = False
        self.old_modified: bool = False

    def configure(self, skip_empty: bool) -> None:
        """Configure whether empty fader pages should be skipped."""
        self.skip_empty = bool(skip_empty)

    def get_history_details(self) -> str:
        """Return human-readable enabled/disabled state for history panel."""
        return _("Enabled") if self.skip_empty else _("Disabled")

    def execute(self) -> None:
        """Update fader_bank.skip_empty_pages and notify listeners."""
        fader_bank = self.app.lightshow.fader_bank
        self.old_skip_empty = bool(getattr(fader_bank, "skip_empty_pages", False))
        self.old_modified = bool(self.app.lightshow.modified)
        if self.old_skip_empty == self.skip_empty:
            self.can_undo = False
            return

        fader_bank.skip_empty_pages = self.skip_empty
        self.app.lightshow.set_modified()
        self.app.emit("fader.skip_empty_pages_changed", self.skip_empty)

    def undo(self) -> None:
        """Restore previous skip_empty_pages setting."""
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.skip_empty_pages = self.old_skip_empty
        if self.old_modified:
            self.app.lightshow.set_modified()
        else:
            self.app.lightshow.set_not_modified()
        self.app.emit("fader.skip_empty_pages_changed", self.old_skip_empty)

    def redo(self) -> None:
        """Re-apply skip_empty_pages setting."""
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.skip_empty_pages = self.skip_empty
        self.app.lightshow.set_modified()
        self.app.emit("fader.skip_empty_pages_changed", self.skip_empty)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return skip_empty_pages feedback state metadata."""
        return {"skip_empty_pages": self.skip_empty}


class FaderSetFixedAction(Action):
    """Action to fix or unfix a fader across all fader pages with Undo/Redo."""

    name = "fader.set_fixed"
    history_label = _("Fix fader")
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.fixed: bool | None = None
        self._applied_fixed: bool = False
        self.old_source_page: int | None = None
        self.old_modified: bool = False

    def configure(self, page: int, index: int, fixed: bool | None = None) -> None:
        """Configure target fader *(page, index)* and optional explicit fixed state."""
        self.page = int(page)
        self.index = int(index)
        self.fixed = None if fixed is None else bool(fixed)

    def get_history_details(self) -> str:
        """Return formatted page, index, and fixed state for history panel."""
        state_str = _("Fixed") if self._applied_fixed else _("Unfixed")
        return f"P{self.page}.{self.index} ({state_str})"

    def execute(self) -> None:
        """Apply fixed/unfixed state on target fader column and notify listeners."""
        fader_bank = self.app.lightshow.fader_bank
        if (
            self.page not in fader_bank.faders
            or self.index not in fader_bank.faders[self.page]
        ):
            self.can_undo = False
            return

        currently_fixed_here = fader_bank.is_fader_fixed(self.page, self.index)
        target_fixed = (not currently_fixed_here) if self.fixed is None else self.fixed
        if (
            target_fixed
            and fader_bank.get_fader_type(self.page, self.index) == FaderType.NONE
        ):
            self.can_undo = False
            return
        if target_fixed == currently_fixed_here:
            self.can_undo = False
            return

        self._applied_fixed = target_fixed
        self.old_source_page = fader_bank.get_fixed_source_page(self.index)
        self.old_modified = bool(self.app.lightshow.modified)

        fader_bank.set_fader_fixed(self.page, self.index, target_fixed)
        self.app.lightshow.set_modified()
        self.app.emit("fader.fixed_changed", self.page, self.index, target_fixed)
        self.app.emit("fader.changed", fader_bank.active_page, self.index)

    def undo(self) -> None:
        """Restore previous fixed column ownership."""
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.fixed_faders.pop(self.index, None)
        if self.old_source_page is not None:
            fader_bank.set_fader_fixed(self.old_source_page, self.index, True)
        if self.old_modified:
            self.app.lightshow.set_modified()
        else:
            self.app.lightshow.set_not_modified()

        is_now_fixed = fader_bank.is_fader_fixed(self.page, self.index)
        self.app.emit("fader.fixed_changed", self.page, self.index, is_now_fixed)
        self.app.emit("fader.changed", fader_bank.active_page, self.index)

    def redo(self) -> None:
        """Re-apply fixed/unfixed state on target fader column."""
        fader_bank = self.app.lightshow.fader_bank
        fader_bank.set_fader_fixed(self.page, self.index, self._applied_fixed)
        self.app.lightshow.set_modified()
        self.app.emit("fader.fixed_changed", self.page, self.index, self._applied_fixed)
        self.app.emit("fader.changed", fader_bank.active_page, self.index)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return fixed state metadata."""
        return {
            "page": self.page,
            "index": self.index,
            "fixed": self._applied_fixed,
        }


class FaderSetOptionsAction(Action):
    """Action to toggle exclusion/protection flags on a Fader with Undo/Redo."""

    name = "fader.set_options"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.page: int = 1
        self.index: int = 1
        self.new_options: dict[str, bool] = {}
        self.old_options: dict[str, bool] = {}
        self.old_level: float = 0.0

    def configure(self, page: int, index: int, **options: bool) -> None:
        """Configure target fader and option flags to apply."""
        self.page = page
        self.index = index
        self.new_options = {
            k: bool(v) for k, v in options.items() if k in FADER_OPTION_FLAGS
        }

    def _apply_options(
        self, options: dict[str, bool], level: float | None = None
    ) -> None:
        fader_bank = self.app.lightshow.fader_bank
        fader = fader_bank.faders[self.page][self.index]
        for key, val in options.items():
            if hasattr(fader, key):
                setattr(fader, key, bool(val))
        if level is not None:
            fader.level = float(level)
        fader_bank.update_levels()
        if hasattr(self.app, "backend") and self.app.backend:
            self.app.backend.dmx.set_levels()
        self.app.lightshow.set_modified()
        self.app.emit("fader.changed", self.page, self.index)

    def execute(self) -> None:
        """Snapshot existing flags and apply new options."""
        fader = self.app.lightshow.fader_bank.faders[self.page][self.index]
        self.old_options = {
            key: bool(getattr(fader, key))
            for key in self.new_options
            if hasattr(fader, key)
        }
        self.old_level = float(fader.level)
        new_level: float | None = None
        if (
            self.new_options.get("inhibitive") is True
            and not self.old_options.get("inhibitive", False)
            and fader.level == 0.0
        ):
            new_level = 1.0
        self._apply_options(self.new_options, level=new_level)

    def undo(self) -> None:
        """Restore previous flags and fader level."""
        self._apply_options(self.old_options, level=self.old_level)

    def redo(self) -> None:
        """Re-apply new options."""
        new_level: float | None = None
        if (
            self.new_options.get("inhibitive") is True
            and not self.old_options.get("inhibitive", False)
            and self.old_level == 0.0
        ):
            new_level = 1.0
        self._apply_options(self.new_options, level=new_level)

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
"""Optional local GDTF enrichment for native ETC Eos ``.esf3d`` personalities."""

from __future__ import annotations

from collections.abc import Mapping

from olc.devices.channel import ChannelRange, ChannelType
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
)
from olc.files.ascii.gdtf_matcher import (
    _STATUS_RANK,
    GdtfMatchResult,
    MatchStatus,
    _find_candidate_definitions,
    validate_eos_vs_gdtf_mode,
)

_WHEEL_LABEL_KEYWORDS = ("gobo", "color", "animation")


def match_eos_fixture_definition(
    pers_id: int,
    eos_fdef: FixtureDefinition,
    fixture_library: FixtureLibrary | None,
) -> GdtfMatchResult:
    """Find and validate the best matching local GDTF mode for *eos_fdef*."""
    eos_fdef_dict = eos_fdef.to_dict()
    eos_fp = eos_fdef.dmx_modes[0].footprint() if eos_fdef.dmx_modes else 0
    candidates = _find_candidate_definitions(
        eos_fdef.manufacturer, eos_fdef.model, fixture_library
    )

    if not candidates:
        return GdtfMatchResult(
            pers_id=pers_id,
            eos_manufacturer=eos_fdef.manufacturer,
            eos_model=eos_fdef.model,
            eos_footprint=eos_fp,
            status=MatchStatus.NO_CANDIDATE,
            score=0.0,
            gdtf_definition=None,
            gdtf_mode=None,
            gobo_count=0,
            issues=(),
            offset_channel_map={},
        )

    evaluated: list[GdtfMatchResult] = []
    for g_def in candidates:
        for g_mode in g_def.dmx_modes:
            if g_mode.footprint() == eos_fp:
                evaluated.append(
                    validate_eos_vs_gdtf_mode(pers_id, eos_fdef_dict, g_def, g_mode)
                )

    if not evaluated:
        first_def = candidates[0]
        first_mode = first_def.dmx_modes[0] if first_def.dmx_modes else None
        if first_mode is not None:
            return validate_eos_vs_gdtf_mode(
                pers_id, eos_fdef_dict, first_def, first_mode
            )
        return GdtfMatchResult(
            pers_id=pers_id,
            eos_manufacturer=eos_fdef.manufacturer,
            eos_model=eos_fdef.model,
            eos_footprint=eos_fp,
            status=MatchStatus.INCOMPATIBLE,
            score=0.0,
            gdtf_definition=first_def,
            gdtf_mode=None,
            gobo_count=0,
            issues=(),
            offset_channel_map={},
        )

    evaluated.sort(
        key=lambda r: (_STATUS_RANK[r.status], r.score, r.gobo_count),
        reverse=True,
    )
    return evaluated[0]


def should_use_gdtf_for_personality(
    pers_id: int,
    match: GdtfMatchResult | None,
    actions: Mapping[str, object],
) -> bool:
    """Return True if *match* should be used to enrich *pers_id*."""
    use_gdtf = bool(actions.get("use_gdtf_matches", True))
    if not use_gdtf or match is None:
        return False
    if match.gdtf_definition is None or match.gdtf_mode is None:
        return False

    raw_overrides = actions.get("gdtf_overrides")
    override = "auto"
    if isinstance(raw_overrides, Mapping):
        val = raw_overrides.get(pers_id, raw_overrides.get(str(pers_id), "auto"))
        override = str(val)

    if override == "eos":
        return False
    if override == "gdtf":
        return True
    return match.status in (MatchStatus.COMPATIBLE, MatchStatus.WARNING)


def _clone_range(r: ChannelRange, ctype: ChannelType | None = None) -> ChannelRange:
    return ChannelRange(
        label=r.label,
        channel_type=ctype if ctype is not None else r.channel_type,
        value_min=r.value_min,
        value_max=r.value_max,
        snap_value=r.snap_value,
        description=r.description,
        physical_min=r.physical_min,
        physical_max=r.physical_max,
        physical_unit=r.physical_unit,
        gobo_id=r.gobo_id,
    )


def _is_wheel_channel(ch: ChannelDefinition) -> bool:
    if ch.channel_type in (ChannelType.GOBO_WHEEL, ChannelType.COLOR_WHEEL):
        return True
    low = ch.label.lower()
    return any(kw in low for kw in _WHEEL_LABEL_KEYWORDS)


def _best_overlapping_range(
    eos_r: ChannelRange, g_ranges: list[ChannelRange]
) -> ChannelRange | None:
    best: ChannelRange | None = None
    best_overlap = 0
    for g_r in g_ranges:
        overlap = (
            min(eos_r.value_max, g_r.value_max)
            - max(eos_r.value_min, g_r.value_min)
            + 1
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best = g_r
    return best


def _enrich_ranges(
    eos_ch: ChannelDefinition, g_ch: ChannelDefinition
) -> list[ChannelRange]:
    if not g_ch.ranges:
        return [_clone_range(r) for r in eos_ch.ranges]

    if not eos_ch.ranges or (
        _is_wheel_channel(eos_ch) and len(eos_ch.ranges) <= 1 and len(g_ch.ranges) > 1
    ):
        return [
            _clone_range(
                g_r,
                eos_ch.channel_type
                if g_r.channel_type is ChannelType.GENERIC
                else g_r.channel_type,
            )
            for g_r in g_ch.ranges
        ]

    enriched: list[ChannelRange] = []
    for eos_r in eos_ch.ranges:
        cloned = _clone_range(eos_r)
        match_r = _best_overlapping_range(eos_r, g_ch.ranges)
        if match_r is not None:
            if not cloned.gobo_id and match_r.gobo_id:
                cloned.gobo_id = match_r.gobo_id
            if not cloned.description and match_r.description:
                cloned.description = match_r.description
            if cloned.snap_value is None and match_r.snap_value is not None:
                cloned.snap_value = max(
                    cloned.value_min, min(cloned.value_max, match_r.snap_value)
                )
            if cloned.physical_min is None and match_r.physical_min is not None:
                cloned.physical_min = match_r.physical_min
            if cloned.physical_max is None and match_r.physical_max is not None:
                cloned.physical_max = match_r.physical_max
            if not cloned.physical_unit and match_r.physical_unit:
                cloned.physical_unit = match_r.physical_unit
        enriched.append(cloned)
    return enriched


def enrich_fixture_from_gdtf(
    eos_fdef: FixtureDefinition,
    gdtf_def: FixtureDefinition,
    gdtf_mode: DmxModeDefinition,
) -> FixtureDefinition:
    """Return a new FixtureDefinition with Eos DMX layout enriched from GDTF."""
    gdtf_by_offset = {int(ch.offset): ch for ch in gdtf_mode.channel_defs}

    new_modes: list[DmxModeDefinition] = []
    for mode in eos_fdef.dmx_modes:
        new_channels: list[ChannelDefinition] = []
        for eos_ch in mode.channel_defs:
            g_ch = gdtf_by_offset.get(int(eos_ch.offset))
            if g_ch is None:
                new_channels.append(
                    ChannelDefinition(
                        channel_type=eos_ch.channel_type,
                        offset=eos_ch.offset,
                        label=eos_ch.label,
                        default_value=eos_ch.default_value,
                        highlight_value=eos_ch.highlight_value,
                        fine_offset=eos_ch.fine_offset,
                        ultra_fine_offset=eos_ch.ultra_fine_offset,
                        ranges=[_clone_range(r) for r in eos_ch.ranges],
                        physical_min=eos_ch.physical_min,
                        physical_max=eos_ch.physical_max,
                        physical_unit=eos_ch.physical_unit,
                        merge_mode=eos_ch.merge_mode,
                    )
                )
                continue

            highlight = (
                eos_ch.highlight_value
                if eos_ch.highlight_value is not None
                else g_ch.highlight_value
            )
            phys_min = eos_ch.physical_min
            phys_max = eos_ch.physical_max
            phys_unit = eos_ch.physical_unit
            if (phys_min, phys_max, phys_unit) == (0.0, 1.0, "") and (
                g_ch.physical_min,
                g_ch.physical_max,
            ) != (0.0, 1.0):
                phys_min = g_ch.physical_min
                phys_max = g_ch.physical_max
                phys_unit = g_ch.physical_unit

            new_channels.append(
                ChannelDefinition(
                    channel_type=eos_ch.channel_type,
                    offset=eos_ch.offset,
                    label=eos_ch.label,
                    default_value=eos_ch.default_value,
                    highlight_value=highlight,
                    fine_offset=eos_ch.fine_offset,
                    ultra_fine_offset=eos_ch.ultra_fine_offset,
                    ranges=_enrich_ranges(eos_ch, g_ch),
                    physical_min=phys_min,
                    physical_max=phys_max,
                    physical_unit=phys_unit,
                    merge_mode=eos_ch.merge_mode,
                )
            )
        new_modes.append(
            DmxModeDefinition(
                name=mode.name,
                channel_defs=new_channels,
                description=mode.description,
            )
        )

    return FixtureDefinition(
        manufacturer=eos_fdef.manufacturer,
        model=eos_fdef.model,
        fixture_type=eos_fdef.fixture_type,
        dmx_modes=new_modes,
        color_profile=(
            eos_fdef.color_profile
            if eos_fdef.color_profile is not None
            else gdtf_def.color_profile
        ),
        gdtf_id=eos_fdef.gdtf_id or gdtf_def.gdtf_id,
        thumbnail=(
            eos_fdef.thumbnail if eos_fdef.thumbnail is not None else gdtf_def.thumbnail
        ),
        notes=eos_fdef.notes,
        is_builtin=eos_fdef.is_builtin,
    )

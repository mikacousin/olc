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
"""Match Eos ASCII personalities against local GDTF fixtures with DMX validation."""

from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
)
from olc.files.ascii.eos_devices import build_fixture_definition, is_dimmer_personality

_FILLER_TOKENS: frozenset[str] = frozenset(
    {
        "lighting",
        "stage",
        "pro",
        "professional",
        "robin",
        "mac",
        "series",
        "led",
        "inc",
        "gmbh",
        "ltd",
    }
)

_CRITICAL_TYPES: frozenset[ChannelType] = frozenset(
    {ChannelType.INTENSITY, ChannelType.PAN, ChannelType.TILT}
)

_SECONDARY_OPTICAL_TYPES: frozenset[ChannelType] = frozenset(
    {
        ChannelType.ZOOM,
        ChannelType.FOCUS,
        ChannelType.IRIS,
        ChannelType.FROST,
        ChannelType.STROBE,
        ChannelType.PRISM,
        ChannelType.COLOR_WHEEL,
        ChannelType.COLOR_TEMP,
    }
)

_AUXILIARY_TYPES: frozenset[ChannelType] = frozenset(
    {ChannelType.GENERIC, ChannelType.MACRO, ChannelType.RESET}
)

_BOUNDS_CHECK_TYPES: frozenset[ChannelType] = frozenset(
    {ChannelType.PAN, ChannelType.TILT, ChannelType.ZOOM}
)

_NORM_SEP_RE = re.compile(r"[-_/.]+")
_WS_RE = re.compile(r"\s+")


class MatchStatus(str, Enum):
    """Coherence verdict between an Eos personality and a local GDTF mode."""

    COMPATIBLE = "compatible"
    WARNING = "warning"
    INCOMPATIBLE = "incompatible"
    NO_CANDIDATE = "no_candidate"


_STATUS_RANK: dict[MatchStatus, int] = {
    MatchStatus.COMPATIBLE: 3,
    MatchStatus.WARNING: 2,
    MatchStatus.INCOMPATIBLE: 1,
    MatchStatus.NO_CANDIDATE: 0,
}


@dataclass(frozen=True)
class ChannelIssue:
    """Single channel-level discrepancy or note detected during validation."""

    offset: int
    eos_desc: str
    gdtf_desc: str
    severity: Literal["error", "warning", "info"]
    reason: str

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize issue to a JSON-friendly dictionary."""
        return {
            "offset": self.offset,
            "eos_desc": self.eos_desc,
            "gdtf_desc": self.gdtf_desc,
            "severity": self.severity,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GdtfMatchResult:
    """Full matching and DMX coherence result for one Eos $Personality."""

    pers_id: int
    eos_manufacturer: str
    eos_model: str
    eos_footprint: int
    status: MatchStatus
    score: float
    gdtf_definition: FixtureDefinition | None
    gdtf_mode: DmxModeDefinition | None
    gobo_count: int
    issues: tuple[ChannelIssue, ...]
    offset_channel_map: dict[int, ChannelDefinition]

    def to_summary_dict(self) -> dict[str, typing.Any]:
        """Serialize a lightweight summary for UI presentation and persistence."""
        return {
            "pers_id": self.pers_id,
            "eos_manufacturer": self.eos_manufacturer,
            "eos_model": self.eos_model,
            "eos_footprint": self.eos_footprint,
            "status": self.status.value,
            "score": round(self.score, 4),
            "gdtf_manufacturer": (
                self.gdtf_definition.manufacturer if self.gdtf_definition else ""
            ),
            "gdtf_model": (self.gdtf_definition.model if self.gdtf_definition else ""),
            "gdtf_mode": self.gdtf_mode.name if self.gdtf_mode else "",
            "gobo_count": self.gobo_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _normalize_tokens(name: str) -> list[str]:
    """Normalize a manufacturer or model name into meaningful lowercase tokens."""
    cleaned = _NORM_SEP_RE.sub(" ", str(name).strip().lower())
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return []
    tokens = [tok for tok in cleaned.split(" ") if tok and tok not in _FILLER_TOKENS]
    if not tokens:
        return [tok for tok in cleaned.split(" ") if tok]
    return tokens


def _normalize_str(name: str) -> str:
    return " ".join(_normalize_tokens(name))


def _manufacturers_compatible(eos_mfr: str, gdtf_mfr: str) -> bool:
    """Return True if manufacturer names match (exact, normalized, or substring)."""
    e_low = eos_mfr.strip().lower()
    g_low = gdtf_mfr.strip().lower()
    if not e_low or not g_low or e_low == "generic" or g_low == "generic":
        return True
    if e_low == g_low:
        return True
    e_norm = _normalize_str(eos_mfr)
    g_norm = _normalize_str(gdtf_mfr)
    if not e_norm or not g_norm:
        return True
    if e_norm == g_norm:
        return True
    return e_norm in g_norm or g_norm in e_norm


def _model_token_overlap(eos_model: str, gdtf_model: str) -> float:
    """Compute max of Jaccard and containment overlap between normalized tokens."""
    e_tokens = set(_normalize_tokens(eos_model))
    g_tokens = set(_normalize_tokens(gdtf_model))
    if not e_tokens or not g_tokens:
        return 0.0
    inter = len(e_tokens & g_tokens)
    if inter == 0:
        return 0.0
    jaccard = inter / len(e_tokens | g_tokens)
    contain = inter / min(len(e_tokens), len(g_tokens))
    return (
        max(jaccard, contain) if len(e_tokens) >= 2 or len(g_tokens) >= 2 else jaccard
    )


def _find_candidate_definitions(
    eos_mfr: str,
    eos_model: str,
    library: FixtureLibrary | None,
) -> list[FixtureDefinition]:
    """Find non-builtin candidate FixtureDefinitions ordered by name similarity."""
    if library is None:
        return []
    candidates = [d for d in library.all() if not getattr(d, "is_builtin", False)]
    if not candidates:
        return []

    e_mfr_low = eos_mfr.strip().lower()
    e_mod_low = eos_model.strip().lower()
    e_mfr_norm = _normalize_str(eos_mfr)
    e_mod_norm = _normalize_str(eos_model)

    tier1: list[FixtureDefinition] = []
    tier2: list[FixtureDefinition] = []
    tier3: list[tuple[float, FixtureDefinition]] = []

    for fdef in candidates:
        g_mfr_low = fdef.manufacturer.strip().lower()
        g_mod_low = fdef.model.strip().lower()
        if e_mfr_low == g_mfr_low and e_mod_low == g_mod_low:
            tier1.append(fdef)
            continue

        if _manufacturers_compatible(eos_mfr, fdef.manufacturer):
            g_mod_norm = _normalize_str(fdef.model)
            g_mfr_norm = _normalize_str(fdef.manufacturer)
            if e_mfr_norm == g_mfr_norm and e_mod_norm == g_mod_norm:
                tier2.append(fdef)
                continue
            if e_mod_norm and e_mod_norm == g_mod_norm:
                tier2.append(fdef)
                continue
            overlap = _model_token_overlap(eos_model, fdef.model)
            if overlap >= 0.75:
                tier3.append((overlap, fdef))

    tier3.sort(key=lambda item: item[0], reverse=True)
    return tier1 + tier2 + [d for _, d in tier3]


def _is_eos_gobo_wheel(ctype: ChannelType, label: str) -> bool:
    return ctype is ChannelType.GOBO_WHEEL or label.strip().lower() == "gobo_select_2"


def _is_gdtf_gobo_wheel(ch: ChannelDefinition) -> bool:
    if ch.channel_type is not ChannelType.GOBO_WHEEL:
        return False
    low = ch.label.strip().lower()
    return not any(
        kw in low for kw in ("spin", "shake", "index", "rot", "audio", "random")
    )


def _count_custom_gobos(mode: DmxModeDefinition) -> int:
    """Count distinct non-builtin gobo_id values in *mode*."""
    ids: set[str] = set()
    for ch in mode.channel_defs:
        for r in ch.ranges:
            gid = str(getattr(r, "gobo_id", "") or "").strip()
            if gid and not gid.startswith("builtin:"):
                ids.add(gid)
    return len(ids)


def validate_eos_vs_gdtf_mode(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    pers_id: int,
    eos_fdef_dict: dict[str, typing.Any],
    gdtf_def: FixtureDefinition,
    gdtf_mode: DmxModeDefinition,
) -> GdtfMatchResult:
    """Validate DMX offset-by-offset coherence between Eos and a GDTF mode."""
    eos_mfr = str(eos_fdef_dict.get("manufacturer", "Generic"))
    eos_model = str(eos_fdef_dict.get("model", f"Personality {pers_id}"))
    eos_mode_dict = eos_fdef_dict["dmx_modes"][0]
    eos_cdefs: list[dict[str, typing.Any]] = eos_mode_dict["channel_defs"]

    eos_offsets: list[int] = []
    for cd in eos_cdefs:
        eos_offsets.append(int(cd["offset"]))
        if cd.get("fine_offset") is not None:
            eos_offsets.append(int(cd["fine_offset"]))
    eos_footprint = (max(eos_offsets) + 1) if eos_offsets else 0
    gdtf_footprint = gdtf_mode.footprint()
    gobo_count = _count_custom_gobos(gdtf_mode)

    if gdtf_footprint != eos_footprint:
        return GdtfMatchResult(
            pers_id=pers_id,
            eos_manufacturer=eos_mfr,
            eos_model=eos_model,
            eos_footprint=eos_footprint,
            status=MatchStatus.INCOMPATIBLE,
            score=0.0,
            gdtf_definition=gdtf_def,
            gdtf_mode=gdtf_mode,
            gobo_count=gobo_count,
            issues=(
                ChannelIssue(
                    offset=0,
                    eos_desc=f"{eos_footprint}ch",
                    gdtf_desc=f"{gdtf_footprint}ch",
                    severity="error",
                    reason=(
                        f"Footprint mismatch: Eos={eos_footprint}ch vs "
                        f"GDTF={gdtf_footprint}ch"
                    ),
                ),
            ),
            offset_channel_map={},
        )

    gdtf_by_offset: dict[int, ChannelDefinition] = {}
    gdtf_fine_by_offset: dict[int, ChannelDefinition] = {}
    for ch in gdtf_mode.channel_defs:
        gdtf_by_offset[int(ch.offset)] = ch
        if ch.fine_offset is not None:
            gdtf_fine_by_offset[int(ch.fine_offset)] = ch
        if ch.ultra_fine_offset is not None:
            gdtf_fine_by_offset[int(ch.ultra_fine_offset)] = ch

    issues: list[ChannelIssue] = []
    matched_points = 0.0

    for cd in eos_cdefs:
        off = int(cd["offset"])
        eos_ctype = ChannelType(cd["channel_type"])
        eos_lbl = str(cd.get("label", eos_ctype.value))
        eos_fine = cd.get("fine_offset")
        eos_desc = f"{eos_lbl} ({eos_ctype.value})"

        g_ch = gdtf_by_offset.get(off)
        if g_ch is None:
            if off in gdtf_fine_by_offset:
                parent = gdtf_fine_by_offset[off]
                g_desc = f"{parent.label}_fine ({parent.channel_type.value})"
            else:
                g_desc = "<unmapped>"
            sev: Literal["error", "warning", "info"] = (
                "error"
                if (
                    eos_ctype in _CRITICAL_TYPES
                    or eos_ctype in COLOR_CHANNEL_TYPES
                    or _is_eos_gobo_wheel(eos_ctype, eos_lbl)
                )
                else "warning"
            )
            issues.append(
                ChannelIssue(
                    offset=off,
                    eos_desc=eos_desc,
                    gdtf_desc=g_desc,
                    severity=sev,
                    reason=(
                        f"Offset {off + 1}: Eos {eos_desc} has no coarse "
                        f"GDTF channel ({g_desc})"
                    ),
                )
            )
            continue

        g_ctype = g_ch.channel_type
        g_desc = f"{g_ch.label} ({g_ctype.value})"

        # 1. Critical types: INTENSITY, PAN, TILT
        if eos_ctype in _CRITICAL_TYPES or g_ctype in _CRITICAL_TYPES:
            if eos_ctype is not g_ctype:
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=eos_desc,
                        gdtf_desc=g_desc,
                        severity="error",
                        reason=(
                            f"Offset {off + 1}: critical mismatch "
                            f"Eos={eos_ctype.value} vs GDTF={g_ctype.value}"
                        ),
                    )
                )
                continue
            if eos_fine is not None and g_ch.fine_offset != int(eos_fine):
                g_fine_lbl = (
                    (g_ch.fine_offset + 1) if g_ch.fine_offset is not None else "none"
                )
                issues.append(
                    ChannelIssue(
                        offset=int(eos_fine),
                        eos_desc=f"{eos_lbl}_fine (offset {int(eos_fine) + 1})",
                        gdtf_desc=f"{g_ch.label}_fine (offset {g_fine_lbl})",
                        severity="error",
                        reason=(
                            f"Offset {int(eos_fine) + 1}: 16-bit fine_offset "
                            f"mismatch for {eos_ctype.value}"
                        ),
                    )
                )
                continue
            matched_points += 1.0
        # 2. Color emitters
        elif eos_ctype in COLOR_CHANNEL_TYPES or g_ctype in COLOR_CHANNEL_TYPES:
            if eos_ctype is not g_ctype:
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=eos_desc,
                        gdtf_desc=g_desc,
                        severity="error",
                        reason=(
                            f"Offset {off + 1}: color mismatch "
                            f"Eos={eos_ctype.value} vs GDTF={g_ctype.value}"
                        ),
                    )
                )
                continue
            matched_points += 1.0
        # 3. Gobo wheels (including Eos gobo_select_2)
        elif _is_eos_gobo_wheel(eos_ctype, eos_lbl):
            if not _is_gdtf_gobo_wheel(g_ch):
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=eos_desc,
                        gdtf_desc=g_desc,
                        severity="error",
                        reason=(
                            f"Offset {off + 1}: gobo wheel mismatch "
                            f"Eos={eos_desc} vs GDTF={g_desc}"
                        ),
                    )
                )
                continue
            matched_points += 1.0
        # 4. Secondary optical types
        elif (
            eos_ctype in _SECONDARY_OPTICAL_TYPES or g_ctype in _SECONDARY_OPTICAL_TYPES
        ):
            if eos_ctype is g_ctype:
                matched_points += 1.0
            elif eos_ctype is ChannelType.GENERIC or g_ctype is ChannelType.GENERIC:
                matched_points += 0.75
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=eos_desc,
                        gdtf_desc=g_desc,
                        severity="warning",
                        reason=(
                            f"Offset {off + 1}: Eos={eos_desc} mapped to GDTF={g_desc}"
                        ),
                    )
                )
            else:
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=eos_desc,
                        gdtf_desc=g_desc,
                        severity="error",
                        reason=(
                            f"Offset {off + 1}: optical mismatch "
                            f"Eos={eos_ctype.value} vs GDTF={g_ctype.value}"
                        ),
                    )
                )
                continue
        # 5. Auxiliary / control types
        elif eos_ctype in _AUXILIARY_TYPES or g_ctype in _AUXILIARY_TYPES:
            if eos_ctype is g_ctype:
                matched_points += 1.0
            else:
                matched_points += 0.85
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=eos_desc,
                        gdtf_desc=g_desc,
                        severity="info",
                        reason=(
                            f"Offset {off + 1}: auxiliary "
                            f"Eos={eos_desc} vs GDTF={g_desc}"
                        ),
                    )
                )
        else:
            matched_points += 1.0

        # Physical bounds check (informative warning only)
        if eos_ctype in _BOUNDS_CHECK_TYPES and eos_ctype is g_ctype:
            e_min = float(cd.get("physical_min", 0.0))
            e_max = float(cd.get("physical_max", 1.0))
            g_min = float(g_ch.physical_min)
            g_max = float(g_ch.physical_max)
            if (
                (e_min, e_max) != (0.0, 1.0)
                and (g_min, g_max) != (0.0, 1.0)
                and (abs(e_min - g_min) > 1e-3 or abs(e_max - g_max) > 1e-3)
            ):
                issues.append(
                    ChannelIssue(
                        offset=off,
                        eos_desc=f"{eos_lbl} [{e_min:g}..{e_max:g}]",
                        gdtf_desc=f"{g_ch.label} [{g_min:g}..{g_max:g}]",
                        severity="warning",
                        reason=(
                            f"Offset {off + 1}: physical bounds differ "
                            f"Eos=[{e_min:g}..{e_max:g}] vs GDTF=[{g_min:g}..{g_max:g}]"
                        ),
                    )
                )

    has_error = any(i.severity == "error" for i in issues)
    has_warning = any(i.severity == "warning" for i in issues)
    if has_error:
        status = MatchStatus.INCOMPATIBLE
    elif has_warning:
        status = MatchStatus.WARNING
    else:
        status = MatchStatus.COMPATIBLE

    denom = max(1, len(eos_cdefs))
    score = max(0.0, min(1.0, matched_points / denom))
    if has_warning and not has_error:
        score = max(0.0, score - 0.05)

    return GdtfMatchResult(
        pers_id=pers_id,
        eos_manufacturer=eos_mfr,
        eos_model=eos_model,
        eos_footprint=eos_footprint,
        status=status,
        score=score,
        gdtf_definition=gdtf_def,
        gdtf_mode=gdtf_mode,
        gobo_count=gobo_count,
        issues=tuple(issues),
        offset_channel_map=gdtf_by_offset,
    )


def match_eos_personality(
    pers_id: int,
    pers: dict[str, typing.Any],
    param_types: dict[int, str],
    fixture_library: FixtureLibrary | None,
) -> GdtfMatchResult | None:
    """Find and validate the best matching local GDTF mode for one Eos personality."""
    if is_dimmer_personality(pers, param_types):
        return None
    eos_fdef_dict = build_fixture_definition(pers_id, pers, param_types)
    if eos_fdef_dict is None:
        return None

    eos_mfr = str(eos_fdef_dict.get("manufacturer", "Generic"))
    eos_model = str(eos_fdef_dict.get("model", f"Personality {pers_id}"))
    eos_fp = int(pers.get("footprint", 1))
    candidates = _find_candidate_definitions(eos_mfr, eos_model, fixture_library)

    if not candidates:
        return GdtfMatchResult(
            pers_id=pers_id,
            eos_manufacturer=eos_mfr,
            eos_model=eos_model,
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
            eos_manufacturer=eos_mfr,
            eos_model=eos_model,
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


def match_eos_personalities(
    personalities: dict[int, dict[str, typing.Any]],
    param_types: dict[int, str],
    fixture_library: FixtureLibrary | None,
) -> dict[int, GdtfMatchResult]:
    """Match all non-dimmer Eos personalities against *fixture_library*."""
    results: dict[int, GdtfMatchResult] = {}
    for pers_id, pers in personalities.items():
        res = match_eos_personality(pers_id, pers, param_types, fixture_library)
        if res is not None:
            results[pers_id] = res
    return results

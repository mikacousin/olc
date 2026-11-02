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
"""Toolkit-independent logic behind the console-style color picker.

Nothing here imports GTK, so everything can be unit tested headless.
"""

from __future__ import annotations

from olc.devices.color import (
    SOLVER_STRATEGIES,
    CIExyY,
    ColorMatcher,
    EmitterProfile,
    FixtureColorProfile,
    MatchResult,
    delta_e76,
    sRGB,
)

from .conversions import (
    DUV_MAX,
    DUV_MIN,
    KELVIN_MAX,
    KELVIN_MIN,
    PRESETS,
    RGB,
    XY,
    hs_to_rgb,
    kelvin_duv_to_xy,
    kelvin_to_srgb,
    kelvin_to_uv,
    kelvin_to_xy,
    parse_hex,
    planckian_locus_xy,
    rgb_to_hex,
    rgb_to_hs,
    srgb_to_xy,
    to_8bit,
    to_24bit,
    uv_to_xy,
    xy_max_luminance,
    xy_to_srgb,
    xy_to_uv,
)
from .gels import (
    GEL_LIBRARY,
    GelSwatch,
    classify_match,
    evaluate_gel_for_profile,
    filter_gels,
    find_gel,
)
from .geometry import (
    CIE_X_MAX,
    CIE_Y_MAX,
    SPECTRAL_LOCUS_XY,
    clamp_xy_to_locus,
    convex_hull_2d,
    device_emitters_xy,
    device_gamut_hs,
    device_gamut_xy,
    effective_color_profile,
    point_in_polygon,
    profile_gamut_hs,
    profile_gamut_xy,
    render_cie_xy_diagram,
    render_hs_disc,
)
from .solver import (
    WHEEL_SLOT_COLORS,
    ColorApplyResult,
    ColorSolver,
    Throttle,
    apply_color_cie_to_devices,
    apply_color_to_devices,
    compute_color_fan,
    extract_color_wheel_slots,
    fan_colors_to_devices,
    profile_signature,
    shift_color_hs,
    snap_device_color_wheel,
)

__all__ = [
    # Color science re-exports
    "CIExyY",
    "ColorMatcher",
    "EmitterProfile",
    "FixtureColorProfile",
    "MatchResult",
    "SOLVER_STRATEGIES",
    "delta_e76",
    "sRGB",
    # Conversions
    "DUV_MAX",
    "DUV_MIN",
    "KELVIN_MAX",
    "KELVIN_MIN",
    "PRESETS",
    "RGB",
    "XY",
    "hs_to_rgb",
    "kelvin_duv_to_xy",
    "kelvin_to_srgb",
    "kelvin_to_uv",
    "kelvin_to_xy",
    "parse_hex",
    "planckian_locus_xy",
    "rgb_to_hex",
    "rgb_to_hs",
    "srgb_to_xy",
    "to_8bit",
    "to_24bit",
    "uv_to_xy",
    "xy_max_luminance",
    "xy_to_srgb",
    "xy_to_uv",
    # Geometry
    "CIE_X_MAX",
    "CIE_Y_MAX",
    "SPECTRAL_LOCUS_XY",
    "clamp_xy_to_locus",
    "convex_hull_2d",
    "device_emitters_xy",
    "device_gamut_hs",
    "device_gamut_xy",
    "effective_color_profile",
    "point_in_polygon",
    "profile_gamut_hs",
    "profile_gamut_xy",
    "render_cie_xy_diagram",
    "render_hs_disc",
    # Gels
    "GEL_LIBRARY",
    "GelSwatch",
    "classify_match",
    "evaluate_gel_for_profile",
    "filter_gels",
    "find_gel",
    # Solver & Tools
    "ColorApplyResult",
    "ColorSolver",
    "Throttle",
    "WHEEL_SLOT_COLORS",
    "apply_color_cie_to_devices",
    "apply_color_to_devices",
    "compute_color_fan",
    "extract_color_wheel_slots",
    "fan_colors_to_devices",
    "profile_signature",
    "shift_color_hs",
    "snap_device_color_wheel",
]

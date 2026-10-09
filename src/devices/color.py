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
"""Color science module.

Provides CIE xyY, XYZ, sRGB spaces, emitter profiles, and NNLS matching.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class CIExyY:
    """CIE xy chromaticity coordinates and relative luminance Y (0.0 to 100.0)."""

    x: float
    y: float
    Y: float = 100.0  # pylint: disable=invalid-name

    def to_XYZ(self) -> CIEXYZ:  # pylint: disable=invalid-name
        """Convert CIE xyY to CIE XYZ space."""
        if self.y == 0.0:
            return CIEXYZ(0.0, 0.0, 0.0)
        big_x = (self.x / self.y) * self.Y
        big_z = ((1.0 - self.x - self.y) / self.y) * self.Y
        return CIEXYZ(big_x, self.Y, big_z)

    def __repr__(self) -> str:
        return f"CIExyY(x={self.x:.4f}, y={self.y:.4f}, Y={self.Y:.2f})"


@dataclass
class CIEXYZ:
    """CIE 1931 XYZ color space with D65 reference illuminant."""

    X: float  # pylint: disable=invalid-name
    Y: float  # pylint: disable=invalid-name
    Z: float  # pylint: disable=invalid-name

    def to_xyY(self) -> CIExyY:  # pylint: disable=invalid-name
        """Convert CIE XYZ to CIE xyY chromaticity."""
        total = self.X + self.Y + self.Z
        if total == 0.0:
            return CIExyY(0.3127, 0.3290, 0.0)
        return CIExyY(self.X / total, self.Y / total, self.Y)

    def to_srgb(self) -> sRGB:  # pylint: disable=invalid-name
        """Convert CIE XYZ (Y=100 for reference white) to sRGB with gamma 2.2."""
        xn, yn, zn = self.X / 100.0, self.Y / 100.0, self.Z / 100.0
        r_lin = 3.2406 * xn - 1.5372 * yn - 0.4986 * zn
        g_lin = -0.9689 * xn + 1.8758 * yn + 0.0415 * zn
        b_lin = 0.0557 * xn - 0.2040 * yn + 1.0570 * zn

        def gamma(v: float) -> float:
            v_clamped = max(0.0, min(1.0, v))
            if v_clamped <= 0.0031308:
                return 12.92 * v_clamped
            return 1.055 * (v_clamped ** (1.0 / 2.4)) - 0.055

        return sRGB(gamma(r_lin), gamma(g_lin), gamma(b_lin))

    def to_sRGB(self) -> sRGB:  # pylint: disable=invalid-name
        """Alias for to_srgb()."""
        return self.to_srgb()

    def as_array(self) -> np.ndarray:
        """Return [X, Y, Z] as a 1D NumPy array."""
        return np.array([self.X, self.Y, self.Z], dtype=np.float64)

    def __repr__(self) -> str:
        return f"CIEXYZ(X={self.X:.3f}, Y={self.Y:.3f}, Z={self.Z:.3f})"


@dataclass
class sRGB:  # pylint: disable=invalid-name
    """sRGB color with components normalized in [0.0, 1.0]."""

    r: float
    g: float
    b: float

    @classmethod
    def from_255(cls, r: int, g: int, b: int) -> sRGB:
        """Create sRGB instance from [0..255] byte components."""
        return cls(r / 255.0, g / 255.0, b / 255.0)

    @classmethod
    def from_hex(cls, hex_str: str) -> sRGB:
        """Create sRGB instance from HTML hex string (#RRGGBB or RRGGBB)."""
        clean = hex_str.lstrip("#")
        if len(clean) != 6:
            raise ValueError(f"Invalid hex color string: '{hex_str}'")
        r = int(clean[0:2], 16)
        g = int(clean[2:4], 16)
        b = int(clean[4:6], 16)
        return cls.from_255(r, g, b)

    def to_255(self) -> tuple[int, int, int]:
        """Convert to (R, G, B) tuple of bytes [0..255]."""
        return (
            round(max(0.0, min(1.0, self.r)) * 255),
            round(max(0.0, min(1.0, self.g)) * 255),
            round(max(0.0, min(1.0, self.b)) * 255),
        )

    def to_XYZ(self) -> CIEXYZ:  # pylint: disable=invalid-name
        """Linearize sRGB and convert to CIE XYZ space."""

        def linear(v: float) -> float:
            v_clamped = max(0.0, min(1.0, v))
            if v_clamped <= 0.04045:
                return v_clamped / 12.92
            return ((v_clamped + 0.055) / 1.055) ** 2.4

        rl, gl, bl = linear(self.r), linear(self.g), linear(self.b)
        return CIEXYZ(
            X=(0.4124 * rl + 0.3576 * gl + 0.1805 * bl) * 100.0,
            Y=(0.2126 * rl + 0.7152 * gl + 0.0722 * bl) * 100.0,
            Z=(0.0193 * rl + 0.1192 * gl + 0.9505 * bl) * 100.0,
        )

    def hex(self) -> str:
        """Return HTML hex string (#RRGGBB)."""
        r, g, b = self.to_255()
        return f"#{r:02X}{g:02X}{b:02X}"

    def to_hex(self) -> str:
        """Return HTML hex string (#RRGGBB)."""
        return self.hex()

    def __repr__(self) -> str:
        r, g, b = self.to_255()
        return f"sRGB({r}, {g}, {b}) {self.hex()}"


@dataclass
class EmitterProfile:
    """Colorimetric profile of an individual LED emitter."""

    name: str
    cie: CIExyY
    dominant_wavelength: float = 0.0
    diode_part: str = ""
    gdtf_attribute: str = ""

    @property
    def xyz(self) -> CIEXYZ:
        """CIE XYZ coordinates of this emitter at full power."""
        return self.cie.to_XYZ()

    @property
    def srgb(self) -> sRGB:
        """Approximate sRGB color of this emitter."""
        return self.xyz.to_srgb()

    def __repr__(self) -> str:
        wl = f" λ={self.dominant_wavelength:.0f}nm" if self.dominant_wavelength else ""
        return f"<Emitter '{self.name}' {self.cie}{wl} ≈{self.srgb.hex()}>"


@dataclass
class FixtureColorProfile:
    """Complete colorimetric profile of a multi-emitter LED fixture."""

    fixture_name: str
    emitters: list[EmitterProfile] = field(default_factory=list)
    white_point: CIExyY = field(default_factory=lambda: CIExyY(0.3127, 0.3290, 100.0))
    color_space_mode: str = "sRGB"

    def get_emitter(self, name: str) -> Optional[EmitterProfile]:
        """Retrieve emitter profile by name (case-insensitive)."""
        name_lower = name.lower()
        for e in self.emitters:
            if e.name.lower() == name_lower:
                return e
        return None

    @property
    def emitter_count(self) -> int:
        """Total number of physical emitters in this fixture."""
        return len(self.emitters)

    @property
    def mixing_matrix(self) -> np.ndarray:
        """Spectral mixing matrix (3 x N) where each column is an emitter's XYZ."""
        return np.column_stack([e.xyz.as_array() for e in self.emitters])

    @property
    def gamut_area(self) -> float:
        """Area of the color gamut triangle in the CIE xy chromaticity diagram."""
        chromatic = [e for e in self.emitters if e.dominant_wavelength > 0.0][:3]
        if len(chromatic) < 3:
            return 0.0
        (x1, y1), (x2, y2), (x3, y3) = [(e.cie.x, e.cie.y) for e in chromatic]
        return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0

    def __repr__(self) -> str:
        names = ", ".join(e.name for e in self.emitters)
        return (
            f"<FixtureColorProfile '{self.fixture_name}' "
            f"[{names}] gamut={self.gamut_area:.4f}>"
        )


def extract_color_profile(
    gdtf_fixture: Any,  # noqa: ANN401
    fixture_name: str = "",
) -> FixtureColorProfile:
    """Extract a FixtureColorProfile from a pygdtf.FixtureType instance."""
    name = fixture_name or (
        f"{getattr(gdtf_fixture, 'manufacturer', '')} "
        f"{getattr(gdtf_fixture, 'name', '')}".strip()
    )

    emitters: list[EmitterProfile] = []
    gdtf_emitters = getattr(gdtf_fixture, "emitters", [])
    for e in gdtf_emitters:
        color = getattr(e, "color", None)
        if color is None:
            continue
        emitters.append(
            EmitterProfile(
                name=getattr(e, "name", "") or "",
                cie=CIExyY(
                    x=getattr(color, "x", 0.0),
                    y=getattr(color, "y", 0.0),
                    Y=getattr(color, "Y", 100.0),
                ),
                dominant_wavelength=getattr(e, "dominant_wave_length", 0.0) or 0.0,
                diode_part=getattr(e, "diode_part", "") or "",
            )
        )

    if not emitters:
        raise ValueError(
            f"No emitters found in '{name}'. Ensure GDTF has an <Emitters> section."
        )

    cs = getattr(gdtf_fixture, "color_space", None)
    mode = (
        str(getattr(cs, "mode", "sRGB")) if cs and getattr(cs, "mode", None) else "sRGB"
    )
    wp = (
        CIExyY(cs.white_point.x, cs.white_point.y, cs.white_point.Y)
        if mode == "Custom" and hasattr(cs, "white_point") and cs.white_point
        else CIExyY(0.3127, 0.3290, 100.0)
    )

    return FixtureColorProfile(
        fixture_name=name,
        emitters=emitters,
        white_point=wp,
        color_space_mode=mode,
    )


def profile_from_emitters(
    name: str,
    emitters: list[tuple[str, float, float, float, float]],
) -> FixtureColorProfile:
    """Build a FixtureColorProfile manually without a GDTF file.

    emitters: list of (name, x, y, Y, dominant_wavelength_nm)
    """
    return FixtureColorProfile(
        fixture_name=name,
        emitters=[
            EmitterProfile(name=n, cie=CIExyY(x, y, Y), dominant_wavelength=wl)
            for n, x, y, Y, wl in emitters
        ],
    )


@dataclass
class MatchResult:
    """Result of color matching optimization for a fixture."""

    fixture_name: str
    emitter_names: list[str]
    coefficients: list[float]
    dmx_values: list[int]
    achieved_xyz: CIEXYZ
    delta_e: float
    warning: str = ""

    def as_dict(self) -> dict[str, int]:
        """Return {emitter_name: dmx_value} mapping ready to apply."""
        return dict(zip(self.emitter_names, self.dmx_values, strict=False))

    def __repr__(self) -> str:
        pairs = " ".join(
            f"{n}={d}"
            for n, d in zip(self.emitter_names, self.dmx_values, strict=False)
        )
        warn = f" ⚠ {self.warning}" if self.warning else ""
        return (
            f"<MatchResult '{self.fixture_name}' ΔE={self.delta_e:.2f} [{pairs}]{warn}>"
        )


class ColorMatcher:
    """Calculates DMX levels to accurately reproduce target colors across fixtures."""

    def __init__(self, profiles: list[FixtureColorProfile] | None = None) -> None:
        self.profiles: dict[str, FixtureColorProfile] = {}
        for p in profiles or []:
            self.add_profile(p)

    def add_profile(self, profile: FixtureColorProfile) -> None:
        """Register a fixture color profile."""
        self.profiles[profile.fixture_name] = profile

    def match_srgb(self, r: int, g: int, b: int) -> dict[str, MatchResult]:
        """Calculate DMX outputs to match sRGB(r, g, b) on all registered fixtures."""
        target = sRGB.from_255(r, g, b).to_XYZ()
        return {name: self._solve(p, target) for name, p in self.profiles.items()}

    def match_cie(
        self,
        x: float,
        y: float,
        Y: float = 100.0,  # pylint: disable=invalid-name
    ) -> dict[str, MatchResult]:
        """Calculate DMX outputs to match CIE xyY on all registered fixtures."""
        target = CIExyY(x, y, Y).to_XYZ()
        return {name: self._solve(p, target) for name, p in self.profiles.items()}

    def match_hex(self, hex_color: str) -> dict[str, MatchResult]:
        """Calculate DMX outputs to match an HTML hex color string (#RRGGBB)."""
        clean_hex = hex_color.lstrip("#")
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
        return self.match_srgb(r, g, b)

    def _solve(self, profile: FixtureColorProfile, target: CIEXYZ) -> MatchResult:
        mat_m = profile.mixing_matrix  # (3, N)
        target_vec = target.as_array()  # (3,)

        try:
            from scipy.optimize import nnls  # pylint: disable=import-outside-toplevel

            coeffs, _ = nnls(mat_m, target_vec)
        except ImportError:
            coeffs, *_ = np.linalg.lstsq(mat_m, target_vec, rcond=None)
            coeffs = np.clip(coeffs, 0.0, None)

        warning = ""
        max_c = float(coeffs.max()) if len(coeffs) > 0 else 0.0
        if max_c > 1.0:
            coeffs = coeffs / max_c
            warning = "out of gamut — brightness reduced"

        achieved = mat_m @ coeffs
        achieved_xyz = CIEXYZ(
            float(achieved[0]), float(achieved[1]), float(achieved[2])
        )

        return MatchResult(
            fixture_name=profile.fixture_name,
            emitter_names=[e.name for e in profile.emitters],
            coefficients=[round(float(c) * 100.0, 1) for c in coeffs],
            dmx_values=[round(float(c) * 255.0) for c in coeffs],
            achieved_xyz=achieved_xyz,
            delta_e=self._delta_e(target, achieved_xyz),
            warning=warning,
        )

    @staticmethod
    def _xyz_to_lab(xyz: CIEXYZ) -> tuple[float, float, float]:
        return xyz_to_lab(xyz)

    def _delta_e(self, xyz1: CIEXYZ, xyz2: CIEXYZ) -> float:
        return delta_e76(xyz1, xyz2)


def xyz_to_lab(xyz: CIEXYZ) -> tuple[float, float, float]:
    """Convert CIE XYZ to CIE L*a*b* coordinates."""
    xn, yn, zn = 95.047, 100.0, 108.883

    def func_t(t: float) -> float:
        if t > 0.008856:
            return t ** (1.0 / 3.0)
        return 7.787 * t + 16.0 / 116.0

    fx = func_t(xyz.X / xn)
    fy = func_t(xyz.Y / yn)
    fz = func_t(xyz.Z / zn)
    lab_l = 116.0 * fy - 16.0
    lab_a = 500.0 * (fx - fy)
    lab_b = 200.0 * (fy - fz)
    return lab_l, lab_a, lab_b


def delta_e76(xyz1: CIEXYZ, xyz2: CIEXYZ) -> float:
    """Calculate CIE 1976 color difference (ΔE*76) between two XYZ colors."""
    l1, a1, b1 = xyz_to_lab(xyz1)
    l2, a2, b2 = xyz_to_lab(xyz2)
    return math.sqrt((l2 - l1) ** 2 + (a2 - a1) ** 2 + (b2 - b1) ** 2)

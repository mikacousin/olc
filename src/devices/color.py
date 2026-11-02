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
from typing import Any, Iterable, Optional

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

    def to_dict(self) -> dict[str, float]:
        """Serialize CIE xyY coordinates to dictionary."""
        return {"x": float(self.x), "y": float(self.y), "Y": float(self.Y)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CIExyY:
        """Deserialize CIE xyY coordinates from dictionary."""
        return cls(
            x=float(data.get("x", 0.3127)),
            y=float(data.get("y", 0.3290)),
            Y=float(data.get("Y", 100.0)),
        )

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

    def to_dict(self) -> dict[str, Any]:
        """Serialize emitter profile to dictionary."""
        return {
            "name": self.name,
            "cie": self.cie.to_dict(),
            "dominant_wavelength": float(self.dominant_wavelength),
            "diode_part": self.diode_part,
            "gdtf_attribute": self.gdtf_attribute,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmitterProfile:
        """Deserialize emitter profile from dictionary."""
        return cls(
            name=str(data.get("name", "")),
            cie=CIExyY.from_dict(data.get("cie", {})),
            dominant_wavelength=float(data.get("dominant_wavelength", 0.0)),
            diode_part=str(data.get("diode_part", "")),
            gdtf_attribute=str(data.get("gdtf_attribute", "")),
        )

    def __repr__(self) -> str:
        wl = f" λ={self.dominant_wavelength:.0f}nm" if self.dominant_wavelength else ""
        return f"<Emitter '{self.name}' {self.cie}{wl} ≈{self.srgb.hex()}>"


def convex_hull_2d(
    points: Iterable[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Monotone chain 2D convex hull in counter-clockwise order."""
    pts = sorted({(round(float(x), 6), round(float(y), 6)) for x, y in points})
    if len(pts) <= 2:
        return list(pts)

    def cross(
        o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
    ) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0.0:
            lower.pop()
        lower.append(p)

    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0.0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


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
    def gamut_polygon(self) -> list[tuple[float, float]]:
        """Convex hull vertices of all chromatic emitters in CIE xy space."""
        pts = [
            (e.cie.x, e.cie.y) for e in self.emitters if e.cie.x > 0.0 or e.cie.y > 0.0
        ]
        return convex_hull_2d(pts)

    @property
    def gamut_area(self) -> float:
        """Area of the color gamut polygon in the CIE xy chromaticity diagram."""
        poly = self.gamut_polygon
        n = len(poly)
        if n < 3:
            return 0.0
        # Shoelace formula (Gauss's area formula)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
        return abs(area) / 2.0

    def contains_xy(self, x: float, y: float, tol: float = 1e-4) -> bool:
        """Return True if (x, y) is inside or on the boundary of the fixture's gamut."""
        poly = self.gamut_polygon
        n = len(poly)
        if n < 3:
            return False
        # Cross product test with each directed edge of the CCW polygon
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            cross = (p2[0] - p1[0]) * (y - p1[1]) - (p2[1] - p1[1]) * (x - p1[0])
            if cross < -tol:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize fixture colorimetric profile to dictionary."""
        return {
            "fixture_name": self.fixture_name,
            "emitters": [e.to_dict() for e in self.emitters],
            "white_point": self.white_point.to_dict(),
            "color_space_mode": self.color_space_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixtureColorProfile:
        """Deserialize fixture colorimetric profile from dictionary."""
        return cls(
            fixture_name=str(data.get("fixture_name", "")),
            emitters=[EmitterProfile.from_dict(ed) for ed in data.get("emitters", [])],
            white_point=CIExyY.from_dict(data.get("white_point", {})),
            color_space_mode=str(data.get("color_space_mode", "sRGB")),
        )

    def __repr__(self) -> str:
        names = ", ".join(e.name for e in self.emitters)
        return (
            f"<FixtureColorProfile '{self.fixture_name}' "
            f"[{names}] gamut={self.gamut_area:.4f}>"
        )


def _extract_colorspace_rgb(cs: Any) -> list[EmitterProfile]:  # noqa: ANN401
    """Build Red, Green, Blue EmitterProfiles from a GDTF ColorSpace."""
    defn = getattr(cs, "definition", None) if cs is not None else None
    r_cie = getattr(defn, "r", None) if defn is not None else None
    g_cie = getattr(defn, "g", None) if defn is not None else None
    b_cie = getattr(defn, "b", None) if defn is not None else None
    w_cie = getattr(defn, "w", None) if defn is not None else None

    if r_cie is not None and g_cie is not None and b_cie is not None:
        w_y = float(getattr(w_cie, "Y", 1.0) or 1.0)
        scale = 100.0 if w_y <= 1.5 else 1.0
        return [
            EmitterProfile(
                name="Red",
                cie=CIExyY(
                    float(getattr(r_cie, "x", 0.64)),
                    float(getattr(r_cie, "y", 0.33)),
                    float(getattr(r_cie, "Y", 0.2126)) * scale,
                ),
                dominant_wavelength=625.0,
                gdtf_attribute="ColorAdd_R",
            ),
            EmitterProfile(
                name="Green",
                cie=CIExyY(
                    float(getattr(g_cie, "x", 0.30)),
                    float(getattr(g_cie, "y", 0.60)),
                    float(getattr(g_cie, "Y", 0.7152)) * scale,
                ),
                dominant_wavelength=525.0,
                gdtf_attribute="ColorAdd_G",
            ),
            EmitterProfile(
                name="Blue",
                cie=CIExyY(
                    float(getattr(b_cie, "x", 0.15)),
                    float(getattr(b_cie, "y", 0.06)),
                    float(getattr(b_cie, "Y", 0.0722)) * scale,
                ),
                dominant_wavelength=465.0,
                gdtf_attribute="ColorAdd_B",
            ),
        ]

    return [
        EmitterProfile(
            "Red", CIExyY(0.6400, 0.3300, 21.26), 625.0, gdtf_attribute="ColorAdd_R"
        ),
        EmitterProfile(
            "Green", CIExyY(0.3000, 0.6000, 71.52), 525.0, gdtf_attribute="ColorAdd_G"
        ),
        EmitterProfile(
            "Blue", CIExyY(0.1500, 0.0600, 7.22), 465.0, gdtf_attribute="ColorAdd_B"
        ),
    ]


def _gdtf_has_rgb_channels(gdtf_fixture: Any) -> bool:  # noqa: ANN401
    """Return True if any DMX mode in the GDTF fixture uses additive R/G/B."""
    rgb_attrs = {
        "ColorAdd_R",
        "ColorAdd_G",
        "ColorAdd_B",
        "ColorRGB_Red",
        "ColorRGB_Green",
        "ColorRGB_Blue",
    }
    for mode in getattr(gdtf_fixture, "dmx_modes", []) or []:
        dmx_chs = getattr(mode, "dmx_channels", None)
        if dmx_chs is not None and hasattr(dmx_chs, "as_dict"):
            for ch in dmx_chs.as_dict():
                if ch.get("attribute") in rgb_attrs:
                    return True
    return False


def extract_color_profile(  # pylint: disable=too-many-locals
    gdtf_fixture: Any,  # noqa: ANN401
    fixture_name: str = "",
) -> FixtureColorProfile:
    """Extract a FixtureColorProfile from a pygdtf.FixtureType instance."""
    name = fixture_name or (
        f"{getattr(gdtf_fixture, 'manufacturer', '')} "
        f"{getattr(gdtf_fixture, 'name', '')}".strip()
    )

    _default_name_to_attr = {
        "red": "ColorAdd_R",
        "green": "ColorAdd_G",
        "blue": "ColorAdd_B",
        "white": "ColorAdd_W",
        "amber": "ColorAdd_A",
        "lime": "ColorAdd_GY",
        "green-yellow": "ColorAdd_GY",
        "cyan": "ColorAdd_C",
        "indigo": "ColorAdd_BC",
        "royal blue": "ColorAdd_BC",
        "blue-cyan": "ColorAdd_BC",
        "magenta": "ColorAdd_M",
        "yellow": "ColorAdd_Y",
        "red-orange": "ColorAdd_RY",
    }

    emitter_to_attr: dict[str, str] = {}
    for dmx_mode in getattr(gdtf_fixture, "dmx_modes", []) or []:
        for ch in getattr(dmx_mode, "dmx_channels", []) or []:
            ch_dict = ch.as_dict() if hasattr(ch, "as_dict") else {}
            for lc in ch_dict.get("logical_channels", []):
                for cf in lc.get("channel_functions", []):
                    attr = cf.get("attribute", "")
                    em_ref = cf.get("emitter")
                    if em_ref and attr:
                        em_ref_name = getattr(em_ref, "name", str(em_ref))
                        emitter_to_attr[em_ref_name.lower()] = attr

    emitters: list[EmitterProfile] = []
    gdtf_emitters = getattr(gdtf_fixture, "emitters", [])
    for e in gdtf_emitters:
        color = getattr(e, "color", None)
        if color is None:
            continue
        em_name = getattr(e, "name", "") or ""
        gdtf_attr = emitter_to_attr.get(em_name.lower()) or _default_name_to_attr.get(
            em_name.lower(), ""
        )
        emitters.append(
            EmitterProfile(
                name=em_name,
                cie=CIExyY(
                    x=getattr(color, "x", 0.0),
                    y=getattr(color, "y", 0.0),
                    Y=getattr(color, "Y", 100.0),
                ),
                dominant_wavelength=getattr(e, "dominant_wave_length", 0.0) or 0.0,
                diode_part=getattr(e, "diode_part", "") or "",
                gdtf_attribute=gdtf_attr,
            )
        )

    cs = getattr(gdtf_fixture, "color_space", None)
    existing_lower = {e.name.lower() for e in emitters}
    has_all_rgb = {"red", "green", "blue"}.issubset(existing_lower)
    if not has_all_rgb and (
        _gdtf_has_rgb_channels(gdtf_fixture) or 0 < len(emitters) < 3
    ):
        cs_rgb = [
            pe
            for pe in _extract_colorspace_rgb(cs)
            if pe.name.lower() not in existing_lower
        ]
        emitters = cs_rgb + emitters

    if not emitters:
        raise ValueError(
            f"No emitters found in '{name}'. Ensure GDTF has an <Emitters> section."
        )

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
class MatchResult:  # pylint: disable=too-many-instance-attributes
    """Result of color matching optimization for a fixture."""

    fixture_name: str
    emitter_names: list[str]
    coefficients: list[float]
    dmx_values: list[int]
    achieved_xyz: CIEXYZ
    delta_e: float
    warning: str = ""
    ratios: list[float] = field(default_factory=list)
    normalized_weights: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.normalized_weights and self.ratios:
            self.normalized_weights = list(self.ratios)
        elif not self.ratios and self.normalized_weights:
            self.ratios = list(self.normalized_weights)

    @property
    def dmx_values_16(self) -> list[int]:
        """Return 16-bit DMX values [0..65535] based on normalized weights."""
        weights = (
            self.normalized_weights
            or self.ratios
            or [d / 255.0 for d in self.dmx_values]
        )
        return [max(0, min(65535, round(w * 65535.0))) for w in weights]

    @property
    def dmx_values_24(self) -> list[int]:
        """Return 24-bit DMX values [0..16777215] based on normalized weights."""
        weights = (
            self.normalized_weights
            or self.ratios
            or [d / 255.0 for d in self.dmx_values]
        )
        return [max(0, min(16777215, round(w * 16777215.0))) for w in weights]

    def as_dict(self) -> dict[str, int]:
        """Return {emitter_name: dmx_value} mapping ready to apply (8-bit)."""
        return dict(zip(self.emitter_names, self.dmx_values, strict=False))

    def as_dict_16(self) -> dict[str, int]:
        """Return {emitter_name: dmx_value_16} mapping ready to apply (16-bit)."""
        return dict(zip(self.emitter_names, self.dmx_values_16, strict=False))

    def as_dict_24(self) -> dict[str, int]:
        """Return {emitter_name: dmx_value_24} mapping ready to apply (24-bit)."""
        return dict(zip(self.emitter_names, self.dmx_values_24, strict=False))

    def as_normalized_dict(self) -> dict[str, float]:
        """Return {emitter_name: ratio} mapping in [0.0, 1.0] float precision."""
        weights = self.normalized_weights or self.ratios
        if weights and len(weights) == len(self.emitter_names):
            return dict(zip(self.emitter_names, weights, strict=False))
        return {
            name: dmx / 255.0
            for name, dmx in zip(self.emitter_names, self.dmx_values, strict=False)
        }

    def __repr__(self) -> str:
        pairs = " ".join(
            f"{n}={d}"
            for n, d in zip(self.emitter_names, self.dmx_values, strict=False)
        )
        warn = f" ⚠ {self.warning}" if self.warning else ""
        return (
            f"<MatchResult '{self.fixture_name}' ΔE={self.delta_e:.2f} [{pairs}]{warn}>"
        )


# Largest NNLS coefficient accepted without an "out of gamut" warning (0.5 %).
GAMUT_WARNING_TOLERANCE = 1.005

SOLVER_STRATEGIES: tuple[str, ...] = ("spectral", "punch", "rgb_only")
_RGB_EMITTER_NAMES = frozenset({"red", "green", "blue"})
_BROADBAND_EMITTER_NAMES = frozenset(
    {
        "white",
        "amber",
        "lime",
        "cyan",
        "warm white",
        "cold white",
        "ww",
        "cw",
        "yellow",
    }
)


def _solve_nled(  # pylint: disable=too-many-locals
    profile: FixtureColorProfile,
    target: CIEXYZ,
    strategy: str = "spectral",
) -> np.ndarray:
    """Solve multi-LED mixing (N >= 4) with strict chromaticity & L2 regularization."""
    n_emitters = len(profile.emitters)
    if n_emitters == 0:
        return np.zeros(0, dtype=float)

    sum_xyz = target.X + target.Y + target.Z
    if sum_xyz < 1e-9 or target.Y < 1e-9:
        return np.zeros(n_emitters, dtype=float)

    mat_m = profile.mixing_matrix  # (3, N)
    x_t = target.X / sum_xyz
    y_t = target.Y / sum_xyz
    y_target = target.Y

    # Chromaticity constraint rows
    # (1 - x_t) * X_i - x_t * Y_i - x_t * Z_i = 0
    # -y_t * X_i + (1 - y_t) * Y_i - y_t * Z_i = 0
    r1 = (1.0 - x_t) * mat_m[0] - x_t * mat_m[1] - x_t * mat_m[2]
    r2 = -y_t * mat_m[0] + (1.0 - y_t) * mat_m[1] - y_t * mat_m[2]
    r3 = mat_m[1]  # Luminance row: Y_i * c_i = y_target

    w_chroma = 100.0
    w_lum = 1.0
    lambda_reg = 1e-4

    # Regularization weights: lower penalty for broadband emitters encourages
    # recruitment.
    w_reg = np.array(
        [
            0.5 if e.name.lower() in _BROADBAND_EMITTER_NAMES else 1.0
            for e in profile.emitters
        ],
        dtype=float,
    )
    reg_rows = np.diag(np.sqrt(lambda_reg) * w_reg)

    mat_a = np.vstack([w_chroma * r1, w_chroma * r2, w_lum * r3, reg_rows])
    vec_b = np.concatenate([[0.0, 0.0, w_lum * y_target], np.zeros(n_emitters)])

    bounds_lower = np.zeros(n_emitters, dtype=float)
    bounds_upper = np.ones(n_emitters, dtype=float)

    if strategy == "rgb_only":
        for i, e in enumerate(profile.emitters):
            if e.name.lower() not in _RGB_EMITTER_NAMES:
                bounds_upper[i] = 0.0

    try:
        from scipy.optimize import (  # pylint: disable=import-outside-toplevel
            lsq_linear,
        )

        res = lsq_linear(mat_a, vec_b, bounds=(bounds_lower, bounds_upper))
        return np.asarray(res.x, dtype=float)
    except ImportError:
        coeffs, *_ = np.linalg.lstsq(mat_a, vec_b, rcond=None)
        return np.clip(np.asarray(coeffs, dtype=float), bounds_lower, bounds_upper)


def _raw_nnls(mat_m: np.ndarray, target_vec: np.ndarray) -> np.ndarray:
    """Solve non-negative least squares min_{c >= 0} ||M c - target||_2."""
    if mat_m.shape[1] == 0:
        return np.zeros(0, dtype=float)
    try:
        from scipy.optimize import nnls  # pylint: disable=import-outside-toplevel

        coeffs, _ = nnls(mat_m, target_vec)
        return np.asarray(coeffs, dtype=float)
    except ImportError:
        coeffs, *_ = np.linalg.lstsq(mat_m, target_vec, rcond=None)
        return np.clip(np.asarray(coeffs, dtype=float), 0.0, None)


def _bounded_punch_nnls(mat_m: np.ndarray, target_vec: np.ndarray) -> np.ndarray:
    """Solve bounded NNLS (0 <= c_i <= 1) for boosted luminance along target ray."""
    n_emitters = mat_m.shape[1]
    if n_emitters == 0 or float(np.linalg.norm(target_vec)) < 1e-9:
        return np.zeros(n_emitters, dtype=float)

    base = _raw_nnls(mat_m, target_vec)
    max_base = float(base.max()) if len(base) > 0 else 0.0
    if max_base <= 1e-9:
        return base
    # Boost target so primary emitters saturate at 1.0 and supplementary
    # emitters (White, Amber, Lime) are recruited along the same CIE xy ray.
    boost = max(2.0, 1.8 / max_base)
    rem_target = target_vec * boost
    coeffs = np.zeros(n_emitters, dtype=float)
    free_mask = np.ones(n_emitters, dtype=bool)

    for _ in range(n_emitters):
        free_idx = np.flatnonzero(free_mask)
        if len(free_idx) == 0:
            break
        sub_c = _raw_nnls(mat_m[:, free_idx], rem_target)
        over = sub_c >= 1.0 - 1e-7
        if not np.any(over):
            coeffs[free_idx] = sub_c
            break
        for idx_in_sub, col_idx in enumerate(free_idx):
            if over[idx_in_sub]:
                coeffs[col_idx] = 1.0
                free_mask[col_idx] = False
                rem_target = rem_target - mat_m[:, col_idx]
    return coeffs


class ColorMatcher:
    """Calculates DMX levels to accurately reproduce target colors across fixtures."""

    def __init__(self, profiles: list[FixtureColorProfile] | None = None) -> None:
        self.profiles: dict[str, FixtureColorProfile] = {}
        for p in profiles or []:
            self.add_profile(p)

    def add_profile(self, profile: FixtureColorProfile) -> None:
        """Register a fixture color profile."""
        self.profiles[profile.fixture_name] = profile

    def match_srgb(
        self, r: int, g: int, b: int, strategy: str = "spectral"
    ) -> dict[str, MatchResult]:
        """Calculate DMX outputs to match sRGB(r, g, b) on all registered fixtures."""
        target = sRGB.from_255(r, g, b).to_XYZ()
        return {
            name: self._solve(p, target, strategy=strategy)
            for name, p in self.profiles.items()
        }

    def match_cie(
        self,
        x: float,
        y: float,
        Y: float = 100.0,  # pylint: disable=invalid-name
        strategy: str = "spectral",
    ) -> dict[str, MatchResult]:
        """Calculate DMX outputs to match CIE xyY on all registered fixtures."""
        target = CIExyY(x, y, Y).to_XYZ()
        return {
            name: self._solve(p, target, strategy=strategy)
            for name, p in self.profiles.items()
        }

    def match_hex(
        self, hex_color: str, strategy: str = "spectral"
    ) -> dict[str, MatchResult]:
        """Calculate DMX outputs to match an HTML hex color string (#RRGGBB)."""
        clean_hex = hex_color.lstrip("#")
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
        return self.match_srgb(r, g, b, strategy=strategy)

    def _solve(  # pylint: disable=too-many-locals, too-many-branches
        self,
        profile: FixtureColorProfile,
        target: CIEXYZ,
        strategy: str = "spectral",
    ) -> MatchResult:
        full_m = profile.mixing_matrix  # (3, N)
        mat_m = full_m.copy()
        target_vec = target.as_array()  # (3,)
        n_emitters = len(profile.emitters)

        sum_xyz = target.X + target.Y + target.Z
        if sum_xyz > 1e-9 and target.Y > 1e-9:
            target_x = target.X / sum_xyz
            target_y = target.Y / sum_xyz
            inside_gamut = profile.contains_xy(target_x, target_y)
        else:
            inside_gamut = True

        if strategy != "punch" and n_emitters >= 4 and strategy != "rgb_only":
            coeffs = _solve_nled(profile, target, strategy=strategy)
        else:
            if strategy == "rgb_only":
                rgb_cols = [
                    i
                    for i, e in enumerate(profile.emitters)
                    if e.name.lower() in _RGB_EMITTER_NAMES
                ]
                if rgb_cols:
                    for i in range(len(profile.emitters)):
                        if i not in rgb_cols:
                            mat_m[:, i] = 0.0

            if strategy == "punch":
                coeffs = _bounded_punch_nnls(mat_m, target_vec)
            else:
                coeffs = _raw_nnls(mat_m, target_vec)

        max_c = float(coeffs.max()) if len(coeffs) > 0 else 0.0
        if max_c > 1.0:
            coeffs = coeffs / max_c

        warning = ""
        if not inside_gamut:
            warning = "out of gamut — brightness reduced"

        achieved = full_m @ coeffs
        achieved_xyz = CIEXYZ(
            float(achieved[0]), float(achieved[1]), float(achieved[2])
        )
        eval_xyz = achieved_xyz
        if strategy == "punch" and achieved_xyz.Y > target.Y > 1e-6:
            scale = target.Y / achieved_xyz.Y
            eval_xyz = CIEXYZ(
                achieved_xyz.X * scale, achieved_xyz.Y * scale, achieved_xyz.Z * scale
            )

        norm_weights = [float(c) for c in coeffs]
        return MatchResult(
            fixture_name=profile.fixture_name,
            emitter_names=[e.name for e in profile.emitters],
            coefficients=[round(float(c) * 100.0, 1) for c in coeffs],
            dmx_values=[round(float(c) * 255.0) for c in coeffs],
            achieved_xyz=achieved_xyz,
            delta_e=self._delta_e(target, eval_xyz),
            warning=warning,
            ratios=norm_weights,
            normalized_weights=norm_weights,
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

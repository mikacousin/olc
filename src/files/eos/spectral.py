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
"""Build calibrated ``FixtureColorProfile`` instances from Eos SPD blobs."""

from __future__ import annotations

import base64
import json
from typing import Any

import numpy as np

from olc.devices.color import (
    DEFAULT_D65_SPD,
    SPECTRAL_WAVELENGTHS,
    CIExyY,
    EmitterProfile,
    FilterProfile,
    FixtureColorProfile,
    resample_spectrum,
    spectrum_to_xyz,
)

_SUBTRACTIVE_ATTR_MAP: dict[str, str] = {
    "cyan": "ColorSub_C",
    "magenta": "ColorSub_M",
    "yellow": "ColorSub_Y",
    "cto": "CTO",
    "cto1": "CTO",
    "ctc": "CTO",
    "color temperature orange": "CTO",
}


def decode_eos_spd_blob(pers_raw: list[Any]) -> dict[str, Any] | None:
    """Decode optional Base64 SPD JSON from ``tree[2]`` personality ``entry[22][6]``."""
    if len(pers_raw) <= 22 or not isinstance(pers_raw[22], list):
        return None
    blob_container = pers_raw[22]
    if len(blob_container) <= 6 or not isinstance(blob_container[6], str):
        return None
    if not blob_container[6]:
        return None
    try:
        decoded = base64.b64decode(blob_container[6])
        spd = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return spd if isinstance(spd, dict) else None


def _pick_full_spectrum(ch: dict[str, Any]) -> dict[str, Any] | None:
    """Select the full-power spectrum entry (intensity closest to 1.0)."""
    spectra = ch.get("spectra")
    if not isinstance(spectra, list):
        return None
    valid = [s for s in spectra if isinstance(s, dict)]
    if not valid:
        return None
    with_int = [s for s in valid if isinstance(s.get("intensity"), (int, float))]
    if not with_int:
        return valid[0]
    return min(with_int, key=lambda s: abs(float(s["intensity"]) - 1.0))


def _xyz_to_ciexyy(xyz: list[float], ref_y: float) -> CIExyY:
    """Convert raw CIE XYZ triplet to ``CIExyY`` normalized against *ref_y*."""
    x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
    total = x + y + z
    if total <= 1e-12:
        return CIExyY(0.3127, 0.3290, 0.0)
    y_rel = max(0.0, min(100.0, (y / ref_y) * 100.0)) if ref_y > 1e-12 else 100.0
    return CIExyY(x=x / total, y=y / total, Y=y_rel)


def _resample_eos_curve(wavelengths: list[float], values: list[float]) -> np.ndarray:
    """Resample an Eos spectral power curve onto ``SPECTRAL_WAVELENGTHS`` (81 pts)."""
    pairs = [
        (float(w), max(0.0, float(v)))
        for w, v in zip(wavelengths, values, strict=False)
    ]
    return resample_spectrum(pairs, normalize_transmission=False)


def _dominant_wavelength(wavelengths: list[float], values: list[float]) -> float:
    """Return the peak wavelength in nm from a spectral power curve."""
    if not wavelengths or not values or len(wavelengths) != len(values):
        return 0.0
    best_idx = max(range(len(values)), key=lambda i: float(values[i]))
    return float(wavelengths[best_idx]) if float(values[best_idx]) > 0.0 else 0.0


def _extract_xyz(
    spec: dict[str, Any],
    wavelengths: list[float],
    ref_white_spd: np.ndarray | None = None,
) -> list[float] | None:
    """Return [X, Y, Z] from ``tristimulus_xyz`` or integrated ``spectral_power``."""
    raw_xyz = spec.get("tristimulus_xyz")
    if (
        isinstance(raw_xyz, list)
        and len(raw_xyz) == 3
        and all(isinstance(v, (int, float)) for v in raw_xyz)
    ):
        vals = [max(0.0, float(v)) for v in raw_xyz]
        if vals[0] + vals[1] + vals[2] > 0.0:
            return vals
    sp = spec.get("spectral_power")
    if (
        isinstance(sp, list)
        and wavelengths
        and len(sp) == len(wavelengths)
        and all(isinstance(v, (int, float)) for v in sp)
    ):
        spd_arr = _resample_eos_curve(wavelengths, [float(v) for v in sp])
        xyz_arr = spectrum_to_xyz(spd_arr, ref_white_spd=ref_white_spd)
        return [float(xyz_arr[0]), float(xyz_arr[1]), float(xyz_arr[2])]
    return None


def _build_subtractive_profile(
    fixture_name: str,
    wavelengths: list[float],
    add_channels: list[dict[str, Any]],
    sub_channels: list[dict[str, Any]],
) -> FixtureColorProfile | None:
    """Build a subtractive CMY(+CTO) ``FixtureColorProfile`` with spectral curves."""
    white_ch = next(
        (c for c in add_channels if "white" in str(c.get("name", "")).lower()),
        add_channels[0] if add_channels else None,
    )
    white_spec = _pick_full_spectrum(white_ch) if white_ch is not None else None

    w_spd = DEFAULT_D65_SPD
    has_measured_white = False
    if white_spec is not None:
        w_sp = white_spec.get("spectral_power")
        if (
            isinstance(w_sp, list)
            and wavelengths
            and len(w_sp) == len(wavelengths)
            and all(isinstance(v, (int, float)) for v in w_sp)
        ):
            w_spd = _resample_eos_curve(wavelengths, [float(v) for v in w_sp])
            has_measured_white = float(np.max(w_spd)) > 1e-12

    w_xyz = _extract_xyz(white_spec, wavelengths) if white_spec is not None else None
    if w_xyz is None:
        xyz_arr = spectrum_to_xyz(w_spd)
        w_xyz = [float(xyz_arr[0]), float(xyz_arr[1]), float(xyz_arr[2])]

    ref_y = w_xyz[1] if w_xyz[1] > 1e-12 else 100.0
    white_point = _xyz_to_ciexyy(w_xyz, ref_y)

    source_spectrum: list[tuple[float, float]] = []
    if has_measured_white:
        w_max = float(np.max(w_spd))
        w_norm = w_spd / w_max
        source_spectrum = [
            (float(wl), round(float(val), 6))
            for wl, val in zip(SPECTRAL_WAVELENGTHS, w_norm, strict=False)
        ]

    filters: list[FilterProfile] = []
    for ch in sub_channels:
        spec = _pick_full_spectrum(ch)
        if spec is None:
            continue
        f_xyz = _extract_xyz(spec, wavelengths, ref_white_spd=w_spd)
        if f_xyz is None:
            continue

        name = str(ch.get("name", "")).strip() or "Filter"
        attr = _SUBTRACTIVE_ATTR_MAP.get(name.lower(), name)
        cie = _xyz_to_ciexyy(f_xyz, ref_y)

        transmission: list[tuple[float, float]] = []
        f_sp = spec.get("spectral_power")
        if (
            has_measured_white
            and isinstance(f_sp, list)
            and wavelengths
            and len(f_sp) == len(wavelengths)
            and all(isinstance(v, (int, float)) for v in f_sp)
        ):
            f_spd = _resample_eos_curve(wavelengths, [float(v) for v in f_sp])
            w_max = float(np.max(w_spd))
            t_arr = np.where(
                w_spd > 1e-6 * w_max,
                np.clip(f_spd / np.maximum(w_spd, 1e-12), 0.0, 1.0),
                0.0,
            )
            transmission = [
                (float(wl), round(float(val), 5))
                for wl, val in zip(SPECTRAL_WAVELENGTHS, t_arr, strict=False)
            ]

        filters.append(
            FilterProfile(
                name=name,
                cie=cie,
                gdtf_attribute=attr,
                spectral_transmission=transmission,
            )
        )

    if not filters:
        return None
    return FixtureColorProfile(
        fixture_name=fixture_name,
        white_point=white_point,
        mixing_mode="subtractive",
        filters=filters,
        source_spectrum=source_spectrum,
    )


def _build_additive_profile(
    fixture_name: str,
    wavelengths: list[float],
    add_channels: list[dict[str, Any]],
) -> FixtureColorProfile | None:
    """Build an additive multi-emitter ``FixtureColorProfile`` from SPD data."""
    parsed: list[tuple[str, list[float], float]] = []
    for ch in add_channels:
        spec = _pick_full_spectrum(ch)
        if spec is None:
            continue
        xyz = _extract_xyz(spec, wavelengths)
        if xyz is None:
            continue
        name = str(ch.get("name", "")).strip() or "Emitter"
        sp = spec.get("spectral_power")
        dom_wl = (
            _dominant_wavelength(wavelengths, [float(v) for v in sp])
            if isinstance(sp, list) and all(isinstance(v, (int, float)) for v in sp)
            else 0.0
        )
        parsed.append((name, xyz, dom_wl))

    if not parsed:
        return None

    total_xyz = [
        sum(item[1][0] for item in parsed),
        sum(item[1][1] for item in parsed),
        sum(item[1][2] for item in parsed),
    ]
    total_y = total_xyz[1] if total_xyz[1] > 1e-12 else 1.0
    emitters = [
        EmitterProfile(
            name=name,
            cie=_xyz_to_ciexyy(xyz, total_y),
            dominant_wavelength=dom_wl,
        )
        for name, xyz, dom_wl in parsed
    ]
    return FixtureColorProfile(
        fixture_name=fixture_name,
        emitters=emitters,
        white_point=_xyz_to_ciexyy(total_xyz, total_y),
        mixing_mode="additive",
    )


def build_color_profile_from_eos_spd(
    fixture_name: str,
    spd: dict[str, Any] | None,
) -> FixtureColorProfile | None:
    """Build a calibrated ``FixtureColorProfile`` from a decoded Eos SPD dict."""
    if not isinstance(spd, dict):
        return None
    raw_channels = spd.get("channels")
    if not isinstance(raw_channels, list) or not raw_channels:
        return None

    raw_wls = spd.get("wavelengths")
    wavelengths = (
        [float(w) for w in raw_wls if isinstance(w, (int, float))]
        if isinstance(raw_wls, list)
        else []
    )

    add_channels: list[dict[str, Any]] = []
    sub_channels: list[dict[str, Any]] = []
    for ch in raw_channels:
        if not isinstance(ch, dict):
            continue
        method = str(ch.get("method", "")).strip().lower()
        if method == "subtractive":
            sub_channels.append(ch)
        elif method == "additive":
            add_channels.append(ch)

    if sub_channels:
        return _build_subtractive_profile(
            fixture_name, wavelengths, add_channels, sub_channels
        )
    if add_channels:
        return _build_additive_profile(fixture_name, wavelengths, add_channels)
    return None

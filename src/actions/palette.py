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
"""Core actions for recalling, recording, updating, and deleting Palettes/Presets."""

from __future__ import annotations

import copy
import typing

from olc.core.action import Action
from olc.define import MAX_CHANNELS
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType
from olc.show.palette import (
    Palette,
    PaletteCategory,
    PaletteMode,
    get_channel_type_key,
)

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication

_UNIVERSAL_ATTR_KEYS: frozenset[str] = frozenset(
    {"intensity", "color", "cie", "rgb", "red", "green", "blue", "zoom", "frost"}
)


def _filter_universal_attrs(attrs: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Keep only generic/universal attributes from a captured device attribute dict."""
    return {
        str(k): copy.deepcopy(v)
        for k, v in attrs.items()
        if str(k).lower() in _UNIVERSAL_ATTR_KEYS
    }


def _normalize_palette_mode(mode: PaletteMode | str) -> PaletteMode:
    if isinstance(mode, PaletteMode):
        return mode
    return PaletteMode(str(mode).lower())


def format_palette_number(number: float) -> str:
    """Format palette/preset number concisely (2.0 -> '2', 2.5 -> '2.5')."""
    num = float(number)
    return str(int(num)) if num.is_integer() else str(num)


def format_palette_label(category: PaletteCategory | str, number: float) -> str:
    """Return a human-readable identifier such as 'Color Palette 2' or 'Preset 1'."""
    cat = (
        category
        if isinstance(category, PaletteCategory)
        else PaletteCategory(str(category).lower())
    )
    num_str = format_palette_number(number)
    if cat is PaletteCategory.PRESET:
        return f"Preset {num_str}"
    return f"{cat.value.capitalize()} Palette {num_str}"


def _normalize_category(category: PaletteCategory | str) -> PaletteCategory:
    if isinstance(category, PaletteCategory):
        return category
    return PaletteCategory(str(category).lower())


def _is_channel_modified(dev: typing.Any, ch_type_val: str) -> bool:  # noqa: ANN401
    """Return True if any DMX channel matching *ch_type_val* differs from default."""
    for ch in getattr(dev, "channels", []):
        ctype = getattr(ch, "channel_type", None)
        if getattr(ctype, "value", ctype) == ch_type_val:
            if getattr(ch, "value", 0) != getattr(ch, "default_value", 0):
                return True
    return False


def _any_color_channel_modified(dev: typing.Any) -> bool:  # noqa: ANN401
    """Return True if any additive color emitter channel differs from its default."""
    for ch in getattr(dev, "channels", []):
        if getattr(ch, "channel_type", None) in COLOR_CHANNEL_TYPES:
            if getattr(ch, "value", 0) != getattr(ch, "default_value", 0):
                return True
    return False


def _extract_device_palette_values(
    dev: typing.Any,  # noqa: ANN401
    category: PaletteCategory,
    *,
    explicit_selection: bool,
) -> dict[str, typing.Any]:
    """Extract live parameters matching *category* from a LightingDevice."""
    vals: dict[str, typing.Any] = {}
    has_channels = hasattr(dev, "channels")

    if category in (PaletteCategory.FOCUS, PaletteCategory.PRESET):
        has_pan = (
            dev.get_channel(ChannelType.PAN) is not None if has_channels else False
        )
        has_tilt = (
            dev.get_channel(ChannelType.TILT) is not None if has_channels else False
        )
        pan_mod = (
            _is_channel_modified(dev, "pan")
            if has_channels
            else getattr(dev, "pan_degrees", 0.0) != 0.0
        )
        tilt_mod = (
            _is_channel_modified(dev, "tilt")
            if has_channels
            else getattr(dev, "tilt_degrees", 0.0) != 0.0
        )
        force_focus = category is PaletteCategory.FOCUS and explicit_selection
        if has_pan and (pan_mod or force_focus):
            vals["pan"] = dev.pan_degrees
        if has_tilt and (tilt_mod or force_focus):
            vals["tilt"] = dev.tilt_degrees

    if category in (PaletteCategory.COLOR, PaletteCategory.PRESET):
        base_emitters = getattr(dev, "_base_emitters", {})
        if getattr(dev, "is_subtractive_cmy", False):
            ch_mod = _any_color_channel_modified(dev) if has_channels else False
            force_color = category is PaletteCategory.COLOR and explicit_selection
            if ch_mod or force_color:
                preview = (
                    dev.get_preview_rgb() if hasattr(dev, "get_preview_rgb") else None
                )
                if preview is not None:
                    vals["color"] = (
                        f"#{round(preview[0] * 255):02x}"
                        f"{round(preview[1] * 255):02x}"
                        f"{round(preview[2] * 255):02x}"
                    )
                elif hasattr(dev, "color_srgb") and hasattr(dev.color_srgb, "to_hex"):
                    vals["color"] = dev.color_srgb.to_hex()
        elif base_emitters:
            emitters_altered = any(
                abs(float(v) - 1.0) > 1e-4 for v in base_emitters.values()
            )
            ch_mod = _any_color_channel_modified(dev) if has_channels else False
            force_color = category is PaletteCategory.COLOR and explicit_selection
            if emitters_altered or ch_mod or force_color:
                vals["color"] = dev.color_srgb.to_hex()
        elif hasattr(dev, "color_srgb") and hasattr(dev.color_srgb, "to_hex"):
            vals["color"] = dev.color_srgb.to_hex()

        if (
            has_channels
            and dev.get_channel(ChannelType.COLOR_TEMP) is not None
            and dev.color_temp_kelvin is not None
            and (
                _is_channel_modified(dev, "color_temp")
                or (category is PaletteCategory.COLOR and explicit_selection)
            )
        ):
            vals["cct"] = dev.color_temp_kelvin

        if (
            has_channels
            and dev.get_channel(ChannelType.COLOR_WHEEL) is not None
            and _is_channel_modified(dev, "color_wheel")
        ):
            norm_cw = dev.get_parameter_normalized(ChannelType.COLOR_WHEEL)
            if norm_cw is not None:
                vals["color_wheel"] = norm_cw

    if category in (PaletteCategory.BEAM, PaletteCategory.PRESET):
        force_beam = category is PaletteCategory.BEAM and explicit_selection
        if dev.zoom_degrees is not None and (
            not has_channels or _is_channel_modified(dev, "zoom") or force_beam
        ):
            vals["zoom"] = dev.zoom_degrees
        if (
            has_channels
            and dev.focus_meters is not None
            and (_is_channel_modified(dev, "focus") or force_beam)
        ):
            vals["focus"] = dev.focus_meters
        if (
            has_channels
            and getattr(dev, "iris", None) is not None
            and _is_channel_modified(dev, "iris")
        ):
            vals["iris"] = dev.iris
        if (
            has_channels
            and dev.strobe_hz is not None
            and _is_channel_modified(dev, "strobe")
        ):
            vals["strobe"] = dev.strobe_hz
        if has_channels and getattr(dev, "gobo", None) is not None:
            vals["gobo"] = dev.gobo
        for extra_ctype in (ChannelType.FROST, ChannelType.PRISM):
            if (
                has_channels
                and dev.get_channel(extra_ctype) is not None
                and _is_channel_modified(dev, extra_ctype.value)
            ):
                norm_val = dev.get_parameter_normalized(extra_ctype)
                if norm_val is not None:
                    vals[extra_ctype.value] = norm_val

    return vals


def capture_live_palette_data(  # pylint: disable=too-many-branches
    app: CoreApplication,
    category: PaletteCategory,
    target_channels: list[int] | None = None,
) -> tuple[dict[int, float], dict[int, dict[str, typing.Any]]]:
    """Capture live channel intensities and/or IFCB device attributes for a palette."""
    selected = (
        [int(ch) for ch in target_channels]
        if target_channels
        else [int(ch) for ch in getattr(app, "selected_channels", [])]
    )
    explicit_selection = bool(selected)
    lightshow = getattr(app, "lightshow", None)
    patch = getattr(lightshow, "patch", None) if lightshow is not None else None
    backend = getattr(app, "backend", None)
    backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
    user_levels = (
        backend_dmx.levels.get("user", [])
        if backend_dmx is not None
        and isinstance(getattr(backend_dmx, "levels", None), dict)
        else []
    )

    channels_data: dict[int, float] = {}
    device_values: dict[int, dict[str, typing.Any]] = {}

    if category in (PaletteCategory.INTENSITY, PaletteCategory.PRESET):
        if explicit_selection:
            int_candidates = selected
        else:
            seen: set[int] = set()
            limit = min(MAX_CHANNELS, len(user_levels))
            for ch in range(1, limit + 1):
                if float(user_levels[ch - 1]) > 0.0:
                    seen.add(ch)
            if patch is not None:
                for ch, dev in patch.devices.items():
                    if float(getattr(dev, "intensity", 0.0)) > 0.0:
                        seen.add(int(ch))
            int_candidates = sorted(seen)

        for ch in int_candidates:
            user_lvl = (
                float(user_levels[ch - 1]) if 1 <= ch <= len(user_levels) else -1.0
            )
            dev = patch.devices.get(ch) if patch is not None else None
            dev_int = float(getattr(dev, "intensity", 0.0)) if dev is not None else 0.0
            if user_lvl >= 0.0:
                channels_data[ch] = max(0.0, min(1.0, user_lvl))
            elif dev_int > 0.0:
                channels_data[ch] = max(0.0, min(1.0, dev_int))
            elif category is PaletteCategory.INTENSITY and explicit_selection:
                channels_data[ch] = 0.0

    if (
        category
        in (
            PaletteCategory.FOCUS,
            PaletteCategory.COLOR,
            PaletteCategory.BEAM,
            PaletteCategory.PRESET,
        )
        and patch is not None
    ):
        dev_candidates = (
            [ch for ch in selected if ch in patch.devices]
            if explicit_selection
            else sorted(patch.devices.keys())
        )
        for ch in dev_candidates:
            dev = patch.devices[ch]
            vals = _extract_device_palette_values(
                dev, category, explicit_selection=explicit_selection
            )
            if vals:
                device_values[int(ch)] = vals

    return channels_data, device_values


def _sync_preset_live_refs(
    live_state: typing.Any,  # noqa: ANN401
    ch_data: typing.Mapping[int, float],
    dev_vals: typing.Mapping[int, typing.Mapping[str, typing.Any]],
    target_refs: dict[int, dict[str, tuple[str, float]]],
) -> None:
    """Sync live sub-palette references into *target_refs* for a Preset."""
    if live_state is None:
        return
    for ch in set(ch_data.keys()) | set(dev_vals.keys()):
        ch_int = int(ch)
        ch_refs = target_refs.setdefault(ch_int, {})
        if ch in ch_data:
            int_ref = live_state.get_palette_ref(ch_int, "intensity")
            if int_ref is not None and int_ref[0] != PaletteCategory.PRESET.value:
                ch_refs["intensity"] = int_ref
            else:
                ch_refs.pop("intensity", None)
        for param_name in dev_vals.get(ch, {}):
            p_key = str(param_name)
            p_ref = live_state.get_palette_ref(ch_int, p_key)
            if p_ref is not None and p_ref[0] != PaletteCategory.PRESET.value:
                ch_refs[p_key] = p_ref
            else:
                ch_refs.pop(p_key, None)
        if not ch_refs:
            target_refs.pop(ch_int, None)


def _snapshot_device_state(dev: typing.Any) -> dict[str, typing.Any]:  # noqa: ANN401
    """Capture complete mutable DMX and cached color/parameter state of a device."""
    return {
        "channel_values": [int(ch.value) for ch in getattr(dev, "channels", [])],
        "intensity": float(getattr(dev, "_intensity", 0.0)),
        "base_emitters": dict(getattr(dev, "_base_emitters", {})),
        "target_color": getattr(dev, "_target_color", None),
        "target_cie": getattr(dev, "_target_cie", None),
        "param_normalized": dict(getattr(dev, "_param_normalized", {})),
        "param_last_raw": dict(getattr(dev, "_param_last_raw", {})),
    }


def _restore_device_state(
    dev: typing.Any,  # noqa: ANN401
    snapshot: dict[str, typing.Any],
) -> None:
    """Restore a device's channels and cached attributes from a snapshot."""
    for ch, val in zip(
        getattr(dev, "channels", []), snapshot["channel_values"], strict=False
    ):
        if hasattr(ch, "set_value"):
            ch.set_value(int(val))
        else:
            ch.value = int(val)
    if hasattr(dev, "_intensity"):
        dev._intensity = float(snapshot["intensity"])  # pylint: disable=protected-access
    if hasattr(dev, "_base_emitters"):
        dev._base_emitters = dict(snapshot["base_emitters"])  # pylint: disable=protected-access
    if snapshot["target_color"] is not None and hasattr(dev, "_target_color"):
        dev._target_color = snapshot["target_color"]  # pylint: disable=protected-access
    if snapshot["target_cie"] is not None and hasattr(dev, "_target_cie"):
        dev._target_cie = snapshot["target_cie"]  # pylint: disable=protected-access
    if hasattr(dev, "_param_normalized"):
        dev._param_normalized = dict(snapshot["param_normalized"])  # pylint: disable=protected-access
    if hasattr(dev, "_param_last_raw"):
        dev._param_last_raw = dict(snapshot["param_last_raw"])  # pylint: disable=protected-access


def _flush_dmx(app: CoreApplication) -> None:
    """Refresh playback/channel state and push DMX frame if available."""
    lightshow = getattr(app, "lightshow", None)
    engine = getattr(app, "playback_engine", None)
    main_pb = (
        engine.main_sequence
        if engine is not None and engine.main_sequence is not None
        else (getattr(lightshow, "main_playback", None) if lightshow else None)
    )
    if main_pb is not None and hasattr(main_pb, "update_channels"):
        main_pb.update_channels()
    backend = getattr(app, "backend", None)
    backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
    if backend_dmx is not None and hasattr(backend_dmx, "set_levels"):
        backend_dmx.set_levels()


class PaletteApplyAction(Action):
    """Apply a stored IFCB Palette or Preset onto target or active channels."""

    name = "palette.apply"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self.channels: list[int] | None = None
        self.absolute: bool = False
        self._old_user_levels: dict[int, float] = {}
        self._new_user_levels: dict[int, float] = {}
        self._old_device_states: dict[int, dict[str, typing.Any]] = {}
        self._new_device_states: dict[int, dict[str, typing.Any]] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}
        self._affected_channels: list[int] = []

    def configure(
        self,
        category: PaletteCategory | str,
        number: float,
        channels: list[int] | None = None,
        *,
        absolute: bool = False,
    ) -> None:
        """Configure the palette/preset to recall and optional target channel list."""
        self.category = _normalize_category(category)
        self.number = float(number)
        self.channels = [int(ch) for ch in channels] if channels else None
        self.absolute = bool(absolute)

    def execute(self) -> list[int]:
        """Apply the palette values to matching channels/devices."""
        lightshow = getattr(self.app, "lightshow", None)
        palette = (
            lightshow.palettes.get(self.category, self.number)
            if lightshow is not None
            else None
        )
        if palette is None:
            self.can_undo = False
            return []

        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        patch_devices = getattr(patch, "devices", None) if patch is not None else None

        if self.channels:
            candidates = list(self.channels)
        else:
            active_sel = [int(ch) for ch in getattr(self.app, "selected_channels", [])]
            if active_sel:
                candidates = active_sel
            elif palette.mode is PaletteMode.BY_TYPE and isinstance(
                patch_devices, dict
            ):
                type_keys = set(palette.by_type_channels) | set(palette.by_type_values)
                by_type_chs = [
                    int(ch)
                    for ch, dev in patch_devices.items()
                    if getattr(dev, "type_key", None) in type_keys
                ]
                candidates = sorted(
                    set(palette.channels)
                    | set(palette.device_values)
                    | set(by_type_chs)
                )
            else:
                candidates = sorted(set(palette.channels) | set(palette.device_values))

        targets: list[int] = []
        seen: set[int] = set()
        for ch in candidates:
            if ch in seen:
                continue
            type_key = get_channel_type_key(lightshow, ch)
            if palette.has_data_for_channel(ch, type_key):
                seen.add(ch)
                targets.append(ch)

        if not targets:
            self.can_undo = False
            return []

        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
        user_levels = (
            backend_dmx.levels.get("user")
            if backend_dmx is not None
            and isinstance(getattr(backend_dmx, "levels", None), dict)
            else None
        )

        self._old_user_levels = {}
        self._new_user_levels = {}
        self._old_device_states = {}
        self._new_device_states = {}
        self._old_live_states = {}
        self._new_live_states = {}
        self._affected_channels = []
        device_changed: list[int] = []
        live_state = getattr(self.app, "live_state", None)
        pal_ref = (self.category.value, float(self.number))

        for ch in targets:
            dev = patch.devices.get(ch) if patch is not None else None
            if user_levels is not None and 1 <= ch <= len(user_levels):
                self._old_user_levels[ch] = float(user_levels[ch - 1])
            if dev is not None:
                self._old_device_states[ch] = _snapshot_device_state(dev)
            if live_state is not None:
                self._old_live_states[ch] = live_state.snapshot_channel(ch)

            changed = False
            applied_refs: dict[str, tuple[str, float]] = {}
            type_key = get_channel_type_key(lightshow, ch)
            resolved_int, resolved_devs = palette.resolve_channel(ch, type_key)

            target_intensity: float | None = None
            if (
                self.category in (PaletteCategory.INTENSITY, PaletteCategory.PRESET)
                and resolved_int is not None
            ):
                target_intensity = max(0.0, min(1.0, float(resolved_int)))
            elif (
                self.category is PaletteCategory.PRESET and "intensity" in resolved_devs
            ):
                raw_int = resolved_devs["intensity"]
                if isinstance(raw_int, (int, float)):
                    val = float(raw_int)
                    target_intensity = max(
                        0.0, min(1.0, val / 255.0 if val > 1.0 else val)
                    )

            if target_intensity is not None:
                if user_levels is not None and 1 <= ch <= len(user_levels):
                    user_levels[ch - 1] = target_intensity
                    self._new_user_levels[ch] = target_intensity
                if dev is not None and hasattr(dev, "set_intensity"):
                    dev.set_intensity(target_intensity)
                applied_refs["intensity"] = pal_ref
                changed = True

            if (
                dev is not None
                and self.category is not PaletteCategory.INTENSITY
                and resolved_devs
            ):
                attrs = {k: v for k, v in resolved_devs.items() if k != "intensity"}
                if attrs and hasattr(dev, "apply_device_values"):
                    dev.apply_device_values(attrs)
                    for attr_name in attrs:
                        applied_refs[str(attr_name).lower()] = pal_ref
                    device_changed.append(ch)
                    changed = True

            if dev is not None:
                self._new_device_states[ch] = _snapshot_device_state(dev)
            if changed:
                if live_state is not None and applied_refs:
                    if not self.absolute:
                        live_state.set_palette_refs(ch, applied_refs, mark_manual=True)
                    elif hasattr(live_state, "mark_manual_params"):
                        live_state.mark_manual_params(
                            ch, list(applied_refs.keys()), break_refs=True
                        )
                    self._new_live_states[ch] = live_state.snapshot_channel(ch)
                self._affected_channels.append(ch)

        if not self._affected_channels:
            self.can_undo = False
            return []

        _flush_dmx(self.app)
        for ch, lvl in self._new_user_levels.items():
            self.app.emit("channel.level_changed", ch, lvl)
        if self._new_user_levels:
            self.app.emit("channels.updated", list(self._new_user_levels.keys()))
        if device_changed:
            self.app.emit("device.parameters_changed", device_changed)
        self.app.emit(
            "palette.applied",
            self.category.value,
            self.number,
            list(self._affected_channels),
        )
        return list(self._affected_channels)

    def _apply_saved_snapshots(
        self,
        user_map: dict[int, float],
        device_map: dict[int, dict[str, typing.Any]],
        live_map: dict[int, typing.Any] | None = None,
    ) -> None:
        lightshow = getattr(self.app, "lightshow", None)
        patch = getattr(lightshow, "patch", None) if lightshow is not None else None
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
        user_levels = (
            backend_dmx.levels.get("user")
            if backend_dmx is not None
            and isinstance(getattr(backend_dmx, "levels", None), dict)
            else None
        )

        if user_levels is not None:
            for ch, lvl in user_map.items():
                if 1 <= ch <= len(user_levels):
                    user_levels[ch - 1] = lvl

        if patch is not None:
            for ch, snap in device_map.items():
                dev = patch.devices.get(ch)
                if dev is not None:
                    _restore_device_state(dev, snap)

        live_state = getattr(self.app, "live_state", None)
        if live_state is not None and live_map is not None:
            for ch, snap in live_map.items():
                live_state.restore_channel(ch, snap)

        _flush_dmx(self.app)
        for ch, lvl in user_map.items():
            self.app.emit("channel.level_changed", ch, lvl)
        if user_map:
            self.app.emit("channels.updated", list(user_map.keys()))
        if device_map:
            self.app.emit("device.parameters_changed", list(device_map.keys()))

    def undo(self) -> None:
        """Revert channels and devices to their pre-palette state."""
        self._apply_saved_snapshots(
            self._old_user_levels, self._old_device_states, self._old_live_states
        )

    def redo(self) -> None:
        """Reapply the palette state."""
        self._apply_saved_snapshots(
            self._new_user_levels, self._new_device_states, self._new_live_states
        )

    def get_history_details(self) -> str:
        """Return palette label and target channel count for Undo History."""
        label = format_palette_label(self.category, self.number)
        if not self._affected_channels:
            return label
        return f"{label} ({len(self._affected_channels)} ch)"


class PaletteRecordAction(Action):
    """Record or overwrite a Palette or Preset and propagate to references."""

    name = "palette.record"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self.label: str = ""
        self.channels: list[int] | None = None
        self.channels_data: dict[int, float] | None = None
        self.device_values: dict[int, dict[str, typing.Any]] | None = None
        self.palette_refs: dict[int, dict[str, tuple[str, float]]] | None = None
        self.mode: PaletteMode | None = None
        self._previous_palette: Palette | None = None
        self._recorded_palette: Palette | None = None

    def configure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        category: PaletteCategory | str,
        number: float,
        label: str = "",
        channels: list[int] | None = None,
        channels_data: dict[int, float] | None = None,
        device_values: dict[int, dict[str, typing.Any]] | None = None,
        palette_refs: dict[int, dict[str, tuple[str, float]]] | None = None,
        mode: PaletteMode | str | None = None,
    ) -> None:
        """Configure palette recording target and optional explicit payload."""
        self.category = _normalize_category(category)
        self.number = float(number)
        self.label = str(label)
        self.channels = [int(ch) for ch in channels] if channels else None
        self.channels_data = (
            {int(k): float(v) for k, v in channels_data.items()}
            if channels_data is not None
            else None
        )
        self.device_values = (
            copy.deepcopy(device_values) if device_values is not None else None
        )
        self.palette_refs = (
            copy.deepcopy(palette_refs) if palette_refs is not None else None
        )
        self.mode = _normalize_palette_mode(mode) if mode is not None else None

    def execute(self) -> dict[str, typing.Any]:
        """Store the recorded palette/preset and propagate cascade updates."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is not None and existing.locked:
            self.can_undo = False
            return {"palette": existing, "locked": True, "propagation": {}}
        self._previous_palette = copy.deepcopy(existing)

        if self.channels_data is None and self.device_values is None:
            ch_data, dev_vals = capture_live_palette_data(
                self.app, self.category, self.channels
            )
        else:
            ch_data = dict(self.channels_data or {})
            dev_vals = copy.deepcopy(self.device_values or {})

        eff_mode = (
            self.mode
            if self.mode is not None
            else (existing.mode if existing is not None else PaletteMode.SELECTIVE)
        )

        text = self.label or (existing.text if existing is not None else "")
        if self.palette_refs is not None:
            refs = copy.deepcopy(self.palette_refs)
        elif (
            self.category is PaletteCategory.PRESET
            and self.channels_data is None
            and self.device_values is None
        ):
            refs = {}
            _sync_preset_live_refs(
                getattr(self.app, "live_state", None), ch_data, dev_vals, refs
            )
        else:
            refs = copy.deepcopy(existing.palette_refs if existing is not None else {})

        sel_channels: dict[int, float] = {}
        sel_devs: dict[int, dict[str, typing.Any]] = {}
        by_type_ch: dict[str, float] = {}
        by_type_vals: dict[str, dict[str, typing.Any]] = {}
        univ_int: float | None = None
        univ_vals: dict[str, typing.Any] = {}

        if eff_mode is PaletteMode.BY_TYPE:
            for ch, lvl in ch_data.items():
                tk = get_channel_type_key(lightshow, ch)
                if tk:
                    by_type_ch.setdefault(tk, float(lvl))
                else:
                    sel_channels[ch] = float(lvl)
            for ch, attrs in dev_vals.items():
                tk = get_channel_type_key(lightshow, ch)
                if tk:
                    by_type_vals.setdefault(tk, copy.deepcopy(attrs))
                else:
                    sel_devs[ch] = copy.deepcopy(attrs)
        elif eff_mode is PaletteMode.UNIVERSAL:
            if ch_data:
                first_ch = next(iter(ch_data))
                univ_int = float(ch_data[first_ch])
            if dev_vals:
                first_ch = next(iter(dev_vals))
                univ_vals = _filter_universal_attrs(dev_vals[first_ch])
        else:
            sel_channels = ch_data
            sel_devs = dev_vals

        new_palette = Palette(
            category=self.category,
            number=self.number,
            text=text,
            channels=sel_channels,
            device_values=sel_devs,
            palette_refs=refs,
            mode=eff_mode,
            by_type_channels=by_type_ch,
            by_type_values=by_type_vals,
            universal_intensity=univ_int,
            universal_values=univ_vals,
        )
        self._recorded_palette = copy.deepcopy(new_palette)
        lightshow.palettes.add(new_palette)
        propagation = lightshow.palettes.propagate_update(
            lightshow, self.category, self.number
        )
        lightshow.set_modified()
        self.app.emit("palette.recorded", self.category.value, self.number)
        self.app.emit("palettes.changed", self.category.value, self.number)
        return {"palette": new_palette, "propagation": propagation}

    def undo(self) -> None:
        """Restore prior palette state (or delete if newly created) and re-propagate."""
        lightshow = self.app.lightshow
        if self._previous_palette is None:
            lightshow.palettes.delete(self.category, self.number)
        else:
            lightshow.palettes.add(copy.deepcopy(self._previous_palette))
            lightshow.palettes.propagate_update(lightshow, self.category, self.number)
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def redo(self) -> None:
        """Re-apply the recorded palette and cascade updates."""
        if self._recorded_palette is None:
            return
        lightshow = self.app.lightshow
        lightshow.palettes.add(copy.deepcopy(self._recorded_palette))
        lightshow.palettes.propagate_update(lightshow, self.category, self.number)
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def get_history_details(self) -> str:
        """Return recorded palette label for Undo History."""
        return format_palette_label(self.category, self.number)


class PaletteUpdateAction(Action):
    """Merge live values into an existing Palette/Preset and cascade updates."""

    name = "palette.update"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self.channels: list[int] | None = None
        self.channels_data: dict[int, float] | None = None
        self.device_values: dict[int, dict[str, typing.Any]] | None = None
        self.selective_override: bool = False
        self._previous_palette: Palette | None = None
        self._updated_palette: Palette | None = None

    def configure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        category: PaletteCategory | str,
        number: float,
        channels: list[int] | None = None,
        channels_data: dict[int, float] | None = None,
        device_values: dict[int, dict[str, typing.Any]] | None = None,
        selective_override: bool = False,
    ) -> None:
        """Configure palette/preset update target and optional explicit values."""
        self.category = _normalize_category(category)
        self.number = float(number)
        self.channels = [int(ch) for ch in channels] if channels else None
        self.channels_data = (
            {int(k): float(v) for k, v in channels_data.items()}
            if channels_data is not None
            else None
        )
        self.device_values = (
            copy.deepcopy(device_values) if device_values is not None else None
        )
        self.selective_override = bool(selective_override)

    def execute(self) -> dict[str, typing.Any] | None:
        """Merge updated values into existing palette and propagate cascade."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None or existing.locked:
            self.can_undo = False
            return None

        self._previous_palette = copy.deepcopy(existing)

        if self.channels_data is None and self.device_values is None:
            ch_data, dev_vals = capture_live_palette_data(
                self.app, self.category, self.channels
            )
        else:
            ch_data = dict(self.channels_data or {})
            dev_vals = copy.deepcopy(self.device_values or {})

        if self.selective_override or existing.mode is PaletteMode.SELECTIVE:
            for ch, lvl in ch_data.items():
                existing.channels[int(ch)] = float(lvl)
            for ch, attrs in dev_vals.items():
                existing.device_values.setdefault(int(ch), {}).update(
                    copy.deepcopy(attrs)
                )
        elif existing.mode is PaletteMode.BY_TYPE:
            for ch, lvl in ch_data.items():
                tk = get_channel_type_key(lightshow, int(ch))
                if tk:
                    existing.by_type_channels[tk] = float(lvl)
                else:
                    existing.channels[int(ch)] = float(lvl)
            for ch, attrs in dev_vals.items():
                tk = get_channel_type_key(lightshow, int(ch))
                if tk:
                    existing.by_type_values.setdefault(tk, {}).update(
                        copy.deepcopy(attrs)
                    )
                else:
                    existing.device_values.setdefault(int(ch), {}).update(
                        copy.deepcopy(attrs)
                    )
        else:
            if ch_data:
                first_ch = next(iter(ch_data))
                existing.universal_intensity = float(ch_data[first_ch])
            if dev_vals:
                first_ch = next(iter(dev_vals))
                existing.universal_values.update(
                    _filter_universal_attrs(dev_vals[first_ch])
                )

        if (
            self.category is PaletteCategory.PRESET
            and self.channels_data is None
            and self.device_values is None
        ):
            _sync_preset_live_refs(
                getattr(self.app, "live_state", None),
                ch_data,
                dev_vals,
                existing.palette_refs,
            )

        self._updated_palette = copy.deepcopy(existing)
        propagation = lightshow.palettes.propagate_update(
            lightshow, self.category, self.number
        )
        lightshow.set_modified()
        self.app.emit("palette.updated", self.category.value, self.number, propagation)
        self.app.emit("palettes.changed", self.category.value, self.number)
        return {"palette": existing, "propagation": propagation}

    def undo(self) -> None:
        """Restore the pre-update palette and cascade-revert referencing targets."""
        if self._previous_palette is None:
            return
        lightshow = self.app.lightshow
        lightshow.palettes.add(copy.deepcopy(self._previous_palette))
        lightshow.palettes.propagate_update(lightshow, self.category, self.number)
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def redo(self) -> None:
        """Re-apply the updated palette and cascade updates."""
        if self._updated_palette is None:
            return
        lightshow = self.app.lightshow
        lightshow.palettes.add(copy.deepcopy(self._updated_palette))
        lightshow.palettes.propagate_update(lightshow, self.category, self.number)
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def get_history_details(self) -> str:
        """Return updated palette label for Undo History."""
        return format_palette_label(self.category, self.number)


class PaletteDeleteAction(Action):
    """Delete an existing Palette or Preset."""

    name = "palette.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self._deleted_palette: Palette | None = None

    def configure(self, category: PaletteCategory | str, number: float) -> None:
        """Configure which palette or preset to delete."""
        self.category = _normalize_category(category)
        self.number = float(number)

    def execute(self) -> bool:
        """Remove the palette/preset from LightShow.palettes."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            self.can_undo = False
            return False

        self._deleted_palette = copy.deepcopy(existing)
        lightshow.palettes.delete(self.category, self.number)
        lightshow.set_modified()
        self.app.emit("palette.deleted", self.category.value, self.number)
        self.app.emit("palettes.changed", self.category.value, self.number)
        return True

    def undo(self) -> None:
        """Restore the deleted palette/preset."""
        if self._deleted_palette is None:
            return
        lightshow = self.app.lightshow
        lightshow.palettes.add(copy.deepcopy(self._deleted_palette))
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def get_history_details(self) -> str:
        """Return deleted palette label for Undo History."""
        return format_palette_label(self.category, self.number)


class PaletteRenameAction(Action):
    """Rename an existing Palette or Preset with Undo/Redo support."""

    name = "palette.rename"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self.text: str = ""
        self._old_text: str = ""

    def configure(
        self, category: PaletteCategory | str, number: float, text: str
    ) -> None:
        """Configure target palette/preset and new label."""
        self.category = _normalize_category(category)
        self.number = float(number)
        self.text = str(text)

    def execute(self) -> bool:
        """Update the label on the stored palette/preset."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            self.can_undo = False
            return False

        self._old_text = existing.text
        existing.text = self.text
        lightshow.set_modified()
        self.app.emit("palette.renamed", self.category.value, self.number, self.text)
        self.app.emit("palettes.changed", self.category.value, self.number)
        return True

    def undo(self) -> None:
        """Restore previous label."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            return
        existing.text = self._old_text
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def redo(self) -> None:
        """Reapply new label."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            return
        existing.text = self.text
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def get_history_details(self) -> str:
        """Return renamed palette label for Undo History."""
        return f"{format_palette_label(self.category, self.number)} \u2192 {self.text}"


class PaletteSetModeAction(Action):
    """Change the storage/resolution mode of an existing Palette or Preset."""

    name = "palette.set_mode"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self.mode: PaletteMode = PaletteMode.SELECTIVE
        self._old_mode: PaletteMode = PaletteMode.SELECTIVE

    def configure(
        self,
        category: PaletteCategory | str,
        number: float,
        mode: PaletteMode | str,
    ) -> None:
        """Configure target palette and new mode."""
        self.category = _normalize_category(category)
        self.number = float(number)
        self.mode = _normalize_palette_mode(mode)

    def execute(self) -> bool:
        """Set palette mode if it exists and is not locked."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None or existing.locked:
            self.can_undo = False
            return False
        self._old_mode = existing.mode
        if self._old_mode is self.mode:
            self.can_undo = False
            return True
        existing.mode = self.mode
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)
        return True

    def undo(self) -> None:
        """Restore previous palette mode."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            return
        existing.mode = self._old_mode
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def redo(self) -> None:
        """Reapply new palette mode."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            return
        existing.mode = self.mode
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def get_history_details(self) -> str:
        """Return palette mode change summary for Undo History."""
        return f"{format_palette_label(self.category, self.number)}: {self.mode.value}"


class PaletteSetLockedAction(Action):
    """Lock or unlock an existing Palette or Preset."""

    name = "palette.set_locked"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.category: PaletteCategory = PaletteCategory.COLOR
        self.number: float = 0.0
        self.locked: bool = True
        self._old_locked: bool = False

    def configure(
        self,
        category: PaletteCategory | str,
        number: float,
        locked: bool,
    ) -> None:
        """Configure target palette and lock state."""
        self.category = _normalize_category(category)
        self.number = float(number)
        self.locked = bool(locked)

    def execute(self) -> bool:
        """Set palette lock state."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            self.can_undo = False
            return False
        self._old_locked = bool(existing.locked)
        if self._old_locked is self.locked:
            self.can_undo = False
            return True
        existing.locked = self.locked
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)
        return True

    def undo(self) -> None:
        """Restore previous lock state."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            return
        existing.locked = self._old_locked
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def redo(self) -> None:
        """Reapply new lock state."""
        lightshow = self.app.lightshow
        existing = lightshow.palettes.get(self.category, self.number)
        if existing is None:
            return
        existing.locked = self.locked
        lightshow.set_modified()
        self.app.emit("palettes.changed", self.category.value, self.number)

    def get_history_details(self) -> str:
        """Return palette lock state change summary for Undo History."""
        state = "Lock" if self.locked else "Unlock"
        return f"{format_palette_label(self.category, self.number)} ({state})"

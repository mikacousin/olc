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

import threading
import typing

from olc.actions import register_all_actions
from olc.core.binding import MidiBinding, OscBinding
from olc.core.commandline import CoreCommandLine
from olc.core.crossfade import CrossFade
from olc.core.dmx_backend import DMXBackend
from olc.core.effects_engine import EffectsEngine
from olc.core.event import EventDispatcher
from olc.core.history import HistoryManager
from olc.core.live_state import LiveParameterState
from olc.core.registry import ActionRegistry
from olc.core.selection import SelectionManager
from olc.core.sneak import SneakController
from olc.core.tabs import CoreTabs
from olc.define import MAX_CHANNELS
from olc.show.lightshow import LightShow

if typing.TYPE_CHECKING:
    from olc.controllers.midi import Midi
    from olc.controllers.osc import Osc
    from olc.core.tracking import ResolvedState
    from olc.dmx_engine.engine import CoreEngine


# pylint: disable=too-many-instance-attributes
class CoreApplication(EventDispatcher):
    """The headless core application managing engines, midi, and actions.

    Acts as the single source of truth for the entire application logic.
    Decoupled from all GTK graphical interfaces.
    """

    backend: typing.Optional[DMXBackend]
    engine: typing.Optional[CoreEngine]
    midi: typing.Optional[Midi]
    osc: typing.Optional[Osc]
    crossfade: typing.Optional[CrossFade]
    commandline: CoreCommandLine
    live_selection: SelectionManager
    action_registry: ActionRegistry
    history: HistoryManager
    live_state: LiveParameterState
    effects_engine: EffectsEngine
    selected_cue: typing.Optional[tuple[float, int]]
    selected_group: typing.Optional[float]
    tabs: CoreTabs
    dark_theme: bool
    blackout_active: bool
    main_fader_level: float
    _ZOOM_DEBOUNCE_SECONDS: float = 0.6

    def __init__(
        self,
        settings: object,
        lightshow: typing.Optional[LightShow] = None,
    ) -> None:
        """Initialize the CoreApplication.

        Args:
            settings: Configuration settings instance.
            lightshow: Optional pre-instantiated LightShow model.
        """
        super().__init__()
        self.settings = settings

        # Load standard LightShow state model
        if lightshow is not None:
            self.lightshow = lightshow
            self.lightshow.app = typing.cast(typing.Any, self)
        else:
            self.lightshow = LightShow(typing.cast(typing.Any, self))

        # Initialize engines and control backends as None
        self.backend = None
        self.engine = None
        self.midi = None
        self.osc = None
        self.blackout_active = False
        self.main_fader_level = 1.0

        # For crossfade
        self.crossfade = CrossFade(self)

        # Command line logical state helper
        self.commandline = CoreCommandLine(typing.cast(typing.Any, self))

        # Action and Undo/Redo plumbing layers
        self.action_registry = ActionRegistry(typing.cast(typing.Any, self))
        self.history = HistoryManager(typing.cast(typing.Any, self))
        self.live_state = LiveParameterState()
        self.effects_engine = EffectsEngine(
            app=typing.cast(typing.Any, self), lightshow=self.lightshow
        )
        self.sneak_controller = SneakController(typing.cast(typing.Any, self))

        # Logical selection states
        self.live_selection = SelectionManager(
            commandline=self.commandline,
            on_changed_callback=self._on_live_selection_changed,
            history_manager=self.history,
            get_level_callback=self.get_channel_level,
        )
        self.selected_cue: typing.Optional[tuple[float, int]] = None
        self.selected_group: typing.Optional[float] = None
        self.address_check: typing.Optional[tuple[int, int, int]] = None
        self.channel_check: typing.Optional[tuple[int, float, float]] = None
        self.zoom_level: float = 1.0
        self.dark_theme: bool = True
        self.tabs: CoreTabs = CoreTabs(typing.cast(typing.Any, self))
        self._is_zooming: bool = False
        self._zoom_start_level: float = 1.0
        self._zoom_timer: typing.Optional[threading.Timer] = None

        # Auto-register action classes from the actions package
        self._register_actions()

    def step_address_check(self, delta: int) -> bool:
        """Step active Address Check to next (+1) or previous (-1) DMX address."""
        if self.address_check is None or delta == 0:
            return False

        univ, out, dmx_level = self.address_check
        universes = sorted(self.lightshow.patch.universes) or [univ]
        if univ not in universes:
            universes = sorted({*universes, univ})

        step_dir = 1 if delta > 0 else -1
        next_univ = univ
        next_out = out + step_dir

        if next_out > 512:
            idx = universes.index(univ)
            if idx + 1 < len(universes):
                next_univ = universes[idx + 1]
                next_out = 1
            else:
                next_out = 512
        elif next_out < 1:
            idx = universes.index(univ)
            if idx - 1 >= 0:
                next_univ = universes[idx - 1]
                next_out = 512
            else:
                next_out = 1

        if (next_univ, next_out) != (univ, out):
            self.action_registry.execute(
                "dmx.test_output",
                [(next_out, next_univ)],
                level=dmx_level,
                release_targets=[(out, univ)],
            )
            self.address_check = (next_univ, next_out, dmx_level)

        self.commandline.set_string(self.format_address_check_command())
        return True

    def format_address_check_command(self) -> str:
        """Format the active Address Check state for the command line display."""
        if self.address_check is None:
            return ""
        univ, out, dmx_level = self.address_check
        if dmx_level >= 255:
            lvl_str = "FULL"
        elif typing.cast(typing.Any, self.settings).get_boolean("percent"):
            lvl_str = str(int(round((dmx_level / 255.0) * 100)))
        else:
            lvl_str = str(dmx_level)
        return f"ADDRESS {univ}/{out} AT {lvl_str}"

    def clear_address_check(self) -> None:
        """Exit Address Check mode and restore the active test address."""
        if self.address_check is None:
            return
        univ, out, _lvl = self.address_check
        self.address_check = None
        self.action_registry.execute("dmx.test_output", [(out, univ)], level=0)

    def get_default_channel_check_level(self) -> float:
        """Return default Channel Check percentage (0.0-100.0, default 80.0)."""
        try:
            settings = typing.cast(typing.Any, self.settings)
            props = getattr(settings, "props", None)
            schema = getattr(props, "settings_schema", None)
            if schema is not None and callable(getattr(schema, "has_key", None)):
                if not schema.has_key("channel-check-level"):
                    return 80.0
            val = settings.get_double("channel-check-level")
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return max(0.0, min(100.0, float(val)))
        except (AttributeError, TypeError, ValueError):
            pass
        return 80.0

    def get_channel_user_level(self, channel: int) -> float:
        """Return raw user override level (-1.0 if released) for 1-based *channel*."""
        backend = getattr(self, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            try:
                return float(backend.dmx.levels["user"][channel - 1])
            except (IndexError, TypeError, KeyError):
                pass
        return -1.0

    def _get_channel_check_targets(self) -> list[int]:
        """Return sorted patched channel IDs, or all channels if patch is empty."""
        patched = sorted(self.lightshow.patch.devices.keys())
        if patched:
            return patched
        return list(range(1, MAX_CHANNELS + 1))

    def step_channel_check(self, delta: int) -> bool:
        """Step active Channel Check to next (+1) or previous (-1) channel."""
        if self.channel_check is None or delta == 0:
            return False

        curr_ch, test_norm, old_user = self.channel_check
        targets = self._get_channel_check_targets()
        if not targets:
            return False

        if curr_ch in targets:
            idx = targets.index(curr_ch)
            step = 1 if delta > 0 else -1
            next_ch = targets[max(0, min(len(targets) - 1, idx + step))]
        else:
            next_ch = targets[0]

        if next_ch != curr_ch:
            self.action_registry.execute("channel.set_level", curr_ch, old_user)
            next_old = self.get_channel_user_level(next_ch)
            self.action_registry.execute("channel.set_level", next_ch, test_norm)
            self.channel_check = (next_ch, test_norm, next_old)

        self.commandline.set_string(self.format_channel_check_command())
        return True

    def clear_channel_check(self) -> None:
        """Exit Channel Check mode and restore the tested channel's previous level."""
        if self.channel_check is None:
            return
        ch, _test_norm, old_user = self.channel_check
        self.channel_check = None
        self.action_registry.execute("channel.set_level", ch, old_user)

    def format_channel_check_command(self) -> str:
        """Format the active Channel Check state for the command line display."""
        if self.channel_check is None:
            return ""
        ch, test_norm, _old = self.channel_check
        if test_norm >= 1.0:
            lvl_str = "FULL"
        elif typing.cast(typing.Any, self.settings).get_boolean("percent"):
            lvl_str = str(int(round(test_norm * 100.0)))
        else:
            lvl_str = str(int(round(test_norm * 255.0)))
        return f"CHANNEL {ch} CHECK AT {lvl_str}"

    @property
    def selected_channels(self) -> list[int]:
        """Get the live selection channels."""
        return self.live_selection.selected_channels

    @selected_channels.setter
    def selected_channels(self, value: list[int]) -> None:
        """Set the live selection channels."""
        self.live_selection.selected_channels = value

    @property
    def last_selected_channel(self) -> typing.Optional[int]:
        """Get the last selected live channel."""
        return self.live_selection.last_selected_channel

    @last_selected_channel.setter
    def last_selected_channel(self, value: typing.Optional[int]) -> None:
        """Set the last selected live channel."""
        self.live_selection.last_selected_channel = value

    def _on_live_selection_changed(self, channels: list[int]) -> None:
        """Propagate live selection changes to listeners."""
        if self.address_check is not None:
            self.clear_address_check()
        if self.channel_check is not None:
            self.clear_channel_check()
        self.emit("channels.selected_changed", channels)

    def get_channel_level(self, channel: int) -> int:
        """Get the current level of a channel in the active backend/dmx state."""
        backend = getattr(self, "backend", None)
        if backend and backend.dmx:
            try:
                return int(backend.dmx.levels["user"][channel - 1])
            except (IndexError, TypeError, KeyError):
                pass
        return 0

    def get_artnet_devices(self) -> list[list[str]]:
        """Return a thread-safe snapshot of discovered Art-Net devices."""
        if self.engine is not None:
            return self.engine.get_artnet_devices_snapshot()
        return []

    def _register_actions(self) -> None:
        """Register all concrete actions from the actions package."""
        register_all_actions(self.action_registry)

    def init_engine(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        hz: float = 44.0,
        monitor_port: int | None = None,
        monitor_fps: float = 15.0,
        no_listen: bool = False,
        loopback: bool = False,
        no_transmit: bool = False,
    ) -> CoreEngine:
        """Create the CoreEngine bound to the lightshow UniverseMap.

        Args:
            hz: Output refresh frequency in Hz.
            monitor_port: Optional ZMQ PUB port for DMX monitoring.
            monitor_fps: Monitor update rate in FPS.
            no_listen: Disable incoming network listeners if True.
            loopback: Force loopback IP for network output if True.
            no_transmit: Disable actual network/hardware transmission if True.

        Returns:
            The CoreEngine instance attached to this application.
        """
        if self.engine is not None:
            return self.engine

        # pylint: disable=import-outside-toplevel
        from olc.dmx_engine.engine import CoreEngine

        self.engine = CoreEngine(
            self.lightshow.universe_map,
            hz=hz,
            monitor_port=monitor_port,
            monitor_fps=monitor_fps,
            no_listen=no_listen,
            loopback=loopback,
            no_transmit=no_transmit,
        )
        if self.backend is not None:
            self.backend.bind_engine(typing.cast(typing.Any, self.engine))
        return self.engine

    def init_midi(
        self, on_ports_changed: typing.Optional[typing.Callable[[], None]] = None
    ) -> Midi:
        """Create the MIDI controller (if needed) and register default bindings.

        Args:
            on_ports_changed: Optional callback invoked when MIDI ports change.

        Returns:
            The MIDI controller attached to this application.
        """
        if self.midi is not None:
            return self.midi

        # pylint: disable=import-outside-toplevel
        from olc.controllers.midi import Midi

        self.midi = Midi(typing.cast(typing.Any, self), on_ports_changed)
        for name, note in [
            ("playback.go", 94),
            ("playback.go_back", 86),
            ("playback.pause", 93),
            ("playback.sequence_minus", 91),
            ("playback.sequence_plus", 92),
        ]:
            self.action_registry.register_binding(
                name, MidiBinding(name, "note", 0, note)
            )
        self.midi.messages.lcd.show_faders()
        return self.midi

    def init_osc(self) -> Osc:
        """Create the OSC controller (if needed) and register default bindings.

        Returns:
            The OSC controller attached to this application.
        """
        if self.osc is not None:
            return self.osc

        # pylint: disable=import-outside-toplevel
        from olc.controllers.osc import Osc

        self.osc = Osc(typing.cast(typing.Any, self))
        for name in (
            "playback.go",
            "playback.go_back",
            "playback.pause",
            "playback.sequence_minus",
            "playback.sequence_plus",
        ):
            self.action_registry.register_binding(
                name, OscBinding(name, f"/olc/{name.replace('.', '/')}")
            )
        return self.osc

    def start(self) -> None:
        """Start backend hardware and communications services."""
        self.backend = DMXBackend(self.lightshow)
        if self.engine:
            self.engine.start()
        if self.osc is None:
            self.init_osc()
        if self.midi is None:
            try:
                self.init_midi()
            except Exception as err:  # pylint: disable=broad-exception-caught
                print(f"[MIDI] Unable to initialize MIDI: {err}")

    def stop(self) -> None:
        """Gracefully stop DMX, OSC, and MIDI services."""
        self.effects_engine.stop_all()
        if self.backend:
            self.backend.stop()
        if self.osc:
            self.osc.stop()
        if self.midi:
            self.midi.stop()
        if self.engine:
            self.engine.stop()

    def zoom(self, direction: str) -> None:
        """Adjust zoom level with debouncing, emitting events in real-time.

        Args:
            direction: Zoom direction, "in" or "out".
        """
        if not self._is_zooming:
            self._is_zooming = True
            self._zoom_start_level = self.zoom_level

        current_zoom = self.zoom_level
        if direction == "in":
            new_zoom = min(current_zoom + 0.05, 2.0)
        else:
            new_zoom = max(current_zoom - 0.05, 0.5)

        self.zoom_level = new_zoom
        self.emit("gui.zoom_changed", new_zoom)

        if self._zoom_timer is not None:
            self._zoom_timer.cancel()

        self._zoom_timer = threading.Timer(
            self._ZOOM_DEBOUNCE_SECONDS, self._finalize_zoom
        )
        self._zoom_timer.start()

    def _finalize_zoom(self) -> None:
        """Callback to finalize continuous zoom by executing Core Action."""
        self._is_zooming = False
        self._zoom_timer = None
        final_zoom = self.zoom_level
        self.zoom_level = self._zoom_start_level
        self.action_registry.execute("gui.zoom", final_zoom)

    def get_channel_composite_level(
        self,
        channel_idx: int,
        *,
        curr_resolved: ResolvedState | None = None,
        prev_resolved: ResolvedState | None = None,
    ) -> tuple[float, dict[str, float]]:
        """Return (level, color_level) for 0-based *channel_idx* from DMX backend."""
        if self.backend is None:
            return (0.0, {})
        if curr_resolved is None and prev_resolved is None:
            return self.backend.dmx.get_composite_level(channel_idx)
        try:
            return self.backend.dmx.get_composite_level(
                channel_idx,
                curr_resolved=curr_resolved,
                prev_resolved=prev_resolved,
            )
        except TypeError:
            return self.backend.dmx.get_composite_level(channel_idx)

    def get_main_fader_value(self) -> float:
        """Return the current Main Fader value [0.0..1.0]."""
        if self.backend is None:
            return 1.0
        return float(self.backend.dmx.main_fader.value)

    def get_dmx_frame_level(self, universe_idx: int, offset: int) -> int | None:
        """Return DMX frame value for *universe_idx* and 0-based *offset*."""
        if self.backend is None:
            return None
        frame = self.backend.dmx.frame
        if 0 <= universe_idx < len(frame) and 0 <= offset < len(frame[universe_idx]):
            return int(frame[universe_idx][offset])
        return None

    def get_user_channel_level(self, channel_idx: int) -> float:
        """Return the manual user level for 0-based *channel_idx* (-1.0 if unset)."""
        if self.backend is None:
            return -1.0
        user_levels = self.backend.dmx.levels.get("user")
        if user_levels is not None and 0 <= channel_idx < len(user_levels):
            return float(user_levels[channel_idx])
        return -1.0

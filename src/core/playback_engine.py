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
"""Central sequence playback engine with strict main vs secondary isolation."""

from __future__ import annotations

import threading
import time
import typing
from dataclasses import dataclass
from enum import Enum

from olc.core.playback_arbitrator import PlaybackPriority

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.sequence import Sequence


class RunnerState(str, Enum):
    """Runtime execution state of one SequenceRunner."""

    IDLE = "idle"
    ACTIVE = "active"
    FADING = "fading"
    PAUSED = "paused"
    RELEASING = "releasing"


@dataclass(frozen=True)
class PlaybackRunnerSnapshot:
    """Immutable real-time telemetry snapshot for one Sequence."""

    seq_index: float
    name: str
    is_main: bool
    state: RunnerState
    position: int
    active_cue: float | None
    active_cue_text: str
    next_cue: float | None
    next_cue_text: str
    fade_progress: float
    fade_remaining: float
    fader_level: float
    priority: PlaybackPriority
    htp_intensity: bool
    owned_channels_count: int
    assigned_fader: str


@dataclass
class SequenceRunner:
    """Per-sequence runtime state tracked by PlaybackEngine."""

    seq_index: float
    state: RunnerState = RunnerState.IDLE
    fade_progress: float = 0.0
    fade_remaining: float = 0.0


@dataclass
class _ActiveReleaseFade:
    """State for an active progressive release fade."""

    seq_index: float
    start_time: float
    duration: float
    start_level: float


class PlaybackEngine:
    """Coordinates concurrent SequenceRunners and configurable Main Sequence."""

    def __init__(self, app: CoreApplication) -> None:
        self.app = app
        self._lock = threading.RLock()
        self._main_sequence_index: float = 1.0
        self._runners: dict[float, SequenceRunner] = {}
        self._release_fades: dict[float, _ActiveReleaseFade] = {}
        self._tick_interval: float = 0.025  # 40 Hz
        self._tick_stop = threading.Event()
        self._tick_thread: threading.Thread | None = None

    @property
    def main_sequence_index(self) -> float:
        """Index of the sequence currently bound to CrossFade & main header."""
        with self._lock:
            ws = getattr(getattr(self.app, "lightshow", None), "workspace", None)
            if isinstance(ws, dict) and "main_sequence_index" in ws:
                return float(ws["main_sequence_index"])
            return self._main_sequence_index

    @property
    def main_sequence(self) -> Sequence | None:
        """Resolve the current Main Sequence (fallback to lightshow.main_playback)."""
        ls = getattr(self.app, "lightshow", None)
        if ls is None:
            return None
        idx = self.main_sequence_index
        if idx == 1.0:
            return getattr(ls, "main_playback", None)
        seq = ls.get_sequence(idx) if hasattr(ls, "get_sequence") else None
        return seq if seq is not None else getattr(ls, "main_playback", None)

    def is_main_sequence(self, seq_index: float) -> bool:
        """Return True iff *seq_index* is the currently configured Main Sequence."""
        main_seq = self.main_sequence
        if main_seq is not None:
            return float(main_seq.index) == float(seq_index)
        return float(seq_index) == self.main_sequence_index

    def _resolve_sequence(self, seq_index: float) -> Sequence | None:
        ls = getattr(self.app, "lightshow", None)
        if ls is None:
            return None
        idx = float(seq_index)
        if idx == 1.0:
            return getattr(ls, "main_playback", None)
        return ls.get_sequence(idx) if hasattr(ls, "get_sequence") else None

    def set_main_sequence(self, seq_index: float) -> bool:
        """Set which sequence drives CrossFade and the main window playback UI."""
        idx = float(seq_index)
        target_seq = self._resolve_sequence(idx)
        if target_seq is None:
            return False
        with self._lock:
            self._main_sequence_index = idx
            ls = getattr(self.app, "lightshow", None)
            if ls is not None and isinstance(getattr(ls, "workspace", None), dict):
                ls.workspace["main_sequence_index"] = idx
        if hasattr(target_seq, "update_channels"):
            target_seq.update_channels()
        if hasattr(self.app, "emit"):
            self.app.emit("playback.main_sequence_changed", idx)
        return True

    def get_runner(self, seq_index: float) -> SequenceRunner:
        """Return (creating if needed) the SequenceRunner for *seq_index*."""
        key = float(seq_index)
        with self._lock:
            runner = self._runners.get(key)
            if runner is None:
                runner = SequenceRunner(seq_index=key)
                self._runners[key] = runner
            return runner

    def notify_runner_state(
        self,
        seq_index: float,
        state: RunnerState,
        *,
        fade_progress: float = 0.0,
        fade_remaining: float = 0.0,
    ) -> None:
        """Update runner telemetry and emit ``playback.runner_changed``."""
        key = float(seq_index)
        with self._lock:
            runner = self.get_runner(key)
            runner.state = state
            runner.fade_progress = max(0.0, min(1.0, float(fade_progress)))
            runner.fade_remaining = max(0.0, float(fade_remaining))
        if hasattr(self.app, "emit"):
            self.app.emit("playback.runner_changed", key)

    def clear(self) -> None:
        """Reset all runners, stop worker, and restore Main Sequence to 1.0."""
        self.stop_worker()
        with self._lock:
            self._release_fades.clear()
            self._runners.clear()
            self._main_sequence_index = 1.0

    def stop_worker(self) -> None:
        """Stop the background 40 Hz tick thread if running."""
        self._tick_stop.set()
        with self._lock:
            thread = self._tick_thread
            self._tick_thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _ensure_tick_worker(self) -> None:
        """Start the background 40 Hz tick thread if not already alive."""
        with self._lock:
            if self._tick_thread is None or not self._tick_thread.is_alive():
                self._tick_stop.clear()
                self._tick_thread = threading.Thread(
                    target=self._tick_loop,
                    name="playback-engine-tick",
                    daemon=True,
                )
                self._tick_thread.start()

    def _tick_loop(self) -> None:
        """Run 40 Hz ticks while release fades remain active."""
        while not self._tick_stop.is_set():
            has_work = self.tick()
            if not has_work:
                with self._lock:
                    if not self._release_fades:
                        self._tick_thread = None
                        return
            self._tick_stop.wait(self._tick_interval)

    def cancel_release_fade(self, seq_index: float) -> bool:
        """Cancel an active progressive release fade for *seq_index*."""
        key = float(seq_index)
        with self._lock:
            fade = self._release_fades.pop(key, None)
        if fade is None:
            return False
        arb = getattr(self.app, "playback_arbitrator", None)
        if arb is not None:
            seq = self._resolve_sequence(key)
            restore_level = (
                float(getattr(seq, "fader_level", fade.start_level))
                if seq is not None
                else fade.start_level
            )
            composed = arb.set_fader_level(key, restore_level)
            if seq is not None:
                from olc.show.sequence_threads import apply_arbitrated_output

                apply_arbitrated_output(self.app, seq.backend, seq.patch, composed)
        return True

    def tick(self, now: float | None = None) -> bool:
        """Advance all active release fades by one tick.

        Returns True if any fades remain active after this tick.
        """
        current_time = time.monotonic() if now is None else float(now)
        with self._lock:
            fades = list(self._release_fades.values())
        if not fades:
            return False

        from olc.show.sequence_threads import apply_arbitrated_output

        arb = getattr(self.app, "playback_arbitrator", None)
        completed: list[_ActiveReleaseFade] = []

        for fade in fades:
            with self._lock:
                if fade.seq_index not in self._release_fades:
                    continue
            elapsed = max(0.0, current_time - fade.start_time)
            progress = min(1.0, elapsed / fade.duration) if fade.duration > 0 else 1.0
            remaining = max(0.0, fade.duration - elapsed)
            if progress >= 1.0:
                completed.append(fade)
                continue

            seq = self._resolve_sequence(fade.seq_index)
            if seq is None:
                completed.append(fade)
                continue

            if arb is not None:
                level = fade.start_level * (1.0 - progress)
                composed = arb.set_fader_level(fade.seq_index, level)
                apply_arbitrated_output(self.app, seq.backend, seq.patch, composed)

            self.notify_runner_state(
                fade.seq_index,
                RunnerState.RELEASING,
                fade_progress=progress,
                fade_remaining=remaining,
            )

        for fade in completed:
            with self._lock:
                active = self._release_fades.get(fade.seq_index)
                if active is not fade:
                    continue
                self._release_fades.pop(fade.seq_index, None)
            seq = self._resolve_sequence(fade.seq_index)
            if seq is not None:
                seq.release(fade_time=0.0)
                if arb is not None:
                    arb.set_fader_level(fade.seq_index, fade.start_level)

        with self._lock:
            return bool(self._release_fades)

    def go(self, seq_index: float) -> bool:
        """Trigger Go on *seq_index*."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return False
        seq.do_go(None)
        return True

    def go_back(self, seq_index: float) -> bool:
        """Trigger Go Back on *seq_index*."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return False
        return bool(seq.go_back(None, None))

    def goto(
        self,
        seq_index: float,
        cue: str | float,
        override_time: float | None = None,
    ) -> bool:
        """Jump *seq_index* to *cue*."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return False
        seq.goto(str(cue), override_time=override_time)
        return True

    def pause(self, seq_index: float) -> bool:
        """Pause or resume *seq_index*."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return False
        seq.pause(None, None)
        return True

    def release(self, seq_index: float, fade_time: float | None = None) -> bool:
        """Release *seq_index* immediately or progressively over *fade_time*."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return False
        key = float(seq.index)
        eff_time = (
            float(fade_time)
            if fade_time is not None
            else float(getattr(seq, "release_time", 0.0) or 0.0)
        )
        if eff_time <= 0.0:
            with self._lock:
                self._release_fades.pop(key, None)
            seq.release(fade_time=0.0)
            return True

        seq.stop()
        seq.on_go = False
        start_level = float(getattr(seq, "fader_level", 1.0))
        now = time.monotonic()
        with self._lock:
            self._release_fades[key] = _ActiveReleaseFade(
                seq_index=key,
                start_time=now,
                duration=eff_time,
                start_level=start_level,
            )
            self._ensure_tick_worker()
        self.notify_runner_state(
            key,
            RunnerState.RELEASING,
            fade_progress=0.0,
            fade_remaining=eff_time,
        )
        return True

    def assert_sequence(self, seq_index: float) -> bool:
        """Assert *seq_index* to reclaim parameter ownership."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return False
        seq.assert_playback()
        return True

    def pause_all(self) -> list[float]:
        """Pause all sequences currently fading."""
        paused: list[float] = []
        ls = getattr(self.app, "lightshow", None)
        if ls is None:
            return paused
        for seq in (ls.main_playback, *ls.sequences):
            if (
                getattr(seq, "on_go", False)
                and getattr(seq, "thread", None) is not None
            ):
                if not seq.thread.pause.is_set():
                    seq.pause(None, None)
                    paused.append(float(seq.index))
        return paused

    def release_all(self) -> list[float]:
        """Release all active sequences in PlaybackArbitrator."""
        arb = getattr(self.app, "playback_arbitrator", None)
        active = arb.active_sequences() if arb is not None else []
        released: list[float] = []
        for idx in active:
            if self.release(idx):
                released.append(float(idx))
        return released

    def _find_assigned_fader(self, seq_index: float) -> str:
        ls = getattr(self.app, "lightshow", None)
        fb = getattr(ls, "fader_bank", None) if ls is not None else None
        if fb is None:
            return ""
        for page, faders in fb.faders.items():
            for idx, fader in faders.items():
                contents = getattr(fader, "contents", None)
                if contents is not None and float(
                    getattr(contents, "index", -1)
                ) == float(seq_index):
                    return f"P{page}-F{idx}"
        return ""

    def get_runner_snapshot(self, seq_index: float) -> PlaybackRunnerSnapshot | None:
        """Build an immutable PlaybackRunnerSnapshot for *seq_index*."""
        seq = self._resolve_sequence(seq_index)
        if seq is None:
            return None
        arb = getattr(self.app, "playback_arbitrator", None)
        arb_state = arb.get_state(seq.index) if arb is not None else None
        runner = self.get_runner(seq.index)

        state = runner.state
        if state is RunnerState.IDLE and arb_state is not None and arb_state.active:
            state = RunnerState.ACTIVE
        elif state is RunnerState.ACTIVE and (
            arb_state is None or not arb_state.active
        ):
            state = RunnerState.IDLE

        pos = int(getattr(seq, "position", 0))
        steps = getattr(seq, "steps", [])
        active_cue_num: float | None = None
        active_cue_txt = ""
        if 0 < pos < len(steps) - 1:
            cue = getattr(steps[pos], "cue", None)
            if cue is not None:
                active_cue_num = float(cue.number)
                active_cue_txt = str(getattr(cue, "text", "") or "")
        elif (
            arb_state is not None
            and arb_state.active
            and arb_state.cue_number is not None
        ):
            active_cue_num = float(arb_state.cue_number)

        next_cue_num: float | None = None
        next_cue_txt = ""
        next_pos = pos + 1
        if 0 < next_pos < len(steps) - 1:
            ncue = getattr(steps[next_pos], "cue", None)
            if ncue is not None:
                next_cue_num = float(ncue.number)
                next_cue_txt = str(getattr(ncue, "text", "") or "")

        owned_count = 0
        if arb is not None:
            composed = arb.compose()
            owned_count = sum(
                1
                for o_seq, _cue in composed.owners.values()
                if o_seq == float(seq.index)
            )

        fader_lvl = arb_state.fader_level if arb_state is not None else 1.0
        return PlaybackRunnerSnapshot(
            seq_index=float(seq.index),
            name=str(getattr(seq, "text", "") or f"Seq {int(seq.index)}"),
            is_main=self.is_main_sequence(seq.index),
            state=state,
            position=pos,
            active_cue=active_cue_num,
            active_cue_text=active_cue_txt,
            next_cue=next_cue_num,
            next_cue_text=next_cue_txt,
            fade_progress=runner.fade_progress,
            fade_remaining=runner.fade_remaining,
            fader_level=fader_lvl,
            priority=getattr(seq, "priority", PlaybackPriority.NORMAL),
            htp_intensity=bool(getattr(seq, "htp_intensity", True)),
            owned_channels_count=owned_count,
            assigned_fader=self._find_assigned_fader(seq.index),
        )

    def get_all_runner_snapshots(
        self, *, active_only: bool = False
    ) -> list[PlaybackRunnerSnapshot]:
        """Return snapshots for all sequences (optionally only non-IDLE ones)."""
        ls = getattr(self.app, "lightshow", None)
        if ls is None:
            return []
        seqs = [ls.main_playback, *list(getattr(ls, "sequences", []))]
        seqs.sort(key=lambda s: float(s.index))
        snapshots: list[PlaybackRunnerSnapshot] = []
        for seq in seqs:
            snap = self.get_runner_snapshot(seq.index)
            if snap is None:
                continue
            if active_only and snap.state is RunnerState.IDLE:
                continue
            snapshots.append(snap)
        return snapshots

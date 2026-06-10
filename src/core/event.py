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


class EventDispatcher:
    """A lightweight, synchronous, and thread-safe event dispatcher.

    Allows different parts of the application (Core, MIDI, OSC, GTK) to
    communicate via decoupled publish/subscribe events without graphical
    loop dependencies.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listeners: dict[str, list[typing.Callable[..., None]]] = {}

    def subscribe(self, event_name: str, callback: typing.Callable[..., None]) -> None:
        """Subscribe a callback to an event name.

        Args:
            event_name: The name of the event to listen to.
            callback: The callable to invoke when the event is emitted.
        """
        with self._lock:
            if event_name not in self._listeners:
                self._listeners[event_name] = []
            self._listeners[event_name].append(callback)

    def unsubscribe(
        self, event_name: str, callback: typing.Callable[..., None]
    ) -> None:
        """Unsubscribe a callback from an event name.

        Args:
            event_name: The name of the event.
            callback: The callback to remove.
        """
        with self._lock:
            if event_name in self._listeners:
                try:
                    self._listeners[event_name].remove(callback)
                except ValueError:
                    pass

    def emit(self, event_name: str, *args: object, **kwargs: object) -> None:
        """Emit an event to all subscribers synchronously on the calling thread.

        Args:
            event_name: The name of the event.
            *args: Arguments to pass to the callbacks.
            **kwargs: Keyword arguments to pass to the callbacks.
        """
        with self._lock:
            # Copy listeners to avoid race conditions or modifications
            # to subscriptions during execution of the callbacks.
            listeners = list(self._listeners.get(event_name, []))

        for callback in listeners:
            try:
                callback(*args, **kwargs)
            except Exception as err:  # pylint: disable=broad-exception-caught
                print(f"[EventDispatcher] Error in callback for '{event_name}': {err}")

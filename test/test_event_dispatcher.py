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
"""Unit tests for EventDispatcher."""

from __future__ import annotations

from olc.core.event import EventDispatcher


def test_subscribe_and_emit() -> None:
    """Test standard subscribe and emit cycle."""
    dispatcher = EventDispatcher()
    received_data = []

    def callback(value: int) -> None:
        received_data.append(value)

    dispatcher.subscribe("test.event", callback)
    dispatcher.emit("test.event", 42)

    assert received_data == [42]


def test_unsubscribe() -> None:
    """Test unsubscribing a listener."""
    dispatcher = EventDispatcher()
    received_data = []

    def callback(value: int) -> None:
        received_data.append(value)

    dispatcher.subscribe("test.event", callback)
    dispatcher.emit("test.event", 10)
    dispatcher.unsubscribe("test.event", callback)
    dispatcher.emit("test.event", 20)

    assert received_data == [10]


def test_multiple_listeners() -> None:
    """Test that multiple listeners receive the event."""
    dispatcher = EventDispatcher()
    calls = {"a": 0, "b": 0}

    dispatcher.subscribe("test.event", lambda: calls.__setitem__("a", calls["a"] + 1))
    dispatcher.subscribe("test.event", lambda: calls.__setitem__("b", calls["b"] + 1))

    dispatcher.emit("test.event")

    assert calls["a"] == 1
    assert calls["b"] == 1


def test_callback_exception_isolation() -> None:
    """Test that an exception in one callback doesn't crash subsequent callbacks."""
    dispatcher = EventDispatcher()
    second_callback_called = False

    def crashing_callback() -> None:
        raise ValueError("Crashing deliberately")

    def second_callback() -> None:
        nonlocal second_callback_called
        second_callback_called = True

    dispatcher.subscribe("test.event", crashing_callback)
    dispatcher.subscribe("test.event", second_callback)

    # Should not raise exception
    dispatcher.emit("test.event")

    assert second_callback_called is True

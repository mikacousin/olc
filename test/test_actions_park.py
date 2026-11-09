# -*- coding: utf-8 -*-
"""Unit tests for Park actions and undo/redo."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication


def test_channel_park_and_unpark_actions() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)

    # 1. Park channel 5 at 80% (approx 204)
    app.action_registry.execute("channel.park", 5, 204)
    assert app.lightshow.park.is_channel_parked(5)
    assert app.lightshow.park.get_channel_park_level(5) == 204
    assert app.lightshow.park.total_parked_count() == 1

    # Undo
    app.history.undo()
    assert not app.lightshow.park.is_channel_parked(5)
    assert app.lightshow.park.total_parked_count() == 0

    # Redo
    app.history.redo()
    assert app.lightshow.park.is_channel_parked(5)
    assert app.lightshow.park.get_channel_park_level(5) == 204

    # 2. Unpark channel 5
    app.action_registry.execute("channel.unpark", 5)
    assert not app.lightshow.park.is_channel_parked(5)
    assert app.lightshow.park.total_parked_count() == 0

    # Undo unpark
    app.history.undo()
    assert app.lightshow.park.is_channel_parked(5)
    assert app.lightshow.park.get_channel_park_level(5) == 204


def test_address_park_and_unpark_actions() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)

    app.action_registry.execute("address.park", (1, 12), 255)
    assert app.lightshow.park.is_address_parked(1, 12)
    assert app.lightshow.park.get_address_park_level(1, 12) == 255

    app.history.undo()
    assert not app.lightshow.park.is_address_parked(1, 12)

    app.history.redo()
    assert app.lightshow.park.is_address_parked(1, 12)

    app.action_registry.execute("address.unpark", (1, 12))
    assert not app.lightshow.park.is_address_parked(1, 12)

    app.history.undo()
    assert app.lightshow.park.is_address_parked(1, 12)


def test_park_unpark_all_action() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)

    app.action_registry.execute("channel.park", [1, 2, 3], 100)
    app.action_registry.execute("address.park", [(1, 10), (2, 20)], 200)
    assert app.lightshow.park.total_parked_count() == 5

    app.action_registry.execute("park.unpark_all")
    assert app.lightshow.park.total_parked_count() == 0

    # Undo unpark all
    app.history.undo()
    assert app.lightshow.park.total_parked_count() == 5
    assert app.lightshow.park.get_channel_park_level(1) == 100
    assert app.lightshow.park.get_address_park_level(2, 20) == 200

    # Redo
    app.history.redo()
    assert app.lightshow.park.total_parked_count() == 0

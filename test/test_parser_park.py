# -*- coding: utf-8 -*-
"""Unit tests for parsing and executing PARK and UNPARK commands."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.core.parser.ast_nodes import (
    AddressParkCommandNode,
    AddressUnparkCommandNode,
    ChannelParkCommandNode,
    ChannelUnparkCommandNode,
    ParkUnparkAllCommandNode,
)
from olc.core.parser.executor import CommandExecutor
from olc.core.parser.parser import CommandParser


def test_parser_channel_park_and_unpark() -> None:
    parser = CommandParser()

    # 1 PARK
    node = parser.parse("1 PARK")
    assert isinstance(node, ChannelParkCommandNode)
    assert node.level is None

    # 1 THRU 5 PARK AT 80
    node = parser.parse("1 THRU 5 PARK AT 80")
    assert isinstance(node, ChannelParkCommandNode)
    assert node.level == 80.0

    # 1 PARK AT FULL
    node = parser.parse("1 PARK AT FULL")
    assert isinstance(node, ChannelParkCommandNode)
    assert node.level == 100.0

    # 1 UNPARK
    node = parser.parse("1 UNPARK")
    assert isinstance(node, ChannelUnparkCommandNode)

    # 1 THRU 5 PARK AT (standard EOS unpark syntax)
    node = parser.parse("1 THRU 5 PARK AT")
    assert isinstance(node, ChannelUnparkCommandNode)

    # PARK 1 AT 50
    node = parser.parse("PARK 1 AT 50")
    assert isinstance(node, ChannelParkCommandNode)
    assert node.level == 50.0

    # UNPARK 1 THRU 3
    node = parser.parse("UNPARK 1 THRU 3")
    assert isinstance(node, ChannelUnparkCommandNode)


def test_parser_address_park_and_unpark() -> None:
    parser = CommandParser()

    # ADDRESS 12 PARK AT 100
    node = parser.parse("ADDRESS 12 PARK AT 100")
    assert isinstance(node, AddressParkCommandNode)
    assert node.level == 100.0
    assert len(node.addresses.items) == 1

    # ADDRESS 2/15 PARK AT FULL
    node = parser.parse("ADDRESS 2/15 PARK AT FULL")
    assert isinstance(node, AddressParkCommandNode)
    assert node.level == 100.0

    # ADDRESS 1/1 THRU 10 PARK AT 50
    node = parser.parse("ADDRESS 1/1 THRU 10 PARK AT 50")
    assert isinstance(node, AddressParkCommandNode)
    assert node.level == 50.0

    # ADDRESS 2/15 UNPARK
    node = parser.parse("ADDRESS 2/15 UNPARK")
    assert isinstance(node, AddressUnparkCommandNode)

    # UNPARK ADDRESS 1/12
    node = parser.parse("UNPARK ADDRESS 1/12")
    assert isinstance(node, AddressUnparkCommandNode)

    # PARK ALL / UNPARK ALL
    node = parser.parse("PARK ALL")
    assert isinstance(node, ParkUnparkAllCommandNode)

    node = parser.parse("UNPARK ALL")
    assert isinstance(node, ParkUnparkAllCommandNode)


def test_executor_park_and_unpark() -> None:
    settings = MagicMock()
    app = CoreApplication(settings)
    parser = CommandParser()
    executor = CommandExecutor(app)

    # Execute 1 THRU 3 PARK AT 80
    node = parser.parse("1 THRU 3 PARK AT 80")
    res = executor.execute(node)
    assert res.success
    assert app.lightshow.park.is_channel_parked(1)
    assert app.lightshow.park.is_channel_parked(2)
    assert app.lightshow.park.is_channel_parked(3)
    assert app.lightshow.park.get_channel_park_level(1) == 204  # 80% of 255

    # Execute ADDRESS 1/10 THRU 12 PARK AT FULL
    node = parser.parse("ADDRESS 1/10 THRU 12 PARK AT FULL")
    res = executor.execute(node)
    assert res.success
    assert app.lightshow.park.is_address_parked(1, 10)
    assert app.lightshow.park.is_address_parked(1, 11)
    assert app.lightshow.park.is_address_parked(1, 12)
    assert app.lightshow.park.get_address_park_level(1, 10) == 255

    # Execute UNPARK ALL
    node = parser.parse("UNPARK ALL")
    res = executor.execute(node)
    assert res.success
    assert app.lightshow.park.total_parked_count() == 0

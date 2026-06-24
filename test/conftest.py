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
"""Configuration for Pytest."""

# pylint: disable=wrong-spelling-in-comment, wrong-spelling-in-docstring

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line option for GUI tests."""
    parser.addoption(
        "--run-gui",
        action="store_true",
        default=False,
        help="Run GUI behavioral tests",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Filter GUI tests if --run-gui option is not set."""
    if config.getoption("--run-gui"):
        # --run-gui option is set, run everything
        return

    skip_gui = pytest.mark.skip(
        reason="GUI behavioral tests require the --run-gui option to run."
    )
    for item in items:
        if "gui" in item.keywords:
            item.add_marker(skip_gui)

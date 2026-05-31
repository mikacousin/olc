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
# pylint: disable=protected-access, comparison-with-callable
from unittest.mock import MagicMock, patch

import numpy as np
from olc.define import MAX_CHANNELS, UNIVERSES
from olc.dmx import Dmx


def test_dmx_send_triggers_callbacks() -> None:
    """Test that Dmx.send() correctly identifies frame changes and triggers
    callbacks.
    """

    # Mock lightshow and app
    lightshow = MagicMock()
    lightshow.patch.is_patched.return_value = False
    lightshow.patch.is_patched_mask = np.zeros(MAX_CHANNELS, dtype=bool)
    lightshow.independents.dmx = np.zeros(MAX_CHANNELS, dtype=np.uint8)
    app = MagicMock()
    engine = MagicMock()
    lightshow.app = app
    app.engine = engine

    # Mock universe buffers in engine
    universe_mocks = {}
    for universe in UNIVERSES:
        univ_mock = MagicMock()
        univ_mock.array = [0] * 512
        def make_apply(m):  # noqa: ANN001,ANN202
            def apply_array(arr):  # noqa: ANN001,ANN202
                m.array[:] = list(arr)
            return apply_array
        univ_mock.apply_array.side_effect = make_apply(univ_mock)
        universe_mocks[universe] = univ_mock

    engine.universe.side_effect = lambda u: universe_mocks[u]

    # Initialize Dmx, patching RepeatedTimer to avoid starting actual background threads
    with patch("olc.dmx.RepeatedTimer") as mock_timer_class:
        dmx = Dmx(backend=None, lightshow=lightshow)
        mock_timer_class.assert_called_once()

    # Register output callback
    callback = MagicMock()
    dmx.add_output_callback(callback)

    # Mock GLib on the olc.dmx module
    mock_glib = MagicMock()
    with patch("olc.dmx.GLib", mock_glib):
        # Simulate change on Universe 1 (index 0) at address 0 and 10
        dmx.frame[0][0] = 255
        dmx.frame[0][10] = 128

        # Trigger send
        dmx.send()

        # Assert GLib.idle_add was called
        mock_glib.idle_add.assert_called_once()
        args, _ = mock_glib.idle_add.call_args
        assert args[0] == dmx.trigger_output_callbacks
        assert args[1] == UNIVERSES[0]
        assert args[2] == [0, 10]

        # Verify old_frame was updated
        assert dmx._old_frame[0][0] == 255
        assert dmx._old_frame[0][10] == 128

        # Verify engine.universe was updated
        assert engine.universe(UNIVERSES[0]).array[:] == list(dmx.frame[0])

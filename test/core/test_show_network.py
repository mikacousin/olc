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
from unittest.mock import MagicMock

from gi.repository import Gio
from olc.core.universe_config import Protocol, UniverseMap
from olc.files.file_type import FileType
from olc.files.import_file import ImportFile
from olc.files.olc.writer import OlcWriter


def test_universes_serialization_deserialization() -> None:
    """Verify that OLC universe network configurations are serialized/deserialized."""
    # pylint: disable=protected-access,too-many-statements
    # Setup mocks
    app = MagicMock()
    engine = MagicMock()
    app.engine = engine

    # Setup universe configurations
    umap = UniverseMap(5)
    # Universe 1: Art-Net only with custom net/sub and sync
    umap.enable_protocol(1, Protocol.ARTNET)
    umap[1].artnet.net = 3
    umap[1].artnet.sub = 4
    umap[1].artnet.sync_active = True

    # Universe 2: sACN only with custom priority and sync_address
    umap.enable_protocol(2, Protocol.SACN)
    umap[2].sacn.priority = 150
    umap[2].sacn.sync_address = 42

    engine.universe_map = umap
    engine._map = umap

    lightshow = MagicMock()
    lightshow.app = app

    # Serialize
    file_mock = MagicMock(spec=Gio.File)
    writer = OlcWriter(file_mock, lightshow)
    writer._universes()

    data = writer.data["universes"]
    assert "1" in data
    assert "ARTNET" in data["1"]["protocols"]
    assert data["1"]["artnet"]["net"] == 3
    assert data["1"]["artnet"]["sub"] == 4
    assert data["1"]["artnet"]["sync_active"] is True

    assert "2" in data
    assert "SACN" in data["2"]["protocols"]
    assert data["2"]["sacn"]["priority"] == 150
    assert data["2"]["sacn"]["sync_address"] == 42

    # Deserialization
    parser_data = MagicMock()
    parser_data.data = {"universes": {}}
    imported = MagicMock(spec=ImportFile)
    imported.data = parser_data
    imported.file_type = FileType.OLC
    imported.lightshow = lightshow

    # Prepare new clean UniverseMap for target engine
    target_umap = UniverseMap(5)
    target_engine = MagicMock()
    target_engine.universe_map = target_umap
    target_engine._map = target_umap
    app.engine = target_engine

    # Load serialized universes into parsed data
    parser_data.data["universes"] = data

    # Import
    ImportFile._do_import_universes(imported)

    # Verify reload_universe was called for the universes 1, 2, 3, 4
    assert target_engine.reload_universe.call_count == 4

    # Verify state was restored
    config1 = target_umap[1]
    assert Protocol.ARTNET in config1.protocols
    assert config1.artnet.net == 3
    assert config1.artnet.sub == 4
    assert config1.artnet.sync_active is True

    config2 = target_umap[2]
    assert Protocol.SACN in config2.protocols
    assert config2.sacn.priority == 150
    assert config2.sacn.sync_address == 42

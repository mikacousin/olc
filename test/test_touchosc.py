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
"""Tests for TouchOSC template generator."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zlib

from olc.core.backends.osc.touchosc import (
    COLOR_ACCENT_PURPLE,
    COLOR_CYAN_ACCENT,
    COLOR_GREEN_GO,
    COLOR_RED_DBO,
    TOSCNode,
    build_phone_template,
    build_tablet_template,
    create_button,
    create_fader,
    create_label,
    create_radial,
    create_xy_pad,
    export_tosc_file,
    generate_all_templates,
)


def test_tosc_node_creation() -> None:
    """Test TOSCNode properties, values, messages and XML serialization."""
    node = TOSCNode(node_type="BOX", name="test_box")
    node.set_property("frame", "rect", (10.0, 20.0, 100.0, 50.0))
    node.set_property("color", "color", (1.0, 0.5, 0.0, 1.0))
    node.set_property("interactive", "boolean", True)
    node.set_property("tag", "string", "Hello")
    node.values["x"] = 0.75
    node.add_osc_message(path="/olc/test", send=True, receive=False)

    elem = node.to_xml_element()
    xml_str = ET.tostring(elem, encoding="utf-8").decode("utf-8")
    root = ET.fromstring(xml_str)
    assert root.tag == "node"
    assert root.get("type") == "BOX"

    # Properties check (<property type="..."><key>...</key><value>...</value>)
    props = {p.findtext("key"): p for p in root.findall("./properties/property")}
    assert "frame" in props
    assert props["frame"].get("type") == "r"
    assert "color" in props
    assert props["color"].get("type") == "c"
    assert "interactive" in props
    assert props["interactive"].get("type") == "b"
    assert props["interactive"].findtext("value") == "1"
    assert "tag" in props
    assert props["tag"].get("type") == "s"
    assert props["tag"].findtext("value") == "Hello"

    # Values check (<value><key>x</key><default>0.75</default>...</value>)
    vals = {v.findtext("key"): v for v in root.findall("./values/value")}
    assert "x" in vals
    assert vals["x"].findtext("default") == "0.75"
    assert vals["x"].findtext("locked") == "0"

    # OSC messages check
    osc_path = root.find("./messages/osc/path/partial/value")
    assert osc_path is not None
    assert osc_path.text == "/olc/test"
    osc_conns = root.find("./messages/osc/connections")
    assert osc_conns is not None
    assert osc_conns.text == "1111111111"


def test_ui_element_helpers() -> None:
    """Test UI helper functions create well-formed nodes."""
    # Button
    btn = create_button(
        "btn_go", 0, 0, 80, 40, "GO", osc_path="/olc/key/go", color=COLOR_GREEN_GO
    )
    assert btn.node_type == "BUTTON"
    assert btn.properties["tag"][1] == "GO"
    assert btn.overlay_label is not None
    assert btn.overlay_label.values["text"] == "GO"
    assert btn.osc_messages[0]["path"] == "/olc/key/go"

    # Fader
    fader = create_fader(
        "fad_main", 0, 0, 60, 200, osc_path="/olc/mainfader", color=COLOR_RED_DBO
    )
    assert fader.node_type == "FADER"
    assert fader.osc_messages[0]["path"] == "/olc/mainfader"

    # Label
    lbl = create_label(
        "lbl_info", 0, 0, 120, 30, "Current Cue", osc_path="/olc/cue/active"
    )
    assert lbl.node_type == "LABEL"
    assert lbl.values["text"] == "Current Cue"

    # Radial
    rad = create_radial(
        "rad_pan", 0, 0, 70, 70, osc_path="/olc/wheel/pan", color=COLOR_CYAN_ACCENT
    )
    assert rad.node_type == "RADIAL"
    assert rad.osc_messages[0]["path"] == "/olc/wheel/pan"

    # XY Pad
    xy = create_xy_pad(
        "xy_pt",
        0,
        0,
        200,
        200,
        osc_path_x="/olc/selected/pan",
        osc_path_y="/olc/selected/tilt",
        color=COLOR_ACCENT_PURPLE,
    )
    assert xy.node_type == "XY"
    assert len(xy.osc_messages) == 2
    paths = [m["path"] for m in xy.osc_messages]
    assert "/olc/selected/pan" in paths
    assert "/olc/selected/tilt" in paths


def test_build_tablet_template() -> None:
    """Test Tablet template layout, tabs and dimensions."""
    root = build_tablet_template()
    assert root.node_type == "GROUP"
    assert root.properties["frame"][1] == (0.0, 0.0, 1024.0, 768.0)
    assert "script" in root.properties
    assert "sendOSC('/olc/fader/pageupdate', 1)" in str(root.properties["script"][1])

    # Must contain tab pager
    pager = next(c for c in root.children if c.node_type == "PAGER")
    assert pager is not None
    assert "script" in pager.properties
    assert "onValueChanged" in str(pager.properties["script"][1])

    # Must contain 6 tab groups
    tab_names = [c.name for c in pager.children]
    expected_tabs = [
        "1. Playback",
        "2. Circuits",
        "3. Faders",
        "4. Asservis",
        "5. Couleur",
        "6. Clavier",
    ]
    for exp in expected_tabs:
        assert exp in tab_names

    # Check Channels tab has 24 cells
    ch_tab = next(c for c in pager.children if c.name == "2. Circuits")
    cell_nodes = [c for c in ch_tab.children if c.name and c.name.startswith("cell_")]
    assert len(cell_nodes) == 24

    # Check Faders tab has 10 playback faders
    fad_tab = next(c for c in pager.children if c.name == "3. Faders")
    faders = [c for c in fad_tab.children if c.node_type == "FADER"]
    assert len(faders) == 10


def test_build_phone_template() -> None:
    """Test Phone template layout, tabs and dimensions."""
    root = build_phone_template()
    assert root.node_type == "GROUP"
    assert root.properties["frame"][1] == (0.0, 0.0, 400.0, 800.0)

    # Must contain tab pager
    pager = next(c for c in root.children if c.node_type == "PAGER")
    assert pager is not None

    # Must contain 6 tabs
    tab_names = [c.name for c in pager.children]
    assert len(tab_names) == 6
    expected_tabs = [
        "Playback",
        "Circuits",
        "Faders",
        "Asservis",
        "Couleur",
        "Clavier",
    ]
    for exp in expected_tabs:
        assert exp in tab_names

    # Check Channels tab has 12 cells
    ch_tab = next(c for c in pager.children if c.name == "Circuits")
    cell_nodes = [c for c in ch_tab.children if c.name and c.name.startswith("cell_")]
    assert len(cell_nodes) == 12

    # Check Faders tab has 4 playback faders
    fad_tab = next(c for c in pager.children if c.name == "Faders")
    faders = [c for c in fad_tab.children if c.node_type == "FADER"]
    assert len(faders) == 4


def test_export_and_compression(tmp_path: object) -> None:
    """Test exporting to .tosc produces valid zlib compressed XML."""
    out_file = os.path.join(str(tmp_path), "test.tosc")
    node = build_phone_template()
    compressed = export_tosc_file(node, out_file)

    assert os.path.isfile(out_file)
    assert os.path.getsize(out_file) > 1000
    assert len(compressed) == os.path.getsize(out_file)

    # Verify zlib decompression
    decompressed = zlib.decompress(compressed).decode("utf-8")
    assert decompressed.startswith("<?xml")
    assert "<node " in decompressed

    # Verify valid XML
    parsed_root = ET.fromstring(decompressed)
    assert parsed_root.tag == "lexml"
    assert parsed_root.get("version") == "5"
    assert parsed_root.find("node") is not None


def test_generate_all_templates(tmp_path: object) -> None:
    """Test batch template generator produces both templates."""
    results = generate_all_templates(str(tmp_path))
    assert "tablet" in results
    assert "phone" in results
    assert os.path.isfile(results["tablet"])
    assert os.path.isfile(results["phone"])
    assert "OpenLightingConsole_Tablet.tosc" in results["tablet"]
    assert "OpenLightingConsole_Phone.tosc" in results["phone"]


def test_momentary_buttons_do_not_latch() -> None:
    """Ensure momentary buttons do not disable release reset in TouchOSC."""
    btn = create_button("go", 0, 0, 100, 50, "GO", "/olc/key/go", COLOR_GREEN_GO)
    # release property must be True (False latches buttons in TouchOSC)
    assert btn.properties["release"] == ("b", True)
    assert btn.properties["buttonType"] == ("i", 0)
    assert btn.osc_messages[0]["condition"] == "RISE"

    # Toggle button uses buttonType=1 and ANY condition with receive=True
    dbo = create_button(
        "dbo", 0, 0, 100, 50, "BLACKOUT", "/olc/blackout", COLOR_RED_DBO, is_toggle=True
    )
    assert dbo.properties["buttonType"] == ("i", 1)
    assert dbo.osc_messages[0]["condition"] == "ANY"
    assert dbo.osc_messages[0]["receive"] is True


def test_osc_delegate_momentary_release_and_touchosc_routes() -> None:
    """Test OSCDelegate ignores 0 release on keys and supports TouchOSC routes."""
    from unittest.mock import MagicMock

    from olc.core.app import CoreApplication
    from olc.core.backends.osc.delegate import OSCDelegate

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    # Momentary release (0.0) on keypad must be ignored
    delegate._1("/olc/key/1", [1.0])
    delegate._1("/olc/key/1", [0.0])
    assert app.commandline.get_string() == "1"

    # Clear on release (0.0) ignored, on press (1.0) clears
    delegate._clear("/olc/key/clear", [0.0])
    assert app.commandline.get_string() == "1"
    delegate._clear("/olc/key/clear", [1.0])
    assert app.commandline.get_string() == ""

    # Sync / pageupdate triggers full sync
    mock_engine.publish_osc.reset_mock()
    delegate._sub_launch("/olc/fader/pageupdate", [1.0])
    published_paths = [c[0][1] for c in mock_engine.publish_osc.call_args_list]
    assert "/olc/channels/page/label" in published_paths
    assert "/olc/fader/page/label" in published_paths
    assert "/olc/playback/active/cue" in published_paths

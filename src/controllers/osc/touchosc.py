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
"""TouchOSC template generator for Open Lighting Console.

Generates comprehensive, themed TouchOSC (.tosc) templates for both Tablet
and Smartphone form factors with full OSC two-way feedback.
"""

from __future__ import annotations

import os
import uuid
import xml.etree.ElementTree as ET
import zlib

type PropertyValue = str | int | float | bool | tuple[float, ...]

# Color Palette (Normalized RGBA 0.0..1.0)
COLOR_DARK_BG = (0.12, 0.12, 0.14, 1.0)
COLOR_PANEL_BG = (0.18, 0.18, 0.22, 1.0)
COLOR_TAB_ACTIVE = (0.24, 0.24, 0.28, 1.0)
COLOR_GREEN_GO = (0.18, 0.80, 0.44, 1.0)
COLOR_AMBER_PAUSE = (0.95, 0.61, 0.07, 1.0)
COLOR_RED_DBO = (0.91, 0.30, 0.24, 1.0)
COLOR_BLUE_SEL = (0.20, 0.60, 1.0, 1.0)
COLOR_GRAY_CTRL = (0.35, 0.35, 0.40, 1.0)
COLOR_WHITE_TEXT = (0.95, 0.95, 0.95, 1.0)
COLOR_ACCENT_PURPLE = (0.61, 0.35, 0.71, 1.0)
COLOR_CYAN_ACCENT = (0.15, 0.75, 0.85, 1.0)


_PROP_TYPE_MAP: dict[str, str] = {
    "b": "b",
    "boolean": "b",
    "bool": "b",
    "i": "i",
    "integer": "i",
    "int": "i",
    "f": "f",
    "float": "f",
    "s": "s",
    "string": "s",
    "str": "s",
    "c": "c",
    "color": "c",
    "r": "r",
    "rect": "r",
    "rectangle": "r",
}


def _fmt_num(val: float) -> str:
    """Format a floating point number cleanly for TouchOSC XML."""
    rounded = round(float(val), 4)
    if rounded.is_integer():
        return str(int(rounded))
    return str(rounded)


class TOSCNode:
    """Represents a TouchOSC XML layout node (Control, Group, or Pager)."""

    def __init__(
        self,
        node_type: str,
        name: str = "",
        node_id: str | None = None,
    ) -> None:
        self.node_type = node_type
        self.name = name
        self.node_id = node_id or str(uuid.uuid4())
        self.properties: dict[str, tuple[str, PropertyValue]] = {}
        self.values: dict[str, str | int | float | bool] = {}
        self.osc_messages: list[dict[str, str | bool | float]] = []
        self.children: list[TOSCNode] = []
        self.overlay_label: TOSCNode | None = None
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize standard TouchOSC properties and values per node type."""
        is_group_or_label = self.node_type in ("GROUP", "LABEL")
        self.set_property("background", "b", self.node_type != "LABEL")
        self.set_property("color", "c", (0.25, 0.25, 0.25, 1.0))
        self.set_property("cornerRadius", "f", 0.0 if is_group_or_label else 4.0)
        self.set_property("frame", "r", (0.0, 0.0, 100.0, 100.0))
        self.set_property(
            "grabFocus", "b", self.node_type in ("FADER", "RADIAL", "XY", "LABEL")
        )
        self.set_property("interactive", "b", not is_group_or_label)
        self.set_property("locked", "b", False)
        self.set_property("name", "s", self.name)
        self.set_property("orientation", "i", 0)
        self.set_property(
            "outline", "b", self.node_type in ("BUTTON", "FADER", "RADIAL", "XY")
        )
        self.set_property("outlineStyle", "i", 1)
        self.set_property("pointerPriority", "i", 0)
        self.set_property("shape", "i", 2 if self.node_type == "RADIAL" else 1)
        self.set_property("visible", "b", True)

        self.values["touch"] = "false"

        if self.node_type == "PAGER":
            self.set_property("tabLabels", "b", True)
            self.set_property("tabbar", "b", True)
            self.set_property("tabbarDoubleTap", "b", False)
            self.set_property("tabbarSize", "i", 40)
            self.set_property("textSizeOff", "i", 12)
            self.set_property("textSizeOn", "i", 14)
            self.values["page"] = "0"
        elif self.node_type == "BUTTON":
            self.set_property("buttonType", "i", 0)
            self.set_property("press", "b", True)
            self.set_property("release", "b", True)
            self.set_property("valuePosition", "b", False)
            self.values["x"] = "0"
        elif self.node_type == "FADER":
            self.set_property("bar", "b", True)
            self.set_property("barDisplay", "i", 0)
            self.set_property("centered", "b", False)
            self.set_property("cursor", "b", True)
            self.set_property("cursorDisplay", "i", 0)
            self.set_property("grid", "b", True)
            self.set_property("gridColor", "c", (0.0, 0.0, 0.0, 0.25))
            self.set_property("gridSteps", "i", 10)
            self.set_property("response", "i", 0)
            self.set_property("responseFactor", "i", 100)
            self.values["x"] = "0"
        elif self.node_type == "LABEL":
            self.set_property("textAlignH", "i", 2)
            self.set_property("textAlignV", "i", 2)
            self.set_property("textClip", "b", False)
            self.set_property("textColor", "c", COLOR_WHITE_TEXT)
            self.set_property("textLength", "i", 0)
            self.set_property("textSize", "i", 14)
            self.values["text"] = ""
        elif self.node_type == "RADIAL":
            self.set_property("centered", "b", False)
            self.set_property("grid", "b", True)
            self.set_property("gridSteps", "i", 20)
            self.set_property("inverted", "b", False)
            self.set_property("response", "i", 0)
            self.set_property("responseFactor", "i", 100)
            self.values["x"] = "0"
        elif self.node_type == "XY":
            self.set_property("cursor", "b", True)
            self.set_property("cursorDisplay", "i", 0)
            self.set_property("gridStepsX", "i", 10)
            self.set_property("gridStepsY", "i", 10)
            self.set_property("gridX", "b", True)
            self.set_property("gridY", "b", True)
            self.set_property("lines", "b", True)
            self.set_property("linesDisplay", "i", 0)
            self.set_property("lockX", "b", False)
            self.set_property("lockY", "b", False)
            self.set_property("response", "i", 0)
            self.set_property("responseFactor", "i", 100)
            self.values["x"] = "0.5"
            self.values["y"] = "0.5"

    def set_frame(self, x: float, y: float, w: float, h: float) -> None:
        """Set node position and bounding dimensions."""
        self.properties["frame"] = ("r", (x, y, w, h))

    def set_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        """Set primary RGBA color."""
        self.properties["color"] = ("c", (r, g, b, a))

    def set_text(self, text: str) -> None:
        """Set label text or caption."""
        if self.node_type in ("LABEL", "TEXT"):
            self.values["text"] = text
        else:
            self.properties["tag"] = ("s", text)

    def set_property(self, name: str, prop_type: str, value: PropertyValue) -> None:
        """Set a generic property with normalized TouchOSC single-char type."""
        norm_type = _PROP_TYPE_MAP.get(prop_type, prop_type)
        self.properties[name] = (norm_type, value)

    def add_osc_message(
        self,
        path: str,
        send: bool = True,
        receive: bool = True,
        var: str = "x",
        condition: str = "ANY",
        conversion: str = "FLOAT",
        scale_min: float = 0.0,
        scale_max: float = 1.0,
    ) -> None:
        """Configure two-way OSC address mapping."""
        if path == "/olc/selected/pan" and scale_min == 0.0 and scale_max == 1.0:
            scale_min, scale_max = -270.0, 270.0
        elif path == "/olc/selected/tilt" and scale_min == 0.0 and scale_max == 1.0:
            scale_min, scale_max = -135.0, 135.0
        elif (
            path == "/olc/selected/color/kelvin"
            and scale_min == 0.0
            and scale_max == 1.0
        ):
            scale_min, scale_max = 2000.0, 10000.0

        self.osc_messages.append(
            {
                "path": path,
                "send": send,
                "receive": receive,
                "enabled": True,
                "var": var,
                "condition": condition,
                "conversion": conversion,
                "scale_min": scale_min,
                "scale_max": scale_max,
            }
        )

    def add_child(self, child: TOSCNode) -> None:
        """Add a child node (and configure PAGER tabs or BUTTON label overlays)."""
        if self.node_type == "PAGER" and child.node_type == "GROUP":
            child.set_property("tabLabel", "s", child.name)
            child.set_property("tabColorOff", "c", COLOR_PANEL_BG)
            child.set_property("tabColorOn", "c", COLOR_TAB_ACTIVE)
            child.set_property("textColorOff", "c", (0.7, 0.7, 0.7, 1.0))
            child.set_property("textColorOn", "c", COLOR_WHITE_TEXT)
            p_frame = self.properties.get("frame", ("r", (0.0, 0.0, 1024.0, 713.0)))[1]
            if isinstance(p_frame, tuple) and len(p_frame) == 4:
                _, _, pw, ph = p_frame
                child.set_frame(0.0, 40.0, float(pw), max(100.0, float(ph) - 40.0))

        self.children.append(child)
        if child.overlay_label is not None:
            self.children.append(child.overlay_label)

    def to_xml_element(self) -> ET.Element:
        """Serialize node and its subtree into TouchOSC lexml ElementTree Element."""
        elem = ET.Element("node", {"ID": self.node_id, "type": self.node_type})

        # Properties
        props_elem = ET.SubElement(elem, "properties")
        self.properties["name"] = ("s", self.name)

        for p_name, (raw_type, p_val) in sorted(self.properties.items()):
            p_type = _PROP_TYPE_MAP.get(raw_type, raw_type)
            p_elem = ET.SubElement(props_elem, "property", {"type": p_type})
            key_el = ET.SubElement(p_elem, "key")
            key_el.text = p_name
            val_el = ET.SubElement(p_elem, "value")

            if p_type == "r" and isinstance(p_val, (tuple, list)) and len(p_val) == 4:
                x, y, w, h = (float(v) for v in p_val)
                ET.SubElement(val_el, "x").text = _fmt_num(x)
                ET.SubElement(val_el, "y").text = _fmt_num(y)
                ET.SubElement(val_el, "w").text = _fmt_num(w)
                ET.SubElement(val_el, "h").text = _fmt_num(h)
            elif p_type == "c" and isinstance(p_val, (tuple, list)) and len(p_val) == 4:
                r, g, b, a = (float(v) for v in p_val)
                ET.SubElement(val_el, "r").text = _fmt_num(r)
                ET.SubElement(val_el, "g").text = _fmt_num(g)
                ET.SubElement(val_el, "b").text = _fmt_num(b)
                ET.SubElement(val_el, "a").text = _fmt_num(a)
            elif p_type == "b":
                if isinstance(p_val, str):
                    val_el.text = "1" if p_val.lower() in ("true", "1", "yes") else "0"
                else:
                    val_el.text = "1" if p_val else "0"
            elif p_type == "f" and isinstance(p_val, (int, float)):
                val_el.text = _fmt_num(float(p_val))
            else:
                val_el.text = str(p_val)

        # Values
        values_elem = ET.SubElement(elem, "values")
        for v_name, v_val in self.values.items():
            v_elem = ET.SubElement(values_elem, "value")
            ET.SubElement(v_elem, "key").text = v_name
            ET.SubElement(v_elem, "locked").text = "0"
            ET.SubElement(v_elem, "lockedDefaultCurrent").text = (
                "1" if v_name == "text" else "0"
            )
            ET.SubElement(v_elem, "default").text = str(v_val)
            ET.SubElement(v_elem, "defaultPull").text = "0"

        # Messages
        if self.osc_messages:
            messages_elem = ET.SubElement(elem, "messages")
            for msg in self.osc_messages:
                osc_elem = ET.SubElement(messages_elem, "osc")
                ET.SubElement(osc_elem, "enabled").text = (
                    "1" if msg.get("enabled", True) else "0"
                )
                is_send = bool(msg.get("send", True))
                is_recv = bool(msg.get("receive", True))
                ET.SubElement(osc_elem, "send").text = "1" if is_send else "0"
                ET.SubElement(osc_elem, "receive").text = "1" if is_recv else "0"
                ET.SubElement(osc_elem, "feedback").text = "0"
                ET.SubElement(osc_elem, "connections").text = "1111111111"

                var_name = str(msg.get("var", "x"))
                cond_name = str(msg.get("condition", "ANY"))
                conv_name = str(msg.get("conversion", "FLOAT"))
                s_min = _fmt_num(float(msg.get("scale_min", 0.0)))
                s_max = _fmt_num(float(msg.get("scale_max", 1.0)))

                if is_send:
                    triggers_el = ET.SubElement(osc_elem, "triggers")
                    trig_el = ET.SubElement(triggers_el, "trigger")
                    ET.SubElement(trig_el, "var").text = var_name
                    ET.SubElement(trig_el, "condition").text = cond_name

                path_el = ET.SubElement(osc_elem, "path")
                part_path = ET.SubElement(path_el, "partial")
                ET.SubElement(part_path, "type").text = "CONSTANT"
                ET.SubElement(part_path, "conversion").text = "STRING"
                ET.SubElement(part_path, "value").text = str(msg.get("path", ""))
                ET.SubElement(part_path, "scaleMin").text = "0"
                ET.SubElement(part_path, "scaleMax").text = "1"

                args_el = ET.SubElement(osc_elem, "arguments")
                part_arg = ET.SubElement(args_el, "partial")
                ET.SubElement(part_arg, "type").text = "VALUE"
                ET.SubElement(part_arg, "conversion").text = conv_name
                ET.SubElement(part_arg, "value").text = var_name
                ET.SubElement(part_arg, "scaleMin").text = s_min
                ET.SubElement(part_arg, "scaleMax").text = s_max

        # Children (only on container nodes that have children)
        if self.children:
            children_elem = ET.SubElement(elem, "children")
            for child in self.children:
                children_elem.append(child.to_xml_element())

        return elem


def create_button(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    osc_path: str = "",
    color: tuple[float, float, float, float] = COLOR_GRAY_CTRL,
    is_toggle: bool = False,
) -> TOSCNode:
    """Helper to create a TouchOSC BUTTON control with a non-interactive label."""
    btn = TOSCNode("BUTTON", name=name)
    btn.set_frame(x, y, w, h)
    btn.set_color(*color)
    btn.set_text(text)
    btn.set_property("buttonType", "i", 1 if is_toggle else 0)
    is_flash = "/flash" in osc_path
    if osc_path:
        cond = "ANY" if (is_toggle or is_flash) else "RISE"
        btn.add_osc_message(osc_path, send=True, receive=is_toggle, condition=cond)
    if text:
        btn.overlay_label = create_label(
            f"lbl_btn_{name}",
            x,
            y,
            w,
            h,
            text,
            color=COLOR_WHITE_TEXT,
            size=13,
        )
    return btn


def create_fader(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    osc_path: str = "",
    color: tuple[float, float, float, float] = COLOR_BLUE_SEL,
    is_horizontal: bool = False,
) -> TOSCNode:
    """Helper to create a TouchOSC FADER control."""
    fader = TOSCNode("FADER", name=name)
    fader.set_frame(x, y, w, h)
    fader.set_color(*color)
    fader.set_property("orientation", "i", 1 if is_horizontal else 0)
    if osc_path == "/olc/mainfader":
        fader.values["x"] = "1"
    if osc_path:
        fader.add_osc_message(osc_path)
    return fader


def create_label(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    osc_path: str = "",
    color: tuple[float, float, float, float] = COLOR_WHITE_TEXT,
    size: int = 14,
) -> TOSCNode:
    """Helper to create a TouchOSC LABEL control."""
    lbl = TOSCNode("LABEL", name=name)
    lbl.set_frame(x, y, w, h)
    lbl.set_color(*color)
    lbl.set_property("textColor", "c", color)
    lbl.set_text(text)
    lbl.set_property("textSize", "i", size)
    lbl.set_property("background", "b", False)
    lbl.set_property("outline", "b", False)
    lbl.set_property("interactive", "b", False)
    if osc_path:
        lbl.add_osc_message(
            osc_path,
            send=False,
            receive=True,
            var="text",
            conversion="STRING",
        )
    return lbl


def create_radial(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    osc_path: str = "",
    color: tuple[float, float, float, float] = COLOR_CYAN_ACCENT,
) -> TOSCNode:
    """Helper to create a TouchOSC RADIAL / encoder wheel control."""
    rad = TOSCNode("RADIAL", name=name)
    rad.set_frame(x, y, w, h)
    rad.set_color(*color)
    if osc_path in ("/olc/selected/pan", "/olc/selected/tilt"):
        rad.set_property("centered", "b", True)
        rad.values["x"] = "0.5"
    if osc_path:
        rad.add_osc_message(osc_path)
    return rad


def create_xy_pad(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    osc_path_x: str = "",
    osc_path_y: str = "",
    color: tuple[float, float, float, float] = COLOR_ACCENT_PURPLE,
) -> TOSCNode:
    """Helper to create a TouchOSC XY Pad control."""
    xy = TOSCNode("XY", name=name)
    xy.set_frame(x, y, w, h)
    xy.set_color(*color)
    if osc_path_x:
        xy.add_osc_message(osc_path_x, var="x")
    if osc_path_y:
        xy.add_osc_message(osc_path_y, var="y")
    return xy


def _create_selection_indicator(
    name: str,
    x: float,
    y: float,
    w: float,
    h: float,
    osc_path: str,
) -> TOSCNode:
    """Create a non-interactive LED strip receiving 0/1 selection feedback."""
    ind = TOSCNode("BUTTON", name=name)
    ind.set_frame(x, y, w, h)
    ind.set_color(*COLOR_BLUE_SEL)
    ind.set_property("interactive", "b", False)
    ind.set_property("outline", "b", False)
    ind.add_osc_message(osc_path, send=False, receive=True)
    return ind


_ROOT_INIT_SCRIPT = (
    "local syncSent = false\n"
    "local startTime = 0\n\n"
    "function init()\n"
    "  startTime = getMillis()\n"
    "  syncSent = false\n"
    "  sendOSC('/olc/fader/pageupdate', 1)\n"
    "end\n\n"
    "function update()\n"
    "  if(not syncSent and getMillis() - startTime > 300) then\n"
    "    syncSent = true\n"
    "    sendOSC('/olc/fader/pageupdate', 1)\n"
    "  end\n"
    "end\n"
)

_PAGER_SYNC_SCRIPT = (
    "function onValueChanged(key)\n"
    "  if(key == 'page') then\n"
    "    sendOSC('/olc/fader/pageupdate', 1)\n"
    "  end\n"
    "end\n"
)


def build_tablet_template() -> TOSCNode:
    """Build complete 6-tab TouchOSC template for Tablets (1024x768 Landscape)."""
    root = TOSCNode("GROUP", name="OpenLightingConsole_Tablet")
    root.set_frame(0, 0, 1024, 768)
    root.set_color(*COLOR_DARK_BG)
    root.set_property("script", "s", _ROOT_INIT_SCRIPT)

    # Permanent Header / Master Strip (Top 55px)
    hdr = TOSCNode("GROUP", name="Header")
    hdr.set_frame(0, 0, 1024, 55)
    hdr.set_color(*COLOR_PANEL_BG)

    # Title label and Sync button
    hdr.add_child(
        create_label("title", 15, 12, 220, 30, "OPEN LIGHTING CONSOLE", size=18)
    )
    hdr.add_child(
        create_button(
            "sync_btn",
            510,
            10,
            80,
            35,
            "SYNC",
            "/olc/fader/pageupdate",
            COLOR_CYAN_ACCENT,
        )
    )

    # Master controls: Blackout (DBO) and Main Fader
    hdr.add_child(
        create_button(
            "dbo",
            890,
            10,
            115,
            35,
            "BLACKOUT",
            "/olc/blackout",
            COLOR_RED_DBO,
            is_toggle=True,
        )
    )
    hdr.add_child(create_label("lbl_mf", 610, 15, 90, 25, "MAIN FADER:", size=13))
    hdr.add_child(
        create_fader(
            "main_fader",
            705,
            15,
            170,
            25,
            "/olc/mainfader",
            COLOR_AMBER_PAUSE,
            is_horizontal=True,
        )
    )
    root.add_child(hdr)

    # Main Pager containing the 6 themed tabs (55px to 768px -> 713px height)
    pager = TOSCNode("PAGER", name="Tabs")
    pager.set_frame(0, 55, 1024, 713)
    pager.set_color(*COLOR_DARK_BG)
    pager.set_property("script", "s", _PAGER_SYNC_SCRIPT)

    # --- TAB 1: Playback / Show Control ---
    t_play = TOSCNode("GROUP", name="1. Playback")
    t_play.set_frame(0, 0, 1024, 670)

    # Big Playback status card
    card_pb = TOSCNode("GROUP", name="StatusCard")
    card_pb.set_frame(30, 20, 964, 180)
    card_pb.set_color(*COLOR_PANEL_BG)

    card_pb.add_child(create_label("lbl_act", 20, 15, 120, 25, "ACTIVE CUE", size=14))
    card_pb.add_child(
        create_label(
            "act_cue_num", 20, 45, 140, 50, "0.0", "/olc/playback/active/cue", size=36
        )
    )
    card_pb.add_child(
        create_label(
            "act_cue_txt",
            170,
            55,
            300,
            35,
            "-",
            "/olc/playback/active/text",
            size=18,
        )
    )

    card_pb.add_child(create_label("lbl_nxt", 520, 15, 120, 25, "NEXT CUE", size=14))
    card_pb.add_child(
        create_label(
            "nxt_cue_num", 520, 45, 140, 50, "1.0", "/olc/playback/next/cue", size=36
        )
    )
    card_pb.add_child(
        create_label(
            "nxt_cue_txt",
            670,
            55,
            270,
            35,
            "-",
            "/olc/playback/next/text",
            size=18,
        )
    )

    # Crossfade progress bar
    card_pb.add_child(create_label("lbl_prog", 20, 115, 150, 20, "CROSSFADE", size=12))
    card_pb.add_child(
        create_fader(
            "pb_progress",
            20,
            135,
            924,
            25,
            "/olc/playback/progress",
            COLOR_GREEN_GO,
            is_horizontal=True,
        )
    )
    t_play.add_child(card_pb)

    # Big GO / PAUSE / BACK action buttons
    t_play.add_child(
        create_button("go", 30, 230, 360, 210, "GO", "/olc/key/go", COLOR_GREEN_GO)
    )
    t_play.add_child(
        create_button(
            "pause", 420, 230, 260, 210, "PAUSE", "/olc/key/pause", COLOR_AMBER_PAUSE
        )
    )
    t_play.add_child(
        create_button(
            "back", 710, 230, 284, 210, "BACK", "/olc/key/goback", COLOR_GRAY_CTRL
        )
    )

    # Cue Navigation and Goto Cue Strip
    t_play.add_child(
        create_button("seq_prev", 30, 470, 160, 60, "SEQ -", "/olc/key/seq-")
    )
    t_play.add_child(
        create_button("seq_next", 210, 470, 160, 60, "SEQ +", "/olc/key/seq+")
    )
    t_play.add_child(
        create_button("goto_cue_1", 420, 470, 160, 60, "GOTO CUE", "/olc/playback/goto")
    )
    t_play.add_child(
        create_button(
            "cue_dump", 600, 470, 180, 60, "DUMP CUES", "/olc/cue/dump", COLOR_GRAY_CTRL
        )
    )
    pager.add_child(t_play)

    # --- TAB 2: Channels (24 Paged Cells Matrix) ---
    t_chan = TOSCNode("GROUP", name="2. Circuits")
    t_chan.set_frame(0, 0, 1024, 670)

    # Navigation header for Channels
    t_chan.add_child(
        create_button("pg_prev", 30, 15, 120, 40, "<< PAGE", "/olc/channels/page/-")
    )
    t_chan.add_child(
        create_label(
            "pg_info",
            170,
            20,
            350,
            30,
            "Page 1/43 (Ch 1-24)",
            "/olc/channels/page/label",
            size=16,
        )
    )
    t_chan.add_child(
        create_button("pg_next", 540, 15, 120, 40, "PAGE >>", "/olc/channels/page/+")
    )
    t_chan.add_child(
        create_button(
            "ch_clear", 680, 15, 100, 40, "CLEAR", "/olc/key/clear", COLOR_GRAY_CTRL
        )
    )
    t_chan.add_child(
        create_button(
            "ch_all", 790, 15, 100, 40, "ALL", "/olc/key/all", COLOR_GRAY_CTRL
        )
    )
    t_chan.add_child(
        create_radial(
            "wheel_int", 910, 10, 80, 80, "/olc/selected/intensity", COLOR_AMBER_PAUSE
        )
    )

    # 24 Channel Cells Grid (6 columns x 4 rows)
    cell_w, cell_h = 145, 115
    start_x, start_y = 30, 100
    gap_x, gap_y = 18, 18

    for idx in range(1, 25):
        c_col = (idx - 1) % 6
        c_row = (idx - 1) // 6
        cx = start_x + c_col * (cell_w + gap_x)
        cy = start_y + c_row * (cell_h + gap_y)

        cell_group = TOSCNode("GROUP", name=f"cell_{idx}")
        cell_group.set_frame(cx, cy, cell_w, cell_h)
        cell_group.set_color(*COLOR_PANEL_BG)

        # Interactive touch button (top 85px so level fader at bottom remains draggable)
        cell_group.add_child(
            create_button(
                f"touch_{idx}",
                0,
                0,
                cell_w,
                88,
                "",
                f"/olc/cell/{idx}/touch",
                COLOR_GRAY_CTRL,
            )
        )
        # Selection highlight strip
        cell_group.add_child(
            _create_selection_indicator(
                f"sel_{idx}",
                0,
                0,
                cell_w,
                32,
                f"/olc/cell/{idx}/selected",
            )
        )
        # Dynamic channel number
        cell_group.add_child(
            create_label(
                f"ch_{idx}",
                5,
                5,
                cell_w - 10,
                24,
                f"{idx}",
                f"/olc/cell/{idx}/channel",
                COLOR_WHITE_TEXT,
                size=16,
            )
        )
        # Channel label feedback
        cell_group.add_child(
            create_label(
                f"lbl_{idx}",
                5,
                42,
                cell_w - 10,
                36,
                f"Ch {idx}",
                f"/olc/cell/{idx}/label",
                COLOR_WHITE_TEXT,
                size=12,
            )
        )
        # Level feedback & control indicator
        cell_group.add_child(
            create_fader(
                f"lvl_{idx}",
                5,
                92,
                cell_w - 10,
                18,
                f"/olc/cell/{idx}/level",
                COLOR_AMBER_PAUSE,
                is_horizontal=True,
            )
        )
        t_chan.add_child(cell_group)

    pager.add_child(t_chan)

    # --- TAB 3: Faders (10 Submasters Wing) ---
    t_fader = TOSCNode("GROUP", name="3. Faders")
    t_fader.set_frame(0, 0, 1024, 670)

    # Fader page controls
    t_fader.add_child(
        create_button("fd_pg_prev", 30, 15, 120, 35, "PAGE -", "/olc/fader/page-")
    )
    t_fader.add_child(
        create_label(
            "fd_pg_info",
            170,
            20,
            200,
            25,
            "Page 1",
            "/olc/fader/page/label",
            size=15,
        )
    )
    t_fader.add_child(
        create_button("fd_pg_next", 390, 15, 120, 35, "PAGE +", "/olc/fader/page+")
    )

    # 10 Vertical Faders with Flash and Label
    f_w = 80
    f_gap = 18
    f_start_x = 30
    for fi in range(1, 11):
        fx = f_start_x + (fi - 1) * (f_w + f_gap)

        # Flash Button
        t_fader.add_child(
            create_button(
                f"flash_{fi}",
                fx,
                70,
                f_w,
                55,
                f"F{fi}",
                f"/olc/fader/1/{fi}/flash",
                COLOR_AMBER_PAUSE,
            )
        )
        # Vertical Fader
        t_fader.add_child(
            create_fader(
                f"fader_{fi}",
                fx,
                140,
                f_w,
                420,
                f"/olc/fader/1/{fi}/level",
                COLOR_BLUE_SEL,
                is_horizontal=False,
            )
        )
        # Dynamic label
        t_fader.add_child(
            create_label(
                f"lbl_f_{fi}",
                fx,
                570,
                f_w,
                45,
                f"Fader {fi}",
                f"/olc/fader/1/{fi}/label",
                COLOR_WHITE_TEXT,
                size=11,
            )
        )

    pager.add_child(t_fader)

    # --- TAB 4: Moving Lights & Beam (Pan/Tilt + Optics) ---
    t_beam = TOSCNode("GROUP", name="4. Asservis")
    t_beam.set_frame(0, 0, 1024, 670)

    # Pan / Tilt 2D XY Pad
    t_beam.add_child(
        create_label("lbl_pt", 30, 15, 300, 25, "POSITION (PAN / TILT)", size=15)
    )
    t_beam.add_child(
        create_xy_pad(
            "xy_pantilt",
            30,
            45,
            420,
            420,
            "/olc/selected/pan",
            "/olc/selected/tilt",
            COLOR_ACCENT_PURPLE,
        )
    )
    # Pan & Tilt Knobs below XY pad
    t_beam.add_child(
        create_radial(
            "w_pan", 80, 485, 120, 120, "/olc/selected/pan", COLOR_CYAN_ACCENT
        )
    )
    t_beam.add_child(create_label("lbl_w_pan", 80, 615, 120, 25, "PAN", size=13))
    t_beam.add_child(
        create_radial(
            "w_tilt", 250, 485, 120, 120, "/olc/selected/tilt", COLOR_CYAN_ACCENT
        )
    )
    t_beam.add_child(create_label("lbl_w_tilt", 250, 615, 120, 25, "TILT", size=13))

    # Beam / Optics controls (Zoom, Focus, Iris, Strobe, Frost, Gobo, Prism)
    t_beam.add_child(
        create_label(
            "lbl_optics", 480, 15, 300, 25, "FAISCEAU & EFFETS (BEAM)", size=15
        )
    )

    beam_params = [
        ("ZOOM", "/olc/selected/zoom"),
        ("FOCUS", "/olc/selected/focus"),
        ("IRIS", "/olc/selected/iris"),
        ("STROBE", "/olc/selected/strobe"),
        ("FROST", "/olc/selected/frost"),
        ("GOBO", "/olc/selected/gobo"),
        ("PRISM", "/olc/selected/prism"),
    ]

    b_y = 50
    for label, sel_path in beam_params:
        t_beam.add_child(
            create_label(f"lbl_{label}", 480, b_y + 10, 80, 25, label, size=13)
        )
        t_beam.add_child(
            create_fader(
                f"f_{label}",
                570,
                b_y + 8,
                300,
                32,
                sel_path,
                COLOR_CYAN_ACCENT,
                is_horizontal=True,
            )
        )
        t_beam.add_child(
            create_radial(f"w_{label}", 890, b_y, 48, 48, sel_path, COLOR_GRAY_CTRL)
        )
        b_y += 75

    pager.add_child(t_beam)

    # --- TAB 5: Color & CCT ---
    t_color = TOSCNode("GROUP", name="5. Couleur")
    t_color.set_frame(0, 0, 1024, 670)

    # Color Picker 2D Pad
    t_color.add_child(
        create_label("lbl_cp", 30, 15, 300, 25, "COLOR PICKER (HUE / SAT)", size=15)
    )
    t_color.add_child(
        create_xy_pad(
            "xy_color",
            30,
            45,
            440,
            440,
            "/olc/selected/color/hue",
            "/olc/selected/color/sat",
            COLOR_GREEN_GO,
        )
    )

    # Individual RGB Faders
    t_color.add_child(
        create_label("lbl_rgbw", 510, 15, 200, 25, "CANAUX COULEUR", size=15)
    )
    t_color.add_child(create_label("lbl_r", 510, 60, 40, 25, "R", size=16))
    t_color.add_child(
        create_fader(
            "f_r",
            550,
            55,
            380,
            35,
            "/olc/selected/color/r",
            (0.9, 0.2, 0.2, 1.0),
            is_horizontal=True,
        )
    )
    t_color.add_child(create_label("lbl_g", 510, 120, 40, 25, "G", size=16))
    t_color.add_child(
        create_fader(
            "f_g",
            550,
            115,
            380,
            35,
            "/olc/selected/color/g",
            (0.2, 0.9, 0.2, 1.0),
            is_horizontal=True,
        )
    )
    t_color.add_child(create_label("lbl_b", 510, 180, 40, 25, "B", size=16))
    t_color.add_child(
        create_fader(
            "f_b",
            550,
            175,
            380,
            35,
            "/olc/selected/color/b",
            (0.2, 0.4, 0.9, 1.0),
            is_horizontal=True,
        )
    )

    # Color Temperature CCT Kelvin
    t_color.add_child(
        create_label(
            "lbl_cct", 510, 260, 300, 25, "TEMPÉRATURE DE COULEUR (CCT)", size=15
        )
    )
    t_color.add_child(
        create_fader(
            "f_kelvin",
            510,
            295,
            420,
            40,
            "/olc/selected/color/kelvin",
            COLOR_AMBER_PAUSE,
            is_horizontal=True,
        )
    )
    t_color.add_child(
        create_button(
            "cct_3200",
            510,
            355,
            130,
            45,
            "3200K (Tungstène)",
            "/olc/selected/color/kelvin/3200",
        )
    )
    t_color.add_child(
        create_button(
            "cct_4000",
            655,
            355,
            130,
            45,
            "4000K (Neutre)",
            "/olc/selected/color/kelvin/4000",
        )
    )
    t_color.add_child(
        create_button(
            "cct_5600",
            800,
            355,
            130,
            45,
            "5600K (Daylight)",
            "/olc/selected/color/kelvin/5600",
        )
    )

    pager.add_child(t_color)

    # --- TAB 6: Keypad & Command Line ---
    t_key = TOSCNode("GROUP", name="6. Clavier")
    t_key.set_frame(0, 0, 1024, 670)

    # Command line feedback display
    t_key.add_child(
        create_label(
            "cmd_display",
            100,
            25,
            700,
            60,
            "COMMANDE : ",
            "/olc/command_line",
            COLOR_WHITE_TEXT,
            size=22,
        )
    )
    t_key.add_child(
        create_label(
            "cmd_status",
            820,
            25,
            120,
            60,
            "OK",
            "/olc/cmd/status",
            COLOR_GREEN_GO,
            size=18,
        )
    )

    # Numeric Keypad (4x4 buttons)
    key_w, key_h = 130, 80
    k_start_x, k_start_y = 100, 110
    k_gap_x, k_gap_y = 20, 20

    keypad_matrix = [
        [
            ("7", "/olc/key/7"),
            ("8", "/olc/key/8"),
            ("9", "/olc/key/9"),
            ("THRU", "/olc/key/thru"),
        ],
        [
            ("4", "/olc/key/4"),
            ("5", "/olc/key/5"),
            ("6", "/olc/key/6"),
            ("AT", "/olc/key/at"),
        ],
        [
            ("1", "/olc/key/1"),
            ("2", "/olc/key/2"),
            ("3", "/olc/key/3"),
            ("FULL", "/olc/key/full"),
        ],
        [
            ("CLEAR", "/olc/key/clear"),
            ("0", "/olc/key/0"),
            (".", "/olc/key/."),
            ("ENTER", "/olc/key/enter"),
        ],
    ]

    for r_idx, row in enumerate(keypad_matrix):
        for c_idx, (txt, k_path) in enumerate(row):
            kx = k_start_x + c_idx * (key_w + k_gap_x)
            ky = k_start_y + r_idx * (key_h + k_gap_y)
            col = COLOR_GRAY_CTRL
            if txt in ("FULL", "ENTER"):
                col = COLOR_GREEN_GO
            elif txt == "CLEAR":
                col = COLOR_RED_DBO
            t_key.add_child(
                create_button(f"k_{txt}", kx, ky, key_w, key_h, txt, k_path, col)
            )

    # Extra channel operators
    t_key.add_child(
        create_button("k_chan", 700, 110, 120, 80, "CHANNEL", "/olc/key/channel")
    )
    t_key.add_child(create_button("k_plus", 700, 210, 120, 80, "+", "/olc/key/+"))
    t_key.add_child(create_button("k_minus", 700, 310, 120, 80, "-", "/olc/key/-"))
    t_key.add_child(
        create_button("k_plus_pct", 840, 210, 100, 80, "+ %", "/olc/key/+%")
    )
    t_key.add_child(
        create_button("k_minus_pct", 840, 310, 100, 80, "- %", "/olc/key/-%")
    )

    pager.add_child(t_key)
    root.add_child(pager)

    return root


def build_phone_template() -> TOSCNode:
    """Build compact TouchOSC template for Smartphones (400x800 Portrait)."""
    root = TOSCNode("GROUP", name="OpenLightingConsole_Phone")
    root.set_frame(0, 0, 400, 800)
    root.set_color(*COLOR_DARK_BG)
    root.set_property("script", "s", _ROOT_INIT_SCRIPT)

    # Header Master Strip (Top 50px)
    hdr = TOSCNode("GROUP", name="Header")
    hdr.set_frame(0, 0, 400, 50)
    hdr.set_color(*COLOR_PANEL_BG)

    hdr.add_child(create_label("title", 8, 12, 48, 25, "OLC", size=16))
    hdr.add_child(
        create_button(
            "sync_btn",
            60,
            8,
            55,
            34,
            "SYNC",
            "/olc/fader/pageupdate",
            COLOR_CYAN_ACCENT,
        )
    )
    hdr.add_child(
        create_fader(
            "main_fader",
            122,
            12,
            155,
            26,
            "/olc/mainfader",
            COLOR_AMBER_PAUSE,
            is_horizontal=True,
        )
    )
    hdr.add_child(
        create_button(
            "dbo",
            285,
            8,
            105,
            34,
            "BLACKOUT",
            "/olc/blackout",
            COLOR_RED_DBO,
            is_toggle=True,
        )
    )
    root.add_child(hdr)

    # Main Pager (50px to 800px -> 750px height)
    pager = TOSCNode("PAGER", name="Tabs")
    pager.set_frame(0, 50, 400, 750)
    pager.set_color(*COLOR_DARK_BG)
    pager.set_property("script", "s", _PAGER_SYNC_SCRIPT)

    # --- TAB 1: Playback ---
    t_play = TOSCNode("GROUP", name="Playback")
    t_play.set_frame(0, 0, 400, 700)

    # Status card
    card = TOSCNode("GROUP", name="Card")
    card.set_frame(15, 15, 370, 150)
    card.set_color(*COLOR_PANEL_BG)

    card.add_child(create_label("lbl_c", 15, 10, 80, 20, "CUE", size=12))
    card.add_child(
        create_label(
            "act_num", 15, 30, 90, 45, "0.0", "/olc/playback/active/cue", size=32
        )
    )
    card.add_child(
        create_label(
            "act_txt", 115, 35, 240, 30, "-", "/olc/playback/active/text", size=16
        )
    )

    card.add_child(
        create_fader(
            "progress",
            15,
            100,
            340,
            25,
            "/olc/playback/progress",
            COLOR_GREEN_GO,
            is_horizontal=True,
        )
    )
    t_play.add_child(card)

    # Huge GO Button for Thumb
    t_play.add_child(
        create_button("go", 15, 185, 370, 240, "GO", "/olc/key/go", COLOR_GREEN_GO)
    )

    # Pause & Back Buttons
    t_play.add_child(
        create_button(
            "pause", 15, 445, 175, 110, "PAUSE", "/olc/key/pause", COLOR_AMBER_PAUSE
        )
    )
    t_play.add_child(
        create_button(
            "back", 210, 445, 175, 110, "BACK", "/olc/key/goback", COLOR_GRAY_CTRL
        )
    )

    # Seq navigation
    t_play.add_child(create_button("seq_p", 15, 575, 175, 65, "SEQ -", "/olc/key/seq-"))
    t_play.add_child(
        create_button("seq_n", 210, 575, 175, 65, "SEQ +", "/olc/key/seq+")
    )
    pager.add_child(t_play)

    # --- TAB 2: Channels (12 Cells Compact) ---
    t_chan = TOSCNode("GROUP", name="Circuits")
    t_chan.set_frame(0, 0, 400, 700)

    # Navigation bar
    t_chan.add_child(
        create_button("p_prev", 15, 10, 80, 40, "<<", "/olc/channels/page/-")
    )
    t_chan.add_child(
        create_label(
            "p_info",
            105,
            15,
            190,
            30,
            "Page 1 (Ch 1-12)",
            "/olc/channels/page/label",
            size=14,
        )
    )
    t_chan.add_child(
        create_button("p_next", 305, 10, 80, 40, ">>", "/olc/channels/page/+")
    )

    # 12 cells (3 columns x 4 rows)
    cw, ch = 112, 105
    start_x, start_y = 15, 65
    gx, gy = 17, 15

    for idx in range(1, 13):
        col = (idx - 1) % 3
        row = (idx - 1) // 3
        cx = start_x + col * (cw + gx)
        cy = start_y + row * (ch + gy)

        cg = TOSCNode("GROUP", name=f"cell_{idx}")
        cg.set_frame(cx, cy, cw, ch)
        cg.set_color(*COLOR_PANEL_BG)

        cg.add_child(
            create_button(
                f"t_{idx}",
                0,
                0,
                cw,
                80,
                "",
                f"/olc/cell/{idx}/touch",
                COLOR_GRAY_CTRL,
            )
        )
        cg.add_child(
            _create_selection_indicator(
                f"sel_{idx}",
                0,
                0,
                cw,
                28,
                f"/olc/cell/{idx}/selected",
            )
        )
        cg.add_child(
            create_label(
                f"ch_{idx}",
                5,
                4,
                cw - 10,
                20,
                f"{idx}",
                f"/olc/cell/{idx}/channel",
                COLOR_WHITE_TEXT,
                size=14,
            )
        )
        cg.add_child(
            create_label(
                f"l_{idx}",
                5,
                38,
                cw - 10,
                32,
                f"Ch {idx}",
                f"/olc/cell/{idx}/label",
                COLOR_WHITE_TEXT,
                size=10,
            )
        )
        cg.add_child(
            create_fader(
                f"lvl_{idx}",
                5,
                82,
                cw - 10,
                16,
                f"/olc/cell/{idx}/level",
                COLOR_AMBER_PAUSE,
                is_horizontal=True,
            )
        )
        t_chan.add_child(cg)

    # Bottom quick wheel
    t_chan.add_child(
        create_radial(
            "wh_int", 150, 555, 100, 100, "/olc/selected/intensity", COLOR_AMBER_PAUSE
        )
    )
    t_chan.add_child(create_label("lbl_wh", 140, 660, 120, 25, "INTENSITÉ", size=13))
    pager.add_child(t_chan)

    # --- TAB 3: Faders (4 Large Faders) ---
    t_fader = TOSCNode("GROUP", name="Faders")
    t_fader.set_frame(0, 0, 400, 700)

    t_fader.add_child(
        create_button("fd_p", 15, 10, 100, 40, "PAGE -", "/olc/fader/page-")
    )
    t_fader.add_child(
        create_label(
            "fd_pg_info",
            125,
            15,
            150,
            30,
            "Page 1",
            "/olc/fader/page/label",
            size=14,
        )
    )
    t_fader.add_child(
        create_button("fd_n", 285, 10, 100, 40, "PAGE +", "/olc/fader/page+")
    )

    fw = 76
    fgap = 18
    for fi in range(1, 5):
        fx = 15 + (fi - 1) * (fw + fgap)
        t_fader.add_child(
            create_button(
                f"fl_{fi}",
                fx,
                65,
                fw,
                60,
                f"F{fi}",
                f"/olc/fader/1/{fi}/flash",
                COLOR_AMBER_PAUSE,
            )
        )
        t_fader.add_child(
            create_fader(
                f"fd_{fi}",
                fx,
                140,
                fw,
                420,
                f"/olc/fader/1/{fi}/level",
                COLOR_BLUE_SEL,
                is_horizontal=False,
            )
        )
        t_fader.add_child(
            create_label(
                f"lbl_f_{fi}",
                fx,
                570,
                fw,
                40,
                f"Fader {fi}",
                f"/olc/fader/1/{fi}/label",
                COLOR_WHITE_TEXT,
                size=11,
            )
        )

    pager.add_child(t_fader)

    # --- TAB 4: Asservis & Beam ---
    t_beam = TOSCNode("GROUP", name="Asservis")
    t_beam.set_frame(0, 0, 400, 700)

    t_beam.add_child(
        create_xy_pad(
            "xy_pt",
            20,
            15,
            360,
            330,
            "/olc/selected/pan",
            "/olc/selected/tilt",
            COLOR_ACCENT_PURPLE,
        )
    )

    t_beam.add_child(create_label("lbl_z", 20, 360, 60, 25, "ZOOM", size=13))
    t_beam.add_child(
        create_fader(
            "f_z",
            90,
            355,
            290,
            35,
            "/olc/selected/zoom",
            COLOR_CYAN_ACCENT,
            is_horizontal=True,
        )
    )

    t_beam.add_child(create_label("lbl_f", 20, 415, 60, 25, "FOCUS", size=13))
    t_beam.add_child(
        create_fader(
            "f_f",
            90,
            410,
            290,
            35,
            "/olc/selected/focus",
            COLOR_CYAN_ACCENT,
            is_horizontal=True,
        )
    )

    t_beam.add_child(create_label("lbl_s", 20, 470, 60, 25, "STROBE", size=13))
    t_beam.add_child(
        create_fader(
            "f_s",
            90,
            465,
            290,
            35,
            "/olc/selected/strobe",
            COLOR_CYAN_ACCENT,
            is_horizontal=True,
        )
    )

    t_beam.add_child(
        create_radial("w_p", 50, 520, 100, 100, "/olc/selected/pan", COLOR_CYAN_ACCENT)
    )
    t_beam.add_child(create_label("l_wp", 50, 625, 100, 25, "PAN", size=12))

    t_beam.add_child(
        create_radial(
            "w_t", 250, 520, 100, 100, "/olc/selected/tilt", COLOR_CYAN_ACCENT
        )
    )
    t_beam.add_child(create_label("l_wt", 250, 625, 100, 25, "TILT", size=12))

    pager.add_child(t_beam)

    # --- TAB 5: Color & CCT ---
    t_color = TOSCNode("GROUP", name="Couleur")
    t_color.set_frame(0, 0, 400, 700)

    t_color.add_child(
        create_xy_pad(
            "xy_c",
            20,
            15,
            360,
            260,
            "/olc/selected/color/hue",
            "/olc/selected/color/sat",
            COLOR_GREEN_GO,
        )
    )

    t_color.add_child(create_label("lbl_r", 20, 290, 25, 25, "R", size=14))
    t_color.add_child(
        create_fader(
            "f_r",
            50,
            288,
            330,
            28,
            "/olc/selected/color/r",
            (0.9, 0.2, 0.2, 1.0),
            is_horizontal=True,
        )
    )
    t_color.add_child(create_label("lbl_g", 20, 328, 25, 25, "G", size=14))
    t_color.add_child(
        create_fader(
            "f_g",
            50,
            326,
            330,
            28,
            "/olc/selected/color/g",
            (0.2, 0.9, 0.2, 1.0),
            is_horizontal=True,
        )
    )
    t_color.add_child(create_label("lbl_b", 20, 366, 25, 25, "B", size=14))
    t_color.add_child(
        create_fader(
            "f_b",
            50,
            364,
            330,
            28,
            "/olc/selected/color/b",
            (0.2, 0.4, 0.9, 1.0),
            is_horizontal=True,
        )
    )

    t_color.add_child(
        create_label("lbl_cct", 20, 405, 220, 25, "TEMPÉRATURE KELVIN", size=14)
    )
    t_color.add_child(
        create_fader(
            "f_kelvin",
            20,
            435,
            360,
            35,
            "/olc/selected/color/kelvin",
            COLOR_AMBER_PAUSE,
            is_horizontal=True,
        )
    )

    t_color.add_child(
        create_button(
            "c_3200", 20, 490, 110, 45, "3200K", "/olc/selected/color/kelvin/3200"
        )
    )
    t_color.add_child(
        create_button(
            "c_4000", 145, 490, 110, 45, "4000K", "/olc/selected/color/kelvin/4000"
        )
    )
    t_color.add_child(
        create_button(
            "c_5600", 270, 490, 110, 45, "5600K", "/olc/selected/color/kelvin/5600"
        )
    )
    pager.add_child(t_color)

    # --- TAB 6: Keypad ---
    t_key = TOSCNode("GROUP", name="Clavier")
    t_key.set_frame(0, 0, 400, 700)

    t_key.add_child(
        create_label(
            "cmd",
            15,
            15,
            280,
            45,
            "CMD : ",
            "/olc/command_line",
            COLOR_WHITE_TEXT,
            size=16,
        )
    )
    t_key.add_child(
        create_label(
            "status",
            305,
            15,
            80,
            45,
            "OK",
            "/olc/cmd/status",
            COLOR_GREEN_GO,
            size=15,
        )
    )

    # 4 columns keypad
    btn_w, btn_h = 85, 65
    bx, by = 15, 75
    bgx, bgy = 10, 10

    pad = [
        [
            ("7", "/olc/key/7"),
            ("8", "/olc/key/8"),
            ("9", "/olc/key/9"),
            ("THRU", "/olc/key/thru"),
        ],
        [
            ("4", "/olc/key/4"),
            ("5", "/olc/key/5"),
            ("6", "/olc/key/6"),
            ("AT", "/olc/key/at"),
        ],
        [
            ("1", "/olc/key/1"),
            ("2", "/olc/key/2"),
            ("3", "/olc/key/3"),
            ("FULL", "/olc/key/full"),
        ],
        [
            ("CLR", "/olc/key/clear"),
            ("0", "/olc/key/0"),
            (".", "/olc/key/."),
            ("ENTER", "/olc/key/enter"),
        ],
    ]

    for ri, r_data in enumerate(pad):
        for ci, (txt, pth) in enumerate(r_data):
            x = bx + ci * (btn_w + bgx)
            y = by + ri * (btn_h + bgy)
            c = (
                COLOR_GREEN_GO
                if txt in ("FULL", "ENTER")
                else (COLOR_RED_DBO if txt == "CLR" else COLOR_GRAY_CTRL)
            )
            t_key.add_child(create_button(f"kp_{txt}", x, y, btn_w, btn_h, txt, pth, c))

    pager.add_child(t_key)
    root.add_child(pager)

    return root


def export_tosc_file(root_node: TOSCNode, output_path: str) -> bytes:
    """Serialize layout node tree to zlib-compressed TouchOSC .tosc binary.

    Args:
        root_node: Root TOSCNode.
        output_path: File system path where to write .tosc file.

    Returns:
        The compressed binary bytes.
    """
    lexml_root = ET.Element("lexml", {"version": "5"})
    lexml_root.append(root_node.to_xml_element())
    ET.indent(lexml_root, space="")
    body_str = ET.tostring(lexml_root, encoding="unicode")
    xml_bytes = f"<?xml version='1.0' encoding='UTF-8'?>\n{body_str}\n".encode("utf-8")
    compressed_bytes = zlib.compress(xml_bytes)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(compressed_bytes)

    return compressed_bytes


def generate_all_templates(target_dir: str) -> dict[str, str]:
    """Generate both Tablet and Phone .tosc templates into target directory.

    Args:
        target_dir: Output directory.

    Returns:
        Dictionary mapping template type to saved file path.
    """
    os.makedirs(target_dir, exist_ok=True)

    tablet_path = os.path.join(target_dir, "OpenLightingConsole_Tablet.tosc")
    tablet_node = build_tablet_template()
    export_tosc_file(tablet_node, tablet_path)

    phone_path = os.path.join(target_dir, "OpenLightingConsole_Phone.tosc")
    phone_node = build_phone_template()
    export_tosc_file(phone_node, phone_path)

    return {
        "tablet": tablet_path,
        "phone": phone_path,
    }

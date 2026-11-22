[Français](../doc.fr/intro.md) | [← Table of Contents](index.md)

# 1. Introduction

**Open Lighting Console (`olc`)** is an open-source Linux lighting control console built for theater, live performance, and multi-parameter lighting systems.

## Core Concepts

### Logical Channels vs. DMX Addresses
- **Channel**: logical fixture or dimmer number operated by the lighting designer (`1` to `MAX_CHANNELS`). A channel can drive a single dimmer (8/16-bit) or an entire multi-parameter intelligent fixture (*Device*).
- **DMX Address (`Universe / Address`)**: physical or network DMX output slot (`1` to `512` per universe) mapped in the patch. One channel may feed multiple parallel dimmer addresses, whereas an intelligent fixture occupies a contiguous address footprint matching its active DMX mode.

### HTP / LTP Logic & Continuous Floating-Point Engine
- **Continuous `[0.0 .. 1.0]` levels**: `CoreEngine` computes all internal levels in floating point at **44 Hz**, before quantizing output frames to **8-bit**, **16-bit**, or **24-bit** depending on the fixture profile.
- **HTP (*Highest Takes Precedence*)**: applied to dimmer/intensity levels across sources (Main Playback, Faders, Independents, DMX-In merge). The highest value wins.
- **LTP (*Latest Takes Precedence*)**: applied to non-intensity attributes (Position, Color, Beam) and manual operator overrides.

### Console Status Color Scheme
Across channel grids (`LiveView`, `Sequences`, `Track Channels`), text and bar colors convey parameter state at a glance:
- **Red**: value captured in **manual** control by the operator (command line, wheel, `Device Inspector`, or live palette/preset recall). Overrides playback until `Sneak`, release, or recording into a cue.
- **Yellow / Amber**: active live level from playback or faders, or active tile selection outline.
- **Green**: intensity or attribute **increasing** relative to the previous cue.
- **Blue / Cyan**: intensity **decreasing** relative to the previous cue (or tracked effect state).
- **Magenta**: **blocked** or **tracked** unchanging level/reference depending on view context.
- **Color swatch & badges**: in `Summary+` and `Table` views, compact indicators display `F` (Focus), `C` (Color), `B` (Beam) activity alongside a live RGB color swatch.

---

*Previous: [Table of Contents](index.md) — Next: [2. Main Window & LiveView →](general.md)*

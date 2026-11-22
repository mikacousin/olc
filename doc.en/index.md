[Français](../doc.fr/index.md) | [← Home](../index.md)

# User Manual — Open Lighting Console

Welcome to the reference manual for **Open Lighting Console (`olc`)** (`0.11.1.beta`).

---

## Table of Contents

### 1. Getting Started & Interface
1. [Introduction](intro.md) — Overview, core concepts (channels, addresses, HTP/LTP, tracking), and console color scheme.
2. [Main Window & Live Views (`LiveView`)](general.md) — Header bar, movable tabs, display formats (`Compact`, `Summary+`, `Table`), readout modes, Flexi filters, and keyboard shortcuts.
3. [Command Line (`CLI`)](commandline.md) — ETC Eos-inspired LL(1) syntax, auto-completion, selections, levels, patch, palettes, effects, sequences, Check/Park/Sneak, and direct keybindings.
4. [Files, Formats & Import/Export](files.md) — Native `.olc` show format, USITT ASCII & ETC Eos import/export, New show, and workspace layout persistence.

### 2. Patch & Intelligent Fixtures
5. [Patch & DMX Outputs](patch.md) — `Patch` tab (`Add Device`, `Fixture Exchange`, `Patch 1:1`) and `DMX Outputs` tab (real-time 512-address visualizer per universe).
6. [Fixture Library & GDTF](fixtures.md) — `Fixtures` tab: modes, 8/16-bit channels, Channel Ranges, emitter Color Profiles, and `.gdtf` import.
7. [Device Inspector](device_inspector.md) — Full IFCB control for moving lights & LEDs: 16-bit Pan/Tilt encoders, XY pad, N-LED Color Picker (`CIE 1931 xy`, CCT/Duv, gels), and `Beam`.

### 3. Show Building & Effects
8. [Palettes & Presets](palettes.md) — `IP`, `FP`, `CP`, `BP` and `Presets (PR)` categories, cascading references, `Direct Select`, `Select Live`, `Inspector` panel, and live manual recalls.
9. [Groups](groups.md) — Ordered channel selections without levels (`Direct Select`, `Select Live`, `Reverse`, `Sort`, selection order badges `#1`, `#2`, …).
10. [Parametric Effects](effects.md) — Real-time parametric generator, 10 built-in templates, `Groups / Blocks / Wings / Axis° / Spread°`, 1D/2D Visualizer, and cue integration.
11. [Cues](cues.md) — `Cues` tab: channel preview, recording, updating, direct editing, timing, and sequence integration.

### 4. Playback & Real-Time Control
12. [Sequences, Tracking & MIB](sequences.md) — `Sequences` tab, `Tracking` / `Cue-Only` modes, `MIB`, per-family IFCB timings, per-channel times (`Channel Time`), and effect tracking (`FX`).
13. [Multi-Page Faders](faders.md) — `Faders` tab: multi-page banks, assignments (`Main Fader`, `Sequence`, `Preset`, `Effect`), `Size / Rate / Size+Rate` modes, and `Fix` page pinning.
14. [Dimmer Curves (`Curves`)](curves.md) — `Curves` tab: collapsible library, `Limit`, `Segments`, `Interpolate` curves, units (`%` / `DMX`), and 11-step sampled readout.
15. [Track Channels](track_channels.md) — `Track Channels` tab: step-by-step cue history of selected channels with console tracking colors.
16. [Independents](independents.md) — `Independents` tab: 6 auxiliary channels (`knob` / `button`) independent from cues and the main fader.
17. [Virtual Console](virtual_console.md) — Synchronized Eos keypad & action buttons, keyboard shortcut overlay (`F1`), XY cross, level wheel, 10 faders, Flash buttons, and MIDI Learn.

### 5. Preferences, External Control & Tools
18. [Undo History](history.md) — Human-readable Undo/Redo history stack with action names and details.
19. [Preferences](settings.md) — `General`, `OSC`, `MIDI`, `Art-Net`, and `Universes` tabs (Enttec DMX USB Pro / Mk2, sACN, Art-Net).
20. [MIDI & Mackie Control Surfaces](midi.md) — MIDI Learn, rotary encoder modes (`Relative 1`, `Relative 2`, `Mackie`, `Absolute`), motorized feedback, and `MackieLCD` displays.
21. [OSC, OSCQuery & TouchOSC](osc.md) — `asyncio` OSC server on port `7000`, `mDNS` discovery, dynamic Pub/Sub subscriptions, TouchOSC templates, and full `/olc/*` route reference.
22. [Companion Tools & Headless Architecture](tools.md) — `olc-headless`, `olcd`, `olc-monitor` (ZeroMQ TUI), `sacn-monitor` (GTK4), and `olc-bench`.

---

*Next chapter: [1. Introduction →](intro.md)*

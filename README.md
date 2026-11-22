# Open Lighting Console

[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING)

[Français](README.fr.md)

Open Lighting Console (`olc`) is a Linux lighting control console for theater and live shows, combining a headless `CoreEngine`, multi-parameter fixture support, an ETC Eos-style command line, and a GTK3 graphical interface.

**Beta version**

Main Window:
![Screenshot](../assets/olc.png?raw=true)

Virtual Console:
![VirtualConsole](../assets/virtualconsole.png?raw=true)

## Features

- **Multi-Protocol DMX Engine**
  - Hot-configurable multi-universe output over **Art-Net**, **sACN (E1.31)**, and **Enttec DMX USB Pro / Mk2**, with **HTP DMX-In** merging.
  - Continuous `[0.0..1.0]` floating-point internal levels with **8 / 16 / 24-bit** channel resolution and virtual dimmers.
- **Intelligent Fixtures, GDTF & N-LED Colorimetry**
  - Built-in **Fixture Library** tab with definition editor, **DIN SPEC 15800 (`.gdtf`)** import, and live patch synchronization.
  - **IFCB Device Inspector** featuring 16-bit Pan/Tilt rotary encoders, a 2D Pan/Tilt pad, `Home` / `Locate` controls, and a scientific color picker (multi-emitter NNLS solver, **CIE 1931 xy** diagram, gamut hull, Duv tint, and **Lee / Rosco** gel swatchbooks with Delta E matching).
- **Live Views & Show Playback**
  - Three `LiveView` layouts (**Compact**, **Summary+**, and expandable **Table** view with live color swatches), five readout modes (`Auto`, `Label`, `Ref`, `Percent`, `DMX`), and Flexi channel filters (`Patched`, `Active`, `Devices`, `Selected`, `Manual`).
  - **TrackingEngine** with console status colors (including manual red overrides for live palette/preset recalls), **Move In Black (MIB)** look-ahead, per-family IFCB cue timings, timed **Sneak**, **Park / Unpark** (channels and DMX addresses), **Channel Check**, and **Address Check**.
- **Palettes, Presets, Groups, Parametric Effects & Faders**
  - **IFCB Palettes** (`IP`, `FP`, `CP`, `BP`) and **Presets (`PR`)** with cascade propagation, `Direct Select`, and a collapsible content Inspector.
  - Ordered **Groups** with sequence rank badges (`#1`, `#2`, …), `Direct Select`, `Reverse`, `Sort`, and CLI CRUD.
  - **Parametric Effects Engine** (10 built-in templates, `Effects` tab with 1D/2D Cairo preview, cue tracking, and Size/Rate/Both faders).
  - Hot-resizable multi-page **Faders** (assignable to Presets or Effects, with page `Fix` pinning and skip-empty-pages navigation), modernized **Curves** editor, readable **Undo History**, and workspace persistence inside `.olc` show files.
- **Command Line, Virtual Console & Interoperability**
  - **ETC Eos-style LL(1) command line**, full-width CLI bar, and synchronized **Virtual Console** with optional keyboard shortcut overlays (`F1`).
  - Advanced **USITT ASCII / ETC Eos** show import and export (personalities, palettes, cue parts, effects, curves, subs, IFCB timings).
  - Easy **MIDI learning** and bidirectional pure-Python `asyncio` **OSC** with **OSCQuery**, **mDNS** discovery, and ready-to-use **TouchOSC** Phone/Tablet templates (`data/templates/touchosc/`).

## Usage

You can find useful information in the [Documentation](https://mikacousin.github.io/olc/).  
A [manual in French](https://mikacousin.github.io/olc/doc.fr/) is being written and can be translated using online tools in the meantime.

## Installation

### Packages

> Recommended for end users

Distribution | Package
------------ | -------
Flatpak | [![Flathub](https://img.shields.io/flathub/v/com.github.mikacousin.olc)](https://flathub.org/apps/details/com.github.mikacousin.olc)
Archlinux | [![AUR](https://img.shields.io/aur/version/olc-git)](https://aur.archlinux.org/packages/olc-git)

Any help creating packages for other distributions is welcome.

### Manually

> If you want to contribute or run from git, install from source.

#### Core Dependencies

- Python >= 3.10
- GTK3 >= 3.22
- GObject Introspection >= 1.35.0
- PyGObject (`python-gobject`) >= 3.29.1
- py3cairo (`python-cairo`)
- NumPy (`python-numpy`)
- SciPy (`python-scipy`)
- platformdirs (`python-platformdirs`)
- Charset Normalizer (`python-charset-normalizer`)
- ifaddr (`python-ifaddr`)
- mido & python-rtmidi (`python-mido`, `python-rtmidi`)
- pySerial (`python-pyserial`)
- pyzmq (`python-pyzmq`)
- Textual & Rich (`python-textual`, `python-rich` — required by `olc-monitor`)

#### Optional Dependencies

- **GDTF fixture import**: `pygdtf` (`pip install pygdtf`)
- **Enhanced OSC / OSCQuery mDNS discovery**: `zeroconf` (pure-Python mDNS responder fallback is built in)
- **`sacn-monitor` GUI utility**: GTK4 + libadwaita (`gtk4`, `libadwaita`)

#### Ubuntu / Debian

Install build and runtime dependencies:
```bash
sudo apt install meson ninja-build gobject-introspection libgirepository1.0-dev libgtk-3-dev python3-gi python3-gi-dev python3-cairo-dev python3-gi-cairo gettext python3-numpy python3-scipy python3-platformdirs python3-charset-normalizer python3-ifaddr python3-mido python3-rtmidi python3-serial python3-zmq python3-textual python3-rich
```

Optional packages (for `sacn-monitor`, `zeroconf`, and `.gdtf` import):
```bash
sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1 python3-zeroconf
pip install pygdtf
```

#### Building from git

```bash
git clone https://github.com/mikacousin/olc.git
cd olc
meson setup builddir --prefix=/usr/local
sudo ninja -C builddir install
```

Run the software:
```bash
olc
```

## Companion Tools

Open Lighting Console installs helper utilities and remote-control templates alongside the main application:

- **`olc-headless`** (Headless Service): Launches `CoreApplication`, `CoreEngine`, and the OSC server as a background service without any GUI dependencies.
- **`olcd`** (OLC Daemon): Minimal headless `CoreEngine` test runner generating continuous DMX test ramps while exposing OSC control (**currently for testing purposes**).
- **`olc-monitor`** (OLC Monitor): Interactive Terminal User Interface (TUI) built on `textual` and `zmq` streaming live DMX channel values and engine frequency statistics from an active `olc` or `olcd` process.
- **`sacn-monitor`** (sACN Monitor): GTK4 / Adwaita graphical utility for passive sACN network inspection, displaying active sources, priorities, and an intensity grid of all 512 DMX channels.
- **`olc-bench`** (OLC Benchmarking): Stress-testing utility that simulates increasing numbers of active DMX universes to measure the maximum stable universe count at 44 Hz.
- **TouchOSC Templates**: Pre-built phone and tablet layouts (`OpenLightingConsole_Phone.tosc`, `OpenLightingConsole_Tablet.tosc`) are stored in `data/templates/touchosc/` and can be regenerated via `tools/generate_touchosc_templates.py`.

## Development & Testing

```bash
# Lint, formatting, and static type checking
ruff format --check src/ test/
ruff check src/ test/
ty check

# Run core / headless test suite
pytest -m "not gui"

# Run full GTK3 GUI behavioral test suite (under Xvfb)
xvfb-run -a pytest --run-gui -m gui
```

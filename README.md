# Open Lighting Console

[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING) [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)

[French](README.fr.md)

Open Lighting Console (olc) is a linux software to control lights on shows.

**Beta version**

Main Window :
![Screenshot](../assets/olc.png?raw=true)

Virtual console :
![VirtualConsole](../assets/virtualconsole.png?raw=true)

## Usage

You can find some useful informations here: [Documentation](http://mikacousin.github.io/olc/)  
A [manual](http://mikacousin.github.io/olc/doc.fr/) in French is being written, it will be translated when it is advanced enough. In the meantime, you can translate it with online tools.

## Installation

### Packages:
> Recommended for end users

Distribution | Package
------------ | -------
Flatpak | [![Flathub](https://img.shields.io/flathub/v/com.github.mikacousin.olc)](https://flathub.org/apps/details/com.github.mikacousin.olc)
Archlinux | [![AUR](https://img.shields.io/aur/version/olc-git)](https://aur.archlinux.org/packages/olc-git)

Any help to create packages for different distributions is welcome.

### Manually:
> If you want to contribute, you'll need to install from source

#### Depends on

- gtk3 >= 3.20
- python3
- python-gobject
- gobject-introspection
- mido (python-mido (AUR) on archlinux)
- SciPy (python-scipy on archlinux)
- Charset Normalizer (python-charset-normalizer on archlinux)
- NumPy (python-numpy on archlinux)
- ifaddr (python-ifaddr on archlinux)
- pySerial (python-pyserial on archlinux)
- pyzmq (python-pyzmq on archlinux)
- Textual (python-textual on archlinux)
- Rich (python-rich on archlinux)

#### Ubuntu

Install olc dependencies:
```bash
$ sudo apt install meson python3-setuptools gobject-introspection cmake libgirepository1.0-dev libgtk-3-dev python-gi-dev python3-cairo-dev python3-gi-cairo python3-liblo python3-mido python3-rtmidi gettext python3-scipy python3-charset-normalizer python3-numpy python3-ifaddr python3-serial python3-zmq python3-textual python3-rich
```

#### Building from git

```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson setup builddir --prefix=/usr/local
$ sudo ninja -C builddir install
```

You can execute the software:
```bash
$ olc
```

## Companion Tools

Open Lighting Console includes several helper utilities installed alongside the main application to monitor network packages, benchmark performance, or run headless servers:

- **`olcd`** (OLC Daemon): A headless version of Open Lighting Console (**WIP, currently used only for testing purposes**). It initializes and runs the `CoreEngine` without a graphical interface, listening and reacting to OSC messages.
- **`olc-monitor`** (OLC Monitor): An interactive terminal user interface (TUI) based on `textual` and `zmq` that streams real-time DMX channel values and frequency statistics from a running `olcd` or `olc` process.
- **`sacn-monitor`** (sACN Monitor): A modern GTK4/Adwaita graphical utility for passive network packet monitoring of sACN streams. It displays active sources, their priorities, and renders a 3D intensity grid of the 512 DMX channels.
- **`olc-bench`** (OLC Benchmarking): A stress-testing tool that measures the machine's performance limit by incrementally simulating active DMX universes to find the maximum stable universe count at a target 44Hz frequency.


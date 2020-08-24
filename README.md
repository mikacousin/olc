# Open Lighting Console
[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING) [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)

Open Lighting Console (olc) is a linux software to control lights on shows.

Alpha version. **Don't use originals ascii files, test with copies !**

Main Window :
![Screenshot](../assets/olc.png?raw=true)

Virtual console :
![VirtualConsole](../assets/virtual_console.png?raw=true)

## Installation

### Packages:
[![Flathub](https://img.shields.io/flathub/v/com.github.mikacousin.olc)](https://flathub.org/apps/details/com.github.mikacousin.olc)
[![AUR](https://img.shields.io/aur/version/olc-git)](https://aur.archlinux.org/packages/olc-git)

### Manually:

#### Depends on
- gtk3 >= 3.20
- python3
- psutil (python-psutil on archlinux)
- python-gobject
- gobject-introspection
- ola (with python3 support) 
- portmidi
- mido (python-mido on archlinux)
- liblo (python-pyliblo on archlinux)

#### Building from git
```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson builddir --prefix=/usr/local
# sudo ninja -C builddir install
```

## Create and test flakpak package
Compile and run:
```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ flatpak-builder flatpak com.github.mikacousin.olc.json
$ flatpak-builder --run flatpak com.github.mikacousin.olc.json olc
```
To create flatpak file:
```bash
$ flatpak-builder --repo=repo --force-clean flatpak com.github.mikacousin.olc.json
$ flatpak build-bundle repo olc.flatpak com.github.mikacousin.olc
```
To install and launch flatpak file:
```bash
$ flatpak install olc.flatpak
$ flatpak run com.github.mikacousin.olc
```

## Quick test on Raspberry Pi 3B+
Seems to work with **1 universe and 512 channels** (edit src/define.py)

Install ola fom git with python3 support.

And with `sudo apt install` :
- gnome-common
- python-gobject
- gobject-introspection
- libglib2.0-dev
- libgirepository1.0-dev
- libgtk-3-dev
- python3-caido
- python3-gi-caido
- python3-liblo
- python3-mido
- python3-rtmidi
- libasound2-dev
- libjack0
- libjack-dev


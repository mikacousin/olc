
# Open Lighting Console
![License](https://img.shields.io/github/license/mikacousin/olc) [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)

Open Lighting Console (olc) is a linux software to control lights on shows.

Alpha version. **Don't use originals ascii files, test with copies !**

Main Window :
![Screenshot](../assets/olc.png?raw=true)

Virtual console :
![VirtualConsole](../assets/virtual_console.png?raw=true)

## Depends on
- gtk3 >= 3.20
- python3
- python-gobject
- gobject-introspection
- ola (with python3 support) 
- portmidi
- mido (python-mido on archlinux)
- liblo (python-pyliblo on archlinux)

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

## Building from git
```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson builddir --prefix=/usr/local
# sudo ninja -C builddir install
```

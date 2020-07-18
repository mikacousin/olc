
# Open Lighting Console

Open Lighting Console (olc) is a software to control lights on shows.

Alpha version. Don't use it on production !

This project is an exercise to learn python and prepare the real one.

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
Install ola fom git with python3 support

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

## Building from git
```
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ ./autogen.sh
$ make
# make install
```

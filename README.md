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
- psutil (python-psutil on archlinux)
- portmidi
- mido (python-mido on archlinux)
- liblo (python-pyliblo on archlinux)

#### Ubuntu 20.04.1 LTS

Install ola with python 3 support:
```bash
$ sudo apt install git libcppunit-dev libcppunit-1.15-0 uuid-dev pkg-config libncurses5-dev libtool autoconf automake g++ libmicrohttpd-dev libmicrohttpd12 protobuf-compiler libprotobuf-lite17 python-protobuf libprotobuf-dev libprotoc-dev zlib1g-dev bison flex make libftdi-dev libftdi1 libusb-1.0-0-dev liblo-dev libavahi-client-dev python-numpy
$ git clone https://github.com/OpenLightingProject/ola
$ cd ola
$ autoreconf -i
$ PYTHON=python3 ./configure --disable-unittests --disable-examples --disable-osc --enable-http --enable-python-libs
$ make
$ sudo make install
$ sudo ldconfig
```
Install olc dependencies:
```bash
$ sudo apt install meson python3-setuptools gobject-introspection cmake python-gobject libgirepository1.0-dev libgtk-3-dev python-gi-dev python3-cairo-dev python3-psutil python3-liblo python3-mido python3-rtmidi
```

#### Building from git

```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson builddir --prefix=/usr/local
$ sudo ninja -C builddir install
```

#### Raspberry Pi 3B+

**Need some tests**

Seems to work with **1 universe and 512 channels** (edit src/define.py)

Install ola fom git with python3 support.

And with `sudo apt install` :

- gnome-common
- python-gobject
- gobject-introspection
- libglib2.0-dev
- libgirepository1.0-dev
- libgtk-3-dev
- python3-cairo
- python3-gi-cairo
- python3-liblo`
- python3-mido
- python3-rtmidi
- libasound2-dev
- libjack0
- libjack-dev
# Open Lighting Console

[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING) [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)

[English](README.md)

Open Lighting Console (olc) est un logiciel fonctionnant sous linux pour piloter les lumières de spectacles.

**version Beta**

Par précaution, vous ne devriez pas utiliser de fichier ASCII-Light originaux, mais des copies. Ceci afin de ne pas perdre d'information en enregistrant dans le même fichier.

Fenêtre principale :
![Screenshot](../assets/olc.png?raw=true)

Console virtuelle :
![VirtualConsole](../assets/virtualconsole.png?raw=true)

## Usage

Vous trouverez des informations utiles ici : [Documentation](http://mikacousin.github.io/olc/index.fr.html)

## Installation

### Paquets:

Distribution | Paquet
------------ | ------
Flatpak | [![Flathub](https://img.shields.io/flathub/v/com.github.mikacousin.olc)](https://flathub.org/apps/details/com.github.mikacousin.olc)
Archlinux | [![AUR](https://img.shields.io/aur/version/olc-git)](https://aur.archlinux.org/packages/olc-git)

Toute aide pour créer des paquets pour différentes distribution est bienvenue.

### Manuellement:

#### Dependances

- gtk3 >= 3.20
- python3
- python-gobject
- gobject-introspection
- ola (with python3 support)
- portmidi
- mido (python-mido on archlinux)
- liblo (python-pyliblo on archlinux)

#### Ubuntu

Installez ola avec le support de python 3:
```bash
$ sudo apt install git libcppunit-dev libcppunit-1.15-0 uuid-dev pkg-config libncurses5-dev libtool autoconf automake g++ libmicrohttpd-dev libmicrohttpd12 protobuf-compiler libprotobuf-lite23 python3-protobuf libprotobuf-dev libprotoc-dev zlib1g-dev bison flex make libftdi-dev libftdi1 libusb-1.0-0-dev liblo-dev libavahi-client-dev python3-numpy
$ git clone https://github.com/OpenLightingProject/ola
$ cd ola
$ autoreconf -i
$ PYTHON=python3 ./configure --disable-unittests --disable-examples --disable-osc --enable-http --enable-python-libs
$ make
$ sudo make install
$ sudo ldconfig
```
Installez les dépendances pour olc:
```bash
$ sudo apt install meson python3-setuptools gobject-introspection cmake python-gobject libgirepository1.0-dev libgtk-3-dev python-gi-dev python3-cairo-dev python3-gi-cairo python3-liblo python3-mido python3-rtmidi gettext
```

#### Construction à partir de git

```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson setup builddir --prefix=/usr/local
$ sudo ninja -C builddir install
```

#### Raspberry Pi 3B+

**PLus de tests sont nécessaires**

Semble fonctionner avec **1 univers et 512 circuits** (éditez le fichier src/define.py)

Installez ola à partir de  git avec le support de python3.

Et avec `sudo apt install` :

- gnome-common
- python-gobject
- gobject-introspection
- libglib2.0-dev
- libgirepository1.0-dev
- libgtk-3-dev
- python3-cairo
- python3-gi-cairo
- python3-liblo
- python3-mido
- python3-rtmidi
- libasound2-dev
- libjack0
- libjack-dev

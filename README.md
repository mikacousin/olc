# Open Lighting Console

[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING) [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)

[French](README.fr.md)

Open Lighting Console (olc) is a linux software to control lights on shows.

**Beta version**

As a precaution, you should not use original ascii light files, but rather copies. This, in order not to lose information by saving in the same file.

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
- ola (with python3 support)
- sacn (python-sacn (AUR) on archlinux)
- mido (python-mido (AUR) on archlinux)
- liblo (python-pyliblo on archlinux)
- SciPy (python-scipy on archlinux)
- Charset Normalizer (python-charset-normalizer on archlinux)

#### Ubuntu

Install ola with python 3 support:
```bash
$ sudo apt install ola-python
```

Install olc dependencies:
```bash
$ sudo apt install meson python3-setuptools gobject-introspection cmake libgirepository1.0-dev libgtk-3-dev python-gi-dev python3-cairo-dev python3-gi-cairo python3-liblo python3-mido python3-rtmidi gettext python3-scipy python3-charset-normalizer
```

**A package for sacn python module is missing. If you know how to install it, please tell me.**

#### Building from git

```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson setup builddir --prefix=/usr/local
$ sudo ninja -C builddir install
```

You can execute the software without sacn python module:
```bash
$ olc --backend ola
```

#### Raspberry Pi 3B+

**Need some tests**

Seems to work with **1 universe and 512 channels** (edit src/define.py)
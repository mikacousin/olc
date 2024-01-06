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

- Une petite [présentation](http://mikacousin.github.io/olc/index.fr.html).  
- Un [manuel](http://mikacousin.github.io/olc/doc.fr/) en cours d'écriture.  
- Un [espace de discussion francophone](https://github.com/mikacousin/olc/discussions/categories/fran%C3%A7ais).

## Installation

### Paquets:
> Recommandé pour les utilisateurs finaux.

Distribution | Paquet
------------ | ------
Flatpak | [![Flathub](https://img.shields.io/flathub/v/com.github.mikacousin.olc)](https://flathub.org/apps/details/com.github.mikacousin.olc)
Archlinux | [![AUR](https://img.shields.io/aur/version/olc-git)](https://aur.archlinux.org/packages/olc-git)

Toute aide pour créer des paquets pour différentes distribution est bienvenue.

### Manuellement:
> Si vous voulez contribuer, vous aller avoir besoin d'installer depuis les sources.

#### Dependances

- gtk3 >= 3.20
- python3
- python-gobject
- gobject-introspection
- ola (avec support python3)
- sacn (python-sacn (AUR) pour archlinux)
- mido (python-mido (AUR) pour archlinux)
- liblo (python-pyliblo pour archlinux)
- SciPy (python-scipy pour archlinux)
- Charset Normalizer (python-charset-normalizer pour archlinux)

#### Ubuntu

Installez ola avec le support de python 3:
```bash
$ sudo apt install ola-python
```

Installez les dépendances pour olc:
```bash
$ sudo apt install meson python3-setuptools gobject-introspection cmake python-gobject libgirepository1.0-dev libgtk-3-dev python-gi-dev python3-cairo-dev python3-gi-cairo python3-liblo python3-mido python3-rtmidi gettext python3-scipy python3-charset-normalizer
```

**Il manque le paquet pour installer le module sacn pour python. Si vous connaissez une méthode pour l'installer, merci de la partager.**

#### Construction à partir de git

```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson setup builddir --prefix=/usr/local
$ sudo ninja -C builddir install
```

Pour exécuter le logiciel sans le module sacn pour python:
```bash
$ olc --backend ola
```

#### Raspberry Pi 3B+

**Plus de tests sont nécessaires**

Semble fonctionner avec **1 univers et 512 circuits** (éditez le fichier src/define.py)

# Open Lighting Console

[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING) [![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)

[English](README.md)

Open Lighting Console (olc) est un logiciel fonctionnant sous linux pour piloter les lumières de spectacles.

**version Beta**

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
- mido (python-mido (AUR) pour archlinux)
- SciPy (python-scipy pour archlinux)
- Charset Normalizer (python-charset-normalizer pour archlinux)
- NumPy (python-numpy pour archlinux)
- ifaddr (python-ifaddr pour archlinux)
- pySerial (python-pyserial pour archlinux)
- pyzmq (python-pyzmq pour archlinux)
- Textual (python-textual pour archlinux)
- Rich (python-rich pour archlinux)

#### Ubuntu

Installez les dépendances pour olc:
```bash
$ sudo apt install meson python3-setuptools gobject-introspection cmake python-gobject libgirepository1.0-dev libgtk-3-dev python-gi-dev python3-cairo-dev python3-gi-cairo python3-liblo python3-mido python3-rtmidi gettext python3-scipy python3-charset-normalizer python3-numpy python3-ifaddr python3-serial python3-zmq python3-textual python3-rich
```

#### Construction à partir de git

```bash
$ git clone https://github.com/mikacousin/olc.git
$ cd olc
$ meson setup builddir --prefix=/usr/local
$ sudo ninja -C builddir install
```

Pour exécuter le logiciel:
```bash
$ olc
```

## Outils d'accompagnement

Open Lighting Console est fourni avec plusieurs utilitaires complémentaires installés en même temps que l'application principale pour surveiller les trames réseau, évaluer les performances matérielles, ou faire tourner des serveurs en tâche de fond :

- **`olcd`** (Démon OLC) : Version sans interface graphique (headless) d'Open Lighting Console (**en cours de développement - WIP, uniquement pour les tests actuellement**). Cet utilitaire exécute le moteur `CoreEngine` en arrière-plan et réagit aux commandes OSC entrantes.
- **`olc-monitor`** (Moniteur OLC) : Tableau de bord temps réel interactif en mode console (TUI - Terminal User Interface) basé sur `textual` et `zmq` pour suivre en direct les valeurs des canaux DMX et la fréquence d'une instance `olcd` ou `olc` active.
- **`sacn-monitor`** (Moniteur sACN) : Une interface graphique GTK4/Adwaita moderne permettant de surveiller passivement les flux réseau sACN. Elle affiche les émetteurs actifs, leur priorité, et restitue graphiquement les niveaux d'intensité des 512 canaux DMX.
- **`olc-bench`** (Banc de test OLC) : Un outil de stress-test et de benchmarking matériel conçu pour déterminer la limite de la machine en augmentant progressivement le nombre d'univers simulés jusqu'à trouver le seuil de stabilité maximal à 44Hz.


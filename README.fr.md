# Open Lighting Console

[![Release](https://img.shields.io/github/v/release/mikacousin/olc?include_prereleases)](https://github.com/mikacousin/olc/releases/latest) [![License](https://img.shields.io/github/license/mikacousin/olc?color=green)](https://github.com/mikacousin/olc/blob/master/COPYING)

[English](README.md)

Open Lighting Console (`olc`) est un logiciel Linux de conduite lumière pour le théâtre et le spectacle vivant, combinant un moteur `CoreEngine` découplé, la gestion de projecteurs asservis multi-paramètres, une ligne de commande inspirée d'ETC Eos et une interface GTK3.

**Version Bêta**

Fenêtre principale :
![Screenshot](../assets/olc.png?raw=true)

Console virtuelle :
![VirtualConsole](../assets/virtualconsole.png?raw=true)

## Fonctionnalités

- **Moteur DMX multi-protocoles**
  - Configuration à chaud multi-univers en **Art-Net**, **sACN (E1.31)** et **Enttec DMX USB Pro / Mk2**, avec fusion **DMX-In HTP**.
  - Niveaux internes en flottants continus `[0.0..1.0]`, gestion des paramètres **8 / 16 / 24 bits** et gradateurs virtuels.
- **Projecteurs asservis, GDTF & Colorimétrie N-LED**
  - Onglet **Fixture Library** avec éditeur de définitions, import **DIN SPEC 15800 (`.gdtf`)** et synchronisation à chaud du patch.
  - **Device Inspector** IFCB : encodeurs rotatifs Pan/Tilt 16 bits, pad 2D, fonctions `Home` / `Locate` et sélecteur de couleur scientifique (solveur NNLS multi-émetteurs, diagramme **CIE 1931 xy**, polygone de gamut, teinte Duv et nuanciers **Lee / Rosco** avec calcul de Delta E).
- **Vues Live & Conduite**
  - Trois modes d'affichage dans `LiveView` (**Compact**, **Summary+** et **Table** dépliable avec pastilles couleur temps réel), cinq modes de lecture (`Auto`, `Label`, `Ref`, `Percent`, `DMX`) et filtres **Flexi** (`Patched`, `Active`, `Devices`, `Selected`, `Manual`).
  - **TrackingEngine** avec codes couleurs pupitre (dont signalisation rouge des valeurs manuelles y compris après rappel de palette/preset), **Move In Black (MIB)** anticipé, temps par famille IFCB, **Sneak** temporisé, **Park / Unpark** (circuits et adresses DMX), **Channel Check** et **Address Check**.
- **Palettes, Presets, Groupes, Effets paramétriques & Faders**
  - **Palettes IFCB** (`IP`, `FP`, `CP`, `BP`) et **Presets (`PR`)** avec propagation en cascade, `Direct Select` et panneau Inspecteur pliable.
  - **Groupes** ordonnés avec rang de sélection (`#1`, `#2`, …), `Direct Select`, `Reverse`, `Sort` et commandes CLI complètes.
  - **Moteur d'effets paramétriques** (10 modèles intégrés, onglet `Effects` avec aperçu Cairo 1D/2D, tracking en cues, faders Size/Rate/Both).
  - **Faders** multi-pages redimensionnables à chaud (Preset / Effet, épinglage `Fix` sur toutes les pages, saut des pages vides), éditeur de **Courbes** modernisé, historique **Undo/Redo** lisible et persistance de l'espace de travail dans les fichiers `.olc`.
- **Ligne de commande, Console Virtuelle & Interopérabilité**
  - Syntaxe **type ETC Eos** (parseur LL(1)), barre de commande pleine largeur et **Console Virtuelle** avec affichage des raccourcis clavier (`F1`).
  - Import / Export **USITT ASCII / ETC Eos** avancé (personalities, palettes, cue parts, effets, courbes, subs, temps IFCB).
  - Apprentissage **MIDI** simplifié et protocole **OSC** bidirectionnel pur Python (`asyncio`) avec **OSCQuery**, découverte **mDNS** et templates **TouchOSC** téléphone/tablette prêts à l'emploi (`data/templates/touchosc/`).

## Utilisation

- Une [présentation](https://mikacousin.github.io/olc/index.fr.html).
- Un [manuel en français](https://mikacousin.github.io/olc/doc.fr/) en cours d'écriture.
- Un [espace de discussion francophone](https://github.com/mikacousin/olc/discussions/categories/fran%C3%A7ais).

## Installation

### Paquets

> Recommandé pour les utilisateurs finaux.

Distribution | Paquet
------------ | ------
Flatpak | [![Flathub](https://img.shields.io/flathub/v/com.github.mikacousin.olc)](https://flathub.org/apps/details/com.github.mikacousin.olc)
Archlinux | [![AUR](https://img.shields.io/aur/version/olc-git)](https://aur.archlinux.org/packages/olc-git)

Toute aide pour créer des paquets pour différentes distributions est bienvenue.

### Manuellement

> Si vous souhaitez contribuer ou compiler depuis git, installez depuis les sources.

#### Dépendances principales

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
- Textual & Rich (`python-textual`, `python-rich` — requis pour `olc-monitor`)

#### Dépendances optionnelles

- **Import de projecteurs GDTF** : `pygdtf` (`pip install pygdtf`)
- **Découverte mDNS OSC / OSCQuery étendue** : `zeroconf` (un répondeur mDNS natif pur Python est intégré en repli)
- **Utilitaire graphique `sacn-monitor`** : GTK4 + libadwaita (`gtk4`, `libadwaita`)

#### Ubuntu / Debian

Installez les dépendances de compilation et d'exécution :
```bash
sudo apt install meson ninja-build gobject-introspection libgirepository1.0-dev libgtk-3-dev python3-gi python3-gi-dev python3-cairo-dev python3-gi-cairo gettext python3-numpy python3-scipy python3-platformdirs python3-charset-normalizer python3-ifaddr python3-mido python3-rtmidi python3-serial python3-zmq python3-textual python3-rich
```

Paquets optionnels (pour `sacn-monitor`, `zeroconf` et l'import `.gdtf`) :
```bash
sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1 python3-zeroconf
pip install pygdtf
```

#### Construction à partir de git

```bash
git clone https://github.com/mikacousin/olc.git
cd olc
meson setup builddir --prefix=/usr/local
sudo ninja -C builddir install
```

Pour exécuter le logiciel :
```bash
olc
```

## Outils d'accompagnement

Open Lighting Console installe plusieurs utilitaires complémentaires et modèles de contrôle à distance en même temps que l'application principale :

- **`olc-headless`** (Service headless) : Lance `CoreApplication`, `CoreEngine` et le serveur OSC en arrière-plan sans aucune dépendance graphique.
- **`olcd`** (Démon OLC) : Version minimale sans interface graphique exécutant `CoreEngine` avec des rampes de test DMX et un serveur OSC (**utilisée uniquement pour les tests actuellement**).
- **`olc-monitor`** (Moniteur OLC) : Tableau de bord temps réel en mode console (TUI) basé sur `textual` et `zmq` pour suivre en direct les canaux DMX et les statistiques de fréquence d'une instance `olc` ou `olcd`.
- **`sacn-monitor`** (Moniteur sACN) : Utilitaire graphique GTK4 / Adwaita permettant de surveiller passivement les flux réseau sACN (émetteurs actifs, priorités et grille d'intensité des 512 canaux).
- **`olc-bench`** (Banc de test OLC) : Outil de stress-test et de benchmark matériel simulant un nombre croissant d'univers DMX afin de déterminer la limite stable à 44 Hz.
- **Templates TouchOSC** : Layouts téléphone et tablette prêts à l'emploi (`OpenLightingConsole_Phone.tosc`, `OpenLightingConsole_Tablet.tosc`) dans `data/templates/touchosc/`, régénérables via `tools/generate_touchosc_templates.py`.

## Développement & Tests

```bash
# Vérification du formatage, du lint et du typage statique
ruff format --check src/ test/
ruff check src/ test/
ty check

# Lancer la suite de tests headless / Core
pytest -m "not gui"

# Lancer la suite complète des tests GUI GTK3 (sous Xvfb)
xvfb-run -a pytest --run-gui -m gui
```

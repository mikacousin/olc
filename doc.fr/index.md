[English](../doc.en/index.md) | [← Accueil](../index.fr.md)

# Manuel utilisateur — Open Lighting Console

Bienvenue dans le manuel de référence d'**Open Lighting Console (`olc`)** (`0.11.1.beta`).

---

## Table des matières

### 1. Découverte & Interface
1. [Introduction](intro.md) — Présentation, principes fondamentaux (circuits, adresses, HTP/LTP, tracking) et modèle de couleurs de la console.
2. [Fenêtre principale & Vues Direct (`LiveView`)](general.md) — Barre d'en-tête, onglets déplaçables, modes d'affichage (`Compact`, `Summary+`, `Table`), modes de lecture, filtres Flexi et raccourcis clavier.
3. [Ligne de commande (`CLI`)](commandline.md) — Syntaxe inspirée d'ETC Eos, auto-complétion, sélections, niveaux, patch, palettes, effets, séquences, Check/Park/Sneak et touches rapides.
4. [Fichiers, formats & import/export](files.md) — Format natif `.olc`, import/export USITT ASCII & ETC Eos, nouvel espace de travail et persistance des préférences de vue.

### 2. Patch & Projecteurs intelligents
5. [Patch & Sorties DMX](patch.md) — Onglets `Patch` (`Add Device`, `Fixture Exchange`, `Patch 1:1`) et `DMX Outputs` (visualisation temps réel des 512 adresses par univers).
6. [Bibliothèque de projecteurs & GDTF](fixtures.md) — Onglet `Fixtures` : modes, canaux 8/16 bits, plages (*Channel Ranges*), profils colorimétriques d'émetteurs et import `.gdtf`.
7. [Inspecteur de projecteurs (`Device Inspector`)](device_inspector.md) — Contrôle IFCB des projecteurs asservis et LED : encodeurs Pan/Tilt 16 bits, pavé XY, sélecteur couleur N-LED (`CIE 1931 xy`, CCT/Duv, gélatines) et `Beam`.

### 3. Construction & Effets
8. [Palettes & Presets](palettes.md) — Catégories `IP`, `FP`, `CP`, `BP` et `Presets (PR)`, cascade, `Direct Select`, `Select Live`, panneau `Inspector` et rappel en manuel.
9. [Groupes](groups.md) — Sélections ordonnées sans niveau (`Direct Select`, `Select Live`, `Reverse`, `Sort`, badges d'ordre `#1`, `#2`, …).
10. [Effets paramétriques](effects.md) — Générateur paramétrique, 10 modèles intégrés, répartition `Groups / Blocks / Wings / Axis° / Spread°`, visualiseur 1D/2D et intégration aux cues.
11. [Mémoires (`Cues`)](cues.md) — Onglet `Cues`, aperçu des niveaux, création, édition directe, temps et liaison avec les séquences.

### 4. Restitution & Temps réel
12. [Séquences, Tracking & MIB](sequences.md) — Onglet `Sequences`, modes `Tracking` / `Cue-Only`, `MIB`, temps séparés IFCB, temps individuels par circuit (`Channel Time`) et suivi des effets (`FX`).
13. [Faders multi-pages](faders.md) — Onglet `Faders` : banques multi-pages, affectation (`Main Fader`, `Sequence`, `Preset`, `Effect`), modes `Size / Rate / Size+Rate` et épinglage `Fix`.
14. [Courbes de gradation (`Curves`)](curves.md) — Onglet `Curves` : librairie repliable, types `Limit`, `Segments`, `Interpolate`, unités (`%` / `DMX`) et tableau de lecture échantillonné.
15. [Suivi des circuits (`Track Channels`)](track_channels.md) — Onglet `Track Channels` : historique pas-à-pas d'un ou plusieurs circuits dans la conduite avec couleurs de tracking.
16. [Indépendants (`Independents`)](independents.md) — Onglet `Independents` : 6 canaux libres (`knob` / `button`) indépendants des séquences et de la restitution principale.
17. [Console virtuelle (`Virtual Console`)](virtual_console.md) — Pavé numérique et actions Eos synchronisés, calque raccourcis clavier (`F1`), croix X/Y, molette, 10 faders, boutons Flash et apprentissage MIDI.

### 5. Préférences, Contrôle externe & Outils
18. [Historique (`Undo History`)](history.md) — Pile Annuler/Rétablir lisible avec nom d'action et détails.
19. [Préférences (`Preferences`)](settings.md) — Onglets `General`, `OSC`, `MIDI`, `Art-Net` et `Universes` (Enttec DMX USB Pro / Mk2, sACN, Art-Net).
20. [MIDI & Surfaces Mackie Control](midi.md) — Apprentissage MIDI, modes d'encodeurs rotatifs (`Relative 1`, `Relative 2`, `Mackie`, `Absolute`), retour motorisé et écran `MackieLCD`.
21. [OSC, OSCQuery & TouchOSC](osc.md) — Serveur `asyncio` sur port `7000`, découverte `mDNS`, abonnement dynamique Pub/Sub, modèles TouchOSC et référence complète des routes `/olc/*`.
22. [Outils compagnons & Architecture headless](tools.md) — `olc-headless`, `olcd`, `olc-monitor` (TUI ZeroMQ), `sacn-monitor` (GTK4) et `olc-bench`.

---

*Manuel suivant : [1. Introduction →](intro.md)*

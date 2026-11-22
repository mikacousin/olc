[English](../doc.en/files.md) | [← Sommaire](index.md)

# 4. Fichiers, formats & import/export

Le sous-menu **File** (accessible via le bouton de menu de l'en-tête) centralise la gestion des conduites lumière :

- **New** : réinitialise le spectacle en cours (après confirmation si des modifications n'ont pas été enregistrées).
- **Open (`Ctrl+O`)** : ouvre un fichier de spectacle existant.
- **Save (`Ctrl+S`)** / **Save As (`Shift+Ctrl+S`)** : enregistre le spectacle courant au format natif `.olc`.
- **Import ASCII (`Shift+Ctrl+O`)** / **Export ASCII** : importe ou exporte au format texte standardisé **USITT ASCII**.

## Format natif `.olc`

Le fichier `.olc` repose sur une structure **JSON** complète qui sauvegarde sans perte l'intégralité de l'état de la console :

- **Patch & Univers** : circuits simples, projecteurs multi-paramètres, profils personnalisés (*user fixtures*) et affectation des courbes de gradation.
- **Bibliothèque & Construction** : groupes ordonnés, palettes (`Intensity`, `Focus`, `Color`, `Beam`), `Presets`, courbes (`Limit`, `Segments`, `Interpolate`) et effets paramétriques.
- **Restitution** : séquences, étapes (*Steps*), mémoires (*Cues*), références d'effets et de palettes dans les mémoires, temps séparés par famille (`Pos`, `Color`, `Beam`), temps individuels par circuit (`Channel Time`), mode `Tracking / Cue-Only` et `MIB`.
- **Surfaces & Workspace** : configuration multi-pages des faders (y compris épinglage `Fix`), indépendants, affectations MIDI (`note`, `note_cc`, `control_change`) et disposition des onglets ouverts entre les deux volets.

## Import & Export USITT ASCII (avec extensions ETC Eos)

L'import et l'export **USITT ASCII** assurent la compatibilité avec d'autres consoles de théâtre et prennent en charge les extensions **ETC Eos** :

- Circuits, intensités et temps de transfert de base.
- Définitions d'appareils (*personalities* Eos via `eos_devices`), palettes et presets.
- Courbes, submasters / faders, parties de mémoires (*Cue parts*), temps par famille IFCB et données d'effets (`eos_effects`).

---

*Précédent : [3. Ligne de commande (CLI)](commandline.md) — Suivant : [5. Patch & Sorties DMX →](patch.md)*

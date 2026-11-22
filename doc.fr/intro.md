[English](../doc.en/intro.md) | [← Sommaire](index.md)

# 1. Introduction

**Open Lighting Console (`olc`)** est un jeu d'orgue logiciel open source conçu pour le théâtre, le spectacle vivant et le pilotage d'éclairage scénique multi-paramètres sous Linux.

## Concepts fondamentaux

### Circuits et Adresses DMX (`Channels` vs `Outputs`)
- **Circuit (`Channel`)** : numéro logique manipulé par le pupitreur (de `1` à `MAX_CHANNELS`, avec circuits simples ou projecteurs asservis). Un circuit peut contrôler soit un gradateur 8/16 bits, soit un projecteur complet multi-paramètres (*Device*).
- **Adresse DMX (`Universe / Address`)** : sortie physique ou réseau (`1` à `512` par univers) vers laquelle un circuit est patché. Un même circuit peut commander plusieurs gradateurs en parallèle, et un projecteur multi-paramètres occupe un bloc contigu d'adresses selon son mode DMX.

### Logique HTP / LTP & Niveaux continus
- **Niveaux flottants `[0.0 .. 1.0]`** : le moteur `CoreEngine` calcule en interne tous les niveaux en virgule flottante à **44 Hz**, puis quantifie vers **8 bits**, **16 bits** ou **24 bits** selon le profil du projecteur ou de la sortie.
- **HTP (*Highest Takes Precedence*)** : appliqué aux intensités entre les différentes sources (restitution principale, faders, indépendants, fusion DMX-In). La valeur la plus élevée l'emporte.
- **LTP (*Latest Takes Precedence*)** : appliqué aux paramètres non-intensité (Position, Couleur, Beam) ainsi qu'aux valeurs reprises en **manuel** par l'opérateur.

### Code couleur de la console (`Tracking` & priorités)
Dans les grilles de circuits (`LiveView`, `Sequences`, `Track Channels`), la couleur de la valeur indique l'origine et le sens de l'évolution :
- **Rouge** : niveau ou paramètre saisi **en manuel** par l'opérateur (commande clavier, molette, *Device Inspector*, rappel direct de palette/preset en Live). Reste prioritaire jusqu'à un `Sneak`, un `Release` ou un nouvel enregistrement.
- **Jaune / Ambre** : circuit **actif sur scène** en provenance de la restitution ou d'un fader, ou bordure d'indicateur de sélection active.
- **Vert** : niveau ou paramètre qui **monte** par rapport à la mémoire précédente.
- **Bleu / Cyan** : niveau qui **descend** par rapport à la mémoire précédente (ou état suivi en *Tracking*).
- **Magenta** : niveau **bloqué** (*Blocked*), **tracké** inchangé ou associé à une référence de palette/preset selon le contexte d'affichage.
- **Pastille / Badge couleur** : sur les cellules `Summary+` et `Table`, des indicateurs compacts résument l'état `F` (Focus), `C` (Color), `B` (Beam) et l'échantillon RVB temps réel.

---

*Précédent : [Sommaire](index.md) — Suivant : [2. Fenêtre principale & LiveView →](general.md)*

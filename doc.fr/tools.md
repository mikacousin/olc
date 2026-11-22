[English](../doc.en/tools.md) | [← Sommaire](index.md)

# 22. Outils compagnons & Architecture headless

L'installation d'Open Lighting Console fournit un ensemble d'utilitaires en ligne de commande et graphiques autour du moteur sans interface **`CoreEngine`** :

## `olc-headless` — Service sans interface graphique
Lance `CoreApplication`, le moteur `CoreEngine` (avec socket de télémétrie ZeroMQ sur le port `5555`) et le serveur OSC en tâche de fond sans aucune dépendance GTK3 :
```bash
olc-headless
```
Idéal pour exécuter un spectacle piloté exclusivement en OSC ou depuis une machine embarquée/serveur.

## `olcd` — Démon minimal de test `CoreEngine`
Exécute directement un moteur `CoreEngine` (à `44.0 Hz`, port moniteur `5555`) avec des univers de démonstration (Art-Net / sACN) et le serveur OSC exposé (`server_port=7000`, `client_port=9000`) à des fins de test et de validation réseau.

## `olc-monitor` — Moniteur Terminal (TUI)
Interface terminal temps réel basée sur **Textual**, **Rich** et **ZeroMQ (`zmq`)** affichant les valeurs DMX des univers actifs et la fréquence réelle du moteur :
```bash
olc-monitor --fps 10
```
- `--fps <valeur>` : cadence de rafraîchissement de l'interface terminal (défaut : `6.0`).

## `sacn-monitor` — Inspecteur réseau sACN (GTK4)
Utilitaire graphique indépendant développé en **GTK4 / libadwaita** permettant d'inspecter passivement le trafic **sACN (E1.31)** sur le réseau : sources actives, priorités et grille d'intensité des 512 canaux d'un univers.

## `olc-bench` — Banc de charge `CoreEngine`
Outil d'étalonnage mesurant le nombre maximal d'univers simulables à **44.0 Hz** sur la machine courante (et générant des rapports JSON/Markdown) :
```bash
olc-bench --duration 4.0 --max-universes 256 --output olc-bench-report
```
- `--duration <secondes>` : durée de chaque palier de test (`4, 8, 16, 32, 64, 128, 256, ...`, défaut `4.0`).
- `--max-universes <n>` : plafond maximal d'univers à tester (défaut `256`).
- `--listen` : active l'ouverture des sockets de réception bas niveau pendant le benchmark.
- `--output <préfixe>` : préfixe des fichiers de rapport générés (défaut `olc-bench-report`).

## Génération des modèles TouchOSC
Le script `tools/generate_touchosc_templates.py` permet de régénérer les archives `OpenLightingConsole_Phone.tosc` et `OpenLightingConsole_Tablet.tosc` présentes dans `data/templates/touchosc/`.

---

*Précédent : [21. OSC, OSCQuery & TouchOSC](osc.md) — Retour : [Sommaire](index.md)*

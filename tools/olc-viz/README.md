# olc-viz

POC de visualiseur 3D de lumière pour OLC (Rust, `eframe` + `wgpu`), séparé d'OLC et alimenté en ZeroMQ (sans import MVR/GDTF).

## État

| Crate | Rôle | État |
|---|---|---|
| `viz-core` | Modèle pur Z-up (mètres/degrés) : scène, sol/brouillard, projecteurs, canaux DMX | fonctionnel + tests |
| `viz-source` | Trait `DmxSource`, réception ZeroMQ (niveaux + patch/scène), retour `set_focus`/`set_stage`, mode `--demo` | fonctionnel + tests |
| `viz-render` | Rendu `wgpu` : sol paramétrable éclairé, projecteurs procéduraux, faisceaux volumétriques (brouillard), caméra orbitale | fonctionnel + tests |
| `viz-app` | Binaire `olc-viz` : viewport 3D interactif, outil Focus 3D, slider brouillard, vue grille DMX | fonctionnel |
| `viz-mvr` / `viz-export` | Réservés pour évolutions futures (hors périmètre POC) | squelette |

## Utilisation

```sh
# Sans OLC : scène 3D et signal de démonstration
cargo run -p viz-app -- --demo

# Avec OLC (monitor_port 5555 par défaut)
cargo run -p viz-app -- --endpoint tcp://127.0.0.1:5555

# Diagnostic sans interface : affiche niveaux et patch reçus
cargo run -p viz-source --example dump -- tcp://127.0.0.1:5555 5

cargo test --workspace
```

### Raccourcis 3D
- **Navigation** : glisser gauche = orbite, `Shift`+gauche ou milieu/droit = pan, molette = zoom.
- **Focus 3D** : sélectionner un projecteur, activer *Focus 3D*, choisir la hauteur `Z` (`Sol` = 0 m, `Visage` = 1,6 m), cliquer/glisser sur la scène (caméra sur clic droit). La cible est envoyée en direct à OLC (`device.set_focus`, avec cinématique inverse Pan/Tilt sur les lyres).

## Build et installation via Meson

L'option `-Dviz=auto` (par défaut, ou `enabled` / `disabled`) compile `olc-viz` avec `cargo` et l'installe dans `bindir` :

```sh
meson setup _build -Dviz=auto
ninja -C _build        # compiler en utilisateur normal (cache ~/.cargo)
sudo ninja -C _build install
```

## Protocole ZeroMQ

- **Niveaux** (PUB sur `monitor_port`, ex. `5555`) : multipart `[topic, métadonnées JSON, 512 octets]`, `universe:<id>` ou `system` (`status: "shutdown"`).
- **Patch, Scène & Commandes** (REQ/REP sur `monitor_port + 1`, ex. `5556`) :
  - `patch` → snapshot JSON complet (`version`, `stage` `{width, depth, color, grid_spacing, fog_density}`, `devices[]` avec `fixture_type`, `position`, `focus_point`, `orientation`, `beam_angle`, `channels[]`).
  - `{"cmd": "set_focus", "device_id": 101, "target": [x, y, z], "commit": true|false}` → met à jour le focus côté OLC.
  - `{"cmd": "set_stage", "fog_density": 0.4, "commit": true|false}` → synchronise le brouillard / sol dans OLC.

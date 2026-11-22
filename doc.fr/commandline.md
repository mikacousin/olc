[English](../doc.en/commandline.md) | [← Sommaire](index.md)

# 3. Ligne de commande (`CLI`)

Open Lighting Console intègre un analyseur syntaxique **LL(1)** complet (`CommandParser`) inspiré de la logique **ETC Eos**. Il permet de piloter sélections, intensités, attributs de projecteurs, patch, groupes, palettes, presets, effets, mémoires, vérifications de circuits (`Check`) et parquage (`Park`) sans quitter le clavier.

## Ergonomie & Auto-complétion

- Les mots-clés apparaissent colorés en bas de fenêtre au fur et à mesure de la frappe (`CHANNEL`, `GROUP`, `AT`, `FULL`, `THRU`, `EFFECT`, `RECORD`, `SNEAK`, etc.).
- **`Tab`** : complète automatiquement le jeton en cours ou bascule le focus selon le contexte.
- **`Return`** : exécute la commande affichée.
- **`BackSpace`** : efface le dernier jeton ou caractère.
- **`Escape`** ou **`Shift+C`** : vide la ligne de commande et efface la sélection active.
- **`Shift+Haut` / `Shift+Bas`** : parcourt l'historique des commandes exécutées.

## Sélection de circuits

- `<n>` *(ou `CHANNEL <n>`)* : sélectionne le circuit `n`.
- `<a THRU b>` : sélectionne la plage `a` à `b` (`+`, `-` permettent d'ajouter ou retrancher des circuits/plages).
- `GROUP <g>` : rappelle la sélection ordonnée du groupe `g`.
- Filtres relatifs sur la sélection courante : `ALL`, `EVEN` (pairs), `ODD` (impairs), ou `+ <n>` / `- <n>` / `THRU <n>`.
- `LOCATE` : sélectionne et place en position/intensité de repérage le ou les projecteurs sélectionnés.
- `HOME` / `HOME POSITION|COLOR|BEAM` : renvoie les paramètres (ou une famille précise) à leur valeur *Home*.

## Niveaux d'intensité & Attributs

- `<sélection> AT <niveau>` : applique un pourcentage (`0..100`), `FULL` (100 %), `OUT` (0 %), ou un décalage relatif `+ <val>` / `- <val>`.
- `<sélection> PAN|TILT|ZOOM|FOCUS|IRIS|STROBE|CCT|GOBO|PRISM <valeur>` : modifie directement un attribut de projecteur asservi.
- Les commandes `AT <val>` ou `<attribut> <val>` peuvent aussi être saisies directement sans repréciser la sélection : elles s'appliquent alors à la sélection active en Live.

## Patch & Adresses

- `<sélection> PATCH AT <univers>/<adresse>` : patche un circuit ou projecteur sur l'adresse DMX indiquée (le préfixe `<univers>/` est optionnel pour l'univers 1).
- `<sélection> UNPATCH [AT <univers>/<adresse>]` : dépatche totalement un circuit ou retire une adresse précise.
- `ADDRESS <univers>/<adresse> UNPATCH` : dépatche une adresse physique directement.
- `ADDRESS <univers>/<adresse> AT <niveau>` : pilote directement une adresse DMX brute.

## Groupes, Palettes, Presets & Effets

- `RECORD GROUP [<n>] [LABEL "<nom>"]` / `UPDATE GROUP <n>` / `DELETE GROUP <n>` / `LABEL GROUP <n> "<nom>"` : gère les groupes en ligne de commande.
- `RECORD|UPDATE|DELETE IP|FP|CP|BP|INTENSITY|FOCUS|COLOR|BEAM|PRESET <n>` : enregistre, met à jour ou supprime une palette ou un preset.
- `[<sélection>] IP|FP|CP|BP|PRESET <n>` *(ou `INTENSITY|FOCUS|COLOR|BEAM [PALETTE] <n>`)* : applique la palette ou le preset à la sélection (ou aux circuits contenus si aucune sélection n'est active).
- `[<sélection>] EFFECT <n>` : démarre l'effet paramétrique `n` sur la sélection ou sa cible par défaut.
- `STOP [EFFECT [<n>]]` : arrête l'effet `n` ou tous les effets en cours.

## Mémoires (`Cues`), Sneak, Park & Check

- `RECORD [CUE] <n> [TIME <t>]` : enregistre la mémoire `n` (avec options de temps).
- `UPDATE [CUE] [<n>]` : met à jour la mémoire `n` (ou la mémoire active si `<n>` est omis).
- `DELETE [CUE] <n>` : supprime la mémoire `n`.
- `GOTO [CUE] <n> [TIME <t>]` : exécute un saut direct vers la mémoire `n`.
- `BLOCK [CUE] <n>` / `UNBLOCK [CUE] <n>` : bloque ou débloque les valeurs d'une mémoire en mode *Tracking*.
- `[<sélection>] SNEAK [TIME <t>]` : relâche progressivement les valeurs manuelles avec la durée par défaut (`5 s` configurable) ou `t` secondes.
- `<sélection> CHECK [AT <niveau>]` : lance un *Channel Check* séquentiel pas-à-pas au niveau configuré (défaut `80 %`) ou à `<niveau>`.
- `PARK [<sélection>] [AT <niveau>]` / `UNPARK [<sélection> | ALL]` : fige ou libère des circuits (également disponible sur `ADDRESS <u/a> PARK AT <niveau>` et `UNPARK ALL`).
- `INDEPENDENT <n> AT <niveau>` : règle un canal indépendant en ligne de commande.

## Raccourcis clavier directs (touches simples & modificateurs)

En mode direct (sans focus sur un champ texte), les touches suivantes insèrent directement les mots-clés de commande :

| Touche | Jeton | Touche + Shift / Alt | Jeton |
| ------ | ----- | -------------------- | ----- |
| `C` | `CHANNEL` | `Shift+D` | `ADDRESS` |
| `Q` | `CUE` | `Shift+Q` | `GOTO CUE` |
| `G` | `GROUP` | `Shift+P` / `Alt+P` | `PARK` / `UNPARK` |
| `S` | `SEQ` | `Shift+K` | `CHECK` |
| `T` | `THRU` | `Shift+R` / `Shift+U` | `RECORD CUE` / `UPDATE CUE` |
| `M` | `ALL` | `Shift+A` / `Shift+O` | `AT FULL` / `AT OUT` |
| `E` / `J` | `EVEN` / `ODD` | `Shift+H` / `Shift+L` | `HOME` / `LOCATE` |
| `A` / `F` / `O` | `AT` / `FULL` / `OUT` | `Shift+Alt+P` | `POSITION` |
| `N` | `SNEAK` | `Alt+I` / `Alt+F` / `Alt+C` / `Alt+M` | `INTENSITY` / `FOCUS` / `COLOR` / `BEAM` |
| `P` | `PATCH` / `UNPATCH` | `Alt+L` / `Alt+R` | `PALETTE` / `PRESET` |
| `H` / `L` | `HOME` / `LOCATE` | `Alt+E` | `EFFECT` |
| `R` / `U` / `D` | `RECORD` / `UPDATE` / `DELETE` | `Alt+B` | `UNBLOCK` |
| `B` / `I` / `Y` | `BLOCK` / `TIME` / `DELAY` | `Ctrl+Alt+<touche>` *(Stream Deck / POS)* | Couche directe complète |

---

*Précédent : [2. Fenêtre principale & LiveView](general.md) — Suivant : [4. Fichiers, formats & import/export →](files.md)*

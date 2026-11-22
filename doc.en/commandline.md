[Français](../doc.fr/commandline.md) | [← Table of Contents](index.md)

# 3. Command Line (`CLI`)

Open Lighting Console features a dedicated **LL(1) predictive parser** (`CommandParser`) modeled after **ETC Eos** console syntax, allowing fast keyboard-driven programming across channels, fixtures, patch, palettes, effects, cues, Check, Park, and Sneak.

## Workflow & Auto-Completion

- Tokens appear syntax-highlighted in the bottom bar as you type (`CHANNEL`, `GROUP`, `AT`, `FULL`, `THRU`, `EFFECT`, `RECORD`, `SNEAK`, etc.).
- **`Tab`**: auto-completes the current keyword or switches focus depending on context.
- **`Return`**: executes the composed command.
- **`BackSpace`**: deletes the last token or character.
- **`Escape`** or **`Shift+C`**: clears the command line and active selection.
- **`Shift+Up` / `Shift+Down`**: browses command execution history.

## Channel Selection

- `<n>` *(or `CHANNEL <n>`)*: selects channel `n`.
- `<a THRU b>`: selects inclusive range `a` to `b` (`+` and `-` add or subtract channels/ranges).
- `GROUP <g>`: recalls ordered selection from group `g`.
- Relative filters on the current selection: `ALL`, `EVEN`, `ODD`, or `+ <n>` / `- <n>` / `THRU <n>`.
- `LOCATE`: brings selected devices to their locate reference position/intensity.
- `HOME` / `HOME POSITION|COLOR|BEAM`: resets all attributes (or one IFCB family) to *Home*.

## Intensity & Fixture Attributes

- `<selection> AT <level>`: sets percentage (`0..100`), `FULL` (100 %), `OUT` (0 %), or relative step `+ <val>` / `- <val>`.
- `<selection> PAN|TILT|ZOOM|FOCUS|IRIS|STROBE|CCT|GOBO|PRISM <value>`: sets an attribute directly.
- Commands starting with `AT <val>` or `<attribute> <val>` implicitly target the currently selected channels in Live.

## Patch & Direct DMX Addresses

- `<selection> PATCH AT <universe>/<address>`: patches a channel or intelligent fixture (`<universe>/` defaults to universe 1 if omitted).
- `<selection> UNPATCH [AT <universe>/<address>]`: unpatches an entire channel or a specific address.
- `ADDRESS <universe>/<address> UNPATCH`: unpatches a physical DMX address directly.
- `ADDRESS <universe>/<address> AT <level>`: sets a raw DMX address level directly.

## Groups, Palettes, Presets & Effects

- `RECORD GROUP [<n>] [LABEL "<name>"]` / `UPDATE GROUP <n>` / `DELETE GROUP <n>` / `LABEL GROUP <n> "<name>"`: manages ordered groups.
- `RECORD|UPDATE|DELETE IP|FP|CP|BP|INTENSITY|FOCUS|COLOR|BEAM|PRESET <n>`: records, updates, or deletes a palette or preset.
- `[<selection>] IP|FP|CP|BP|PRESET <n>` *(or `INTENSITY|FOCUS|COLOR|BEAM [PALETTE] <n>`)*: applies a palette or preset to the selection (or all stored channels when no live selection is active).
- `[<selection>] EFFECT <n>`: starts parametric effect `n`.
- `STOP [EFFECT [<n>]]`: stops effect `n` or stops all running effects.

## Cues, Sneak, Park & Check

- `RECORD [CUE] <n> [TIME <t>]`: records cue `n` with optional fade time.
- `UPDATE [CUE] [<n>]`: updates cue `n` (or active cue if `<n>` is omitted).
- `DELETE [CUE] <n>`: deletes cue `n`.
- `GOTO [CUE] <n> [TIME <t>]`: jumps directly to cue `n`.
- `BLOCK [CUE] <n>` / `UNBLOCK [CUE] <n>`: blocks or unblocks a cue in Tracking mode.
- `[<selection>] SNEAK [TIME <t>]`: releases manual overrides smoothly over default Sneak time (`5 s`) or `t` seconds.
- `<selection> CHECK [AT <level>]`: steps sequentially through each selected channel at configured check level (default `80 %`) or `<level>`.
- `PARK [<selection>] [AT <level>]` / `UNPARK [<selection> | ALL]`: locks or releases channel overrides (also supported on `ADDRESS <u/a> PARK AT <level>` and `UNPARK ALL`).
- `INDEPENDENT <n> AT <level>`: sets an independent auxiliary channel via CLI.

## Single-Key & Modifier Shortcuts

When no text entry is focused, direct key presses insert CLI tokens:

| Key | Token | Shift / Alt Combo | Token |
| --- | ----- | ----------------- | ----- |
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
| `B` / `I` / `Y` | `BLOCK` / `TIME` / `DELAY` | `Ctrl+Alt+<key>` *(Stream Deck / POS)* | Dedicated non-conflicting command layer |

---

*Previous: [2. Main Window & LiveView](general.md) — Next: [4. Files, Formats & Import/Export →](files.md)*

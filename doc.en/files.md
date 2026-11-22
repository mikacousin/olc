[Français](../doc.fr/files.md) | [← Table of Contents](index.md)

# 4. Files, Formats & Import/Export

The **File** submenu (from the header application menu) manages show persistence and cross-console interchange:

- **New**: resets the current lightshow (prompting if unsaved changes exist).
- **Open (`Ctrl+O`)**: opens an existing show file.
- **Save (`Ctrl+S`)** / **Save As (`Shift+Ctrl+S`)**: writes the show in native `.olc` format.
- **Import ASCII (`Shift+Ctrl+O`)** / **Export ASCII**: imports or exports standard **USITT ASCII** text shows.

## Native `.olc` Format

`.olc` files store the entire console state losslessly in structured **JSON**:

- **Patch & Universes**: dimmers, intelligent devices, custom user fixture definitions, and dimmer curve assignments.
- **Libraries & Construction**: ordered groups, category palettes (`Intensity`, `Focus`, `Color`, `Beam`), `Presets`, dimmer curves (`Limit`, `Segments`, `Interpolate`), and parametric effects.
- **Playback**: sequences, steps, cues, palette & effect references in cues, IFCB family timings (`Pos`, `Color`, `Beam`), per-channel timings (`Channel Time`), `Tracking / Cue-Only` state, and `MIB` flag.
- **Control Surfaces & Workspace**: multi-page fader assignments (including `Fix` page pins), independents, MIDI learn mappings (`note`, `note_cc`, `control_change`), open tabs, pane splits, and divider positions.

## USITT ASCII Import & Export (with ETC Eos Extensions)

USITT ASCII import and export provide interoperability with theater consoles and support **ETC Eos extensions**:

- Channels, dimmer levels, and basic cue timings.
- Fixture personalities (`eos_devices`), palettes, and presets.
- Curves, submasters/faders, cue parts, per-family IFCB timings, and effect records (`eos_effects`).

---

*Previous: [3. Command Line (CLI)](commandline.md) — Next: [5. Patch & DMX Outputs →](patch.md)*

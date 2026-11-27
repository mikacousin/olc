# olc-viz

3D lighting visualizer POC for OLC (Rust, `eframe` + `wgpu`), decoupled from OLC and fed over ZeroMQ (without MVR/GDTF import).

## Status

| Crate | Role | Status |
|---|---|---|
| `viz-core` | Pure Z-up model (meters/degrees): stage, floor/fog, 3D scenery (`SceneryMesh`), fixtures, DMX channels | working + tests |
| `viz-source` | `DmxSource` trait, ZeroMQ receiver (levels + patch/stage/scenery/gobos), `set_focus`/`set_stage` feedback, `--demo` mode | working + tests |
| `viz-render` | `wgpu` renderer: lit floor and 3D scenery (gobo projection, DMX shutter/strobe), procedural fixtures, volumetric beams, orbit camera | working + tests |
| `viz-app` | `olc-viz` binary: interactive 3D viewport, `Scenery` toggle (checked by default), Focus 3D tool, fog slider, DMX grid view | working |
| `viz-mvr` / `viz-export` | Reserved for future features (out of POC scope) | skeleton |

## Usage

```sh
# Without OLC: demo 3D scene and DMX signal
cargo run -p viz-app -- --demo

# With OLC (default monitor_port 5555)
cargo run -p viz-app -- --endpoint tcp://127.0.0.1:5555

# Headless diagnostic: print received levels and patch
cargo run -p viz-source --example dump -- tcp://127.0.0.1:5555 5

cargo test --workspace
```

### 3D Controls
- **Navigation**: left-drag = orbit, `Shift`+left-drag or middle/right-drag = pan, scroll wheel = zoom.
- **Focus 3D**: select a fixture, enable *Focus 3D*, choose the `Z` height (`Floor` = 0 m, `Face` = 1.6 m), click/drag on the stage (right-drag for camera). The target is sent live to OLC (`device.set_focus`, with inverse Pan/Tilt kinematics on moving heads).

## Building and Installing with Meson

The `-Dviz=auto` option (default, or `enabled` / `disabled`) builds `olc-viz` with `cargo` and installs it into `bindir`:

```sh
meson setup _build -Dviz=auto
ninja -C _build        # build as a regular user (~/.cargo cache)
sudo ninja -C _build install
```

## ZeroMQ Protocol

- **Levels** (PUB on `monitor_port`, e.g. `5555`): multipart `[topic, JSON metadata, 512 bytes]`, `universe:<id>` or `system` (`status: "shutdown"`).
- **Patch, Scenery & Commands** (REQ/REP on `monitor_port + 1`, e.g. `5556`):
  - `patch` → full JSON snapshot (`version`, `stage` `{width, depth, color, grid_spacing, fog_density}`, `scenery_count`, `devices[]` with `fixture_type`, `position`, `focus_point`, `orientation`, `beam_angle`, `channels[]`).
  - `{"cmd": "get_scenery"}` → `{"scenery": [...]}` (3D meshes `name`, `color`, `vertices`, `normals`, `indices` from Augment3d).
  - `{"cmd": "get_gobo", "id": "..."}` → raw PNG bytes of a custom gobo.
  - `{"cmd": "set_focus", "device_id": 101, "target": [x, y, z], "commit": true|false}` → updates focus on the OLC side.
  - `{"cmd": "set_stage", "fog_density": 0.4, "commit": true|false}` → syncs fog / stage floor in OLC.

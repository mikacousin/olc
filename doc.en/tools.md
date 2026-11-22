[Français](../doc.fr/tools.md) | [← Table of Contents](index.md)

# 22. Companion Tools & Headless Architecture

Installing Open Lighting Console provides standalone CLI and graphical utilities built around the headless **`CoreEngine`**:

## `olc-headless` — Headless Service Launcher
Starts `CoreApplication`, `CoreEngine` (with ZeroMQ telemetry publisher on port `5555`), and the OSC server as a background service without GTK3 GUI dependencies:
```bash
olc-headless
```
Ideal for headless servers or OSC-driven permanent installations.

## `olcd` — Minimal `CoreEngine` Daemon
Runs `CoreEngine` directly (`44.0 Hz`, monitor port `5555`) with sample Art-Net / sACN universes and OSC routes exposed (`server_port=7000`, `client_port=9000`) for engine testing and network validation.

## `olc-monitor` — Terminal Monitor (TUI)
Interactive terminal UI powered by **Textual**, **Rich**, and **ZeroMQ (`zmq`)**, streaming live DMX universe values and real-time engine frequency telemetry:
```bash
olc-monitor --fps 10
```
- `--fps <value>`: terminal UI refresh rate in frames per second (default: `6.0`).

## `sacn-monitor` — Passive sACN Network Inspector (GTK4)
Standalone **GTK4 / libadwaita** GUI application for passive **sACN (E1.31)** monitoring, showing active network sources, universe priorities, and a live 512-channel intensity matrix.

## `olc-bench` — `CoreEngine` Benchmark Suite
Stress-testing tool measuring the maximum number of universes maintainable at **44.0 Hz** on the host hardware (emitting JSON and Markdown reports):
```bash
olc-bench --duration 4.0 --max-universes 256 --output olc-bench-report
```
- `--duration <seconds>`: duration of each incremental workload step (`4, 8, 16, 32, 64, 128, 256, ...`, default `4.0`).
- `--max-universes <n>`: upper cap of universes to test (default `256`).
- `--listen`: enable low-level DMX receiver sockets during benchmark runs.
- `--output <prefix>`: base filename for generated report artifacts (default `olc-bench-report`).

## Generating TouchOSC Templates
Use `tools/generate_touchosc_templates.py` to rebuild `OpenLightingConsole_Phone.tosc` and `OpenLightingConsole_Tablet.tosc` in `data/templates/touchosc/`.

---

*Previous: [21. OSC, OSCQuery & TouchOSC](osc.md) — Back: [Table of Contents](index.md)*

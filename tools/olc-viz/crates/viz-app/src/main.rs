use std::sync::Arc;
use std::time::{Duration, Instant};

use eframe::egui;
use viz_core::DMX_CHANNELS;
use viz_render::camera::{ray_plane_z, OrbitCamera};
use viz_render::dmx_eval::evaluate_fixtures;
use viz_render::math::project_world_to_screen;
use viz_render::{paint_callback, RenderScene};
use viz_source::{zmq, DmxSource, SharedState, VizCommand};

const COLUMNS: usize = 32;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ViewMode {
    Stage3D,
    DmxGrid,
}

struct VizApp {
    source: SharedState,
    selected_universe: u16,
    endpoint: String,
    view_mode: ViewMode,
    camera: OrbitCamera,
    selected_fixture: Option<u32>,
    show_labels: bool,
    focus_mode: bool,
    focus_height_z: f32,
    local_fog: f32,
    last_patch_version: u64,
    last_cmd_sent: Instant,
    start_time: Instant,
    focus_preview: Option<(u32, [f32; 3])>,
}

impl VizApp {
    fn new(source: SharedState, endpoint: String) -> Self {
        let now = Instant::now();
        Self {
            source,
            selected_universe: 1,
            endpoint,
            view_mode: ViewMode::Stage3D,
            camera: OrbitCamera::iso(),
            selected_fixture: None,
            show_labels: true,
            focus_mode: false,
            focus_height_z: 0.0,
            local_fog: 0.35,
            last_patch_version: 0,
            last_cmd_sent: now - Duration::from_secs(1),
            start_time: now,
            focus_preview: None,
        }
    }

    fn sync_from_source(&mut self) {
        let universes = self.source.universes();
        if !universes.is_empty() && !universes.contains(&self.selected_universe) {
            self.selected_universe = universes[0];
        }
        let patch = self.source.patch();
        if patch.version != self.last_patch_version {
            self.last_patch_version = patch.version;
            self.local_fog = patch.stage.fog_density;
            self.focus_preview = None;
        }
    }

    fn send_throttled(&mut self, cmd: VizCommand, force: bool) {
        if force || self.last_cmd_sent.elapsed() >= Duration::from_millis(50) {
            self.last_cmd_sent = Instant::now();
            self.source.send_command(cmd);
        }
    }

    fn header(&mut self, ui: &mut egui::Ui) {
        let status = self.source.status();
        let patch = self.source.patch();
        ui.horizontal(|ui| {
            let (color, label) = if status.connected {
                (egui::Color32::from_rgb(80, 200, 120), "connecté")
            } else {
                (egui::Color32::from_rgb(220, 90, 90), "déconnecté")
            };
            ui.colored_label(color, label);
            ui.separator();
            ui.label(&self.endpoint);
            ui.separator();
            if status.hz > 0.0 {
                ui.label(format!("{:.0} Hz", status.hz));
                ui.separator();
            }
            ui.label(format!("{} trames", status.frames));
            ui.separator();
            ui.label(format!(
                "patch v{} · {} projecteurs",
                patch.version,
                patch.fixtures.len()
            ));

            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.selectable_value(&mut self.view_mode, ViewMode::DmxGrid, "DMX");
                ui.selectable_value(&mut self.view_mode, ViewMode::Stage3D, "3D");
            });
        });

        if self.view_mode == ViewMode::Stage3D {
            ui.horizontal(|ui| {
                ui.label("Caméra :");
                if ui.button("Iso").clicked() {
                    self.camera = OrbitCamera::iso();
                }
                if ui.button("Face").clicked() {
                    self.camera = OrbitCamera::front();
                }
                if ui.button("Dessus").clicked() {
                    self.camera = OrbitCamera::top();
                }
                if ui.button("Côté").clicked() {
                    self.camera = OrbitCamera::side();
                }
                ui.separator();
                ui.checkbox(&mut self.show_labels, "Étiquettes #id");
                ui.separator();

                ui.label("Brouillard :");
                let fog_resp = ui.add(
                    egui::Slider::new(&mut self.local_fog, 0.0..=1.0)
                        .fixed_decimals(2)
                        .show_value(true),
                );
                if fog_resp.changed() {
                    self.send_throttled(
                        VizCommand::SetStage {
                            width: None,
                            depth: None,
                            color: None,
                            grid_spacing: None,
                            fog_density: Some(self.local_fog),
                            commit: false,
                        },
                        false,
                    );
                }
                if fog_resp.drag_stopped() || (fog_resp.lost_focus() && fog_resp.changed()) {
                    self.send_throttled(
                        VizCommand::SetStage {
                            width: None,
                            depth: None,
                            color: None,
                            grid_spacing: None,
                            fog_density: Some(self.local_fog),
                            commit: true,
                        },
                        true,
                    );
                }

                ui.separator();
                ui.toggle_value(&mut self.focus_mode, "Focus 3D")
                    .on_hover_text("Clic/glisser sur la scène pour viser avec le projecteur sélectionné");
                if self.focus_mode {
                    ui.label("Z :");
                    ui.add(
                        egui::DragValue::new(&mut self.focus_height_z)
                            .speed(0.05)
                            .range(0.0..=4.0)
                            .suffix(" m"),
                    );
                    if ui.button("Sol").clicked() {
                        self.focus_height_z = 0.0;
                    }
                    if ui.button("Visage").clicked() {
                        self.focus_height_z = 1.6;
                    }
                }
            });
        } else {
            ui.horizontal(|ui| {
                ui.label("Univers :");
                let universes = self.source.universes();
                if universes.is_empty() {
                    ui.label("aucun");
                }
                for u in universes {
                    ui.selectable_value(&mut self.selected_universe, u, u.to_string());
                }
            });
        }
    }

    fn fixture_sidebar(&mut self, ui: &mut egui::Ui) {
        let patch = self.source.patch();
        ui.heading("Projecteurs");
        ui.separator();
        if self.focus_mode && self.selected_fixture.is_none() {
            ui.colored_label(
                egui::Color32::from_rgb(245, 190, 80),
                "Sélectionnez un projecteur pour utiliser Focus 3D",
            );
            ui.separator();
        }
        egui::ScrollArea::vertical().show(ui, |ui| {
            if patch.fixtures.is_empty() {
                ui.label("Aucun projecteur patché");
            }
            for f in &patch.fixtures {
                let id = f.channel;
                let selected = id.is_some() && id == self.selected_fixture;
                let text = match id {
                    Some(ch) => format!("#{ch} {}", f.name),
                    None => f.name.clone(),
                };
                if ui.selectable_label(selected, text).clicked() {
                    self.selected_fixture = if selected { None } else { id };
                }
            }
        });
    }

    fn stage_3d(&mut self, ui: &mut egui::Ui) {
        let patch = self.source.patch();
        let mut stage = patch.stage.clone();
        stage.fog_density = self.local_fog;
        let resolved = Arc::new(evaluate_fixtures(
            &patch,
            self.start_time.elapsed().as_secs_f32(),
            |u| self.source.universe(u),
        ));

        let avail = ui.available_size();
        let (rect, response) = ui.allocate_exact_size(avail, egui::Sense::click_and_drag());
        let aspect = (rect.width() / rect.height().max(1.0)).max(0.1);
        let vp = self.camera.view_proj(aspect);

        // Interactions 3D : Focus 3D si actif avec un projecteur sélectionné, sinon caméra / sélection
        let focus_target_id = if self.focus_mode {
            self.selected_fixture
        } else {
            None
        };

        if let Some(dev_id) = focus_target_id {
            let pointer_pos = response.interact_pointer_pos();
            if response.dragged_by(egui::PointerButton::Primary) {
                if let Some(pos) = pointer_pos {
                    if let Some((orig, dir)) = self.camera.screen_ray(pos, rect) {
                        if let Some(hit) = ray_plane_z(orig, dir, self.focus_height_z) {
                            self.focus_preview = Some((dev_id, hit));
                            self.send_throttled(
                                VizCommand::SetFocus {
                                    device_id: dev_id,
                                    target: hit,
                                    commit: false,
                                },
                                false,
                            );
                        }
                    }
                }
            } else if response.drag_stopped_by(egui::PointerButton::Primary)
                || response.clicked_by(egui::PointerButton::Primary)
            {
                if let Some(pos) = pointer_pos {
                    if let Some((orig, dir)) = self.camera.screen_ray(pos, rect) {
                        if let Some(hit) = ray_plane_z(orig, dir, self.focus_height_z) {
                            self.focus_preview = Some((dev_id, hit));
                            self.send_throttled(
                                VizCommand::SetFocus {
                                    device_id: dev_id,
                                    target: hit,
                                    commit: true,
                                },
                                true,
                            );
                        }
                    }
                }
            }

            if response.dragged_by(egui::PointerButton::Secondary) {
                let d = response.drag_delta();
                if ui.input(|i| i.modifiers.shift) {
                    self.camera.pan([d.x, d.y]);
                } else {
                    self.camera.orbit([d.x, d.y]);
                }
            } else if response.dragged_by(egui::PointerButton::Middle) {
                let d = response.drag_delta();
                self.camera.pan([d.x, d.y]);
            }
        } else {
            if response.clicked_by(egui::PointerButton::Primary) {
                if let Some(pos) = response.interact_pointer_pos() {
                    let mut best: Option<(u32, f32)> = None;
                    for f in resolved.iter() {
                        if let Some(ch) = f.channel_id {
                            if let Some(sp) = project_world_to_screen(vp, f.position, rect) {
                                let d = sp.distance(pos);
                                if d < 24.0 && best.is_none_or(|(_, bd)| d < bd) {
                                    best = Some((ch, d));
                                }
                            }
                        }
                    }
                    self.selected_fixture = best.map(|(ch, _)| ch);
                }
            }
            if response.dragged_by(egui::PointerButton::Primary) {
                let d = response.drag_delta();
                if ui.input(|i| i.modifiers.shift) {
                    self.camera.pan([d.x, d.y]);
                } else {
                    self.camera.orbit([d.x, d.y]);
                }
            } else if response.dragged_by(egui::PointerButton::Middle)
                || response.dragged_by(egui::PointerButton::Secondary)
            {
                let d = response.drag_delta();
                self.camera.pan([d.x, d.y]);
            }
        }

        if response.hovered() {
            let scroll = ui.input(|i| i.smooth_scroll_delta.y);
            if scroll.abs() > 0.01 {
                self.camera.zoom(scroll);
            }
        }

        let scene = RenderScene {
            camera: self.camera.clone(),
            stage,
            fixtures: resolved.clone(),
            selected_channel: self.selected_fixture,
            aspect,
            gobo_images: self.source.gobo_images(),
        };
        ui.painter().add(paint_callback(rect, scene));

        let painter = ui.painter_at(rect);
        if self.show_labels {
            for f in resolved.iter() {
                if let Some(ch) = f.channel_id {
                    let pos = [f.position[0], f.position[1], f.position[2] + 0.35];
                    if let Some(sp) = project_world_to_screen(vp, pos, rect) {
                        let is_sel = Some(ch) == self.selected_fixture;
                        let color = if is_sel {
                            egui::Color32::from_rgb(130, 195, 255)
                        } else {
                            egui::Color32::from_gray(220)
                        };
                        painter.text(
                            sp,
                            egui::Align2::CENTER_BOTTOM,
                            format!("#{ch}"),
                            egui::FontId::monospace(11.0),
                            color,
                        );
                    }
                }
            }
        }

        // Repère visuel de la cible Focus du projecteur sélectionné
        if let Some(sel_id) = self.selected_fixture {
            if let Some(f) = resolved.iter().find(|f| f.channel_id == Some(sel_id)) {
                let target = match self.focus_preview {
                    Some((id, p)) if id == sel_id => p,
                    _ => f.focus_point,
                };
                if let (Some(p_src), Some(p_tgt)) = (
                    project_world_to_screen(vp, f.position, rect),
                    project_world_to_screen(vp, target, rect),
                ) {
                    let accent = egui::Color32::from_rgb(255, 200, 80);
                    painter.line_segment([p_src, p_tgt], egui::Stroke::new(1.5, accent));
                    painter.circle_stroke(p_tgt, 7.0, egui::Stroke::new(2.0, accent));
                    painter.text(
                        p_tgt + egui::vec2(10.0, -8.0),
                        egui::Align2::LEFT_BOTTOM,
                        format!("({:.2}, {:.2}, {:.2})", target[0], target[1], target[2]),
                        egui::FontId::monospace(10.5),
                        accent,
                    );
                }
            }
        }
    }

    fn levels(&self, ui: &mut egui::Ui) {
        let Some(frame) = self.source.universe(self.selected_universe) else {
            ui.label("En attente de données…");
            return;
        };
        let avail = ui.available_width();
        let cell = (avail / COLUMNS as f32).clamp(10.0, 40.0);
        let rows = DMX_CHANNELS / COLUMNS;
        let (rect, _) = ui.allocate_exact_size(
            egui::vec2(cell * COLUMNS as f32, cell * rows as f32),
            egui::Sense::hover(),
        );
        let painter = ui.painter_at(rect);
        for (i, &v) in frame.iter().enumerate() {
            let (col, row) = (i % COLUMNS, i / COLUMNS);
            let r = egui::Rect::from_min_size(
                rect.min + egui::vec2(col as f32 * cell, row as f32 * cell),
                egui::vec2(cell - 1.0, cell - 1.0),
            );
            painter.rect_filled(r, 1.0, egui::Color32::from_gray(v));
            if cell >= 24.0 {
                let text_color = if v > 127 {
                    egui::Color32::BLACK
                } else {
                    egui::Color32::WHITE
                };
                painter.text(
                    r.center(),
                    egui::Align2::CENTER_CENTER,
                    v.to_string(),
                    egui::FontId::monospace(10.0),
                    text_color,
                );
            }
        }
    }
}

impl eframe::App for VizApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        self.sync_from_source();
        egui::Panel::top("header").show(ui, |ui| self.header(ui));
        if self.view_mode == ViewMode::Stage3D {
            egui::Panel::left("fixtures")
                .default_size(190.0)
                .show(ui, |ui| self.fixture_sidebar(ui));
            egui::CentralPanel::default()
                .frame(egui::Frame::NONE)
                .show(ui, |ui| self.stage_3d(ui));
        } else {
            egui::CentralPanel::default().show(ui, |ui| self.levels(ui));
        }
        // Les niveaux arrivent en continu : on redessine à ~30 Hz.
        ui.ctx().request_repaint_after(Duration::from_millis(33));
    }
}

fn main() -> eframe::Result {
    let args: Vec<String> = std::env::args().collect();
    let demo = args.iter().any(|a| a == "--demo");
    let endpoint = args
        .iter()
        .position(|a| a == "--endpoint")
        .and_then(|i| args.get(i + 1).cloned())
        .unwrap_or_else(|| zmq::DEFAULT_ENDPOINT.to_string());

    let state = SharedState::new();
    let label = if demo {
        state.spawn_demo();
        "démo".to_string()
    } else {
        zmq::spawn(state.clone(), zmq::ZmqConfig::new(endpoint.clone()));
        endpoint
    };

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("OLC Viz")
            .with_inner_size([1280.0, 760.0]),
        renderer: eframe::Renderer::Wgpu,
        ..Default::default()
    };
    eframe::run_native(
        "OLC Viz",
        options,
        Box::new(move |cc| {
            if let Some(render_state) = &cc.wgpu_render_state {
                viz_render::init_wgpu(render_state);
            }
            Ok(Box::new(VizApp::new(state, label)))
        }),
    )
}

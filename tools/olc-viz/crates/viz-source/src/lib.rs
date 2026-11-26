//! Sources de données du visualiseur : niveaux DMX et patch.
//!
//! L'UI ne dépend que du trait [`DmxSource`]. Aujourd'hui l'implémentation
//! est alimentée par ZeroMQ ([`zmq`]) ; plus tard, un canal en mémoire
//! (visualiseur intégré à OLC) ou du sACN (consoles tierces) pourront
//! l'alimenter sans changer l'UI.

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use serde::Serialize;
use tokio::sync::mpsc::UnboundedSender;
use viz_core::{DmxFrame, Patch, DMX_CHANNELS};

/// Commande envoyée du visualiseur vers OLC (sur `monitor_port + 1`).
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(tag = "cmd", rename_all = "snake_case")]
pub enum VizCommand {
    SetFocus {
        device_id: u32,
        target: [f32; 3],
        commit: bool,
    },
    SetStage {
        #[serde(skip_serializing_if = "Option::is_none")]
        width: Option<f32>,
        #[serde(skip_serializing_if = "Option::is_none")]
        depth: Option<f32>,
        #[serde(skip_serializing_if = "Option::is_none")]
        color: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        grid_spacing: Option<f32>,
        #[serde(skip_serializing_if = "Option::is_none")]
        fog_density: Option<f32>,
        commit: bool,
    },
}

/// Ce que l'UI sait d'une source de données.
pub trait DmxSource: Send + Sync {
    /// Dernière trame reçue pour un univers.
    fn universe(&self, id: u16) -> Option<DmxFrame>;
    /// Univers pour lesquels au moins une trame a été reçue, triés.
    fn universes(&self) -> Vec<u16>;
    /// Patch courant (clone bon marché).
    fn patch(&self) -> Arc<Patch>;
    fn patch_version(&self) -> u64;
    fn status(&self) -> SourceStatus;
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct SourceStatus {
    pub connected: bool,
    /// Nombre total de trames reçues depuis le démarrage.
    pub frames: u64,
    /// Fréquence de sortie DMX annoncée par la source (0 si inconnue).
    pub hz: f32,
}

#[derive(Default)]
struct Inner {
    universes: HashMap<u16, DmxFrame>,
    patch: Arc<Patch>,
    status: SourceStatus,
    cmd_tx: Option<UnboundedSender<VizCommand>>,
    gobo_images: Arc<HashMap<String, Vec<u8>>>,
}

/// État partagé entre le thread de réception et l'UI.
#[derive(Clone, Default)]
pub struct SharedState(Arc<RwLock<Inner>>);

impl SharedState {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn set_universe(&self, id: u16, frame: DmxFrame) {
        if let Ok(mut s) = self.0.write() {
            s.universes.insert(id, frame);
            s.status.frames += 1;
        }
    }

    pub fn remove_universe(&self, id: u16) {
        if let Ok(mut s) = self.0.write() {
            s.universes.remove(&id);
        }
    }

    /// Ne garde que les univers de la liste (ceux qu'OLC déclare actifs).
    pub fn retain_universes(&self, keep: &[u16]) {
        if let Ok(mut s) = self.0.write() {
            s.universes.retain(|id, _| keep.contains(id));
        }
    }

    pub fn clear_universes(&self) {
        if let Ok(mut s) = self.0.write() {
            s.universes.clear();
        }
    }

    pub fn set_patch(&self, patch: Patch) {
        if let Ok(mut s) = self.0.write() {
            s.patch = Arc::new(patch);
        }
    }

    pub fn set_connected(&self, connected: bool) {
        if let Ok(mut s) = self.0.write() {
            s.status.connected = connected;
        }
    }

    pub fn set_hz(&self, hz: f32) {
        if let Ok(mut s) = self.0.write() {
            s.status.hz = hz;
        }
    }

    pub fn set_command_sender(&self, tx: Option<UnboundedSender<VizCommand>>) {
        if let Ok(mut s) = self.0.write() {
            s.cmd_tx = tx;
        }
    }

    /// Envoie une commande vers OLC de façon asynchrone. `false` si aucun transport actif.
    pub fn send_command(&self, cmd: VizCommand) -> bool {
        let tx = self.0.read().ok().and_then(|s| s.cmd_tx.clone());
        match tx {
            Some(tx) => tx.send(cmd).is_ok(),
            None => false,
        }
    }

    pub fn gobo_images(&self) -> Arc<HashMap<String, Vec<u8>>> {
        self.0
            .read()
            .map(|s| s.gobo_images.clone())
            .unwrap_or_default()
    }

    pub fn has_gobo_image(&self, gobo_id: &str) -> bool {
        self.0
            .read()
            .map(|s| s.gobo_images.contains_key(gobo_id))
            .unwrap_or(false)
    }

    pub fn insert_gobo_image(&self, gobo_id: String, bytes: Vec<u8>) {
        if let Ok(mut s) = self.0.write() {
            let mut next = (*s.gobo_images).clone();
            next.insert(gobo_id, bytes);
            s.gobo_images = Arc::new(next);
        }
    }

    /// Génère un signal de démonstration (rampes mobiles + patch 3D sur l'univers 1)
    /// pour développer l'UI sans OLC.
    pub fn spawn_demo(&self) -> std::thread::JoinHandle<()> {
        use viz_core::{DmxAddress, DmxChannel, Fixture, FixtureType, Orientation, Stage, Vec3};

        let demo_patch = Patch {
            version: 1,
            stage: Stage::default(),
            fixtures: vec![
                Fixture {
                    id: "demo:1".into(),
                    channel: Some(1),
                    unit: Some(1),
                    name: "Lyre Jardin".into(),
                    fixture_type: FixtureType::MovingHead,
                    gdtf: None,
                    mode: None,
                    address: Some(DmxAddress { universe: 1, channel: 1 }),
                    footprint: Some(6),
                    position: Vec3::new(-3.5, 2.0, 5.0),
                    focus_point: Vec3::new(-1.0, 0.0, 0.0),
                    orientation: Orientation::default(),
                    beam_angle: 22.0,
                    channels: vec![
                        DmxChannel { channel_type: "intensity".into(), label: String::new(), universe: 1, address: 1, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "red".into(), label: String::new(), universe: 1, address: 2, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "green".into(), label: String::new(), universe: 1, address: 3, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "blue".into(), label: String::new(), universe: 1, address: 4, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "pan".into(), label: String::new(), universe: 1, address: 5, fine: false, ultra_fine: false, physical_min: Some(-90.0), physical_max: Some(90.0), ranges: vec![] },
                        DmxChannel { channel_type: "tilt".into(), label: String::new(), universe: 1, address: 6, fine: false, ultra_fine: false, physical_min: Some(0.0), physical_max: Some(75.0), ranges: vec![] },
                        DmxChannel {
                            channel_type: "gobo_wheel".into(),
                            label: "Gobo_Select".into(),
                            universe: 1,
                            address: 18,
                            fine: false,
                            ultra_fine: false,
                            physical_min: None,
                            physical_max: None,
                            ranges: vec![
                                viz_core::ChannelRange { label: "Stars".into(), min: 0, max: 63, gobo_id: "builtin:stars".into() },
                                viz_core::ChannelRange { label: "Radial".into(), min: 64, max: 127, gobo_id: "builtin:radial".into() },
                                viz_core::ChannelRange { label: "Grid".into(), min: 128, max: 191, gobo_id: "builtin:grid".into() },
                                viz_core::ChannelRange { label: "Breakup".into(), min: 192, max: 255, gobo_id: "builtin:breakup".into() },
                            ],
                        },
                        DmxChannel { channel_type: "generic".into(), label: "gobo_index/speed".into(), universe: 1, address: 19, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "frost".into(), label: "Frost".into(), universe: 1, address: 20, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                    ],
                    static_gobo: String::new(),
                    gel: String::new(),
                    gel_color: String::new(),
                },
                Fixture {
                    id: "demo:2".into(),
                    channel: Some(2),
                    unit: Some(2),
                    name: "Lyre Cour".into(),
                    fixture_type: FixtureType::MovingHead,
                    gdtf: None,
                    mode: None,
                    address: Some(DmxAddress { universe: 1, channel: 7 }),
                    footprint: Some(6),
                    position: Vec3::new(3.5, 2.0, 5.0),
                    focus_point: Vec3::new(1.0, 0.0, 0.0),
                    orientation: Orientation::default(),
                    beam_angle: 22.0,
                    static_gobo: String::new(),
                    gel: String::new(),
                    gel_color: String::new(),
                    channels: vec![
                        DmxChannel { channel_type: "intensity".into(), label: String::new(), universe: 1, address: 7, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "red".into(), label: String::new(), universe: 1, address: 8, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "green".into(), label: String::new(), universe: 1, address: 9, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "blue".into(), label: String::new(), universe: 1, address: 10, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "pan".into(), label: String::new(), universe: 1, address: 11, fine: false, ultra_fine: false, physical_min: Some(-90.0), physical_max: Some(90.0), ranges: vec![] },
                        DmxChannel { channel_type: "tilt".into(), label: String::new(), universe: 1, address: 12, fine: false, ultra_fine: false, physical_min: Some(0.0), physical_max: Some(75.0), ranges: vec![] },
                    ],
                },
                Fixture {
                    id: "demo:3".into(),
                    channel: Some(3),
                    unit: Some(3),
                    name: "Face Centre".into(),
                    fixture_type: FixtureType::LedPar,
                    gdtf: None,
                    mode: None,
                    address: Some(DmxAddress { universe: 1, channel: 13 }),
                    footprint: Some(4),
                    position: Vec3::new(0.0, -4.0, 4.5),
                    focus_point: Vec3::new(0.0, 0.0, 0.0),
                    orientation: Orientation::default(),
                    beam_angle: 32.0,
                    static_gobo: String::new(),
                    gel: String::new(),
                    gel_color: String::new(),
                    channels: vec![
                        DmxChannel { channel_type: "intensity".into(), label: String::new(), universe: 1, address: 13, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "red".into(), label: String::new(), universe: 1, address: 14, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "green".into(), label: String::new(), universe: 1, address: 15, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                        DmxChannel { channel_type: "blue".into(), label: String::new(), universe: 1, address: 16, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] },
                    ],
                },
                Fixture {
                    id: "demo:4".into(),
                    channel: Some(4),
                    unit: Some(4),
                    name: "Douche Jardin".into(),
                    fixture_type: FixtureType::Dimmer,
                    gdtf: None,
                    mode: None,
                    address: Some(DmxAddress { universe: 1, channel: 17 }),
                    footprint: Some(1),
                    position: Vec3::new(-2.5, 0.0, 5.5),
                    focus_point: Vec3::new(-2.5, 0.0, 0.0),
                    orientation: Orientation::default(),
                    beam_angle: 28.0,
                    static_gobo: "builtin:breakup".into(),
                    gel: String::new(),
                    gel_color: String::new(),
                    channels: vec![DmxChannel { channel_type: "intensity".into(), label: String::new(), universe: 1, address: 17, fine: false, ultra_fine: false, physical_min: None, physical_max: None, ranges: vec![] }],
                },
            ],
        };
        self.set_patch(demo_patch);

        let state = self.clone();
        std::thread::spawn(move || {
            state.set_connected(true);
            state.set_hz(44.0);
            let mut t: f32 = 0.0;
            loop {
                let mut frame = [0u8; DMX_CHANNELS];
                // Lyre 1 : bleu/cyan oscillant
                frame[0] = 240;
                frame[1] = 40;
                frame[2] = 180;
                frame[3] = 255;
                frame[4] = (128.0 + 40.0 * t.sin()) as u8;
                frame[5] = (140.0 + 35.0 * (t * 0.7).cos()) as u8;
                // Lyre 2 : magenta/ambre oscillant
                frame[6] = 240;
                frame[7] = 255;
                frame[8] = 60;
                frame[9] = 170;
                frame[10] = (128.0 - 40.0 * t.sin()) as u8;
                frame[11] = (140.0 + 35.0 * (t * 0.7).cos()) as u8;
                // Face centre : blanc chaud
                frame[12] = 220;
                frame[13] = 255;
                frame[14] = 230;
                frame[15] = 200;
                // Douche
                frame[16] = (140.0 + 110.0 * (t * 0.5).sin().abs()) as u8;
                // Roue gobo Lyre 1 : cycle lent sur 4 gobos + rotation continue + frost léger
                frame[17] = (((t * 0.25) as u32 % 4) * 64 + 20) as u8;
                frame[18] = 175;
                frame[19] = (30.0 * (t * 0.4).sin().abs()) as u8;

                state.set_universe(1, frame);
                t += 0.04;
                std::thread::sleep(std::time::Duration::from_millis(23));
            }
        })
    }
}

impl DmxSource for SharedState {
    fn universe(&self, id: u16) -> Option<DmxFrame> {
        self.0.read().ok()?.universes.get(&id).copied()
    }

    fn universes(&self) -> Vec<u16> {
        let mut ids: Vec<u16> = self
            .0
            .read()
            .map(|s| s.universes.keys().copied().collect())
            .unwrap_or_default();
        ids.sort_unstable();
        ids
    }

    fn patch(&self) -> Arc<Patch> {
        self.0.read().map(|s| s.patch.clone()).unwrap_or_default()
    }

    fn patch_version(&self) -> u64 {
        self.0.read().map(|s| s.patch.version).unwrap_or(0)
    }

    fn status(&self) -> SourceStatus {
        self.0.read().map(|s| s.status).unwrap_or_default()
    }
}

/// Réception ZeroMQ depuis OLC.
///
/// **Niveaux DMX** : OLC publie (PUB, `monitor_port`) des messages
/// multipart `[topic, métadonnées JSON, octets DMX]` :
/// - topic `universe:<id>`, payload de 512 octets ;
/// - métadonnées : `hz`, `frames`, `protocols`, `active_universes`, et
///   `patch_version` (ajouté pour le visualiseur) ;
/// - un univers supprimé est annoncé avec `deleted: true` et un payload vide ;
/// - à l'arrêt, un message sur le topic `system` avec `status: "shutdown"`.
///
/// **Patch** : OLC ne publie pas le patch en continu. Quand
/// `patch_version` change dans les métadonnées, le visualiseur demande un
/// snapshot complet en REQ/REP (port `monitor_port + 1`, requête `patch`,
/// réponse JSON). Un patch tient en quelques ko et change rarement : un
/// snapshot complet évite toute logique de deltas et de trous.
pub mod zmq {
    use super::*;
    use serde::Deserialize;
    use std::time::{Duration, Instant};
    use tokio::sync::mpsc::{self, UnboundedReceiver};
    use viz_core::{DmxAddress, DmxChannel, Fixture, FixtureType, Orientation, Stage, Vec3};

    /// Port du `monitor_port` utilisé par défaut par l'application OLC.
    pub const DEFAULT_ENDPOINT: &str = "tcp://127.0.0.1:5555";

    #[derive(Debug, Clone)]
    pub struct ZmqConfig {
        /// PUB d'OLC (niveaux DMX).
        pub endpoint: String,
        /// REP d'OLC (snapshot du patch). `None` désactive la lecture du patch.
        pub patch_endpoint: Option<String>,
    }

    impl ZmqConfig {
        /// Le endpoint du patch est déduit : même hôte, port + 1.
        pub fn new(endpoint: impl Into<String>) -> Self {
            let endpoint = endpoint.into();
            let patch_endpoint = derive_patch_endpoint(&endpoint);
            Self {
                endpoint,
                patch_endpoint,
            }
        }
    }

    impl Default for ZmqConfig {
        fn default() -> Self {
            Self::new(DEFAULT_ENDPOINT)
        }
    }

    /// `tcp://h:5555` devient `tcp://h:5556`.
    pub fn derive_patch_endpoint(endpoint: &str) -> Option<String> {
        let (head, port) = endpoint.rsplit_once(':')?;
        let port: u16 = port.parse().ok()?;
        Some(format!("{head}:{}", port.checked_add(1)?))
    }

    /// Métadonnées publiées par OLC avec chaque trame.
    #[derive(Debug, Clone, PartialEq, Default, Deserialize)]
    pub struct Meta {
        #[serde(default)]
        pub hz: f32,
        #[serde(default)]
        pub frames: u64,
        #[serde(default)]
        pub deleted: bool,
        #[serde(default)]
        pub status: Option<String>,
        #[serde(default)]
        pub active_universes: Vec<u16>,
        #[serde(default)]
        pub patch_version: Option<u64>,
    }

    /// Un message décodé.
    #[derive(Debug, PartialEq)]
    pub enum Message {
        Frame {
            universe: u16,
            frame: DmxFrame,
            meta: Meta,
        },
        UniverseDeleted {
            universe: u16,
        },
        Shutdown,
    }

    /// Décode les trois frames d'un message d'OLC.
    pub fn parse(topic: &[u8], meta: &[u8], data: &[u8]) -> Option<Message> {
        let topic = std::str::from_utf8(topic).ok()?;
        let meta: Meta = serde_json::from_slice(meta).ok()?;
        if topic == "system" {
            return (meta.status.as_deref() == Some("shutdown")).then_some(Message::Shutdown);
        }
        let universe: u16 = topic.strip_prefix("universe:")?.parse().ok()?;
        if meta.deleted {
            return Some(Message::UniverseDeleted { universe });
        }
        let frame: DmxFrame = data.try_into().ok()?;
        Some(Message::Frame {
            universe,
            frame,
            meta,
        })
    }

    #[derive(Debug, Deserialize)]
    struct PatchWire {
        version: u64,
        #[serde(default)]
        stage: Option<Stage>,
        #[serde(default)]
        devices: Vec<DeviceWire>,
    }

    #[derive(Debug, Deserialize)]
    struct DeviceWire {
        id: u32,
        #[serde(default)]
        label: String,
        #[serde(default)]
        manufacturer: String,
        #[serde(default)]
        model: String,
        #[serde(default)]
        mode: String,
        #[serde(default)]
        gdtf: String,
        #[serde(default)]
        fixture_type: FixtureType,
        universe: u16,
        address: u16,
        #[serde(default)]
        footprint: u16,
        #[serde(default = "default_position")]
        position: [f32; 3],
        #[serde(default)]
        focus_point: [f32; 3],
        #[serde(default)]
        orientation: [f32; 3],
        #[serde(default = "default_beam_angle")]
        beam_angle: f32,
        #[serde(default)]
        static_gobo: String,
        #[serde(default)]
        gel: String,
        #[serde(default)]
        gel_color: String,
        #[serde(default)]
        channels: Vec<DmxChannel>,
    }

    fn default_position() -> [f32; 3] {
        [0.0, 0.0, 4.0]
    }

    fn default_beam_angle() -> f32 {
        25.0
    }

    fn non_empty(s: String) -> Option<String> {
        (!s.is_empty()).then_some(s)
    }

    /// Décode un snapshot de patch.
    pub fn parse_patch(bytes: &[u8]) -> Option<Patch> {
        let wire: PatchWire = serde_json::from_slice(bytes).ok()?;
        let fixtures = wire
            .devices
            .into_iter()
            .map(|d| {
                let name = if d.label.is_empty() {
                    format!("{} {}", d.manufacturer, d.model).trim().to_string()
                } else {
                    d.label
                };
                Fixture {
                    id: format!("olc:{}", d.id),
                    channel: Some(d.id),
                    unit: None,
                    name,
                    fixture_type: d.fixture_type,
                    gdtf: non_empty(d.gdtf),
                    mode: non_empty(d.mode),
                    address: Some(DmxAddress {
                        universe: d.universe,
                        channel: d.address,
                    }),
                    footprint: (d.footprint > 0).then_some(d.footprint),
                    position: Vec3::new(d.position[0], d.position[1], d.position[2]),
                    focus_point: Vec3::new(
                        d.focus_point[0],
                        d.focus_point[1],
                        d.focus_point[2],
                    ),
                    orientation: Orientation {
                        yaw: d.orientation[0],
                        pitch: d.orientation[1],
                        roll: d.orientation[2],
                    },
                    beam_angle: d.beam_angle,
                    static_gobo: d.static_gobo,
                    gel: d.gel,
                    gel_color: d.gel_color,
                    channels: d.channels,
                }
            })
            .collect();
        Some(Patch {
            version: wire.version,
            stage: wire.stage.unwrap_or_default(),
            fixtures,
        })
    }

    /// Lance le thread de réception ; il se reconnecte seul en cas d'erreur.
    pub fn spawn(state: SharedState, cfg: ZmqConfig) -> std::thread::JoinHandle<()> {
        let (cmd_tx, mut cmd_rx) = mpsc::unbounded_channel();
        state.set_command_sender(Some(cmd_tx));
        std::thread::spawn(move || {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .expect("runtime tokio");
            rt.block_on(async move {
                loop {
                    if let Err(e) = session(&state, &cfg, &mut cmd_rx).await {
                        eprintln!("zeromq: {e}");
                    }
                    state.set_connected(false);
                    tokio::time::sleep(Duration::from_secs(1)).await;
                }
            });
        })
    }

    /// Demande le snapshot du patch. `None` si OLC ne répond pas en 2 s.
    async fn fetch_patch(endpoint: &str) -> Option<Patch> {
        use ::zeromq::{ReqSocket, Socket, SocketRecv, SocketSend, ZmqMessage};

        let attempt = async {
            let mut req = ReqSocket::new();
            req.connect(endpoint).await.ok()?;
            req.send(ZmqMessage::from("patch")).await.ok()?;
            let reply = req.recv().await.ok()?;
            parse_patch(reply.get(0)?)
        };
        tokio::time::timeout(Duration::from_secs(2), attempt)
            .await
            .ok()
            .flatten()
    }

    /// Demande les octets PNG d'un gobo personnalisé à OLC.
    async fn fetch_gobo_image(endpoint: &str, gobo_id: &str) -> Option<Vec<u8>> {
        use ::zeromq::{ReqSocket, Socket, SocketRecv, SocketSend, ZmqMessage};

        let req_json = serde_json::json!({ "cmd": "get_gobo", "id": gobo_id }).to_string();
        let attempt = async {
            let mut req = ReqSocket::new();
            req.connect(endpoint).await.ok()?;
            req.send(ZmqMessage::from(req_json)).await.ok()?;
            let reply = req.recv().await.ok()?;
            let bytes = reply.get(0)?.to_vec();
            bytes.starts_with(b"\x89PNG").then_some(bytes)
        };
        tokio::time::timeout(Duration::from_secs(2), attempt)
            .await
            .ok()
            .flatten()
    }

    async fn fetch_missing_gobos(state: &SharedState, endpoint: &str, patch: &Patch) {
        let mut ids: Vec<String> = Vec::new();
        for f in &patch.fixtures {
            if !f.static_gobo.is_empty() && !f.static_gobo.starts_with("builtin:") {
                ids.push(f.static_gobo.clone());
            }
            for ch in &f.channels {
                for r in &ch.ranges {
                    if !r.gobo_id.is_empty() && !r.gobo_id.starts_with("builtin:") {
                        ids.push(r.gobo_id.clone());
                    }
                }
            }
        }
        ids.sort();
        ids.dedup();
        for gid in ids {
            if !state.has_gobo_image(&gid) {
                if let Some(bytes) = fetch_gobo_image(endpoint, &gid).await {
                    state.insert_gobo_image(gid, bytes);
                }
            }
        }
    }

    /// Envoie une commande JSON sur le socket REQ/REP (port `monitor_port + 1`).
    async fn send_viz_command(endpoint: &str, cmd: &VizCommand) -> Option<()> {
        use ::zeromq::{ReqSocket, Socket, SocketRecv, SocketSend, ZmqMessage};

        let json = serde_json::to_string(cmd).ok()?;
        let attempt = async {
            let mut req = ReqSocket::new();
            req.connect(endpoint).await.ok()?;
            req.send(ZmqMessage::from(json)).await.ok()?;
            let _reply = req.recv().await.ok()?;
            Some(())
        };
        tokio::time::timeout(Duration::from_secs(2), attempt)
            .await
            .ok()
            .flatten()
    }

    async fn session(
        state: &SharedState,
        cfg: &ZmqConfig,
        cmd_rx: &mut UnboundedReceiver<VizCommand>,
    ) -> Result<(), ::zeromq::ZmqError> {
        use ::zeromq::{Socket, SocketRecv};

        let mut sock = ::zeromq::SubSocket::new();
        sock.connect(&cfg.endpoint).await?;
        sock.subscribe("universe:").await?;
        sock.subscribe("system").await?;

        let mut patch_seen: Option<u64> = None;
        let mut last_patch_try: Option<Instant> = None;

        loop {
            tokio::select! {
                biased;
                Some(cmd) = cmd_rx.recv() => {
                    if let Some(endpoint) = cfg.patch_endpoint.as_deref() {
                        let _ = send_viz_command(endpoint, &cmd).await;
                    }
                }
                recv_res = tokio::time::timeout(Duration::from_secs(3), sock.recv()) => {
                    let msg = match recv_res {
                        Ok(received) => received?,
                        Err(_) => {
                            state.set_connected(false);
                            patch_seen = None;
                            continue;
                        }
                    };
                    let (Some(topic), Some(meta), Some(data)) = (msg.get(0), msg.get(1), msg.get(2))
                    else {
                        continue;
                    };

                    match parse(topic, meta, data) {
                        Some(Message::Frame {
                            universe,
                            frame,
                            meta,
                        }) => {
                            state.set_connected(true);
                            state.set_hz(meta.hz);
                            state.set_universe(universe, frame);
                            if !meta.active_universes.is_empty() {
                                state.retain_universes(&meta.active_universes);
                            }

                            let wanted = meta.patch_version;
                            let retry_ok = last_patch_try
                                .map(|t| t.elapsed() >= Duration::from_secs(2))
                                .unwrap_or(true);
                            if let (Some(version), Some(endpoint)) =
                                (wanted, cfg.patch_endpoint.as_deref())
                            {
                                if patch_seen != Some(version) && retry_ok {
                                    last_patch_try = Some(Instant::now());
                                    if let Some(patch) = fetch_patch(endpoint).await {
                                        patch_seen = Some(patch.version);
                                        fetch_missing_gobos(state, endpoint, &patch).await;
                                        state.set_patch(patch);
                                    }
                                }
                            }
                        }
                        Some(Message::UniverseDeleted { universe }) => state.remove_universe(universe),
                        Some(Message::Shutdown) => {
                            state.set_connected(false);
                            state.clear_universes();
                            patch_seen = None;
                        }
                        None => {}
                    }
                }
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        fn meta_json(extra: &str) -> Vec<u8> {
            format!(r#"{{"hz": 44.0, "frames": 10, "protocols": ["Art-Net"]{extra}}}"#).into_bytes()
        }

        #[test]
        fn parse_frame() {
            let data = [7u8; DMX_CHANNELS];
            let meta = meta_json(r#", "active_universes": [1, 3], "patch_version": 4"#);
            let Some(Message::Frame {
                universe,
                frame,
                meta,
            }) = parse(b"universe:3", &meta, &data)
            else {
                panic!("trame attendue");
            };
            assert_eq!(universe, 3);
            assert_eq!(frame[0], 7);
            assert_eq!(meta.hz, 44.0);
            assert_eq!(meta.active_universes, vec![1, 3]);
            assert_eq!(meta.patch_version, Some(4));
        }

        #[test]
        fn parse_frame_without_patch_version() {
            let data = [0u8; DMX_CHANNELS];
            let Some(Message::Frame { meta, .. }) = parse(b"universe:1", &meta_json(""), &data)
            else {
                panic!("trame attendue");
            };
            assert_eq!(meta.patch_version, None);
        }

        #[test]
        fn parse_deleted_universe_has_empty_payload() {
            let meta = meta_json(r#", "deleted": true"#);
            assert_eq!(
                parse(b"universe:2", &meta, b""),
                Some(Message::UniverseDeleted { universe: 2 })
            );
        }

        #[test]
        fn parse_shutdown() {
            let meta = meta_json(r#", "deleted": true, "status": "shutdown""#);
            assert_eq!(parse(b"system", &meta, b""), Some(Message::Shutdown));
            // Un message system sans status shutdown est ignoré.
            assert_eq!(parse(b"system", &meta_json(""), b""), None);
        }

        #[test]
        fn reject_bad_messages() {
            let data = [0u8; DMX_CHANNELS];
            assert!(parse(b"patch", &meta_json(""), &data).is_none());
            assert!(parse(b"universe:x", &meta_json(""), &data).is_none());
            assert!(parse(b"universe:1", b"pas du json", &data).is_none());
            assert!(parse(b"universe:1", &meta_json(""), &data[..100]).is_none());
        }

        #[test]
        fn patch_endpoint_is_next_port() {
            assert_eq!(
                derive_patch_endpoint("tcp://127.0.0.1:5555").as_deref(),
                Some("tcp://127.0.0.1:5556")
            );
            assert_eq!(derive_patch_endpoint("tcp://hote:65535"), None);
            assert_eq!(derive_patch_endpoint("pas-un-endpoint"), None);
        }

        #[test]
        fn parse_patch_snapshot() {
            let json = br#"{
                "version": 7,
                "devices": [
                    {"id": 101, "label": "Face jardin", "manufacturer": "Robe",
                     "model": "Robin 600", "mode": "Mode 1", "gdtf": "Robe@Robin600",
                     "universe": 2, "address": 17, "footprint": 24},
                    {"id": 5, "label": "", "manufacturer": "Generic", "model": "Dimmer",
                     "universe": 1, "address": 5}
                ]
            }"#;
            let patch = parse_patch(json).expect("patch");
            assert_eq!(patch.version, 7);
            assert_eq!(patch.fixtures.len(), 2);

            let f = &patch.fixtures[0];
            assert_eq!(f.channel, Some(101));
            assert_eq!(f.name, "Face jardin");
            assert_eq!(f.gdtf.as_deref(), Some("Robe@Robin600"));
            assert_eq!(f.address.map(|a| (a.universe, a.channel)), Some((2, 17)));
            assert_eq!(f.footprint, Some(24));

            let g = &patch.fixtures[1];
            assert_eq!(g.name, "Generic Dimmer");
            assert_eq!(g.gdtf, None);
            assert_eq!(g.mode, None);
            assert_eq!(g.footprint, None);
        }

        #[test]
        fn parse_patch_rejects_garbage() {
            assert!(parse_patch(b"{}").is_none());
            assert!(parse_patch(b"nope").is_none());
        }
    }
}

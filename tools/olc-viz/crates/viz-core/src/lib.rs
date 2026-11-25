//! Modèle de données partagé : scène, fixtures, patch, vues.
//!
//! Cette crate ne dépend ni de l'UI, ni du réseau, ni du GPU.
//! Unités : mètres et degrés partout, conversion uniquement aux frontières
//! (import MVR en millimètres, export de plans selon l'échelle).

use serde::{Deserialize, Serialize};

/// Nombre de canaux d'un univers DMX.
pub const DMX_CHANNELS: usize = 512;

/// Une trame DMX complète.
pub type DmxFrame = [u8; DMX_CHANNELS];

#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct Vec3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

impl Vec3 {
    pub const ZERO: Vec3 = Vec3 { x: 0.0, y: 0.0, z: 0.0 };

    pub const fn new(x: f32, y: f32, z: f32) -> Self {
        Self { x, y, z }
    }
}

/// Orientation d'un projecteur (degrés).
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct Orientation {
    pub yaw: f32,
    pub pitch: f32,
    pub roll: f32,
}

/// Adresse DMX : univers (à partir de 1) et canal (1..=512).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct DmxAddress {
    pub universe: u16,
    pub channel: u16,
}

/// Type de projecteur côté OLC.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FixtureType {
    Dimmer,
    MovingHead,
    LedPar,
    Strobe,
    Laser,
    #[default]
    #[serde(other)]
    Generic,
}

/// Canal DMX individuel d'un projecteur.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DmxChannel {
    #[serde(rename = "type")]
    pub channel_type: String,
    pub universe: u16,
    pub address: u16,
    #[serde(default)]
    pub fine: bool,
    #[serde(default)]
    pub ultra_fine: bool,
    #[serde(default)]
    pub physical_min: Option<f32>,
    #[serde(default)]
    pub physical_max: Option<f32>,
}

/// Configuration du sol et du brouillard de scène (en mètres, Z-up).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Stage {
    pub width: f32,
    pub depth: f32,
    pub color: String,
    pub grid_spacing: f32,
    pub fog_density: f32,
}

impl Default for Stage {
    fn default() -> Self {
        Self {
            width: 12.0,
            depth: 10.0,
            color: "#222226".to_string(),
            grid_spacing: 1.0,
            fog_density: 0.35,
        }
    }
}

/// Un projecteur placé dans la scène.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Fixture {
    /// Identifiant stable (UUID MVR si importé).
    pub id: String,
    /// Numéro de canal côté console.
    pub channel: Option<u32>,
    /// Numéro d'unité (plan de feu).
    pub unit: Option<u32>,
    pub name: String,
    #[serde(default)]
    pub fixture_type: FixtureType,
    /// Référence au fichier GDTF (nom ou empreinte), pas la géométrie.
    pub gdtf: Option<String>,
    /// Mode DMX GDTF utilisé.
    pub mode: Option<String>,
    pub address: Option<DmxAddress>,
    /// Nombre de canaux DMX occupés à partir de `address`.
    pub footprint: Option<u16>,
    pub position: Vec3,
    #[serde(default)]
    pub focus_point: Vec3,
    pub orientation: Orientation,
    #[serde(default = "default_beam_angle")]
    pub beam_angle: f32,
    #[serde(default)]
    pub channels: Vec<DmxChannel>,
}

fn default_beam_angle() -> f32 {
    25.0
}

/// Patch complet versionné reçu d'OLC (scène + projecteurs).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Patch {
    pub version: u64,
    #[serde(default)]
    pub stage: Stage,
    pub fixtures: Vec<Fixture>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ViewKind {
    /// Plan de masse (vue de dessus).
    Plan,
    /// Coupe selon un plan.
    Section,
    /// Élévation (vue de face ou de côté, sans coupe).
    Elevation,
}

/// Vue sauvegardée : caméra orthographique + paramètres d'export.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct View {
    pub name: String,
    pub kind: ViewKind,
    /// Point visé et direction de regard.
    pub origin: Vec3,
    pub direction: Vec3,
    /// Plan de coupe : profondeur visible devant/derrière l'origine (mètres).
    pub depth_front: f32,
    pub depth_back: f32,
    /// Dénominateur de l'échelle (50 pour 1:50).
    pub scale: u32,
    pub paper: Paper,
    /// Calques affichés.
    pub layers: Vec<String>,
    pub show_channel: bool,
    pub show_address: bool,
    pub show_unit: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Paper {
    A4,
    A3,
    A2,
    A1,
    A0,
}

impl Paper {
    /// Dimensions en millimètres (paysage).
    pub const fn size_mm(self) -> (f32, f32) {
        match self {
            Paper::A4 => (297.0, 210.0),
            Paper::A3 => (420.0, 297.0),
            Paper::A2 => (594.0, 420.0),
            Paper::A1 => (841.0, 594.0),
            Paper::A0 => (1189.0, 841.0),
        }
    }
}

impl View {
    /// Vue de dessus par défaut au 1:50 sur A3.
    pub fn plan(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            kind: ViewKind::Plan,
            origin: Vec3::ZERO,
            direction: Vec3::new(0.0, 0.0, -1.0),
            depth_front: 100.0,
            depth_back: 100.0,
            scale: 50,
            paper: Paper::A3,
            layers: Vec::new(),
            show_channel: true,
            show_address: false,
            show_unit: true,
        }
    }
}

/// Scène complète : ce qui est sauvegardé dans le fichier de projet.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Scene {
    pub patch: Patch,
    pub views: Vec<View>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plan_view_defaults() {
        let v = View::plan("Masse");
        assert_eq!(v.kind, ViewKind::Plan);
        assert_eq!(v.scale, 50);
        assert_eq!(v.paper.size_mm(), (420.0, 297.0));
    }
}

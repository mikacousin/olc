//! Shared data model: scene, fixtures, patch, views.
//!
//! This crate does not depend on UI, networking, or GPU.
//! Units: meters and degrees everywhere; conversion only at boundaries
//! (MVR import in millimeters, plan export according to scale).

use serde::{Deserialize, Serialize};

/// Number of channels in a DMX universe.
pub const DMX_CHANNELS: usize = 512;

/// A complete DMX frame.
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

/// Fixture orientation (degrees).
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct Orientation {
    pub yaw: f32,
    pub pitch: f32,
    pub roll: f32,
}

/// DMX address: universe (1-based) and channel (1..=512).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct DmxAddress {
    pub universe: u16,
    pub channel: u16,
}

/// Fixture type on the OLC side.
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

/// Discrete range of a DMX channel (gobo wheel, color, etc.).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ChannelRange {
    pub label: String,
    pub min: u8,
    pub max: u8,
    #[serde(default)]
    pub gobo_id: String,
    #[serde(default)]
    pub physical_min: Option<f32>,
    #[serde(default)]
    pub physical_max: Option<f32>,
}

/// Individual DMX channel of a fixture.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct DmxChannel {
    #[serde(rename = "type")]
    pub channel_type: String,
    #[serde(default)]
    pub label: String,
    pub universe: u16,
    pub address: u16,
    #[serde(default)]
    pub fine: bool,
    #[serde(default)]
    pub ultra_fine: bool,
    #[serde(default)]
    pub default_value: Option<u8>,
    #[serde(default)]
    pub physical_min: Option<f32>,
    #[serde(default)]
    pub physical_max: Option<f32>,
    #[serde(default)]
    pub ranges: Vec<ChannelRange>,
}

/// Stage floor and atmospheric fog configuration (in meters, Z-up).
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

/// A fixture placed in the scene.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Fixture {
    /// Stable identifier (MVR UUID if imported).
    pub id: String,
    /// Console channel number.
    pub channel: Option<u32>,
    /// Unit number (light plot).
    pub unit: Option<u32>,
    pub name: String,
    #[serde(default)]
    pub fixture_type: FixtureType,
    /// GDTF file reference (name or fingerprint), not geometry.
    pub gdtf: Option<String>,
    /// Active GDTF DMX mode.
    pub mode: Option<String>,
    pub address: Option<DmxAddress>,
    /// Number of DMX channels occupied starting at `address`.
    pub footprint: Option<u16>,
    pub position: Vec3,
    #[serde(default)]
    pub focus_point: Vec3,
    pub orientation: Orientation,
    #[serde(default = "default_beam_angle")]
    pub beam_angle: f32,
    #[serde(default)]
    pub static_gobo: String,
    #[serde(default)]
    pub gel: String,
    #[serde(default)]
    pub gel_color: String,
    #[serde(default)]
    pub channels: Vec<DmxChannel>,
}

fn default_beam_angle() -> f32 {
    25.0
}

fn default_scenery_color() -> [f32; 3] {
    [0.45, 0.45, 0.48]
}

/// One 3D scenery mesh (wall, truss, prop) imported from Augment3d.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct SceneryMesh {
    #[serde(default)]
    pub name: String,
    #[serde(default = "default_scenery_color")]
    pub color: [f32; 3],
    #[serde(default)]
    pub vertices: Vec<[f32; 3]>,
    #[serde(default)]
    pub normals: Vec<[f32; 3]>,
    #[serde(default)]
    pub indices: Vec<u32>,
}

/// Complete versioned patch received from OLC (stage + fixtures).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Patch {
    pub version: u64,
    #[serde(default)]
    pub stage: Stage,
    pub fixtures: Vec<Fixture>,
    #[serde(default)]
    pub scenery_count: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ViewKind {
    /// Ground plan (top view).
    Plan,
    /// Section cut along a plane.
    Section,
    /// Elevation (front or side view, no cut).
    Elevation,
}

/// Saved view: orthographic camera + export settings.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct View {
    pub name: String,
    pub kind: ViewKind,
    /// Target point and look direction.
    pub origin: Vec3,
    pub direction: Vec3,
    /// Clipping planes: visible depth in front of/behind origin (meters).
    pub depth_front: f32,
    pub depth_back: f32,
    /// Scale denominator (50 for 1:50).
    pub scale: u32,
    pub paper: Paper,
    /// Visible layers.
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
    /// Dimensions in millimeters (landscape).
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
    /// Default top view at 1:50 on A3.
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

/// Complete scene: what is saved in the project file.
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

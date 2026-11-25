//! Évaluation en temps réel des paramètres optiques d'un projecteur depuis les trames DMX.

use viz_core::{DmxChannel, DmxFrame, Fixture, FixtureType, Orientation, Patch};

use crate::math::{forward_pan_tilt, normalize3, sub3};

/// État optique résolu d'un projecteur pour une frame de rendu.
#[derive(Debug, Clone)]
pub struct ResolvedFixture {
    pub channel_id: Option<u32>,
    pub name: String,
    pub fixture_type: FixtureType,
    pub position: [f32; 3],
    pub focus_point: [f32; 3],
    pub orientation: Orientation,
    pub direction: [f32; 3],
    pub pan_deg: f32,
    pub tilt_deg: f32,
    pub intensity: f32,
    pub color: [f32; 3],
    pub beam_angle_deg: f32,
}

fn read_channel_norm<'a>(
    channels: impl Iterator<Item = &'a DmxChannel>,
    get_universe: &impl Fn(u16) -> Option<DmxFrame>,
) -> Option<(f32, Option<(f32, f32)>)> {
    let mut coarse: Option<(u8, Option<(f32, f32)>)> = None;
    let mut fine: Option<u8> = None;
    for ch in channels {
        let Some(frame) = get_universe(ch.universe) else {
            continue;
        };
        let idx = ch.address.saturating_sub(1) as usize;
        if idx >= frame.len() {
            continue;
        }
        let val = frame[idx];
        if ch.fine && !ch.ultra_fine {
            fine = Some(val);
        } else if !ch.fine && !ch.ultra_fine {
            let bounds = match (ch.physical_min, ch.physical_max) {
                (Some(mn), Some(mx)) => Some((mn, mx)),
                _ => None,
            };
            coarse = Some((val, bounds));
        }
    }
    let (c, bounds) = coarse?;
    let norm = match fine {
        Some(f) => (((c as u16) << 8) | (f as u16)) as f32 / 65535.0,
        None => c as f32 / 255.0,
    };
    Some((norm, bounds))
}

fn by_type<'a>(fixture: &'a Fixture, kind: &'a str) -> impl Iterator<Item = &'a DmxChannel> {
    fixture
        .channels
        .iter()
        .filter(move |c| c.channel_type == kind)
}

/// Évalue tous les projecteurs du patch avec les dernières trames DMX reçues.
pub fn evaluate_fixtures(
    patch: &Patch,
    get_universe: impl Fn(u16) -> Option<DmxFrame>,
) -> Vec<ResolvedFixture> {
    patch
        .fixtures
        .iter()
        .map(|f| evaluate_one(f, &get_universe))
        .collect()
}

fn evaluate_one(f: &Fixture, get_universe: &impl Fn(u16) -> Option<DmxFrame>) -> ResolvedFixture {
    // 1. Intensité (supporte les gradateurs multi-sorties : max des canaux intensity)
    let mut intensity = 0.0f32;
    let mut has_intensity = false;
    let mut max_intensity = 0.0f32;
    for ch in by_type(f, "intensity") {
        if !ch.fine && !ch.ultra_fine {
            if let Some(frame) = get_universe(ch.universe) {
                let idx = ch.address.saturating_sub(1) as usize;
                if idx < frame.len() {
                    has_intensity = true;
                    max_intensity = max_intensity.max(frame[idx] as f32 / 255.0);
                }
            }
        }
    }
    if let Some((norm, _)) = read_channel_norm(by_type(f, "intensity"), get_universe) {
        has_intensity = true;
        intensity = norm.max(max_intensity);
    } else if has_intensity {
        intensity = max_intensity;
    } else if f.channels.is_empty() {
        if let Some(addr) = f.address {
            if let Some(frame) = get_universe(addr.universe) {
                let idx = addr.channel.saturating_sub(1) as usize;
                if idx < frame.len() {
                    intensity = frame[idx] as f32 / 255.0;
                    has_intensity = true;
                }
            }
        }
    }

    // 2. Couleur (RGB / White / Amber / CMY)
    let r = read_channel_norm(by_type(f, "red"), get_universe).map(|(v, _)| v);
    let g = read_channel_norm(by_type(f, "green"), get_universe).map(|(v, _)| v);
    let b = read_channel_norm(by_type(f, "blue"), get_universe).map(|(v, _)| v);
    let w = read_channel_norm(by_type(f, "white"), get_universe).map(|(v, _)| v);
    let a = read_channel_norm(by_type(f, "amber"), get_universe).map(|(v, _)| v);
    let c = read_channel_norm(by_type(f, "cyan"), get_universe).map(|(v, _)| v);
    let m = read_channel_norm(by_type(f, "magenta"), get_universe).map(|(v, _)| v);
    let y = read_channel_norm(by_type(f, "yellow"), get_universe).map(|(v, _)| v);

    let has_rgb = r.is_some() || g.is_some() || b.is_some() || w.is_some() || a.is_some();
    let has_cmy = c.is_some() || m.is_some() || y.is_some();

    let color = if has_rgb {
        let wv = w.unwrap_or(0.0);
        let av = a.unwrap_or(0.0);
        [
            (r.unwrap_or(0.0) + wv + av).min(1.0),
            (g.unwrap_or(0.0) + wv + av * 0.6).min(1.0),
            (b.unwrap_or(0.0) + wv).min(1.0),
        ]
    } else if has_cmy {
        [
            1.0 - c.unwrap_or(0.0),
            1.0 - m.unwrap_or(0.0),
            1.0 - y.unwrap_or(0.0),
        ]
    } else {
        // Blanc chaud halogène pour gradateur sans couleur
        [1.0, 0.95, 0.85]
    };

    if !has_intensity && (has_rgb || has_cmy) {
        intensity = 1.0;
    }

    // 3. Pan / Tilt et direction
    let pos = [f.position.x, f.position.y, f.position.z];
    let focus = [f.focus_point.x, f.focus_point.y, f.focus_point.z];

    let pan_res = read_channel_norm(by_type(f, "pan"), get_universe);
    let tilt_res = read_channel_norm(by_type(f, "tilt"), get_universe);

    let (pan_deg, tilt_deg, direction) = if pan_res.is_some() || tilt_res.is_some() {
        let pan = match pan_res {
            Some((norm, bounds)) => {
                let (mn, mx) = bounds.unwrap_or((-270.0, 270.0));
                mn + norm * (mx - mn)
            }
            None => 0.0,
        };
        let tilt = match tilt_res {
            Some((norm, bounds)) => {
                let (mn, mx) = bounds.unwrap_or((-135.0, 135.0));
                mn + norm * (mx - mn)
            }
            None => 0.0,
        };
        (pan, tilt, forward_pan_tilt(f.orientation, pan, tilt))
    } else {
        let mut dir = normalize3(sub3(focus, pos));
        if dir == [0.0, 0.0, 0.0] {
            dir = [0.0, 0.0, -1.0];
        }
        (0.0, 0.0, dir)
    };

    // 4. Zoom
    let beam_angle_deg = match read_channel_norm(by_type(f, "zoom"), get_universe) {
        Some((norm, Some((mn, mx)))) => (mn + norm * (mx - mn)).clamp(2.0, 120.0),
        _ => f.beam_angle.clamp(2.0, 120.0),
    };

    ResolvedFixture {
        channel_id: f.channel,
        name: f.name.clone(),
        fixture_type: f.fixture_type,
        position: pos,
        focus_point: focus,
        orientation: f.orientation,
        direction,
        pan_deg,
        tilt_deg,
        intensity: intensity.clamp(0.0, 1.0),
        color,
        beam_angle_deg,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use viz_core::{DmxAddress, Stage, Vec3, DMX_CHANNELS};

    #[test]
    fn evaluates_moving_head_rgb_and_zoom() {
        let patch = Patch {
            version: 1,
            stage: Stage::default(),
            fixtures: vec![Fixture {
                id: "olc:1".into(),
                channel: Some(1),
                unit: None,
                name: "Spot 1".into(),
                fixture_type: FixtureType::MovingHead,
                gdtf: None,
                mode: None,
                address: Some(DmxAddress {
                    universe: 1,
                    channel: 1,
                }),
                footprint: Some(7),
                position: Vec3::new(0.0, 0.0, 4.0),
                focus_point: Vec3::ZERO,
                orientation: Orientation::default(),
                beam_angle: 25.0,
                channels: vec![
                    DmxChannel {
                        channel_type: "intensity".into(),
                        universe: 1,
                        address: 1,
                        fine: false,
                        ultra_fine: false,
                        physical_min: None,
                        physical_max: None,
                    },
                    DmxChannel {
                        channel_type: "red".into(),
                        universe: 1,
                        address: 2,
                        fine: false,
                        ultra_fine: false,
                        physical_min: None,
                        physical_max: None,
                    },
                    DmxChannel {
                        channel_type: "pan".into(),
                        universe: 1,
                        address: 3,
                        fine: false,
                        ultra_fine: false,
                        physical_min: Some(-270.0),
                        physical_max: Some(270.0),
                    },
                    DmxChannel {
                        channel_type: "tilt".into(),
                        universe: 1,
                        address: 4,
                        fine: false,
                        ultra_fine: false,
                        physical_min: Some(-135.0),
                        physical_max: Some(135.0),
                    },
                    DmxChannel {
                        channel_type: "zoom".into(),
                        universe: 1,
                        address: 5,
                        fine: false,
                        ultra_fine: false,
                        physical_min: Some(10.0),
                        physical_max: Some(50.0),
                    },
                ],
            }],
        };

        let mut frame = [0u8; DMX_CHANNELS];
        frame[0] = 255; // intensity
        frame[1] = 255; // red
        frame[2] = 128; // pan ~ 0
        frame[3] = 170; // tilt > 0
        frame[4] = 255; // zoom = 50°

        let res = evaluate_fixtures(&patch, |u| (u == 1).then_some(frame));
        assert_eq!(res.len(), 1);
        assert!((res[0].intensity - 1.0).abs() < 1e-4);
        assert!((res[0].color[0] - 1.0).abs() < 1e-4);
        assert!((res[0].beam_angle_deg - 50.0).abs() < 1e-4);
        assert!(res[0].tilt_deg > 40.0);
    }
}

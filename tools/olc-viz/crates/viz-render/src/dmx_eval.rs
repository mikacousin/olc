//! Real-time evaluation of fixture optical parameters from DMX frames.

use viz_core::{DmxChannel, DmxFrame, Fixture, FixtureType, Orientation, Patch};

use crate::math::{forward_pan_tilt, normalize3, sub3};

/// State of an engaged gobo wheel on a fixture.
#[derive(Debug, Clone, Default)]
pub struct GoboWheelState {
    pub gobo_id: String,
    pub slot_index: usize,
    pub rot_rad: f32,
}

/// Resolved optical state of a fixture for a render frame.
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
    pub gobos: [GoboWheelState; 2],
    pub gobo_blur_lod: f32,
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

fn is_gobo_rot_channel(ch: &DmxChannel) -> bool {
    if ch.channel_type == "gobo_rotation" {
        return true;
    }
    let low = ch.label.to_ascii_lowercase();
    let has_rot_kw = low.contains("index")
        || low.contains("spin")
        || low.contains("rot")
        || low.contains("pos");
    if ch.channel_type == "gobo_wheel" {
        return has_rot_kw;
    }
    if ch.channel_type == "generic" {
        return low.contains("gobo") && has_rot_kw;
    }
    false
}

fn is_gobo_select_channel(ch: &DmxChannel) -> bool {
    if ch.fine || ch.ultra_fine || is_gobo_rot_channel(ch) {
        return false;
    }
    if ch.channel_type == "gobo_wheel" {
        return true;
    }
    if ch.channel_type == "generic" {
        let low = ch.label.to_ascii_lowercase();
        return low == "gobo_select_2"
            || low == "gobo_select_3"
            || low == "gobo2"
            || low == "gobo3"
            || low.starts_with("gobo_select");
    }
    false
}

fn extract_wheel_number(label: &str) -> Option<u8> {
    let low = label.to_ascii_lowercase();
    for (num, pats) in [
        (1u8, &["gobo1", "gobo_1", "gobo 1", "_1", " 1"][..]),
        (2u8, &["gobo2", "gobo_2", "gobo 2", "_2", " 2"][..]),
        (3u8, &["gobo3", "gobo_3", "gobo 3", "_3", " 3"][..]),
    ] {
        if pats.iter().any(|p| low.contains(p)) {
            return Some(num);
        }
    }
    None
}

const MAX_GOBO_ROT_RAD_PER_SEC: f32 = 8.0;
const STOP_DEADZONE: f32 = 0.03;

fn eval_bipolar_spin(norm: f32, lo: f32, hi: f32, time_sec: f32) -> f32 {
    let mid = (lo + hi) * 0.5;
    let half = ((hi - lo) * 0.5).max(1e-4);
    let rel = ((norm - mid) / half).clamp(-1.0, 1.0);
    if rel.abs() < STOP_DEADZONE {
        0.0
    } else {
        time_sec * rel * MAX_GOBO_ROT_RAD_PER_SEC
    }
}

fn eval_wheel_rotation(
    f: &Fixture,
    wheel_num: u8,
    time_sec: f32,
    get_universe: &impl Fn(u16) -> Option<DmxFrame>,
) -> f32 {
    let mut matched_coarse: Option<&DmxChannel> = None;
    let mut matched_fine: Option<&DmxChannel> = None;
    for c in &f.channels {
        if !is_gobo_rot_channel(c) {
            continue;
        }
        let ch_wheel = extract_wheel_number(&c.label);
        let matches = ch_wheel == Some(wheel_num) || (wheel_num == 1 && ch_wheel.is_none());
        if !matches {
            continue;
        }
        if !c.fine && !c.ultra_fine && matched_coarse.is_none() {
            matched_coarse = Some(c);
        } else if c.fine && !c.ultra_fine && matched_fine.is_none() {
            matched_fine = Some(c);
        }
    }
    let iter = matched_coarse.into_iter().chain(matched_fine);
    let Some((norm, _)) = read_channel_norm(iter, get_universe) else {
        return 0.0;
    };

    if let Some(coarse) = matched_coarse {
        if !coarse.ranges.is_empty() {
            let dmx = (norm * 255.0).round().clamp(0.0, 255.0) as u8;
            if let Some(r) = coarse.ranges.iter().find(|r| dmx >= r.min && dmx <= r.max) {
                let low = r.label.to_ascii_lowercase();
                let lo = r.min as f32 / 255.0;
                let hi = r.max as f32 / 255.0;
                let span = (hi - lo).max(1e-4);
                if low.contains("stop") || low.contains("no rot") {
                    return 0.0;
                }
                if (low.contains("index") || low.contains("pos"))
                    && !low.contains("rot")
                    && !low.contains("spin")
                    && !low.contains("cw")
                {
                    return ((norm - lo) / span).clamp(0.0, 1.0) * std::f32::consts::TAU;
                }
                if low.contains("ccw") || low.contains("counter") {
                    return time_sec
                        * ((norm - lo) / span).clamp(0.0, 1.0)
                        * MAX_GOBO_ROT_RAD_PER_SEC;
                }
                if low.contains("cw") {
                    return -time_sec
                        * ((hi - norm) / span).clamp(0.0, 1.0)
                        * MAX_GOBO_ROT_RAD_PER_SEC;
                }
                if low.contains("rot") || low.contains("spin") {
                    return eval_bipolar_spin(norm, lo, hi, time_sec);
                }
            }
        }
    }

    if norm >= 0.5 {
        eval_bipolar_spin(norm, 0.5, 1.0, time_sec)
    } else {
        (norm / 0.5) * std::f32::consts::TAU
    }
}

fn is_slot_open(gobo_id: &str, slot_index: usize) -> bool {
    if gobo_id.is_empty() || gobo_id.eq_ignore_ascii_case("builtin:open") {
        return true;
    }
    !gobo_id.contains(':') && crate::gobo::resolve_builtin_index(gobo_id, slot_index) == 0
}

/// Evaluate all patched fixtures using the latest received DMX frames.
pub fn evaluate_fixtures(
    patch: &Patch,
    time_sec: f32,
    get_universe: impl Fn(u16) -> Option<DmxFrame>,
) -> Vec<ResolvedFixture> {
    patch
        .fixtures
        .iter()
        .map(|f| evaluate_one(f, time_sec, &get_universe))
        .collect()
}

fn evaluate_one(
    f: &Fixture,
    time_sec: f32,
    get_universe: &impl Fn(u16) -> Option<DmxFrame>,
) -> ResolvedFixture {
    // 1. Intensity (supports multi-output dimmers: max of intensity channels)
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
    } else if !f.gel_color.is_empty() {
        crate::math::parse_hex_color(&f.gel_color)
    } else {
        // Warm tungsten halogen white for dimmer without gel/color
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

    // 5. Active gobos (up to 2 simultaneous DMX wheels or static_gobo on fixed fixture)
    let mut gobos: [GoboWheelState; 2] = Default::default();
    let mut engaged_count = 0usize;
    let mut seq_idx = 0u8;
    for gobo_ch in f.channels.iter().filter(|c| is_gobo_select_channel(c)) {
        seq_idx = seq_idx.saturating_add(1);
        let wheel_num = extract_wheel_number(&gobo_ch.label).unwrap_or(seq_idx);
        if let Some(frame) = get_universe(gobo_ch.universe) {
            let idx = gobo_ch.address.saturating_sub(1) as usize;
            if idx < frame.len() {
                let dmx_val = frame[idx];
                if let Some((slot_idx, range)) = gobo_ch
                    .ranges
                    .iter()
                    .enumerate()
                    .find(|(_, r)| dmx_val >= r.min && dmx_val <= r.max)
                {
                    let gid = if !range.gobo_id.is_empty() {
                        range.gobo_id.clone()
                    } else {
                        range.label.clone()
                    };
                    if !is_slot_open(&gid, slot_idx) && engaged_count < 2 {
                        let rot_rad = eval_wheel_rotation(f, wheel_num, time_sec, get_universe);
                        gobos[engaged_count] = GoboWheelState {
                            gobo_id: gid,
                            slot_index: slot_idx,
                            rot_rad,
                        };
                        engaged_count += 1;
                    }
                }
            }
        }
    }
    if engaged_count == 0 {
        let rot0 = eval_wheel_rotation(f, 1, time_sec, get_universe);
        gobos[0] = GoboWheelState {
            gobo_id: f.static_gobo.clone(),
            slot_index: 0,
            rot_rad: rot0,
        };
    }

    // 6. Flou optique (Frost + Focus defocus) -> niveau mipmap [0.0..4.0]
    let frost_blur = read_channel_norm(by_type(f, "frost"), get_universe)
        .map(|(n, _)| n * 3.5)
        .unwrap_or(0.0);
    let focus_blur = read_channel_norm(by_type(f, "focus"), get_universe)
        .map(|(n, _)| (n - 0.5).abs() * 2.0 * 1.8)
        .unwrap_or(0.0);
    let gobo_blur_lod = (frost_blur + focus_blur).clamp(0.0, 4.0);

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
        gobos,
        gobo_blur_lod,
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
                static_gobo: String::new(),
                gel: String::new(),
                gel_color: String::new(),
                channels: vec![
                    DmxChannel {
                        channel_type: "intensity".into(),
                        label: String::new(),
                        universe: 1,
                        address: 1,
                        fine: false,
                        ultra_fine: false,
                        physical_min: None,
                        physical_max: None,
                        ranges: vec![],
                    },
                    DmxChannel {
                        channel_type: "red".into(),
                        label: String::new(),
                        universe: 1,
                        address: 2,
                        fine: false,
                        ultra_fine: false,
                        physical_min: None,
                        physical_max: None,
                        ranges: vec![],
                    },
                    DmxChannel {
                        channel_type: "pan".into(),
                        label: String::new(),
                        universe: 1,
                        address: 3,
                        fine: false,
                        ultra_fine: false,
                        physical_min: Some(-270.0),
                        physical_max: Some(270.0),
                        ranges: vec![],
                    },
                    DmxChannel {
                        channel_type: "tilt".into(),
                        label: String::new(),
                        universe: 1,
                        address: 4,
                        fine: false,
                        ultra_fine: false,
                        physical_min: Some(-135.0),
                        physical_max: Some(135.0),
                        ranges: vec![],
                    },
                    DmxChannel {
                        channel_type: "zoom".into(),
                        label: String::new(),
                        universe: 1,
                        address: 5,
                        fine: false,
                        ultra_fine: false,
                        physical_min: Some(10.0),
                        physical_max: Some(50.0),
                        ranges: vec![],
                    },
                    DmxChannel {
                        channel_type: "generic".into(),
                        label: "gobo_index/speed".into(),
                        universe: 1,
                        address: 6,
                        fine: false,
                        ultra_fine: false,
                        physical_min: None,
                        physical_max: None,
                        ranges: vec![],
                    },
                    DmxChannel {
                        channel_type: "frost".into(),
                        label: "Frost".into(),
                        universe: 1,
                        address: 7,
                        fine: false,
                        ultra_fine: false,
                        physical_min: None,
                        physical_max: None,
                        ranges: vec![],
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
        frame[5] = 200; // continuous spin (> 0.5)
        frame[6] = 255; // full frost

        let res = evaluate_fixtures(&patch, 2.0, |u| (u == 1).then_some(frame));
        assert_eq!(res.len(), 1);
        assert!((res[0].intensity - 1.0).abs() < 1e-4);
        assert!((res[0].color[0] - 1.0).abs() < 1e-4);
        assert!((res[0].beam_angle_deg - 50.0).abs() < 1e-4);
        assert!(res[0].tilt_deg > 40.0);
        assert!(res[0].gobos[0].rot_rad > 1.0);
        assert!((res[0].gobo_blur_lod - 3.5).abs() < 1e-3);
    }

    fn ch_simple(kind: &str, label: &str, addr: u16, ranges: Vec<viz_core::ChannelRange>) -> DmxChannel {
        DmxChannel {
            channel_type: kind.into(),
            label: label.into(),
            universe: 1,
            address: addr,
            fine: false,
            ultra_fine: false,
            physical_min: None,
            physical_max: None,
            ranges,
        }
    }

    #[test]
    fn evaluates_second_gobo_wheel_and_dual_wheel_superposition() {
        use viz_core::ChannelRange;

        let w1_ranges = vec![
            ChannelRange { label: "Open".into(), min: 0, max: 127, gobo_id: "builtin:open".into() },
            ChannelRange { label: "Stars".into(), min: 128, max: 255, gobo_id: "builtin:stars".into() },
        ];
        let w2_ranges = vec![
            ChannelRange { label: "Open".into(), min: 0, max: 127, gobo_id: "builtin:open".into() },
            ChannelRange { label: "Bars".into(), min: 128, max: 255, gobo_id: "builtin:bars".into() },
        ];
        let patch = Patch {
            version: 1,
            stage: Stage::default(),
            fixtures: vec![Fixture {
                id: "olc:2".into(),
                channel: Some(2),
                unit: None,
                name: "Dual Gobo".into(),
                fixture_type: FixtureType::MovingHead,
                gdtf: None,
                mode: None,
                address: Some(DmxAddress { universe: 1, channel: 1 }),
                footprint: Some(5),
                position: Vec3::new(0.0, 0.0, 4.0),
                focus_point: Vec3::ZERO,
                orientation: Orientation::default(),
                beam_angle: 25.0,
                static_gobo: String::new(),
                gel: String::new(),
                gel_color: String::new(),
                channels: vec![
                    ch_simple("intensity", "Dimmer", 1, vec![]),
                    ch_simple("gobo_wheel", "Gobo1", 2, w1_ranges),
                    ch_simple("gobo_wheel", "Gobo1WheelSpin", 3, vec![]),
                    ch_simple("gobo_wheel", "Gobo2", 4, w2_ranges),
                    ch_simple("gobo_wheel", "Gobo2WheelIndex", 5, vec![]),
                ],
            }],
        };

        // Case A: wheel 1 Open (0), wheel 2 Bars (200) -> gobos[0] gets wheel 2 + wheel 2 rot
        let mut frame = [0u8; DMX_CHANNELS];
        frame[0] = 255;
        frame[1] = 0;   // W1 Open
        frame[2] = 220; // W1 rot (unused since W1 open)
        frame[3] = 200; // W2 Bars
        frame[4] = 64;  // W2 index (~0.25 * 2pi)
        let res_a = evaluate_fixtures(&patch, 2.0, |u| (u == 1).then_some(frame));
        assert_eq!(res_a[0].gobos[0].gobo_id, "builtin:bars");
        let expected_w2_rot = (64.0 / 255.0) * 2.0 * std::f32::consts::TAU;
        assert!((res_a[0].gobos[0].rot_rad - expected_w2_rot).abs() < 1e-3);
        assert!(res_a[0].gobos[1].gobo_id.is_empty());

        // Case B: both wheels active -> gobos[0] = Stars + W1 spin, gobos[1] = Bars + W2 index
        frame[1] = 200; // W1 Stars
        let res_b = evaluate_fixtures(&patch, 2.0, |u| (u == 1).then_some(frame));
        assert_eq!(res_b[0].gobos[0].gobo_id, "builtin:stars");
        assert!(res_b[0].gobos[0].rot_rad > 1.0);
        assert_eq!(res_b[0].gobos[1].gobo_id, "builtin:bars");
        assert!((res_b[0].gobos[1].rot_rad - expected_w2_rot).abs() < 1e-3);
    }

    #[test]
    fn evaluates_eos_gobo_select_2_and_ignores_prism_rotation() {
        use viz_core::ChannelRange;

        let w1_ranges = vec![
            ChannelRange { label: "Open".into(), min: 0, max: 127, gobo_id: "builtin:open".into() },
            ChannelRange { label: "Grid".into(), min: 128, max: 255, gobo_id: "builtin:grid".into() },
        ];
        let w2_ranges = vec![
            ChannelRange { label: "Open".into(), min: 0, max: 127, gobo_id: "builtin:open".into() },
            ChannelRange { label: "Ring".into(), min: 128, max: 255, gobo_id: "builtin:ring".into() },
        ];
        let patch = Patch {
            version: 1,
            stage: Stage::default(),
            fixtures: vec![Fixture {
                id: "olc:3".into(),
                channel: Some(3),
                unit: None,
                name: "Eos Spot".into(),
                fixture_type: FixtureType::MovingHead,
                gdtf: None,
                mode: None,
                address: Some(DmxAddress { universe: 1, channel: 1 }),
                footprint: Some(6),
                position: Vec3::new(0.0, 0.0, 4.0),
                focus_point: Vec3::ZERO,
                orientation: Orientation::default(),
                beam_angle: 25.0,
                static_gobo: String::new(),
                gel: String::new(),
                gel_color: String::new(),
                channels: vec![
                    ch_simple("intensity", "intens", 1, vec![]),
                    ch_simple("gobo_wheel", "gobo_select", 2, w1_ranges),
                    ch_simple("generic", "gobo_index/speed", 3, vec![]),
                    ch_simple("generic", "gobo_select_2", 4, w2_ranges),
                    ch_simple("generic", "gobo_index/speed_2", 5, vec![]),
                    ch_simple("generic", "beam_fx_index/speed", 6, vec![]),
                ],
            }],
        };

        let mut frame = [0u8; DMX_CHANNELS];
        frame[0] = 255;
        frame[1] = 0;   // W1 Open
        frame[2] = 0;
        frame[3] = 200; // W2 Ring (generic gobo_select_2)
        frame[4] = 0;   // W2 rot = 0
        frame[5] = 240; // Prism rotation must NOT bleed into gobo rotation!

        let res = evaluate_fixtures(&patch, 3.0, |u| (u == 1).then_some(frame));
        assert_eq!(res[0].gobos[0].gobo_id, "builtin:ring");
        assert!((res[0].gobos[0].rot_rad - 0.0).abs() < 1e-5);
    }

    #[test]
    fn evaluates_conventional_gel_color_and_default_tungsten() {
        let mk_dimmer = |id: &str, ch: u32, gel_color: &str| Fixture {
            id: id.into(),
            channel: Some(ch),
            unit: None,
            name: id.into(),
            fixture_type: FixtureType::Dimmer,
            gdtf: None,
            mode: None,
            address: Some(DmxAddress { universe: 1, channel: ch as u16 }),
            footprint: Some(1),
            position: Vec3::new(0.0, 0.0, 4.0),
            focus_point: Vec3::ZERO,
            orientation: Orientation::default(),
            beam_angle: 35.0,
            static_gobo: String::new(),
            gel: String::new(),
            gel_color: gel_color.into(),
            channels: vec![ch_simple("intensity", "intens", ch as u16, vec![])],
        };
        let patch = Patch {
            version: 1,
            stage: Stage::default(),
            fixtures: vec![
                mk_dimmer("gelled", 1, "#ff6600"),
                mk_dimmer("open", 2, ""),
            ],
        };
        let mut frame = [0u8; DMX_CHANNELS];
        frame[0] = 255;
        frame[1] = 255;

        let res = evaluate_fixtures(&patch, 0.0, |u| (u == 1).then_some(frame));
        assert!((res[0].color[0] - 1.0).abs() < 1e-3);
        assert!((res[0].color[1] - (0x66 as f32 / 255.0)).abs() < 1e-2);
        assert!(res[0].color[2] < 1e-3);
        // Without gel_color -> default warm halogen
        assert!((res[1].color[0] - 1.0).abs() < 1e-4);
        assert!((res[1].color[1] - 0.95).abs() < 1e-4);
        assert!((res[1].color[2] - 0.85).abs() < 1e-4);
    }

    #[test]
    fn evaluates_gobo_index_stop_and_bidirectional_cw_ccw_rotation() {
        use viz_core::ChannelRange;

        let gobo_ranges = vec![
            ChannelRange { label: "Open".into(), min: 0, max: 9, gobo_id: "builtin:open".into() },
            ChannelRange { label: "Stardust".into(), min: 20, max: 29, gobo_id: "builtin:stars".into() },
        ];
        let pos_ranges = vec![
            ChannelRange { label: "Gobo1Index".into(), min: 0, max: 127, gobo_id: String::new() },
            ChannelRange { label: "Gobo1Rotation".into(), min: 128, max: 255, gobo_id: String::new() },
        ];
        let pos_fine = DmxChannel {
            channel_type: "generic".into(),
            label: "Gobo1Pos".into(),
            universe: 1,
            address: 4,
            fine: true,
            ultra_fine: false,
            physical_min: None,
            physical_max: None,
            ranges: vec![],
        };
        let patch = Patch {
            version: 1,
            stage: Stage::default(),
            fixtures: vec![Fixture {
                id: "olc:4".into(),
                channel: Some(4),
                unit: None,
                name: "Diablo".into(),
                fixture_type: FixtureType::MovingHead,
                gdtf: None,
                mode: None,
                address: Some(DmxAddress { universe: 1, channel: 1 }),
                footprint: Some(4),
                position: Vec3::new(0.0, 0.0, 4.0),
                focus_point: Vec3::ZERO,
                orientation: Orientation::default(),
                beam_angle: 25.0,
                static_gobo: String::new(),
                gel: String::new(),
                gel_color: String::new(),
                channels: vec![
                    ch_simple("intensity", "intens", 1, vec![]),
                    ch_simple("gobo_wheel", "Gobo1", 2, gobo_ranges),
                    ch_simple("generic", "Gobo1Pos", 3, pos_ranges),
                    pos_fine,
                ],
            }],
        };

        let mut frame = [0u8; DMX_CHANNELS];
        frame[0] = 255;
        frame[1] = 24; // Stardust

        let set_u16 = |fr: &mut [u8; DMX_CHANNELS], val: u16| {
            fr[2] = (val >> 8) as u8;
            fr[3] = (val & 0xff) as u8;
        };

        // 1. Index (26760 -> norm ~0.408): constant angle regardless of time_sec
        set_u16(&mut frame, 26760);
        let idx_t0 = evaluate_fixtures(&patch, 0.0, |u| (u == 1).then_some(frame))[0].gobos[0].rot_rad;
        let idx_t5 = evaluate_fixtures(&patch, 5.0, |u| (u == 1).then_some(frame))[0].gobos[0].rot_rad;
        assert!((idx_t0 - idx_t5).abs() < 1e-5);

        // 2. Stop (49152 -> norm 0.75): zero rotation even at t = 5.0
        set_u16(&mut frame, 49152);
        let stop_rot = evaluate_fixtures(&patch, 5.0, |u| (u == 1).then_some(frame))[0].gobos[0].rot_rad;
        assert!(stop_rot.abs() < 1e-5);

        // 3. Cue 114 symmetric values: Ch4=50899 (CCW > 0) and Ch5=47378 (CW < 0)
        set_u16(&mut frame, 50899);
        let ccw_rot = evaluate_fixtures(&patch, 2.0, |u| (u == 1).then_some(frame))[0].gobos[0].rot_rad;
        set_u16(&mut frame, 47378);
        let cw_rot = evaluate_fixtures(&patch, 2.0, |u| (u == 1).then_some(frame))[0].gobos[0].rot_rad;
        assert!(ccw_rot > 0.5);
        assert!(cw_rot < -0.5);
        assert!((ccw_rot + cw_rot).abs() < 0.5);
    }
}

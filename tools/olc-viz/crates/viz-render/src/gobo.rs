//! Atlas de masques de gobos (motifs procéduraux intégrés + PNG personnalisés d'OLC).

pub const GOBO_SIZE: u32 = 128;
pub const GOBO_MIP_LEVELS: u32 = 5;
pub const BUILTIN_COUNT: u32 = 10;
pub const MAX_GOBO_LAYERS: u32 = 256;

const BUILTIN_IDS: [&str; 10] = [
    "builtin:open",
    "builtin:stars",
    "builtin:breakup",
    "builtin:bars",
    "builtin:radial",
    "builtin:ring",
    "builtin:grid",
    "builtin:triangle",
    "builtin:cross",
    "builtin:spiral",
];

pub fn resolve_builtin_index(label_or_id: &str, slot_index: usize) -> u32 {
    let low = label_or_id.trim().to_ascii_lowercase();
    if let Some(pos) = BUILTIN_IDS.iter().position(|id| *id == low) {
        return pos as u32;
    }
    for (idx, kw_list) in [
        (0, &["open", "clear", "no gobo", "empty"][..]),
        (1, &["star", "dot", "circle", "bubble", "shower"][..]),
        (2, &["break", "leaf", "leaves", "foliage", "forest", "tree", "cloud"][..]),
        (3, &["bar", "line", "stripe", "blind", "slit", "venetian"][..]),
        (4, &["rad", "sun", "burst", "ray", "spoke", "cone", "fan"][..]),
        (5, &["ring", "iris", "donut", "halo", "target"][..]),
        (6, &["grid", "window", "square", "check", "brick", "matrix"][..]),
        (7, &["tri", "delta", "pyramid"][..]),
        (8, &["cross", "plus", "x-ray"][..]),
        (9, &["spiral", "vortex", "swirl", "tunnel"][..]),
    ] {
        if kw_list.iter().any(|k| low.contains(k)) {
            return idx;
        }
    }
    if slot_index == 0 {
        0
    } else {
        1 + ((slot_index as u32 - 1) % (BUILTIN_COUNT - 1))
    }
}

/// Génère un masque `GOBO_SIZE × GOBO_SIZE` en `R8Unorm` pour une couche intégrée `0..10`.
pub fn generate_builtin_layer(index: u32) -> Vec<u8> {
    let n = GOBO_SIZE as usize;
    let mut buf = vec![0u8; n * n];
    let half = (GOBO_SIZE as f32) * 0.5;
    for py in 0..n {
        for px in 0..n {
            let x = (px as f32 + 0.5 - half) / (half * 0.88);
            let y = (py as f32 + 0.5 - half) / (half * 0.88);
            let r = (x * x + y * y).sqrt();
            if r > 1.0 {
                continue;
            }
            let edge = ((1.0 - r) * 14.0).clamp(0.0, 1.0);
            let val = match index {
                0 => 1.0,
                1 => {
                    // Stars / dots
                    let mut hit = if r < 0.20 { 1.0 } else { 0.0 };
                    for i in 0..6 {
                        let a = (i as f32) * std::f32::consts::TAU / 6.0;
                        let dx = x - 0.52 * a.cos();
                        let dy = y - 0.52 * a.sin();
                        if (dx * dx + dy * dy).sqrt() < 0.16 {
                            hit = 1.0;
                        }
                    }
                    hit
                }
                2 => {
                    // Breakup / foliage
                    let pts = [
                        (-0.36, -0.32, 0.24),
                        (0.34, -0.26, 0.20),
                        (-0.16, 0.30, 0.26),
                        (0.38, 0.28, 0.21),
                        (0.0, -0.04, 0.17),
                    ];
                    let mut hit = 0.0f32;
                    for (cx, cy, rad) in pts {
                        let d = ((x - cx).powi(2) + (y - cy).powi(2)).sqrt();
                        if d < rad {
                            hit = 1.0;
                        }
                    }
                    hit
                }
                3 => {
                    // Bars
                    if (-0.48..=-0.32).contains(&x)
                        || (-0.18..=-0.02).contains(&x)
                        || (0.02..=0.18).contains(&x)
                        || (0.32..=0.48).contains(&x)
                    {
                        1.0
                    } else {
                        0.0
                    }
                }
                4 => {
                    // Radial spokes
                    let ang = y.atan2(x);
                    let sector = (ang * 8.0 / std::f32::consts::TAU).fract().abs();
                    if r > 0.15 && (sector < 0.28 || sector > 0.72) {
                        1.0
                    } else {
                        0.0
                    }
                }
                5 => {
                    // Ring
                    if (0.42..=0.72).contains(&r) { 1.0 } else { 0.0 }
                }
                6 => {
                    // Grid
                    let gx = ((x + 0.55) * 2.7).fract();
                    let gy = ((y + 0.55) * 2.7).fract();
                    if gx > 0.25 && gx < 0.80 && gy > 0.25 && gy < 0.80 {
                        1.0
                    } else {
                        0.0
                    }
                }
                7 => {
                    // Triangle
                    if y > -0.45 && y < 0.55 && x.abs() < (0.55 - y) * 0.65 {
                        1.0
                    } else {
                        0.0
                    }
                }
                8 => {
                    // Cross
                    if (x.abs() < 0.18 && y.abs() < 0.72) || (y.abs() < 0.18 && x.abs() < 0.72) {
                        1.0
                    } else {
                        0.0
                    }
                }
                _ => {
                    // Spiral
                    let ang = y.atan2(x) + r * 8.0;
                    if ang.sin() > 0.15 { 1.0 } else { 0.0 }
                }
            };
            buf[py * n + px] = ((val * edge).clamp(0.0, 1.0) * 255.0) as u8;
        }
    }
    buf
}

/// Décode un PNG en masque `GOBO_SIZE × GOBO_SIZE` `R8Unorm` avec découpe circulaire.
pub fn decode_png_to_gobo_layer(png_bytes: &[u8]) -> Option<Vec<u8>> {
    let img = image::load_from_memory(png_bytes).ok()?;
    let gray = img
        .resize_exact(
            GOBO_SIZE,
            GOBO_SIZE,
            image::imageops::FilterType::Triangle,
        )
        .to_luma8();
    let n = GOBO_SIZE as usize;
    let half = (GOBO_SIZE as f32) * 0.5;
    let mut out = vec![0u8; n * n];
    for py in 0..n {
        for px in 0..n {
            let x = (px as f32 + 0.5 - half) / (half * 0.92);
            let y = (py as f32 + 0.5 - half) / (half * 0.92);
            let r = (x * x + y * y).sqrt();
            if r > 1.0 {
                continue;
            }
            let edge = ((1.0 - r) * 14.0).clamp(0.0, 1.0);
            let lum = gray.get_pixel(px as u32, py as u32)[0] as f32;
            out[py * n + px] = (lum * edge).clamp(0.0, 255.0) as u8;
        }
    }
    Some(out)
}

/// Génère `GOBO_MIP_LEVELS` niveaux de mipmap (boîte 2×2) pour simuler le flou optique.
pub fn generate_mipmaps(base: &[u8]) -> Vec<(u32, Vec<u8>)> {
    let mut levels = Vec::with_capacity(GOBO_MIP_LEVELS as usize);
    let mut cur_size = GOBO_SIZE;
    let mut cur = base.to_vec();
    levels.push((cur_size, cur.clone()));
    for _ in 1..GOBO_MIP_LEVELS {
        let next_size = (cur_size / 2).max(1);
        let mut next = vec![0u8; (next_size * next_size) as usize];
        for y in 0..next_size {
            for x in 0..next_size {
                let sx = x * 2;
                let sy = y * 2;
                let idx = |px: u32, py: u32| -> u32 {
                    cur[(py * cur_size + px) as usize] as u32
                };
                let sum = idx(sx, sy) + idx(sx + 1, sy) + idx(sx, sy + 1) + idx(sx + 1, sy + 1);
                next[(y * next_size + x) as usize] = (sum / 4) as u8;
            }
        }
        levels.push((next_size, next.clone()));
        cur = next;
        cur_size = next_size;
    }
    levels
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_keywords_and_generates_non_empty_masks() {
        assert_eq!(resolve_builtin_index("builtin:open", 0), 0);
        assert_eq!(resolve_builtin_index("Star Field", 2), 1);
        assert_eq!(resolve_builtin_index("Leaf Breakup", 3), 2);
        for idx in 0..BUILTIN_COUNT {
            let m = generate_builtin_layer(idx);
            assert_eq!(m.len(), (GOBO_SIZE * GOBO_SIZE) as usize);
            assert!(m.iter().any(|&v| v > 128));
            let mips = generate_mipmaps(&m);
            assert_eq!(mips.len(), GOBO_MIP_LEVELS as usize);
            assert_eq!(mips[0].0, 128);
            assert_eq!(mips[4].0, 8);
        }
    }
}

//! Utilitaires mathématiques 3D (repère Z-up en mètres, matrices colonne-majeures pour WGSL).

use viz_core::Orientation;

pub type Mat4 = [[f32; 4]; 4];

pub fn add3(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
}

pub fn sub3(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

pub fn scale3(a: [f32; 3], s: f32) -> [f32; 3] {
    [a[0] * s, a[1] * s, a[2] * s]
}

pub fn dot3(a: [f32; 3], b: [f32; 3]) -> f32 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

pub fn cross3(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

pub fn len3(a: [f32; 3]) -> f32 {
    dot3(a, a).sqrt()
}

pub fn normalize3(a: [f32; 3]) -> [f32; 3] {
    let l = len3(a);
    if l > 1e-6 {
        [a[0] / l, a[1] / l, a[2] / l]
    } else {
        [0.0, 0.0, 0.0]
    }
}

pub fn mat4_mul(a: Mat4, b: Mat4) -> Mat4 {
    let mut out = [[0.0f32; 4]; 4];
    for c in 0..4 {
        for r in 0..4 {
            out[c][r] =
                a[0][r] * b[c][0] + a[1][r] * b[c][1] + a[2][r] * b[c][2] + a[3][r] * b[c][3];
        }
    }
    out
}

pub fn mat4_mul_vec4(m: Mat4, v: [f32; 4]) -> [f32; 4] {
    [
        m[0][0] * v[0] + m[1][0] * v[1] + m[2][0] * v[2] + m[3][0] * v[3],
        m[0][1] * v[0] + m[1][1] * v[1] + m[2][1] * v[2] + m[3][1] * v[3],
        m[0][2] * v[0] + m[1][2] * v[1] + m[2][2] * v[2] + m[3][2] * v[3],
        m[0][3] * v[0] + m[1][3] * v[1] + m[2][3] * v[2] + m[3][3] * v[3],
    ]
}

pub fn mat4_translation(t: [f32; 3]) -> Mat4 {
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [t[0], t[1], t[2], 1.0],
    ]
}

pub fn mat4_rot_x(rad: f32) -> Mat4 {
    let (s, c) = rad.sin_cos();
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, c, s, 0.0],
        [0.0, -s, c, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

pub fn mat4_rot_y(rad: f32) -> Mat4 {
    let (s, c) = rad.sin_cos();
    [
        [c, 0.0, -s, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [s, 0.0, c, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

pub fn mat4_rot_z(rad: f32) -> Mat4 {
    let (s, c) = rad.sin_cos();
    [
        [c, s, 0.0, 0.0],
        [-s, c, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

/// Matrice de vue main droite.
pub fn look_at_rh(eye: [f32; 3], target: [f32; 3], up: [f32; 3]) -> Mat4 {
    let f = normalize3(sub3(target, eye));
    let mut s = cross3(f, up);
    if len3(s) < 1e-5 {
        s = cross3(f, [0.0, 1.0, 0.0]);
    }
    let s = normalize3(s);
    let u = cross3(s, f);
    [
        [s[0], u[0], -f[0], 0.0],
        [s[1], u[1], -f[1], 0.0],
        [s[2], u[2], -f[2], 0.0],
        [-dot3(s, eye), -dot3(u, eye), dot3(f, eye), 1.0],
    ]
}

/// Matrice de projection perspective main droite pour wgpu (profondeur `[0, 1]`).
pub fn perspective_rh(fov_y_rad: f32, aspect: f32, near: f32, far: f32) -> Mat4 {
    let f = 1.0 / (0.5 * fov_y_rad).tan();
    let nf = 1.0 / (near - far);
    [
        [f / aspect.max(1e-4), 0.0, 0.0, 0.0],
        [0.0, f, 0.0, 0.0],
        [0.0, 0.0, far * nf, -1.0],
        [0.0, 0.0, near * far * nf, 0.0],
    ]
}

/// Inversion générique d'une matrice 4×4 (Gauss-Jordan).
pub fn mat4_invert(m: Mat4) -> Option<Mat4> {
    let mut a = [[0.0f64; 8]; 4];
    for r in 0..4 {
        for c in 0..4 {
            a[r][c] = m[c][r] as f64;
        }
        a[r][4 + r] = 1.0;
    }
    for i in 0..4 {
        let mut pivot = i;
        let mut max_v = a[i][i].abs();
        for (r, row) in a.iter().enumerate().skip(i + 1) {
            if row[i].abs() > max_v {
                max_v = row[i].abs();
                pivot = r;
            }
        }
        if max_v < 1e-10 {
            return None;
        }
        a.swap(i, pivot);
        let div = a[i][i];
        for v in &mut a[i] {
            *v /= div;
        }
        for r in 0..4 {
            if r != i {
                let factor = a[r][i];
                for c in 0..8 {
                    a[r][c] -= factor * a[i][c];
                }
            }
        }
    }
    let mut out = [[0.0f32; 4]; 4];
    for c in 0..4 {
        for r in 0..4 {
            out[c][r] = a[r][4 + c] as f32;
        }
    }
    Some(out)
}

/// Projette un point monde vers des coordonnées écran egui dans `rect`.
pub fn project_world_to_screen(
    view_proj: Mat4,
    world: [f32; 3],
    rect: egui::Rect,
) -> Option<egui::Pos2> {
    let clip = mat4_mul_vec4(view_proj, [world[0], world[1], world[2], 1.0]);
    if clip[3] <= 1e-4 {
        return None;
    }
    let ndc_x = clip[0] / clip[3];
    let ndc_y = clip[1] / clip[3];
    if clip[2] / clip[3] < 0.0 || clip[2] / clip[3] > 1.0 {
        return None;
    }
    let sx = rect.left() + (ndc_x * 0.5 + 0.5) * rect.width();
    let sy = rect.top() + (0.5 - ndc_y * 0.5) * rect.height();
    Some(egui::pos2(sx, sy))
}

/// Rotation Euler Z-Y-X (yaw, pitch, roll en degrés) vers matrice 4×4.
pub fn orientation_matrix(o: Orientation) -> Mat4 {
    let r_z = mat4_rot_z(o.yaw.to_radians());
    let r_y = mat4_rot_y(o.pitch.to_radians());
    let r_x = mat4_rot_x(o.roll.to_radians());
    mat4_mul(r_z, mat4_mul(r_y, r_x))
}

/// Direction monde du faisceau d'une lyre (symétrique à `compute_pan_tilt_for_target` d'OLC).
pub fn forward_pan_tilt(orientation: Orientation, pan_deg: f32, tilt_deg: f32) -> [f32; 3] {
    let p = pan_deg.to_radians();
    let t = tilt_deg.to_radians();
    let lx = t.sin() * p.sin();
    let ly = t.sin() * p.cos();
    let lz = -t.cos();
    let rot = orientation_matrix(orientation);
    let w = mat4_mul_vec4(rot, [lx, ly, lz, 0.0]);
    normalize3([w[0], w[1], w[2]])
}

/// Parse une couleur hexadécimale `#RRGGBB` en RGB linéaire `[0..1]`.
pub fn parse_hex_color(hex: &str) -> [f32; 3] {
    let s = hex.trim().trim_start_matches('#');
    if s.len() >= 6 {
        if let (Ok(r), Ok(g), Ok(b)) = (
            u8::from_str_radix(&s[0..2], 16),
            u8::from_str_radix(&s[2..4], 16),
            u8::from_str_radix(&s[4..6], 16),
        ) {
            return [r as f32 / 255.0, g as f32 / 255.0, b as f32 / 255.0];
        }
    }
    [0.13, 0.13, 0.15]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pan_tilt_matches_olc_inverse_kinematics() {
        // Pour target = (0, 4, 0) depuis pos = (0, 0, 4), pan=0, tilt=45° -> dir=(0, 0.707, -0.707)
        let dir = forward_pan_tilt(Orientation::default(), 0.0, 45.0);
        assert!((dir[0]).abs() < 1e-5);
        assert!((dir[1] - std::f32::consts::FRAC_1_SQRT_2).abs() < 1e-5);
        assert!((dir[2] + std::f32::consts::FRAC_1_SQRT_2).abs() < 1e-5);
    }

    #[test]
    fn mat4_invert_roundtrip() {
        let vp = mat4_mul(
            perspective_rh(45f32.to_radians(), 16.0 / 9.0, 0.1, 100.0),
            look_at_rh([6.0, -8.0, 5.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]),
        );
        let inv = mat4_invert(vp).expect("inversible");
        let id = mat4_mul(vp, inv);
        for c in 0..4 {
            for r in 0..4 {
                let expected = if c == r { 1.0 } else { 0.0 };
                assert!((id[c][r] - expected).abs() < 1e-4);
            }
        }
    }
}

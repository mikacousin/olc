//! Lightweight procedural meshes representing fixtures without MVR.

use bytemuck::{Pod, Zeroable};
use viz_core::FixtureType;

use crate::dmx_eval::{GoboWheelState, ResolvedFixture};
use crate::math::{
    add3, cross3, mat4_mul, mat4_mul_vec4, mat4_rot_x, mat4_rot_z, mat4_translation, normalize3,
    orientation_matrix, sub3, Mat4,
};

#[repr(C)]
#[derive(Copy, Clone, Debug, Pod, Zeroable)]
pub struct FixtureVertex {
    pub pos: [f32; 3],
    pub normal: [f32; 3],
    pub color: [f32; 3],
    pub emissive: f32,
}

#[repr(C)]
#[derive(Copy, Clone, Debug, Pod, Zeroable)]
pub struct BeamVertex {
    pub pos: [f32; 3],
    pub normal: [f32; 3],
    pub color: [f32; 3],
    pub alpha: f32,
    pub gobo_uv: [f32; 3],  // cos(theta1), sin(theta1), gobo1_layer
    pub gobo2_uv: [f32; 3], // cos(theta2), sin(theta2), gobo2_layer
}

fn push_tri(
    out: &mut Vec<FixtureVertex>,
    m: Mat4,
    a: [f32; 3],
    b: [f32; 3],
    c: [f32; 3],
    color: [f32; 3],
    emissive: f32,
) {
    let ta = xform_point(m, a);
    let tb = xform_point(m, b);
    let tc = xform_point(m, c);
    let n = normalize3(cross3(sub3(tb, ta), sub3(tc, ta)));
    out.push(FixtureVertex { pos: ta, normal: n, color, emissive });
    out.push(FixtureVertex { pos: tb, normal: n, color, emissive });
    out.push(FixtureVertex { pos: tc, normal: n, color, emissive });
}

fn push_quad(
    out: &mut Vec<FixtureVertex>,
    m: Mat4,
    a: [f32; 3],
    b: [f32; 3],
    c: [f32; 3],
    d: [f32; 3],
    color: [f32; 3],
    emissive: f32,
) {
    push_tri(out, m, a, b, c, color, emissive);
    push_tri(out, m, a, c, d, color, emissive);
}

fn xform_point(m: Mat4, p: [f32; 3]) -> [f32; 3] {
    let v = mat4_mul_vec4(m, [p[0], p[1], p[2], 1.0]);
    [v[0], v[1], v[2]]
}

fn push_box(
    out: &mut Vec<FixtureVertex>,
    m: Mat4,
    half: [f32; 3],
    center: [f32; 3],
    color: [f32; 3],
    emissive: f32,
) {
    let (hx, hy, hz) = (half[0], half[1], half[2]);
    let (cx, cy, cz) = (center[0], center[1], center[2]);
    let p = |sx: f32, sy: f32, sz: f32| [cx + sx * hx, cy + sy * hy, cz + sz * hz];
    // +Z, -Z, +X, -X, +Y, -Y
    push_quad(out, m, p(-1., -1., 1.), p(1., -1., 1.), p(1., 1., 1.), p(-1., 1., 1.), color, emissive);
    push_quad(out, m, p(-1., 1., -1.), p(1., 1., -1.), p(1., -1., -1.), p(-1., -1., -1.), color, emissive);
    push_quad(out, m, p(1., -1., -1.), p(1., 1., -1.), p(1., 1., 1.), p(1., -1., 1.), color, emissive);
    push_quad(out, m, p(-1., 1., -1.), p(-1., -1., -1.), p(-1., -1., 1.), p(-1., 1., 1.), color, emissive);
    push_quad(out, m, p(1., 1., -1.), p(-1., 1., -1.), p(-1., 1., 1.), p(1., 1., 1.), color, emissive);
    push_quad(out, m, p(-1., -1., -1.), p(1., -1., -1.), p(1., -1., 1.), p(-1., -1., 1.), color, emissive);
}

/// Cylinder along local Z axis, from `z0` to `z1` (emissive lens at `z0`).
fn push_cylinder_z(
    out: &mut Vec<FixtureVertex>,
    m: Mat4,
    z0: f32,
    z1: f32,
    r0: f32,
    r1: f32,
    sides: usize,
    body_color: [f32; 3],
    lens_color: [f32; 3],
    lens_emissive: f32,
) {
    let step = std::f32::consts::TAU / sides as f32;
    for i in 0..sides {
        let a0 = i as f32 * step;
        let a1 = (i + 1) as f32 * step;
        let (s0, c0) = a0.sin_cos();
        let (s1, c1) = a1.sin_cos();
        let p00 = [c0 * r0, s0 * r0, z0];
        let p10 = [c1 * r0, s1 * r0, z0];
        let p01 = [c0 * r1, s0 * r1, z1];
        let p11 = [c1 * r1, s1 * r1, z1];
        // Side wall
        push_quad(out, m, p00, p01, p11, p10, body_color, 0.0);
        // Fond (z1)
        push_tri(out, m, [0.0, 0.0, z1], p01, p11, body_color, 0.0);
        // Lentille frontale (z0)
        push_tri(out, m, [0.0, 0.0, z0], p10, p00, lens_color, lens_emissive);
    }
}

/// Matrice qui aligne l'axe `-Z` local sur `dir` (vecteur unitaire).
fn aim_matrix(pos: [f32; 3], dir: [f32; 3]) -> Mat4 {
    let f = normalize3(dir);
    let up_ref = if f[2].abs() > 0.98 {
        [0.0, 1.0, 0.0]
    } else {
        [0.0, 0.0, 1.0]
    };
    let right = normalize3(cross3(up_ref, [-f[0], -f[1], -f[2]]));
    let up = cross3([-f[0], -f[1], -f[2]], right);
    [
        [right[0], right[1], right[2], 0.0],
        [up[0], up[1], up[2], 0.0],
        [-f[0], -f[1], -f[2], 0.0],
        [pos[0], pos[1], pos[2], 1.0],
    ]
}

/// Construit les triangles de tous les projecteurs pour la frame courante.
pub fn build_fixtures_mesh(
    fixtures: &[ResolvedFixture],
    selected_channel: Option<u32>,
) -> Vec<FixtureVertex> {
    let mut verts = Vec::with_capacity(fixtures.len() * 140);
    for f in fixtures {
        let is_selected = selected_channel.is_some() && f.channel_id == selected_channel;
        let body_color = if is_selected {
            [0.35, 0.45, 0.65]
        } else {
            [0.18, 0.19, 0.22]
        };
        let lens_color = if f.intensity > 0.01 {
            [
                (f.color[0] * f.intensity).max(0.05),
                (f.color[1] * f.intensity).max(0.05),
                (f.color[2] * f.intensity).max(0.05),
            ]
        } else {
            [0.08, 0.08, 0.10]
        };
        let lens_emissive = if f.intensity > 0.01 {
            0.3 + f.intensity * 1.4
        } else {
            0.0
        };

        match f.fixture_type {
            FixtureType::MovingHead => {
                // Fixed base + yoke (Pan) + head (Tilt)
                let base_m = mat4_mul(mat4_translation(f.position), orientation_matrix(f.orientation));
                push_box(&mut verts, base_m, [0.16, 0.14, 0.06], [0.0, 0.0, 0.22], body_color, 0.0);

                // Yoke rotating in Pan (-pan_deg around Z to match atan2(lx, ly))
                let yoke_m = mat4_mul(base_m, mat4_rot_z(-f.pan_deg.to_radians()));
                push_box(&mut verts, yoke_m, [0.025, 0.035, 0.14], [0.14, 0.0, 0.08], body_color, 0.0);
                push_box(&mut verts, yoke_m, [0.025, 0.035, 0.14], [-0.14, 0.0, 0.08], body_color, 0.0);
                push_box(&mut verts, yoke_m, [0.16, 0.04, 0.025], [0.0, 0.0, 0.17], body_color, 0.0);

                // Head tilting around X
                let head_m = mat4_mul(yoke_m, mat4_rot_x(f.tilt_deg.to_radians()));
                push_cylinder_z(
                    &mut verts,
                    head_m,
                    -0.16,
                    0.16,
                    0.10,
                    0.09,
                    12,
                    body_color,
                    lens_color,
                    lens_emissive,
                );
            }
            FixtureType::Strobe => {
                let m = aim_matrix(f.position, f.direction);
                push_box(&mut verts, m, [0.22, 0.09, 0.08], [0.0, 0.0, 0.06], body_color, 0.0);
                push_box(&mut verts, m, [0.19, 0.06, 0.01], [0.0, 0.0, -0.025], lens_color, lens_emissive);
            }
            _ => {
                // PAR / PC / Dimmer: slightly tapered cylindrical body aimed at focus_point
                let m = aim_matrix(f.position, f.direction);
                let rear = add3(f.position, scale_neg_dir(f.direction, 0.22));
                let _ = rear;
                push_cylinder_z(
                    &mut verts,
                    m,
                    -0.14,
                    0.18,
                    0.11,
                    0.085,
                    12,
                    body_color,
                    lens_color,
                    lens_emissive,
                );
            }
        }
    }
    verts
}

fn scale_neg_dir(dir: [f32; 3], s: f32) -> [f32; 3] {
    [-dir[0] * s, -dir[1] * s, -dir[2] * s]
}

/// Build additive volumetric cones for atmospheric fog.
pub fn build_beams_mesh(
    fixtures: &[ResolvedFixture],
    fog_density: f32,
    gobo_layer_fn: impl Fn(&GoboWheelState) -> u32,
) -> Vec<BeamVertex> {
    if fog_density <= 0.005 {
        return Vec::new();
    }
    let sides = 20usize;
    let mut verts = Vec::with_capacity(fixtures.len() * sides * 6);

    for f in fixtures {
        if f.intensity <= 0.005 {
            continue;
        }
        let dir = normalize3(f.direction);
        if dir == [0.0, 0.0, 0.0] {
            continue;
        }
        // Beam length to floor (z = 0) or 14 m if aimed upward
        let raw_len = if dir[2] < -0.05 && f.position[2] > 0.05 {
            (f.position[2] / -dir[2]).clamp(0.5, 22.0)
        } else {
            14.0
        };
        let start_offset = 0.16f32;
        if raw_len <= start_offset + 0.1 {
            continue;
        }
        let cone_len = raw_len - start_offset;
        let half_rad = (f.beam_angle_deg * 0.5).clamp(1.0, 65.0).to_radians();
        let r0 = 0.09f32;
        let r1 = r0 + cone_len * half_rad.tan();

        let m = aim_matrix(f.position, dir);
        let z0 = -start_offset;
        let z1 = -(start_offset + cone_len);
        let alpha0 = (f.intensity * fog_density).clamp(0.0, 1.0);
        let alpha1 = 0.0f32;
        let gobo_layer1 = gobo_layer_fn(&f.gobos[0]) as f32;
        let (rot1_s, rot1_c) = f.gobos[0].rot_rad.sin_cos();
        let gobo_layer2 = gobo_layer_fn(&f.gobos[1]) as f32;
        let (rot2_s, rot2_c) = f.gobos[1].rot_rad.sin_cos();

        let step = std::f32::consts::TAU / sides as f32;
        let slope = (r1 - r0) / cone_len;
        for i in 0..sides {
            let a0 = i as f32 * step;
            let a1 = (i + 1) as f32 * step;
            let (s0, c0) = a0.sin_cos();
            let (s1, c1) = a1.sin_cos();

            let n0_local = normalize3([c0, s0, slope]);
            let n1_local = normalize3([c1, s1, slope]);
            let n0 = xform_dir(m, n0_local);
            let n1 = xform_dir(m, n1_local);

            let p00 = xform_point(m, [c0 * r0, s0 * r0, z0]);
            let p10 = xform_point(m, [c1 * r0, s1 * r0, z0]);
            let p01 = xform_point(m, [c0 * r1, s0 * r1, z1]);
            let p11 = xform_point(m, [c1 * r1, s1 * r1, z1]);

            let uv0 = [c0 * rot1_c - s0 * rot1_s, c0 * rot1_s + s0 * rot1_c, gobo_layer1];
            let uv1 = [c1 * rot1_c - s1 * rot1_s, c1 * rot1_s + s1 * rot1_c, gobo_layer1];
            let uv2_0 = [c0 * rot2_c - s0 * rot2_s, c0 * rot2_s + s0 * rot2_c, gobo_layer2];
            let uv2_1 = [c1 * rot2_c - s1 * rot2_s, c1 * rot2_s + s1 * rot2_c, gobo_layer2];
            let v00 = BeamVertex { pos: p00, normal: n0, color: f.color, alpha: alpha0, gobo_uv: uv0, gobo2_uv: uv2_0 };
            let v10 = BeamVertex { pos: p10, normal: n1, color: f.color, alpha: alpha0, gobo_uv: uv1, gobo2_uv: uv2_1 };
            let v01 = BeamVertex { pos: p01, normal: n0, color: f.color, alpha: alpha1, gobo_uv: uv0, gobo2_uv: uv2_0 };
            let v11 = BeamVertex { pos: p11, normal: n1, color: f.color, alpha: alpha1, gobo_uv: uv1, gobo2_uv: uv2_1 };

            verts.push(v00);
            verts.push(v01);
            verts.push(v11);
            verts.push(v00);
            verts.push(v11);
            verts.push(v10);
        }
    }
    verts
}

fn xform_dir(m: Mat4, d: [f32; 3]) -> [f32; 3] {
    let v = mat4_mul_vec4(m, [d[0], d[1], d[2], 0.0]);
    normalize3([v[0], v[1], v[2]])
}

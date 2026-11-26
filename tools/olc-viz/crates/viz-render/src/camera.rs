//! Z-up orbital camera for the 3D visualizer.

use crate::math::{
    add3, cross3, look_at_rh, mat4_invert, mat4_mul, mat4_mul_vec4, normalize3, perspective_rh,
    scale3, sub3, Mat4,
};

#[derive(Debug, Clone)]
pub struct OrbitCamera {
    pub target: [f32; 3],
    pub distance: f32,
    /// Azimut en radians (0 = regarde vers +Y depuis -Y).
    pub yaw: f32,
    /// Elevation in radians above the horizontal plane.
    pub pitch: f32,
    pub fov_y_rad: f32,
}

impl Default for OrbitCamera {
    fn default() -> Self {
        Self::iso()
    }
}

impl OrbitCamera {
    pub fn iso() -> Self {
        Self {
            target: [0.0, 0.0, 1.0],
            distance: 14.0,
            yaw: -0.55,
            pitch: 0.45,
            fov_y_rad: 45f32.to_radians(),
        }
    }

    pub fn front() -> Self {
        Self {
            target: [0.0, 0.0, 1.5],
            distance: 14.0,
            yaw: 0.0,
            pitch: 0.15,
            fov_y_rad: 45f32.to_radians(),
        }
    }

    pub fn top() -> Self {
        Self {
            target: [0.0, 0.0, 0.0],
            distance: 16.0,
            yaw: 0.0,
            pitch: 1.52,
            fov_y_rad: 45f32.to_radians(),
        }
    }

    pub fn side() -> Self {
        Self {
            target: [0.0, 0.0, 1.5],
            distance: 14.0,
            yaw: std::f32::consts::FRAC_PI_2,
            pitch: 0.15,
            fov_y_rad: 45f32.to_radians(),
        }
    }

    pub fn eye(&self) -> [f32; 3] {
        let cp = self.pitch.cos();
        let offset = [
            self.distance * cp * self.yaw.sin(),
            -self.distance * cp * self.yaw.cos(),
            self.distance * self.pitch.sin(),
        ];
        add3(self.target, offset)
    }

    pub fn orbit(&mut self, delta_px: [f32; 2]) {
        self.yaw -= delta_px[0] * 0.006;
        self.pitch = (self.pitch + delta_px[1] * 0.006).clamp(-1.45, 1.54);
    }

    pub fn pan(&mut self, delta_px: [f32; 2]) {
        let eye = self.eye();
        let fwd = normalize3(sub3(self.target, eye));
        let right = normalize3(cross3(fwd, [0.0, 0.0, 1.0]));
        let up = normalize3(cross3(right, fwd));
        let factor = self.distance * 0.0014;
        self.target = add3(
            self.target,
            add3(
                scale3(right, -delta_px[0] * factor),
                scale3(up, delta_px[1] * factor),
            ),
        );
    }

    pub fn zoom(&mut self, scroll_y: f32) {
        let factor = (-scroll_y * 0.002).exp();
        self.distance = (self.distance * factor).clamp(1.5, 80.0);
    }

    pub fn view_proj(&self, aspect: f32) -> Mat4 {
        let view = look_at_rh(self.eye(), self.target, [0.0, 0.0, 1.0]);
        let proj = perspective_rh(self.fov_y_rad, aspect, 0.1, 150.0);
        mat4_mul(proj, view)
    }

    /// Rayon monde `(origine, direction)` passant par un pixel dans `rect`.
    pub fn screen_ray(&self, pos: egui::Pos2, rect: egui::Rect) -> Option<([f32; 3], [f32; 3])> {
        let aspect = (rect.width() / rect.height().max(1.0)).max(0.1);
        let inv = mat4_invert(self.view_proj(aspect))?;
        let ndc_x = ((pos.x - rect.left()) / rect.width().max(1.0)) * 2.0 - 1.0;
        let ndc_y = 1.0 - ((pos.y - rect.top()) / rect.height().max(1.0)) * 2.0;

        let p_near = mat4_mul_vec4(inv, [ndc_x, ndc_y, 0.0, 1.0]);
        let p_far = mat4_mul_vec4(inv, [ndc_x, ndc_y, 1.0, 1.0]);
        if p_near[3].abs() < 1e-6 || p_far[3].abs() < 1e-6 {
            return None;
        }
        let near = [
            p_near[0] / p_near[3],
            p_near[1] / p_near[3],
            p_near[2] / p_near[3],
        ];
        let far = [
            p_far[0] / p_far[3],
            p_far[1] / p_far[3],
            p_far[2] / p_far[3],
        ];
        Some((near, normalize3(sub3(far, near))))
    }
}

/// Intersection d'un rayon monde `(origin, dir)` avec le plan horizontal `z = plane_z`.
pub fn ray_plane_z(origin: [f32; 3], dir: [f32; 3], plane_z: f32) -> Option<[f32; 3]> {
    if dir[2].abs() < 1e-5 {
        return None;
    }
    let t = (plane_z - origin[2]) / dir[2];
    if t <= 0.05 || t > 120.0 {
        return None;
    }
    Some(add3(origin, scale3(dir, t)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn screen_ray_center_hits_target_plane() {
        let cam = OrbitCamera::iso();
        let rect = egui::Rect::from_min_size(egui::pos2(0.0, 0.0), egui::vec2(800.0, 600.0));
        let (orig, dir) = cam.screen_ray(rect.center(), rect).expect("ray");
        // Le rayon du centre doit pointer dans la direction de cam.target - cam.eye()
        let expected = normalize3(sub3(cam.target, cam.eye()));
        assert!((dir[0] - expected[0]).abs() < 1e-4);
        assert!((dir[1] - expected[1]).abs() < 1e-4);
        assert!((dir[2] - expected[2]).abs() < 1e-4);
        assert!((orig[0] - cam.eye()[0]).abs() < 0.2);
    }

    #[test]
    fn ray_plane_z_hits_floor() {
        let cam = OrbitCamera::iso();
        let rect = egui::Rect::from_min_size(egui::pos2(0.0, 0.0), egui::vec2(800.0, 600.0));
        let (orig, dir) = cam.screen_ray(rect.center(), rect).expect("ray");
        let hit = ray_plane_z(orig, dir, 0.0).expect("floor hit");
        assert!((hit[2]).abs() < 1e-4);
    }
}

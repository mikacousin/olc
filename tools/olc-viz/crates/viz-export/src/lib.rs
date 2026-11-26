//! Export views to 2D vector drawings: SVG (pivot format), PDF, DXF.
//!
//! TODO: plan/mesh sectioning, footprint projection, fixture symbols,
//! annotations, title block.

use viz_core::View;

/// Drawing area size in paper millimeters for a view.
pub fn drawing_size_mm(view: &View) -> (f32, f32) {
    view.paper.size_mm()
}

/// Convert a real-world length (meters) to millimeters on paper.
pub fn world_to_paper_mm(meters: f32, scale: u32) -> f32 {
    meters * 1000.0 / scale as f32
}

#[cfg(test)]
mod tests {
    use super::*;
    use viz_core::Paper;

    #[test]
    fn one_meter_at_1_50_is_20mm() {
        assert!((world_to_paper_mm(1.0, 50) - 20.0).abs() < 1e-4);
    }

    #[test]
    fn a3_size() {
        let v = View::plan("test");
        assert_eq!(drawing_size_mm(&v), Paper::A3.size_mm());
    }
}

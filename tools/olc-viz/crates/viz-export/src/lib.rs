//! Export des vues en dessins 2D vectoriels : SVG (format pivot), PDF, DXF.
//!
//! À faire : coupe plan/maillage, projection de l'emprise, symboles de
//! fixtures, annotations, cartouche.

use viz_core::View;

/// Taille de la zone de dessin en millimètres papier pour une vue.
pub fn drawing_size_mm(view: &View) -> (f32, f32) {
    view.paper.size_mm()
}

/// Convertit une longueur réelle (mètres) en millimètres sur le papier.
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

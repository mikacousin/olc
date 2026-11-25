//! Import et export MVR, lecture GDTF.
//!
//! Un MVR est une archive zip contenant `GeneralSceneDescription.xml`,
//! les fichiers GDTF des fixtures et les modèles 3D.
//! À faire : dépendances `zip` et `quick-xml`.

use viz_core::Scene;

/// Erreurs d'import MVR.
#[derive(Debug)]
pub enum MvrError {
    NotImplemented,
}

impl std::fmt::Display for MvrError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MvrError::NotImplemented => write!(f, "import MVR pas encore implémenté"),
        }
    }
}

impl std::error::Error for MvrError {}

/// Importe un fichier MVR et construit la scène correspondante.
pub fn import(_path: &std::path::Path) -> Result<Scene, MvrError> {
    Err(MvrError::NotImplemented)
}

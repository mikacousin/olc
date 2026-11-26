//! MVR import/export and GDTF reading.
//!
//! An MVR is a zip archive containing `GeneralSceneDescription.xml`,
//! fixture GDTF files, and 3D models.
//! TODO: `zip` and `quick-xml` dependencies.

use viz_core::Scene;

/// MVR import errors.
#[derive(Debug)]
pub enum MvrError {
    NotImplemented,
}

impl std::fmt::Display for MvrError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MvrError::NotImplemented => write!(f, "MVR import not yet implemented"),
        }
    }
}

impl std::error::Error for MvrError {}

/// Import an MVR file and build the corresponding scene.
pub fn import(_path: &std::path::Path) -> Result<Scene, MvrError> {
    Err(MvrError::NotImplemented)
}

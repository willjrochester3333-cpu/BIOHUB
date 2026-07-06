"""3D blob detection for zebrafish nuclei/cells in a single timepoint volume.

Pipeline: anisotropic Gaussian smoothing -> intensity threshold -> local-maxima
seeding (spaced by physical radius, not voxel count) -> marker-controlled
watershed -> intensity-weighted centroid per region. No trained model or
ground truth is required, so it runs standalone inside a Kaggle notebook with
internet access disabled.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.filters import threshold_otsu
from skimage.measure import regionprops
from skimage.segmentation import watershed


@dataclass(frozen=True)
class PhysicalScale:
    z: float = 1.625
    y: float = 0.40625
    x: float = 0.40625

    def as_array(self) -> np.ndarray:
        return np.array([self.z, self.y, self.x], dtype=np.float64)


@dataclass
class DetectionParams:
    smooth_sigma_um: float = 1.2
    min_peak_separation_um: float = 4.0
    threshold_rel: float = 0.15
    min_region_voxels: int = 5


def _voxel_sigma(scale: PhysicalScale, sigma_um: float) -> np.ndarray:
    return sigma_um / scale.as_array()


def _voxel_footprint_radius(scale: PhysicalScale, radius_um: float) -> tuple:
    radii = np.maximum(np.round(radius_um / scale.as_array()), 1).astype(int)
    return tuple(radii)


def detect_cells(
    volume: np.ndarray,
    scale: PhysicalScale = PhysicalScale(),
    params: DetectionParams = DetectionParams(),
) -> np.ndarray:
    """Detect cell centroids in a single 3D volume.

    Parameters
    ----------
    volume : (Z, Y, X) intensity array for one timepoint.

    Returns
    -------
    (N, 4) array of columns [z, y, x, intensity] with integer voxel centroids.
    Empty array with shape (0, 4) if nothing is detected.
    """
    volume = np.asarray(volume, dtype=np.float32)
    if volume.size == 0 or not np.any(volume):
        return np.zeros((0, 4), dtype=np.float64)

    sigma = _voxel_sigma(scale, params.smooth_sigma_um)
    smoothed = ndi.gaussian_filter(volume, sigma=sigma)

    try:
        otsu = threshold_otsu(smoothed[smoothed > 0]) if np.any(smoothed > 0) else 0.0
    except ValueError:
        otsu = 0.0
    dynamic = smoothed.max() * params.threshold_rel
    threshold = max(otsu, dynamic)
    mask = smoothed > threshold
    if not np.any(mask):
        return np.zeros((0, 4), dtype=np.float64)

    footprint_radii = _voxel_footprint_radius(scale, params.min_peak_separation_um)
    footprint = np.ones(tuple(2 * r + 1 for r in footprint_radii), dtype=bool)

    coords = peak_local_max(
        smoothed,
        footprint=footprint,
        labels=mask.astype(np.int32),
        exclude_border=False,
    )
    if coords.shape[0] == 0:
        return np.zeros((0, 4), dtype=np.float64)

    markers = np.zeros(volume.shape, dtype=np.int32)
    for i, (z, y, x) in enumerate(coords, start=1):
        markers[z, y, x] = i

    labels = watershed(-smoothed, markers=markers, mask=mask)

    detections = []
    for prop in regionprops(labels, intensity_image=volume):
        if prop.area < params.min_region_voxels:
            continue
        centroid = getattr(prop, "centroid_weighted", None)
        if centroid is None:
            centroid = prop.weighted_centroid
        mean_intensity = getattr(prop, "intensity_mean", None)
        if mean_intensity is None:
            mean_intensity = prop.mean_intensity
        z, y, x = centroid
        detections.append((z, y, x, mean_intensity))

    if not detections:
        return np.zeros((0, 4), dtype=np.float64)

    out = np.array(detections, dtype=np.float64)
    out[:, :3] = np.round(out[:, :3])
    return out

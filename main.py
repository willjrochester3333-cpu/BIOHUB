"""Single-file baseline for the Biohub 3D+time cell tracking competition.

Detect -> link -> recover divisions -> write submission.csv, all in one
`main()` you can paste into a single Kaggle notebook cell or run directly:

    python3 main.py --test-dir /kaggle/input/biohub-cell-tracking/test \
                     --output /kaggle/working/submission.csv

No trained model or internet access required. See README.md / src/ for the
same logic split into modules with tests, if you'd rather work from that.
"""
from __future__ import annotations

import argparse
import glob
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
import zarr
from scipy import ndimage as ndi
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from skimage.feature import peak_local_max
from skimage.filters import threshold_otsu
from skimage.measure import regionprops
from skimage.segmentation import watershed


def main(test_dir: str = "/kaggle/input/biohub-cell-tracking/test",
         output_path: str = "/kaggle/working/submission.csv") -> pd.DataFrame:

    # ---- physical scale (voxel -> micron) and tunable parameters ----

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

    @dataclass
    class TrackingParams:
        max_link_dist_um: float = 12.0
        max_division_dist_um: float = 15.0

    scale = PhysicalScale(z=1.625, y=0.40625, x=0.40625)
    detection_params = DetectionParams()
    tracking_params = TrackingParams()

    # ---- detection: one 3D volume -> [z, y, x, intensity] centroids ----

    def voxel_sigma(sigma_um: float) -> np.ndarray:
        return sigma_um / scale.as_array()

    def voxel_footprint_radius(radius_um: float) -> tuple:
        radii = np.maximum(np.round(radius_um / scale.as_array()), 1).astype(int)
        return tuple(radii)

    def detect_cells(volume: np.ndarray) -> np.ndarray:
        volume = np.asarray(volume, dtype=np.float32)
        if volume.size == 0 or not np.any(volume):
            return np.zeros((0, 4), dtype=np.float64)

        sigma = voxel_sigma(detection_params.smooth_sigma_um)
        smoothed = ndi.gaussian_filter(volume, sigma=sigma)

        try:
            otsu = threshold_otsu(smoothed[smoothed > 0]) if np.any(smoothed > 0) else 0.0
        except ValueError:
            otsu = 0.0
        dynamic = smoothed.max() * detection_params.threshold_rel
        threshold = max(otsu, dynamic)
        mask = smoothed > threshold
        if not np.any(mask):
            return np.zeros((0, 4), dtype=np.float64)

        footprint_radii = voxel_footprint_radius(detection_params.min_peak_separation_um)
        footprint = np.ones(tuple(2 * r + 1 for r in footprint_radii), dtype=bool)

        coords = peak_local_max(smoothed, footprint=footprint, labels=mask.astype(np.int32),
                                 exclude_border=False)
        if coords.shape[0] == 0:
            return np.zeros((0, 4), dtype=np.float64)

        markers = np.zeros(volume.shape, dtype=np.int32)
        for i, (z, y, x) in enumerate(coords, start=1):
            markers[z, y, x] = i

        labels = watershed(-smoothed, markers=markers, mask=mask)

        detections = []
        for prop in regionprops(labels, intensity_image=volume):
            if prop.area < detection_params.min_region_voxels:
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

    # ---- linking: Hungarian assignment + division recovery ----

    def to_physical(points_zyx: np.ndarray) -> np.ndarray:
        return points_zyx * scale.as_array()

    def link_frames(prev_pts: np.ndarray, curr_pts: np.ndarray) -> list:
        n, m = len(prev_pts), len(curr_pts)
        if n == 0 or m == 0:
            return []

        prev_um = to_physical(prev_pts)
        curr_um = to_physical(curr_pts)
        dist = cdist(prev_um, curr_um)

        threshold = tracking_params.max_link_dist_um
        big = threshold * 1000.0 + 1.0

        size = n + m
        cost = np.full((size, size), big, dtype=np.float64)
        cost[:n, :m] = dist
        cost[:n, m:] = np.where(np.eye(n, dtype=bool), threshold, big)
        cost[n:, :m] = np.where(np.eye(m, dtype=bool), threshold, big)
        cost[n:, m:] = 0.0

        row_ind, col_ind = linear_sum_assignment(cost)

        matches = []
        for r, c in zip(row_ind, col_ind):
            if r < n and c < m and dist[r, c] <= threshold:
                matches.append((r, c))
        return matches

    def recover_divisions(prev_pts: np.ndarray, curr_pts: np.ndarray, matches: list) -> list:
        n, m = len(prev_pts), len(curr_pts)
        if n == 0 or m == 0:
            return []

        matched_curr = {c for _, c in matches}
        unmatched_curr = [c for c in range(m) if c not in matched_curr]
        if not unmatched_curr:
            return []

        prev_um = to_physical(prev_pts)
        curr_um = to_physical(curr_pts)

        extra = []
        for c in unmatched_curr:
            d = np.linalg.norm(prev_um - curr_um[c], axis=1)
            p = int(np.argmin(d))
            if d[p] <= tracking_params.max_division_dist_um:
                extra.append((p, c))
        return extra

    # ---- zarr access: single (T,Z,Y,X) array, or group keyed by timepoint ----

    class ZarrTimeSeries:
        def __init__(self, path: str):
            self._store = zarr.open(path, mode="r")
            if hasattr(self._store, "ndim") and self._store.ndim == 4:
                self._mode = "array"
                self._n_frames = self._store.shape[0]
            else:
                self._mode = "group"
                self._n_frames = len(list(self._store.array_keys()))

        def __len__(self) -> int:
            return self._n_frames

        def get_frame(self, t: int):
            if self._mode == "array":
                return self._store[t]
            return self._store[str(t)][:]

    # ---- per-dataset tracking state ----

    def track_dataset(zarr_path: str, dataset_name: str) -> pd.DataFrame:
        series = ZarrTimeSeries(zarr_path)

        nodes = []
        edges = []
        next_node_id = 1
        prev_pts = None
        prev_node_ids = None

        for t in range(len(series)):
            volume = series.get_frame(t)
            detections = detect_cells(volume)
            pts = detections[:, :3] if detections.size else np.zeros((0, 3))
            node_ids = np.arange(next_node_id, next_node_id + len(pts))
            next_node_id += len(pts)

            for nid, (z, y, x) in zip(node_ids, pts):
                nodes.append((int(nid), int(t), int(z), int(y), int(x)))

            if prev_pts is not None and len(prev_pts) and len(pts):
                matches = link_frames(prev_pts, pts)
                extra = recover_divisions(prev_pts, pts, matches)
                for p_idx, c_idx in matches + extra:
                    edges.append((int(prev_node_ids[p_idx]), int(node_ids[c_idx])))

            prev_pts = pts
            prev_node_ids = node_ids

        node_rows = [
            {"dataset": dataset_name, "row_type": "node", "node_id": nid, "t": t,
             "z": z, "y": y, "x": x, "source_id": -1, "target_id": -1}
            for nid, t, z, y, x in nodes
        ]
        edge_rows = [
            {"dataset": dataset_name, "row_type": "edge", "node_id": -1, "t": -1,
             "z": -1, "y": -1, "x": -1, "source_id": src, "target_id": dst}
            for src, dst in edges
        ]
        return pd.DataFrame(node_rows + edge_rows)

    # ---- run over every test dataset and write submission.csv ----

    columns = ["id", "dataset", "row_type", "node_id", "t", "z", "y", "x", "source_id", "target_id"]

    paths = sorted(glob.glob(os.path.join(test_dir, "*.zarr")))
    datasets = [(p, os.path.splitext(os.path.basename(p))[0]) for p in paths]
    if not datasets:
        raise FileNotFoundError(f"No .zarr datasets found under {test_dir}")

    per_dataset = []
    for zarr_path, name in datasets:
        print(f"[{name}] tracking...")
        rows = track_dataset(zarr_path, name)
        n_nodes = (rows["row_type"] == "node").sum()
        n_edges = (rows["row_type"] == "edge").sum()
        print(f"[{name}] {n_nodes} nodes, {n_edges} edges")
        per_dataset.append(rows)

    submission = pd.concat(per_dataset, ignore_index=True)
    submission.insert(0, "id", range(len(submission)))
    submission = submission[columns]

    submission.to_csv(output_path, index=False)
    print(f"Wrote {output_path} ({len(submission)} rows)")
    return submission


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-dir", default="/kaggle/input/biohub-cell-tracking/test")
    parser.add_argument("--output", default="/kaggle/working/submission.csv")
    args = parser.parse_args()
    main(test_dir=args.test_dir, output_path=args.output)

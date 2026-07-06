"""Frame-to-frame linking and division detection for 3D cell tracking.

Linking between consecutive timepoints is posed as a rectangular linear
assignment problem (Hungarian algorithm) on physically-scaled centroid
distance, padded with "no-match" dummy rows/columns so cells may appear,
disappear, or go unmatched instead of being forced into a bad pairing.
Divisions (one parent -> two daughters) are recovered afterwards by looking
for extra daughters near an already-matched (or still-unmatched) parent.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

from src.detection import PhysicalScale


@dataclass
class TrackingParams:
    max_link_dist_um: float = 12.0
    max_division_dist_um: float = 15.0


def _to_physical(points_zyx: np.ndarray, scale: PhysicalScale) -> np.ndarray:
    return points_zyx * scale.as_array()


def link_frames(
    prev_pts: np.ndarray,
    curr_pts: np.ndarray,
    scale: PhysicalScale,
    params: TrackingParams,
) -> list[tuple[int, int]]:
    """1-1 assignment between prev and curr centroids.

    Returns list of (prev_index, curr_index) pairs. Unmatched cells (birth,
    death, or rejected due to distance) are simply absent from the result.
    """
    n, m = len(prev_pts), len(curr_pts)
    if n == 0 or m == 0:
        return []

    prev_um = _to_physical(prev_pts, scale)
    curr_um = _to_physical(curr_pts, scale)
    dist = cdist(prev_um, curr_um)

    threshold = params.max_link_dist_um
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


def recover_divisions(
    prev_pts: np.ndarray,
    curr_pts: np.ndarray,
    matches: list[tuple[int, int]],
    scale: PhysicalScale,
    params: TrackingParams,
) -> list[tuple[int, int]]:
    """Add extra parent->daughter edges to explain unmatched curr cells.

    For every curr cell left unmatched by `link_frames`, attach it to its
    nearest prev cell if within `max_division_dist_um`. This lets a parent
    that already has one 1-1 match acquire a second outgoing edge (a
    division), and lets genuinely close pairs rejected only because of
    Hungarian competition still be linked.
    """
    n, m = len(prev_pts), len(curr_pts)
    if n == 0 or m == 0:
        return []

    matched_curr = {c for _, c in matches}
    unmatched_curr = [c for c in range(m) if c not in matched_curr]
    if not unmatched_curr:
        return []

    prev_um = _to_physical(prev_pts, scale)
    curr_um = _to_physical(curr_pts, scale)

    extra = []
    for c in unmatched_curr:
        d = np.linalg.norm(prev_um - curr_um[c], axis=1)
        p = int(np.argmin(d))
        if d[p] <= params.max_division_dist_um:
            extra.append((p, c))
    return extra


@dataclass
class DatasetTracker:
    """Accumulates nodes/edges for one dataset across all timepoints."""

    scale: PhysicalScale
    params: TrackingParams
    nodes: list = None
    edges: list = None
    _next_node_id: int = 1
    _prev_pts: np.ndarray = None
    _prev_node_ids: np.ndarray = None

    def __post_init__(self):
        self.nodes = []
        self.edges = []

    def add_frame(self, t: int, detections: np.ndarray) -> None:
        """detections: (N, 4) array of [z, y, x, intensity]."""
        pts = detections[:, :3] if detections.size else np.zeros((0, 3))
        node_ids = np.arange(self._next_node_id, self._next_node_id + len(pts))
        self._next_node_id += len(pts)

        for nid, (z, y, x) in zip(node_ids, pts):
            self.nodes.append((int(nid), int(t), int(z), int(y), int(x)))

        if self._prev_pts is not None and len(self._prev_pts) and len(pts):
            matches = link_frames(self._prev_pts, pts, self.scale, self.params)
            extra = recover_divisions(
                self._prev_pts, pts, matches, self.scale, self.params
            )
            for p_idx, c_idx in matches + extra:
                self.edges.append(
                    (int(self._prev_node_ids[p_idx]), int(node_ids[c_idx]))
                )

        self._prev_pts = pts
        self._prev_node_ids = node_ids
